"""
dataset_store.py — Registre des datasets disponibles pour le builder.

Un dataset est un DataFrame nommé (clé = nom de fichier sans extension,
assaini). Deux origines, unifiées dans le même registre :

  - upload  : POST /api/datasets envoie un fichier (csv/parquet/xlsx),
              converti et mis en cache sur disque en parquet.
  - pré-enregistré : n'importe quel fichier .csv/.parquet/.xlsx déjà présent
              dans DATASETS_DIR (ex: déposé manuellement, ou généré par un
              autre outil) est détecté automatiquement au listing.

Le cache mémoire évite de relire le disque à chaque appel ; il est invalidé
si le fichier a changé (mtime) pour rester correct si quelqu'un dépose un
nouveau fichier pendant que le serveur tourne.
"""
from __future__ import annotations

import re
import uuid
from pathlib import Path

import pandas as pd

DATASETS_DIR = Path(__file__).parent / "data" / "datasets"
DATASETS_DIR.mkdir(parents=True, exist_ok=True)

_READERS = {
    ".csv": pd.read_csv,
    ".parquet": pd.read_parquet,
    ".xlsx": pd.read_excel,
    ".xls": pd.read_excel,
}


def slugify(name: str) -> str:
    base = Path(name).stem
    slug = re.sub(r"[^a-zA-Z0-9_-]+", "_", base).strip("_").lower()
    return slug or "dataset"


class DatasetStore:
    def __init__(self) -> None:
        self._cache: dict[str, tuple[float, pd.DataFrame]] = {}

    def _discover(self) -> dict[str, Path]:
        found: dict[str, Path] = {}
        for p in sorted(DATASETS_DIR.iterdir()):
            if p.is_file() and p.suffix.lower() in _READERS:
                found[p.stem] = p
        return found

    def _load(self, key: str, path: Path) -> pd.DataFrame:
        mtime = path.stat().st_mtime
        cached = self._cache.get(key)
        if cached and cached[0] == mtime:
            return cached[1]
        reader = _READERS[path.suffix.lower()]
        df = reader(path)
        self._cache[key] = (mtime, df)
        return df

    def add_upload(self, filename: str, raw: bytes, key: str | None = None) -> str:
        """Parse un fichier uploadé et le persiste en parquet sous `key`."""
        suffix = Path(filename).suffix.lower()
        if suffix not in _READERS:
            raise ValueError(
                f"Format non supporté : {suffix!r}. "
                f"Formats acceptés : {', '.join(sorted(_READERS))}"
            )
        key = slugify(key or filename)

        tmp_path = DATASETS_DIR / f"__upload_tmp_{uuid.uuid4().hex}{suffix}"
        tmp_path.write_bytes(raw)
        try:
            df = _READERS[suffix](tmp_path)
        finally:
            tmp_path.unlink(missing_ok=True)

        dest = DATASETS_DIR / f"{key}.parquet"
        df.to_parquet(dest)
        self._cache[key] = (dest.stat().st_mtime, df)
        return key

    def get(self, key: str) -> pd.DataFrame:
        found = self._discover()
        if key not in found:
            raise KeyError(f"Dataset introuvable : {key!r}")
        return self._load(key, found[key])

    def exists(self, key: str) -> bool:
        return key in self._discover()

    def list(self) -> list[dict]:
        out = []
        for key, path in self._discover().items():
            try:
                df = self._load(key, path)
            except Exception as exc:
                out.append({"key": key, "error": str(exc)})
                continue
            out.append({
                "key": key,
                "rows": int(len(df)),
                "columns": [
                    {"name": c, "dtype": str(df[c].dtype)}
                    for c in df.columns
                ],
            })
        return out

    def sample(self, key: str, n: int = 20) -> list[dict]:
        df = self.get(key)
        import json
        import numpy as np

        preview = df.head(n)

        def _safe(v):
            if isinstance(v, (np.integer,)):
                return int(v)
            if isinstance(v, (np.floating,)):
                v = float(v)
                return None if v != v else v  # NaN -> null
            if isinstance(v, (list, tuple, np.ndarray)):
                return f"[vecteur, {len(v)} pts]"
            try:
                json.dumps(v)
                return v
            except (TypeError, ValueError):
                return str(v)

        return [
            {col: _safe(row[col]) for col in df.columns}
            for _, row in preview.iterrows()
        ]

    def delete(self, key: str) -> None:
        found = self._discover()
        if key not in found:
            raise KeyError(f"Dataset introuvable : {key!r}")
        found[key].unlink()
        self._cache.pop(key, None)


store = DatasetStore()
