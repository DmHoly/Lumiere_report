"""
enrich_liv.py — Enrichit l'index goniomètre avec l'historique LIV (liv.parquet) :
process (MOCVD/MBE), EQE médian autour de la position mesurée, nom du QT (Lot).

L'historique LIV est indexé par (wafername, X, Y) au niveau LED — on agrège
les LEDs dans un voisinage de la position (pos_x, pos_y) de la mesure
goniomètre pour obtenir un EQE représentatif de la zone regardée.
"""
from __future__ import annotations

import json
import math
from pathlib import Path

import pandas as pd

DEFAULT_POSITION_RADIUS = 2.0  # rayon (unités grille wafer) autour de (pos_x, pos_y)


def _wafer_summary(liv_df: pd.DataFrame) -> dict:
    """Pré-calcule, par wafer, le process (mode) et le nom de QT (mode)."""
    out = {}
    for wafer, sub in liv_df.groupby("wafername"):
        process = sub["epi_run_type"].mode()
        qt = sub["Lot"].mode()
        out[wafer] = {
            "epi_run_type": str(process.iloc[0]) if len(process) else None,
            "qt_name": str(qt.iloc[0]) if len(qt) else None,
            "leds": sub[["X", "Y", "max_EQE"]].dropna(subset=["max_EQE"]).to_records(index=False),
        }
    return out


def _eqe_region_median(leds, pos_x: float, pos_y: float, radius: float) -> tuple[float | None, int]:
    if len(leds) == 0:
        return None, 0
    matched = [
        float(eqe) for x, y, eqe in leds
        if math.hypot(float(x) - pos_x, float(y) - pos_y) <= radius
    ]
    if not matched:
        return None, 0
    matched.sort()
    n = len(matched)
    median = matched[n // 2] if n % 2 else (matched[n // 2 - 1] + matched[n // 2]) / 2
    return median, n


def enrich_index_with_liv(
    index_path: Path,
    liv_parquet_path: Path,
    position_radius: float = DEFAULT_POSITION_RADIUS,
) -> dict:
    """
    Pour chaque mesure de l'index, ajoute dans `metadata` :
      - epi_run_type : "MOCVD" | "MBE" | None
      - qt_name      : nom du QT (colonne Lot) du wafer
      - eqe_region_median : médiane de max_EQE des LEDs dans un rayon
        `position_radius` autour de (pos_x, pos_y) — None si aucune LED trouvée
      - eqe_region_n : nombre de LEDs utilisées pour la médiane

    Écrase ces 4 clés de metadata pour chaque mesure ; les autres clés de
    metadata (ex: métadonnées manuelles ajoutées via set_metadata) sont préservées.

    Retourne {"matched": int, "unmatched_wafer": int, "total": int}.
    """
    with open(index_path, "r", encoding="utf-8") as f:
        records = json.load(f)

    liv_df = pd.read_parquet(liv_parquet_path)
    wafer_info = _wafer_summary(liv_df)

    matched = unmatched_wafer = 0
    for rec in records:
        wafer = rec["wafername"]
        info = wafer_info.get(wafer)
        rec.setdefault("metadata", {})
        if info is None:
            unmatched_wafer += 1
            rec["metadata"].update({
                "epi_run_type": None, "qt_name": None,
                "eqe_region_median": None, "eqe_region_n": 0,
            })
            continue

        eqe_median, n = _eqe_region_median(info["leds"], rec["pos_x"], rec["pos_y"], position_radius)
        rec["metadata"].update({
            "epi_run_type": info["epi_run_type"],
            "qt_name": info["qt_name"],
            "eqe_region_median": eqe_median,
            "eqe_region_n": n,
        })
        matched += 1

    with open(index_path, "w", encoding="utf-8") as f:
        json.dump(records, f, indent=2, ensure_ascii=False)

    return {"matched": matched, "unmatched_wafer": unmatched_wafer, "total": len(records)}
