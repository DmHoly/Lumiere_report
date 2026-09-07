"""
vlc_data_loader.py — Chargement des données VLC depuis MISCELLANEOUS + GOZER

Expose deux fonctions principales :

    df_liv, df_f3db = load_vlc_from_miscellaneous(folder)
    df_liv, df_f3db = load_vlc_from_gozer(folder, host=..., user=..., password=...)

Les DataFrames retournés sont directement injectables dans VLCDesignBlock :

    tab.add(VLCDesignBlock(df_liv=df_liv, df_f3db=df_f3db, n_wires_array=1))

Note sur n_wires_array :
    Les fonctions normalisent L (W) en L-par-fil avant de retourner df_liv.
    Passer n_wires_array=1 dans VLCDesignBlock est donc correct — le paramètre
    "Fils/LED" dans l'interface UI représente alors le nombre réel de fils par
    réseau pour les calculs d'énergie et de surface active.
"""
from __future__ import annotations
import os
import re
import warnings
import numpy as np
import pandas as pd


# ─────────────────────────────────────────────────────────────────────────────
#  Helpers internes
# ─────────────────────────────────────────────────────────────────────────────

_WIRE_AREA_CM2 = 25e-8   # surface d'un fil (5µm × 5µm) en cm²


def _nwires_from_device(device: str) -> float:
    """
    Extrait le nombre de fils théoriques depuis le nom device.
    Convention : device = "wafer_X,Y_NW-TypeLED"
    ex : "275BL6D6MMA2_1,7_4-BSM41B-4W-HV1-V1-1" → Nw = 4
    """
    try:
        parts = device.split("_")
        if len(parts) >= 3:
            nw = float(parts[2].split("-")[0])
            if nw > 0:
                return nw
    except (ValueError, IndexError):
        pass
    return float("nan")


def _read_rf_folder(folder: str) -> pd.DataFrame:
    """Lit récursivement tous les fichiers DeviceData.txt du dossier RF."""
    dfs = []
    for root, _, files in os.walk(folder):
        for fname in files:
            if "DeviceData.txt" not in fname:
                continue
            path = os.path.join(root, fname)
            try:
                df_tmp = pd.read_csv(path, sep=r"\s+", header=1)
                df_tmp["_path"] = path
                dfs.append(df_tmp)
            except Exception as exc:
                warnings.warn(f"Impossible de lire {path}: {exc}")

    if not dfs:
        raise FileNotFoundError(f"Aucun fichier DeviceData.txt trouvé dans {folder}")

    df = pd.concat(dfs, ignore_index=True)
    df = df.dropna(subset=["f3dB"])

    # Nombre de fils depuis le nom de device
    df["Nw_theoretical"] = pd.to_numeric(
        df["Device"].str.split("_").str[2].str.split("-").str[0],
        errors="coerce",
    )
    # Courant absolu (A) depuis la densité de courant
    df["current"] = df["CurrentDensity"] * (_WIRE_AREA_CM2 * df["Nw_theoretical"])

    return df


def _meas_suffix_by_path(df_rf: pd.DataFrame) -> pd.DataFrame:
    """
    Ajoute un suffixe _meas1, _meas2… aux devices mesurés plusieurs fois
    (même Device mais paths différents).  L'info de mesure multiple n'est
    disponible que dans le path du fichier, pas dans le nom de device.
    """
    df_rf = df_rf.copy()
    for device, grp in df_rf.groupby("Device"):
        unique_paths = sorted(grp["_path"].unique())
        if len(unique_paths) > 1:
            for i, p in enumerate(unique_paths, 1):
                mask = (df_rf["Device"] == device) & (df_rf["_path"] == p)
                df_rf.loc[mask, "Device"] = f"{device}_meas{i}"
    return df_rf


def _extract_liv_from_rf(df_rf: pd.DataFrame) -> pd.DataFrame | None:
    """
    Tente d'extraire les colonnes LIV (Voltage, L, EQE) depuis le DataFrame RF brut.
    Retourne un DataFrame au format VLCDesignBlock (L déjà normalisé par fil), ou None.
    """
    col_map = {c.lower(): c for c in df_rf.columns}
    volt_col = next((col_map[k] for k in ("voltage", "v", "volt") if k in col_map), None)
    l_col    = next((col_map[k] for k in ("l", "light", "power") if k in col_map), None)
    eqe_col  = next((col_map[k] for k in ("eqe",) if k in col_map), None)

    if volt_col is None or l_col is None:
        warnings.warn(
            "vlc_data_loader: colonnes Voltage/L introuvables dans DeviceData.txt — "
            "l'IV brut ne sera pas affiché dans J vs V."
        )
        return None

    rows = []
    for device, grp in df_rf.groupby("Device"):
        grp = grp.copy()
        grp["_J"]   = pd.to_numeric(grp["CurrentDensity"], errors="coerce")
        grp["_V"]   = pd.to_numeric(grp[volt_col], errors="coerce")
        grp["_L"]   = pd.to_numeric(grp[l_col], errors="coerce") / grp["Nw_theoretical"].replace(0, float("nan"))
        grp["_EQE"] = pd.to_numeric(grp[eqe_col], errors="coerce") if eqe_col else float("nan")
        grp = grp.dropna(subset=["_J", "_V", "_L"]).sort_values("_J")
        if grp.empty:
            continue
        rows.append(pd.DataFrame({
            "Sample":     device,
            "Voltage (V)": grp["_V"].values,
            "J (A/cm²)":  grp["_J"].values,
            "EQE (%)":    grp["_EQE"].values,
            "L (W)":      grp["_L"].values,   # déjà par fil
        }))
    return pd.concat(rows, ignore_index=True) if rows else None


