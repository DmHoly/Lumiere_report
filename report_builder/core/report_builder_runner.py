from __future__ import annotations

import importlib
import json
import sys
import uuid
import zlib
import base64
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd

try:
    from cryptography.fernet import Fernet
    _HAS_CRYPTO = True
except ImportError:
    _HAS_CRYPTO = False


class ReportBuilderRunner:
    """
    Exécute la génération d'un rapport HTML à partir d'un DataFrame
    et d'un dictionnaire de configuration ou d'un hash.
    """

    EXCLUDED_BLOCKS = {
        "ReportBuilder", "Tab", "TabView", "Block", "PlotlyChart",
        "DataTable", "StatAnalysis", "KPIRow", "KPI",
    }

    BLOCKS_WITHOUT_DATA = {
        "Section",
        "KPI",
        "Tab",
        "TabView",
        "ReportBuilder",
        "Block",
        "PlotlyChart",
        'EasterEggs',
        "LumiereTour",
        "PlotlyChartJSON",
    }

    def __init__(
        self,
        auto_report_dir: str | Path = ".",
        output_dir: str | Path | None = None,
        templates_dir: str | Path | None = None,
        secret_key: str | None = None,
    ) -> None:
        self.auto_report_dir = Path(auto_report_dir)
        self.output_dir = Path(output_dir) if output_dir else None

        if self.output_dir:
            self.output_dir.mkdir(parents=True, exist_ok=True)

        self.templates_dir = (
            Path(templates_dir)
            if templates_dir
            else (self.output_dir / "_templates" if self.output_dir else None)
        )

        if self.templates_dir:
            self.templates_dir.mkdir(parents=True, exist_ok=True)

        self._df: pd.DataFrame | None = None
        self._main_key: str = "main"
        self._sources: dict[str, pd.DataFrame] = {}
        self._secret_key: str | None = secret_key

        self._ensure_path()

    def _ensure_path(self) -> None:
        p = str(self.auto_report_dir)
        if p not in sys.path:
            sys.path.insert(0, p)

    def _load_core(self):
        self._ensure_path()
        import Core
        importlib.reload(Core)
        return Core

    @staticmethod
    def _fix_text_encoding(value: Any) -> Any:
        if isinstance(value, str):
            try:
                fixed = value.encode("latin1").decode("utf-8")
                if "Â" in value or "Ã" in value:
                    return fixed
            except Exception:
                pass
            return value

        if isinstance(value, list):
            return [ReportBuilderRunner._fix_text_encoding(v) for v in value]

        if isinstance(value, dict):
            return {
                ReportBuilderRunner._fix_text_encoding(k): ReportBuilderRunner._fix_text_encoding(v)
                for k, v in value.items()
            }

        return value

    @staticmethod
    def _split_config(config: dict) -> tuple[dict, dict, list[dict]]:
        config = ReportBuilderRunner._fix_text_encoding(config)

        meta = config.get("meta", {})
        report_cfg = config.get("config", config)
        pages_cfg = report_cfg.get("pages", [])

        return meta, report_cfg, pages_cfg

    @staticmethod
    def generate_key() -> str:
        if not _HAS_CRYPTO:
            raise ImportError("pip install cryptography")
        return Fernet.generate_key().decode("ascii")

    def config_to_hash(
        self,
        config: dict,
        key: str | None = None,
    ) -> str:
        config = self._fix_text_encoding(config)

        raw = json.dumps(config, ensure_ascii=False, separators=(",", ":"))
        compressed = zlib.compress(raw.encode("utf-8"), level=9)

        _key = key or self._secret_key

        if _key:
            if not _HAS_CRYPTO:
                raise ImportError("pip install cryptography")
            payload = Fernet(_key.encode("ascii")).encrypt(compressed)
        else:
            payload = compressed

        return base64.urlsafe_b64encode(payload).decode("ascii")

    def hash_to_config(
        self,
        hash_str: str,
        key: str | None = None,
    ) -> dict:
        payload = base64.urlsafe_b64decode(hash_str.encode("ascii"))

        _key = key or self._secret_key

        if _key:
            if not _HAS_CRYPTO:
                raise ImportError("pip install cryptography")
            compressed = Fernet(_key.encode("ascii")).decrypt(payload)
        else:
            compressed = payload

        config = json.loads(zlib.decompress(compressed).decode("utf-8"))
        return self._fix_text_encoding(config)

    def load_dataframe(
            self,
            df: pd.DataFrame,
            key: str = "main",
    ) -> None:
        if not key or not isinstance(key, str):
            raise ValueError("La clé du DataFrame doit être une chaîne non vide.")

        key = key.strip()

        if not key:
            raise ValueError("La clé du DataFrame ne peut pas être vide.")

        self._df = df
        self._main_key = key
        self._sources = {key: df}

    def add_source(
            self,
            key: str,
            df: pd.DataFrame,
            overwrite: bool = False,
    ) -> None:
        if not key or not isinstance(key, str):
            raise ValueError("La clé doit être une chaîne non vide.")

        key = key.strip()

        if not key:
            raise ValueError("La clé ne peut pas être vide.")

        if df is None:
            raise ValueError(f"La source {key!r} ne peut pas être None.")

        if key in self._sources and not overwrite:
            raise ValueError(
                f"La source {key!r} existe déjà. "
                "Passe overwrite=True pour la remplacer."
            )

        self._sources[key] = df

    def load_iris_mock(self) -> pd.DataFrame:
        from sklearn.datasets import load_iris

        iris = load_iris()
        df = pd.DataFrame(iris.data, columns=iris.feature_names)
        df["species"] = [iris.target_names[t] for t in iris.target]
        df["wafername"] = "iris_mock"
        df["Led_Name"] = [f"LED_{i}" for i in range(len(df))]

        self.load_dataframe(df, key="main")
        return df

    def _deserialize_params(self, block_type: str, params: dict, Core) -> dict:
        params = self._fix_text_encoding(dict(params or {}))

        if block_type == "KPIRow" and "kpis" in params:
            KPI = getattr(Core, "KPI")
            params["kpis"] = [
                KPI(**k) if isinstance(k, dict) else k
                for k in params["kpis"]
            ]

        if block_type == "SummaryBoxPlots" and "metrics" in params:
            params["metrics"] = {
                k: tuple(v) if isinstance(v, list) else v
                for k, v in params["metrics"].items()
            }

        return params

    def generate(
        self,
        config: dict | str,
        key: str | None = None,
    ) -> dict[str, Any]:

        if isinstance(config, str):
            config = self.hash_to_config(config, key=key)

        config = self._fix_text_encoding(config)
        meta, report_cfg, pages_cfg = self._split_config(config)

        if not pages_cfg:
            raise ValueError(
                "Aucune page trouvée dans la config. "
                "Format attendu : {'meta': ..., 'config': {'pages': [...]}} "
                "ou {'meta': ..., 'pages': [...]}."
            )

        if self._df is None:
            raise RuntimeError(
                "Aucun DataFrame chargé — appelez load_dataframe() d'abord."
            )

        Core = self._load_core()

        title = meta.get("title", "Report")
        author = meta.get("author", "Builder")
        subtitle = meta.get("subtitle", "")

        path_levels = [
            p.strip()
            for p in meta.get("path", [])
            if isinstance(p, str) and p.strip()
        ]

        output_dir_raw = meta.get("output_dir", None) or self.output_dir or "output"
        output_dir = Path(output_dir_raw)
        output_dir.mkdir(parents=True, exist_ok=True)

        dest_dir = output_dir

        for level in path_levels:
            dest_dir = dest_dir / level

        dest_dir.mkdir(parents=True, exist_ok=True)

        report_name = meta.get("report_name", None)
        date_str = datetime.now().strftime("%Y-%m-%d")

        if report_name:
            filename = f"{report_name}.html"
            report_id = report_name
        else:
            report_id = uuid.uuid4().hex[:8]
            filename = f"{report_id}.html"

        out_path = dest_dir / filename

        report = Core.ReportBuilder(
            title=title,
            subtitle=subtitle,
            author=author,
        )

        report.data.register(self._main_key, self._df)

        for key_src, df_src in self._sources.items():
            if key_src != self._main_key and df_src is not None:
                report.data.register(key_src, df_src)

        tabs: list = []
        block_types_used: list[str] = []
        skipped: list[str] = []

        for page_cfg in pages_cfg:
            page_name = page_cfg.get("name", "Page")
            tab = Core.Tab(page_name)

            for block_cfg in page_cfg.get("blocks", []):
                block_type = block_cfg.get("type")
                params_raw = block_cfg.get("params", {})

                if not block_type:
                    skipped.append("Bloc sans type")
                    continue

                cls = getattr(Core, block_type, None)

                if cls is None:
                    skipped.append(block_type)
                    continue

                try:
                    params = self._deserialize_params(block_type, params_raw, Core)

                    if (
                        block_type not in self.BLOCKS_WITHOUT_DATA
                        and "data" not in params
                    ):
                        params["data"] = self._main_key

                    tab.add(cls(**params))
                    block_types_used.append(block_type)

                except Exception as exc:
                    skipped.append(f"{block_type} ({exc})")

            tabs.append(tab)

        if skipped:
            print(f"⚠️ Blocs ignorés : {skipped}")

        report.add(Core.TabView(tabs))
        report.save(str(out_path))

        manifest = {
            "id": report_id,
            "title": title,
            "subtitle": subtitle,
            "author": author,
            "created": datetime.now().isoformat(timespec="seconds"),
            "wafers": meta.get("wafers", []),
            "path": path_levels,
            "blocks": sorted(set(block_types_used)),
            "pages": [p.get("name", "Page") for p in pages_cfg],
            "filename": filename,
            "skipped_blocks": skipped,
            "main_data_key": self._main_key,
            "data_sources": list(self._sources.keys()),
        }

        manifest_path = dest_dir / f"{date_str}_{report_id}.manifest.json"
        manifest_path.write_text(
            json.dumps(manifest, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

        rel = "/".join(path_levels + [filename])

        return {
            "status": "success",
            "url": f"/report_builder/output/{rel}",
            "id": report_id,
            "path": out_path,
            "manifest": manifest,
        }

    def save_template(
        self,
        config: dict,
        template_name: str,
        description: str = "",
        tags: list[str] | None = None,
        sub_path: list[str] | None = None,
    ) -> dict[str, str]:

        if self.templates_dir is None:
            raise RuntimeError(
                "templates_dir n'est pas défini. "
                "Passe output_dir ou templates_dir au ReportBuilderRunner."
            )

        config = self._fix_text_encoding(config)
        meta, report_cfg, pages_cfg = self._split_config(config)

        if not pages_cfg:
            raise ValueError(
                "Impossible de sauvegarder le template : aucune page trouvée."
            )

        tags = [t.strip() for t in (tags or []) if t.strip()]
        sub_path = [p.strip() for p in (sub_path or []) if p and p.strip()]

        dest_dir = self.templates_dir

        for part in sub_path:
            dest_dir = dest_dir / part

        dest_dir.mkdir(parents=True, exist_ok=True)

        template_id = uuid.uuid4().hex[:8]

        safe_name = (
            "".join(c if c.isalnum() or c in "-_ " else "_" for c in template_name)
            .strip()
            .replace(" ", "_")
        )

        filename = f"{safe_name}_{template_id}.template.json"

        payload = {
            "template_meta": {
                "id": template_id,
                "template_name": template_name,
                "description": description,
                "tags": tags,
                "author": meta.get("author", ""),
                "created": datetime.now().isoformat(timespec="seconds"),
                "path": sub_path,
                "blocks": sorted({
                    b["type"]
                    for p in pages_cfg
                    for b in p.get("blocks", [])
                    if "type" in b
                }),
                "pages": [p.get("name", "Page") for p in pages_cfg],
            },
            "config": config,
        }

        out_path = dest_dir / filename
        out_path.write_text(
            json.dumps(payload, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

        return {
            "status": "success",
            "id": template_id,
            "filename": filename,
        }

    def list_templates(self) -> list[dict]:
        if self.templates_dir is None:
            return []

        templates = []

        for f in sorted(self.templates_dir.rglob("*.template.json"), reverse=True):
            try:
                data = json.loads(f.read_text(encoding="utf-8"))
                data = self._fix_text_encoding(data)

                meta = data.get("template_meta", {})
                meta["_rel_path"] = list(f.parent.relative_to(self.templates_dir).parts)
                templates.append(meta)

            except Exception as exc:
                print(f"⚠️ Template illisible : {f} — {exc}")

        return templates

    def load_template(self, template_id: str) -> dict:
        if self.templates_dir is None:
            raise RuntimeError(
                "templates_dir n'est pas défini. "
                "Passe output_dir ou templates_dir au ReportBuilderRunner."
            )

        for f in self.templates_dir.rglob(f"*{template_id}*.template.json"):
            data = json.loads(f.read_text(encoding="utf-8"))
            return self._fix_text_encoding(data)

        raise FileNotFoundError(f"Template introuvable : {template_id!r}")

    def delete_template(self, template_id: str) -> None:
        if self.templates_dir is None:
            raise RuntimeError(
                "templates_dir n'est pas défini. "
                "Passe output_dir ou templates_dir au ReportBuilderRunner."
            )

        for f in self.templates_dir.rglob(f"*{template_id}*.template.json"):
            f.unlink()
            return

        raise FileNotFoundError(f"Template introuvable : {template_id!r}")

    def __repr__(self) -> str:
        rows = len(self._df) if self._df is not None else 0

        return (
            f"<ReportBuilderRunner "
            f"df={rows}rows "
            f"main_key={self._main_key!r} "
            f"sources={list(self._sources.keys())} "
            f"output={self.output_dir}>"
        )