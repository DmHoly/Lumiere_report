"""
loader.py — Lecture d'un result.sqlite (mesure goniomètre) — port de Farfield_MDA.ipynb.

Deux schémas SQL coexistent selon l'ancienneté de la mesure : legacy
(BwtekSpectrumMeasurement) et Odil (OdilBwtekSpectrumMeasurement). On essaie
Odil en premier (schéma le plus récent), puis fallback legacy.
"""
from __future__ import annotations

import re
import sqlite3
from pathlib import Path

import numpy as np
import pandas as pd

REQUEST_ODIL = (
    'SELECT '
    '   "T_Wavelength"."value" AS "Wavelength", '
    '   "T_Intensities"."value" AS "Intensities", '
    '   "devices"."name" '
    'FROM '
    '   "devices" '
    'JOIN "OdilBwtekSpectrumMeasurement" '
    '   ON "devices"."pk" = "OdilBwtekSpectrumMeasurement"."devices" '
    'JOIN "OdilBwtekSpectrumMeasurement_Spectrum" AS "T_Wavelength" '
    '   ON "OdilBwtekSpectrumMeasurement"."pk" = "T_Wavelength"."fk_OdilBwtekSpectrumMeasurement" '
    '      AND "T_Wavelength"."row" = 0 '
    'JOIN "OdilBwtekSpectrumMeasurement_Spectrum" AS "T_Intensities" '
    '   ON "OdilBwtekSpectrumMeasurement"."pk" = "T_Intensities"."fk_OdilBwtekSpectrumMeasurement" '
    '      AND "T_Intensities"."row" = 1 '
)

REQUEST_LEGACY = (
    'SELECT '
    '   "T_Wavelength"."value" AS "Wavelength", '
    '   "T_Intensities"."value" AS "Intensities", '
    '   "devices"."name" '
    'FROM '
    '   "devices" '
    'JOIN "BwtekSpectrumMeasurement" '
    '   ON "devices"."pk" = "BwtekSpectrumMeasurement"."devices" '
    'JOIN "BwtekSpectrumMeasurement_Spectrum" AS "T_Wavelength" '
    '   ON "BwtekSpectrumMeasurement"."pk" = "T_Wavelength"."fk_BwtekSpectrumMeasurement" '
    '      AND "T_Wavelength"."row" = 0 '
    'JOIN "BwtekSpectrumMeasurement_Spectrum" AS "T_Intensities" '
    '   ON "BwtekSpectrumMeasurement"."pk" = "T_Intensities"."fk_BwtekSpectrumMeasurement" '
    '      AND "T_Intensities"."row" = 1 '
)

_DEVICE_NAME_RE = re.compile(r"(.+),(.+),(.+)")


def _run_query(sqlite_path: Path, query: str) -> pd.DataFrame:
    conn = sqlite3.connect(str(sqlite_path))
    try:
        cursor = conn.cursor()
        cursor.execute(query)
        data = cursor.fetchall()
    finally:
        conn.close()
    return pd.DataFrame(data, columns=["Wavelength", "Intensities", "device_name"])


def _fetch_raw(sqlite_path: Path) -> pd.DataFrame:
    try:
        df = _run_query(sqlite_path, REQUEST_ODIL)
        if len(df) > 0:
            return df
    except sqlite3.OperationalError:
        pass
    return _run_query(sqlite_path, REQUEST_LEGACY)


def load_cube(sqlite_path: Path) -> dict:
    """
    Lit un result.sqlite et retourne le cube brut :
      {theta: [...], phi: [...], wavelength: [...],
       intensity_corrected: {(theta,phi): [...]}}
    """
    df = _fetch_raw(Path(sqlite_path))

    df = df.copy()
    for info in df["device_name"]:
        m = _DEVICE_NAME_RE.findall(info)
        if not m:
            continue
        theta, phi = m[0][1], m[0][2]
        df.loc[df["device_name"] == info, "theta"] = int(theta)
        df.loc[df["device_name"] == info, "phi"] = int(phi)

    df["Wavelength"] = df["Wavelength"].apply(
        lambda x: np.array(list(map(float, x.strip("[]").split(","))))
    )
    df["Intensities"] = df["Intensities"].apply(
        lambda x: np.array(list(map(float, x.strip("[]").split(","))))
    )

    df_exp = df.explode(["Wavelength", "Intensities"]).reset_index(drop=True)
    df_exp["Wavelength"] = df_exp["Wavelength"].astype(float)
    df_exp["Intensities"] = df_exp["Intensities"].astype(float)
    df_exp["theta"] = df_exp["theta"].astype(int)
    df_exp["phi"] = df_exp["phi"].astype(int)

    baseline = df_exp[df_exp["Wavelength"] <= 350].groupby(["theta", "phi"])["Intensities"].mean()
    baseline.name = "_baseline"
    df_exp = df_exp.join(baseline, on=["theta", "phi"])
    df_exp["Intensities_corrected"] = df_exp["Intensities"] - df_exp["_baseline"]
    df_exp.drop(columns=["_baseline"], inplace=True)
    df_exp.sort_values(by=["theta", "phi", "Wavelength"], inplace=True)
    df_exp.reset_index(drop=True, inplace=True)

    wavelength_grid = sorted(df_exp["Wavelength"].unique().tolist())
    theta_list = sorted(df_exp["theta"].unique().tolist())
    phi_list = sorted(df_exp["phi"].unique().tolist())

    intensity_corrected: dict = {}
    for (theta, phi), sub in df_exp.groupby(["theta", "phi"]):
        sub_sorted = sub.sort_values("Wavelength")
        intensity_corrected[(int(theta), int(phi))] = sub_sorted["Intensities_corrected"].to_numpy()

    return {
        "theta": theta_list,
        "phi": phi_list,
        "wavelength": wavelength_grid,
        "intensity_corrected": intensity_corrected,
    }