def _build_gozer_sql(parsed_devices: list[tuple]) -> str:
    filter_str = ", ".join(
        f"('{w}','{x}','{y}','{s}')"
        for w, x, y, s in parsed_devices
    )
    return f"""
WITH latest AS (
    SELECT
        w.wafer_name,
        dev."Block_X_Coordinate",
        dev."Block_Y_Coordinate",
        dev."Led_Name",
        test."Test_Date",
        UNNEST(test_l."I")              AS current,
        UNNEST(test_l."V")              AS voltage,
        UNNEST(test_l."L")              AS L,
        UNNEST(test_l."EQE")            AS "EQE",
        UNNEST(test_l."WPE")            AS "WPE",
        UNNEST(test_l."Lambda_Peak")    AS "Lambda_Peak",
        UNNEST(test_l."Lambda_Dominant") AS "Lambda_Dominant",
        ROW_NUMBER() OVER (
            PARTITION BY w.wafer_name,
                         dev."Block_X_Coordinate",
                         dev."Block_Y_Coordinate",
                         dev."Led_Name"
            ORDER BY test."Test_Date" DESC
        ) AS rn
    FROM public.wafer w
    LEFT OUTER JOIN public."Devices" dev       ON dev.fk_wafer = w.pk_wafer
    LEFT OUTER JOIN public."TestLed" test_l    ON test_l."FK_Device" = dev."PK_Devices"
    LEFT OUTER JOIN public."Test" test         ON test."PK_Test" = test_l."FK_Test"
    WHERE (w.wafer_name, dev."Block_X_Coordinate",
           dev."Block_Y_Coordinate", dev."Led_Name")
          IN ({filter_str})
)
SELECT * FROM latest WHERE rn = 1;
"""


def _query_gozer(sql: str, host: str, user: str, password: str,
                 database: str = "GOZER", port: int = 5432) -> pd.DataFrame:
    try:
        import psycopg2
    except ImportError as e:
        raise ImportError("psycopg2 requis pour interroger GOZER : pip install psycopg2") from e

    conn = psycopg2.connect(host=host, database=database, user=user,
                            password=password, port=port)
    try:
        cur = conn.cursor()
        cur.execute(sql)
        rows = cur.fetchall()
        cols = [d[0] for d in cur.description]
        return pd.DataFrame(rows, columns=cols)
    finally:
        conn.close()


