"""
config_store.py — Persistance des configs de rapport créées dans le builder.

Un rapport sauvegardé est un fichier JSON sous app/data/configs/{id}.json,
qui contient la config du compilateur (meta / main_dataset / pages) plus
une clé "_meta_builder" (nom affiché, date de dernière sauvegarde) propre
au builder — ignorée par report_compiler.render_html().
"""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path

from .dataset_store import slugify

CONFIGS_DIR = Path(__file__).parent / "data" / "configs"
CONFIGS_DIR.mkdir(parents=True, exist_ok=True)


def _path(report_id: str) -> Path:
    return CONFIGS_DIR / f"{report_id}.json"


def list_configs() -> list[dict]:
    out = []
    for p in CONFIGS_DIR.glob("*.json"):
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        bm = data.get("_meta_builder", {})
        out.append({
            "id": p.stem,
            "name": bm.get("name", p.stem),
            "title": (data.get("meta") or {}).get("title", ""),
            "updated_at": bm.get("updated_at"),
        })
    out.sort(key=lambda c: c.get("updated_at") or "", reverse=True)
    return out


def save_config(config: dict, name: str, report_id: str | None = None) -> str:
    report_id = report_id or slugify(name) or uuid.uuid4().hex[:8]
    payload = dict(config)
    payload["_meta_builder"] = {
        "name": name,
        "updated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
    _path(report_id).write_text(
        json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    return report_id


def load_config(report_id: str) -> dict:
    p = _path(report_id)
    if not p.exists():
        raise KeyError(report_id)
    return json.loads(p.read_text(encoding="utf-8"))


def delete_config(report_id: str) -> None:
    p = _path(report_id)
    if not p.exists():
        raise KeyError(report_id)
    p.unlink()
