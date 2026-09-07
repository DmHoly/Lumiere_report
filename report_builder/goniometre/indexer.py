"""
indexer.py — Index léger des mesures Goniomètre (Farfield).

Structure scannée :
    <root>/<FDL>/<wafername>/<run_dir>/result.sqlite

Le nom de <run_dir> n'est pas parfaitement homogène sur l'historique des
mesures. Variantes observées et gérées par _RUN_DIR_RE :
    2026-03-16_Run_-1_-6_4mA
    2026-04-07_-1_2_4mA                      (préfixe "Run_" absent)
    2026-03-12_Run_0_-6_0p4mA                (décimale encodée avec 'p')
    2026-03-04_Run_0_-6_20uA_200x200         (unité uA + suffixe taille device)
    2026-06-09_Run_0_11_250mAcm-2            (densité de courant mA/cm²)
    2026-05-26_Run_2_8_210-D2_1Acm-2         (id device inséré + densité A/cm²)
    2026-06-29_Run_0_5_1Acm-2_256-D2         (densité de courant + suffixe device)

Quelques dossiers (noms de wafer isolés, "BP15"/"BP18", schéma
"<wafer>_position_x_y") ne suivent aucun de ces schémas et sont ignorés —
il ne s'agit pas de dossiers de run Farfield.

L'index est un JSON léger : uniquement les chemins + métadonnées dérivées du
nom de dossier. Le contenu du result.sqlite (theta/phi/lambda/intensity) est
chargé à la demande via loader.load_cube().
"""
from __future__ import annotations

import json
import re
from pathlib import Path

DEFAULT_ROOT = Path(r"O:\00-Mesure\TEST\Goniometre")
DEFAULT_INDEX_PATH = Path(__file__).resolve().parent.parent / "data" / "goniometre_index.json"

_RUN_DIR_RE = re.compile(
    r"^(?P<date>\d{4}-\d{2}-\d{2})_(?:Run_)?(?P<pos_x>-?\d+)_(?P<pos_y>-?\d+)"
    r"(?:_[A-Za-z0-9-]+?)?_(?P<current>\d+p?\d*)(?P<unit>mAcm-2|Acm-2|uA|mA)"
    r"(?:_(?P<suffix>.+))?$"
)


def _parse_current(value: str, unit: str) -> dict:
    """Normalise la valeur/unité de courant brute en champs exploitables."""
    num = float(value.replace("p", "."))
    current_mA = None
    current_density_Acm2 = None
    if unit == "mA":
        current_mA = num
    elif unit == "uA":
        current_mA = num / 1000.0
    elif unit == "Acm-2":
        current_density_Acm2 = num
    elif unit == "mAcm-2":
        current_density_Acm2 = num / 1000.0
    return {
        "current_value": num,
        "current_unit": unit,
        "current_mA": current_mA,
        "current_density_Acm2": current_density_Acm2,
        "current_label": f"{value.replace('p', '.')}{unit}",
    }


def _parse_run_dir(name: str) -> dict | None:
    m = _RUN_DIR_RE.match(name)
    if not m:
        return None
    d = m.groupdict()
    parsed = {
        "date": d["date"],
        "pos_x": int(d["pos_x"]),
        "pos_y": int(d["pos_y"]),
        "run_suffix": d["suffix"],
    }
    parsed.update(_parse_current(d["current"], d["unit"]))
    return parsed


def scan_measurements(root: Path = DEFAULT_ROOT) -> list[dict]:
    """Parcourt root/<FDL>/<wafername>/<run>/result.sqlite et retourne les records."""
    root = Path(root)
    records: list[dict] = []
    if not root.exists():
        return records

    for sqlite_path in root.glob("*/*/*/result.sqlite"):
        run_dir = sqlite_path.parent
        wafer_dir = run_dir.parent
        fdl_dir = wafer_dir.parent

        parsed = _parse_run_dir(run_dir.name)
        if parsed is None:
            continue

        rel_path = sqlite_path.relative_to(root).as_posix()
        key = run_dir.relative_to(root).as_posix()

        records.append({
            "key": key,
            "fdl": fdl_dir.name,
            "wafername": wafer_dir.name,
            "path": rel_path,
            "sqlite_mtime": sqlite_path.stat().st_mtime,
            "metadata": {},
            **parsed,
        })

    records.sort(key=lambda r: r["key"])
    return records


def _load_existing(index_path: Path) -> list[dict]:
    if not index_path.exists():
        return []
    with open(index_path, "r", encoding="utf-8") as f:
        return json.load(f)


def _write_index(index_path: Path, records: list[dict]) -> None:
    index_path.parent.mkdir(parents=True, exist_ok=True)
    with open(index_path, "w", encoding="utf-8") as f:
        json.dump(records, f, indent=2, ensure_ascii=False)


def build_index(root: Path = DEFAULT_ROOT, index_path: Path = DEFAULT_INDEX_PATH) -> list[dict]:
    """Scan complet, écrase l'index existant (sans préserver les métadonnées)."""
    records = scan_measurements(root)
    _write_index(index_path, records)
    return records


def rescan_index(root: Path = DEFAULT_ROOT, index_path: Path = DEFAULT_INDEX_PATH) -> dict:
    """
    Rescanne root et met à jour l'index existant :
      - ajoute les nouvelles mesures
      - met à jour sqlite_mtime des mesures modifiées
      - préserve `metadata` des mesures inchangées ou modifiées
      - retire les mesures dont le dossier a disparu

    Retourne {"added": int, "updated": int, "removed": int, "total": int}.
    """
    existing = {r["key"]: r for r in _load_existing(index_path)}
    scanned = scan_measurements(root)
    scanned_keys = {r["key"] for r in scanned}

    added = updated = 0
    merged: list[dict] = []
    for rec in scanned:
        prev = existing.get(rec["key"])
        if prev is None:
            added += 1
            merged.append(rec)
        else:
            if prev.get("sqlite_mtime") != rec["sqlite_mtime"]:
                updated += 1
            rec["metadata"] = prev.get("metadata", {})
            merged.append(rec)

    removed = sum(1 for k in existing if k not in scanned_keys)

    merged.sort(key=lambda r: r["key"])
    _write_index(index_path, merged)

    return {"added": added, "updated": updated, "removed": removed, "total": len(merged)}


def set_metadata(index_path: Path, key: str, field: str, value) -> bool:
    """Ajoute/écrase une info libre (ex: epitaxy_type) pour la mesure `key`. Retourne False si `key` inconnue."""
    records = _load_existing(index_path)
    for rec in records:
        if rec["key"] == key:
            rec.setdefault("metadata", {})[field] = value
            _write_index(index_path, records)
            return True
    return False