def _merge_liv_rf(df_liv_raw: pd.DataFrame, df_rf: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Fusionne LIV + RF et retourne (df_liv_fmt, df_f3db_fmt) prêts pour VLCDesignBlock.

    df_liv_raw  : colonnes Device, voltage, current (A, signé), l ou L (W), EQE (%), Nw_theoretical
    df_rf       : colonnes Device, CurrentDensity (A/cm²), f3dB (Hz), Nw_theoretical
    """
    # ── Préparer LIV ──────────────────────────────────────────────────────────
    liv = df_liv_raw.copy()
    liv["Device"] = liv["Device"].astype(str)

    # PostgreSQL abaisse les alias non-quotés → "L" devient "l"
    l_col = "l" if "l" in liv.columns else "L"

    for col in ["current", "voltage", l_col, "EQE"]:
        liv[col] = pd.to_numeric(liv[col], errors="coerce")

    liv["Abs_current"] = liv["current"].abs()
    liv = liv.dropna(subset=["Abs_current", "voltage", l_col])

    # J (A/cm²) = Abs_current / (Nw * wire_area)
    liv["J"] = liv["Abs_current"] / (liv["Nw_theoretical"] * _WIRE_AREA_CM2)
    # L par fil (W)
    liv["L_per_wire"] = liv[l_col] / liv["Nw_theoretical"]

    # ── Préparer RF ───────────────────────────────────────────────────────────
    rf = df_rf.copy()
    rf["Device"] = rf["Device"].astype(str)
    for col in ["CurrentDensity", "f3dB"]:
        rf[col] = pd.to_numeric(rf[col], errors="coerce")
    rf = rf.dropna(subset=["CurrentDensity", "f3dB"])

    # ── Construire df_liv_fmt (format VLCDesignBlock) ────────────────────────
    liv_fmt_rows = []
    for device, grp in liv.groupby("Device"):
        grp = grp.sort_values("J")
        liv_fmt_rows.append(pd.DataFrame({
            "Sample":       device,
            "Voltage (V)":  grp["voltage"].values,
            "J (A/cm²)":    grp["J"].values,
            "EQE (%)":      grp["EQE"].values,
            "L (W)":        grp["L_per_wire"].values,   # L par fil !
            "n_wires":      grp["Nw_theoretical"].values,
        }))
    df_liv_fmt = pd.concat(liv_fmt_rows, ignore_index=True) if liv_fmt_rows else pd.DataFrame()

    # ── Construire df_f3db_fmt (format VLCDesignBlock) ───────────────────────
    f3db_fmt_rows = []
    for device, grp in rf.groupby("Device"):
        grp = grp.sort_values("CurrentDensity")
        f3db_fmt_rows.append(pd.DataFrame({
            "Sample":       device,
            "Test":         "RF",                          # test unique par device
            "J (A/cm²)":    grp["CurrentDensity"].values,
            "f-3dB (MHz)":  grp["f3dB"].values / 1e6,    # Hz → MHz
        }))
    df_f3db_fmt = pd.concat(f3db_fmt_rows, ignore_index=True) if f3db_fmt_rows else pd.DataFrame()

    return df_liv_fmt, df_f3db_fmt


# ─────────────────────────────────────────────────────────────────────────────
#  API publique
# ─────────────────────────────────────────────────────────────────────────────

def load_vlc_from_miscellaneous(
    folder: str,
    host: str = "INF10",
    user: str = "ymalier",
    password: str = "",
    database: str = "GOZER",
    port: int = 5432,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """
    Charge les données VLC depuis le dossier MISCELLANEOUS RF + base GOZER.

    Parameters
    ----------
    folder   : chemin du dossier RF, ex: r"W:\\Ateliers\\Mesure\\MISCELLANEOUS\\289-RF_Measurements"
    host     : hôte PostgreSQL GOZER
    user     : identifiant GOZER
    password : mot de passe GOZER
    database : nom de la base (défaut "GOZER")
    port     : port PostgreSQL (défaut 5432)

    Returns
    -------
    df_liv    : LIV depuis GOZER (EQE, L optique) — source principale
    df_f3db   : bande passante RF depuis les fichiers
    df_liv_rf : IV brut depuis les fichiers (Voltage électrique précis), ou None
                → passer à ``VLCDesignBlock(df_liv_rf=df_liv_rf)`` pour l'overlay J vs V

    Exemple
    -------
    >>> df_liv, df_f3db, df_liv_rf = load_vlc_from_miscellaneous(
    ...     folder=r"W:\\Ateliers\\Mesure\\MISCELLANEOUS\\289-RF_Measurements",
    ...     password="3X52txX!&",
    ... )
    >>> tab.add(VLCDesignBlock(df_liv=df_liv, df_f3db=df_f3db, df_liv_rf=df_liv_rf, n_wires_array=1))
    """
    # 1) Lire le dossier RF
    df_rf = _read_rf_folder(folder)

    # 2a) Suffixer les devices mesurés plusieurs fois (path différent = mesure distincte)
    df_rf = _meas_suffix_by_path(df_rf)

    # 2b) Extraire l'IV brut du fichier (Voltage, L) pour overlay dans J vs V
    df_liv_rf = _extract_liv_from_rf(df_rf)

    # 3) Extraire la liste de devices depuis le nom (format wafer_X,Y_sample)
    samples_list = df_rf["Device"].dropna().unique().tolist()
    parsed = []
    for device in samples_list:
        try:
            wafer, rest = device.split("_", 1)
            xy, sample = rest.split("_", 1)
            x, y = xy.split(",")
            parsed.append((wafer, x, y, sample))
        except ValueError:
            continue

    if not parsed:
        raise ValueError("Aucun device au format wafer_X,Y_sample trouvé dans le dossier RF.")

    # 3) Requête GOZER
    sql = _build_gozer_sql(parsed)
    df_liv_raw = _query_gozer(sql, host=host, user=user, password=password,
                              database=database, port=port)

    # Reconstruire la colonne Device dans df_liv_raw
    df_liv_raw["X,Y"] = (df_liv_raw["Block_X_Coordinate"].astype(str)
                         + "," + df_liv_raw["Block_Y_Coordinate"].astype(str))
    df_liv_raw["Device"] = (df_liv_raw["wafer_name"].astype(str) + "_"
                            + df_liv_raw["X,Y"].astype(str) + "_"
                            + df_liv_raw["Led_Name"].astype(str))
    df_liv_raw["current"] = pd.to_numeric(df_liv_raw["current"], errors="coerce")
    df_liv_raw["Abs_current"] = df_liv_raw["current"].abs()

    # Nw depuis le nom de device
    df_liv_raw["Nw_theoretical"] = df_liv_raw["Device"].apply(_nwires_from_device)

    # 4) Fusion et mise au format VLCDesignBlock
    df_liv, df_f3db = _merge_liv_rf(df_liv_raw, df_rf)
    return df_liv, df_f3db, df_liv_rf


def load_vlc_rf_only(folder: str) -> pd.DataFrame:
    """
    Charge uniquement les données RF depuis le dossier MISCELLANEOUS.
    Utile pour inspecter les devices disponibles avant de lancer la requête GOZER.

    Returns
    -------
    df_rf brut (colonnes: Device, CurrentDensity, f3dB, Nw_theoretical, ...)
    """
    return _read_rf_folder(folder)
