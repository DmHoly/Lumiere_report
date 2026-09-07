"""
mock_led_dataset.py

Générateur de dataset LED / wafer pour tester un moteur d'exploration de données.

Contenu généré
--------------
Chaque ligne représente une position LED sur un wafer.

Colonnes principales :
- Identifiants : wafername, Led_Name, lot, epi, reactor
- Position : X, Y, R
- Catégories :
    - string : split_str, lot, epi, reactor
    - int : split_int, chamber_id
    - float catégoriel : split_float, reactor_setting
- Variables continues :
    - temperature_c, thickness_nm, doping_cm3
- Vecteurs :
    - I, V, L, EQE
- Longueur d'onde :
    - WL
- Spectres :
    - Spectra = liste de spectres, un spectre par point de courant
- KPI :
    - EQE_max, EQE_drop_pct, Lambda_peak_at_max_EQE, etc.
- Paramètres additionnels :
    - param_1 ... param_N
- Ground truth bugs :
    - injected_EQE_outlier
    - injected_V_non_monotone
    - injected_L_non_monotone

Fonctions principales
---------------------
- generate_mock_led_dataset(...)
- add_curve_outlier_flag(...)
- add_monotonicity_flags(...)
- add_scalar_outlier_flag(...)
- add_quality_flags(...)
"""

from __future__ import annotations

from typing import Any, Literal

import numpy as np
import pandas as pd


def _safe_float(value: Any) -> float:
    """Convertit proprement une valeur numérique en float."""
    if value is None:
        return np.nan
    return float(value)


def _compute_fwhm(x: np.ndarray, y: np.ndarray) -> float:
    """Calcule une FWHM simple sur un spectre."""
    if len(x) != len(y) or len(y) == 0:
        return np.nan

    y_max = float(np.nanmax(y))

    if not np.isfinite(y_max) or y_max <= 0:
        return np.nan

    half_max = y_max / 2
    idx = np.where(y >= half_max)[0]

    if len(idx) <= 1:
        return np.nan

    return float(x[idx[-1]] - x[idx[0]])


def _inject_single_point_outlier(
    y: np.ndarray,
    rng: np.random.Generator,
    strength: tuple[float, float] = (2.5, 6.0),
    avoid_edges: bool = True,
) -> tuple[np.ndarray, int, float, str]:
    """
    Injecte un point aberrant dans un vecteur.

    Retourne
    --------
    y_bugged, bug_index, factor, bug_type
    """
    y = y.copy()

    if len(y) < 3:
        return y, -1, np.nan, "none"

    if avoid_edges and len(y) >= 5:
        bug_idx = int(rng.integers(1, len(y) - 1))
    else:
        bug_idx = int(rng.integers(0, len(y)))

    factor = float(rng.uniform(*strength))

    if rng.random() < 0.5:
        y[bug_idx] *= factor
        bug_type = "spike_up"
    else:
        y[bug_idx] /= factor
        bug_type = "spike_down"

    y = np.clip(y, 0, None)

    return y, bug_idx, factor, bug_type


def _inject_non_monotone_point(
    y: np.ndarray,
    rng: np.random.Generator,
    strength: tuple[float, float] = (0.15, 0.50),
) -> tuple[np.ndarray, int, float]:
    """
    Injecte une rupture de monotonie dans une courbe supposée croissante.

    Exemple :
    - V(I) doit monter
    - L(I) doit monter

    On prend un point interne et on le force sous le point précédent.
    """
    y = y.copy()

    if len(y) < 4:
        return y, -1, np.nan

    bug_idx = int(rng.integers(1, len(y) - 1))
    drop_fraction = float(rng.uniform(*strength))

    y[bug_idx] = y[bug_idx - 1] * (1 - drop_fraction)

    if y[bug_idx] < 0:
        y[bug_idx] = 0

    return y, bug_idx, drop_fraction


def generate_mock_led_dataset(
    n_wafers: int = 5,
    points_per_wafer: int = 200,
    n_iv_points: int = 15,
    n_wavelengths: int = 201,
    n_params: int = 20,
    seed: int = 42,
    inject_eqe_outliers: bool = True,
    eqe_outlier_probability: float = 0.08,
    eqe_outlier_strength: tuple[float, float] = (2.5, 6.0),
    inject_v_non_monotone: bool = True,
    v_non_monotone_probability: float = 0.03,
    inject_l_non_monotone: bool = True,
    l_non_monotone_probability: float = 0.03,
) -> pd.DataFrame:
    """
    Génère un dataset LED mock complexe.

    Parameters
    ----------
    n_wafers:
        Nombre de wafers.
    points_per_wafer:
        Nombre de positions LED par wafer.
    n_iv_points:
        Nombre de points dans les vecteurs I, V, L, EQE.
    n_wavelengths:
        Nombre de points dans le vecteur WL.
    n_params:
        Nombre de colonnes param_1, param_2, ..., param_N à générer.
        Ces colonnes simulent des KPI extraits automatiquement de courbes.
    seed:
        Seed de reproductibilité.
    inject_eqe_outliers:
        Injecte ou non des spikes dans EQE.
    eqe_outlier_probability:
        Probabilité d'avoir un bug EQE par ligne.
    eqe_outlier_strength:
        Facteur min/max du spike EQE.
    inject_v_non_monotone:
        Injecte ou non des défauts de monotonie sur V(I).
    v_non_monotone_probability:
        Probabilité de bug V par ligne.
    inject_l_non_monotone:
        Injecte ou non des défauts de monotonie sur L(I).
    l_non_monotone_probability:
        Probabilité de bug L par ligne.

    Returns
    -------
    pd.DataFrame
        Dataset mock.
    """
    rng = np.random.default_rng(seed)
    wavelengths = np.linspace(400, 750, n_wavelengths)

    rows: list[dict[str, Any]] = []

    for wafer_idx in range(n_wafers):
        wafername = f"WAFER_{wafer_idx:03d}"

        # Effets globaux wafer
        wafer_lambda_shift = rng.normal(0, 8)
        wafer_eqe_gain = rng.normal(1.0, 0.10)
        wafer_voltage_shift = rng.normal(0, 0.08)
        wafer_l_gain = rng.normal(1.0, 0.12)

        lot = str(rng.choice(["LOT_A", "LOT_B", "LOT_C"]))
        epi = str(rng.choice(["EPI_1", "EPI_2", "EPI_3"]))
        reactor = str(rng.choice(["R1", "R2", "R3"]))

        for led_idx in range(points_per_wafer):
            # Position aléatoire dans un disque wafer
            radius = np.sqrt(rng.random())
            theta = rng.uniform(0, 2 * np.pi)

            x = float(radius * np.cos(theta))
            y = float(radius * np.sin(theta))
            radial_distance = float(np.sqrt(x**2 + y**2))

            # Catégories
            split_str = str(rng.choice(["REF", "SPLIT_A", "SPLIT_B", "SPLIT_C"]))
            split_int = int(rng.choice([0, 1, 2, 3]))

            # Catégoriel float volontairement piégeux
            split_float = float(rng.choice([8.0, 9.0, 10.0]))
            reactor_setting = float(rng.choice([0.25, 0.50, 0.75]))

            chamber_id = int(rng.choice([1, 2, 3]))

            # Variables continues scalaires
            temperature_c = float(rng.normal(25, 1.0))
            thickness_nm = float(120 + 10 * radial_distance + rng.normal(0, 2))
            doping_cm3 = float(10 ** rng.uniform(17.5, 18.5))

            # Courant
            I = np.geomspace(1e-6, 20e-3, n_iv_points)

            # V(I), normalement croissante
            V = (
                2.0
                + wafer_voltage_shift
                + 0.25 * np.log10(I / I.min() + 1)
                + 0.05 * radial_distance
                + 0.015 * split_int
                + rng.normal(0, 0.006, n_iv_points)
            )

            # Force une tendance globalement croissante
            V = np.maximum.accumulate(V)

            # EQE(I), cloche/droop
            eqe_peak_true = (
                rng.uniform(0.10, 0.20)
                * wafer_eqe_gain
                * (1 - 0.15 * radial_distance)
                * (1 + 0.02 * split_int)
            )

            droop_current = rng.uniform(5e-3, 12e-3)

            EQE = eqe_peak_true / (1 + (I / droop_current) ** 1.5)
            EQE *= rng.normal(1, 0.03, n_iv_points)
            EQE = np.clip(EQE, 0, None)

            # L(I), normalement croissante dans ce mock
            L = (
                EQE
                * I
                * 1000
                * wafer_l_gain
                * rng.normal(1, 0.03, n_iv_points)
            )

            # Force une tendance globalement croissante pour le test monotonie
            L = np.maximum.accumulate(L)

            # Injection bug EQE
            injected_eqe_outlier = False
            injected_eqe_outlier_index = None
            injected_eqe_outlier_factor = None
            injected_eqe_outlier_type = None

            if inject_eqe_outliers and rng.random() < eqe_outlier_probability:
                (
                    EQE,
                    bug_idx,
                    factor,
                    bug_type,
                ) = _inject_single_point_outlier(
                    EQE,
                    rng=rng,
                    strength=eqe_outlier_strength,
                    avoid_edges=True,
                )

                injected_eqe_outlier = True
                injected_eqe_outlier_index = int(bug_idx)
                injected_eqe_outlier_factor = float(factor)
                injected_eqe_outlier_type = bug_type

            # Injection défaut monotonie V
            injected_v_non_monotone = False
            injected_v_non_monotone_index = None

            if inject_v_non_monotone and rng.random() < v_non_monotone_probability:
                V, bug_idx, _ = _inject_non_monotone_point(V, rng=rng)
                injected_v_non_monotone = True
                injected_v_non_monotone_index = int(bug_idx)

            # Injection défaut monotonie L
            injected_l_non_monotone = False
            injected_l_non_monotone_index = None

            if inject_l_non_monotone and rng.random() < l_non_monotone_probability:
                L, bug_idx, _ = _inject_non_monotone_point(L, rng=rng)
                injected_l_non_monotone = True
                injected_l_non_monotone_index = int(bug_idx)

            # Spectres
            base_lambda = (
                620
                + wafer_lambda_shift
                - 20 * radial_distance
                + 3 * split_int
            )

            spectra: list[list[float]] = []
            lambda_peaks: list[float] = []
            fwhms: list[float] = []

            for k in range(n_iv_points):
                lambda_peak = base_lambda + 3 * np.log10(I[k] / I[0] + 1)
                width = rng.uniform(18, 28)

                spec = np.exp(-0.5 * ((wavelengths - lambda_peak) / width) ** 2)
                spec *= L[k]

                noise_level = max(float(spec.max()), 1e-12) * 0.01
                spec += rng.normal(0, noise_level, len(wavelengths))
                spec = np.clip(spec, 0, None)

                spectra.append(spec.tolist())

                lambda_peaks.append(float(wavelengths[int(np.argmax(spec))]))
                fwhms.append(_compute_fwhm(wavelengths, spec))

            # KPI principaux
            idx_max_eqe = int(np.argmax(EQE))
            idx_max_l = int(np.argmax(L))

            eqe_max = float(EQE[idx_max_eqe])
            eqe_last = float(EQE[-1])
            l_max = float(L[idx_max_l])

            if eqe_max > 0:
                eqe_drop_pct = float(100 * (eqe_max - eqe_last) / eqe_max)
            else:
                eqe_drop_pct = np.nan

            # Paramètres additionnels param_1 ... param_N
            # Mix volontaire :
            # - certains corrélés à EQE
            # - certains corrélés à lambda
            # - certains corrélés à la position
            # - certains bruités
            extra_params: dict[str, float] = {}

            for p in range(1, n_params + 1):
                if p % 4 == 1:
                    value = eqe_max * rng.normal(1.0, 0.05)
                elif p % 4 == 2:
                    value = lambda_peaks[idx_max_eqe] + rng.normal(0, 2)
                elif p % 4 == 3:
                    value = radial_distance + rng.normal(0, 0.03)
                else:
                    value = rng.normal(0, 1)

                extra_params[f"param_{p}"] = float(value)

            row: dict[str, Any] = {
                # Identifiants
                "wafername": wafername,
                "lot": lot,
                "epi": epi,
                "reactor": reactor,
                "Led_Name": f"{wafername}_{led_idx:04d}",

                # Position
                "X": x,
                "Y": y,
                "R": radial_distance,

                # Catégories
                "split_str": split_str,
                "split_int": split_int,
                "split_float": split_float,
                "reactor_setting": reactor_setting,
                "chamber_id": chamber_id,

                # Variables continues scalaires
                "temperature_c": temperature_c,
                "thickness_nm": thickness_nm,
                "doping_cm3": doping_cm3,

                # Vecteurs
                "I": I.tolist(),
                "V": V.tolist(),
                "L": L.tolist(),
                "EQE": EQE.tolist(),
                "WL": wavelengths.tolist(),

                # Vecteur de vecteurs
                "Spectra": spectra,

                # KPI courbes
                "EQE_max": eqe_max,
                "EQE_last": eqe_last,
                "EQE_drop_pct": eqe_drop_pct,
                "Lambda_peak_at_max_EQE": float(lambda_peaks[idx_max_eqe]),
                "Lambda_peak_last": float(lambda_peaks[-1]),
                "Lambda_shift": float(lambda_peaks[-1] - lambda_peaks[0]),
                "FWHM_at_max_EQE": float(fwhms[idx_max_eqe]),
                "V_at_max_EQE": float(V[idx_max_eqe]),
                "L_at_max_EQE": float(L[idx_max_eqe]),
                "L_max": l_max,
                "V_last": float(V[-1]),
                "I_last": float(I[-1]),

                # Ground truth bugs
                "injected_EQE_outlier": injected_eqe_outlier,
                "injected_EQE_outlier_index": injected_eqe_outlier_index,
                "injected_EQE_outlier_factor": injected_eqe_outlier_factor,
                "injected_EQE_outlier_type": injected_eqe_outlier_type,
                "injected_V_non_monotone": injected_v_non_monotone,
                "injected_V_non_monotone_index": injected_v_non_monotone_index,
                "injected_L_non_monotone": injected_l_non_monotone,
                "injected_L_non_monotone_index": injected_l_non_monotone_index,
            }

            row.update(extra_params)
            rows.append(row)

    return pd.DataFrame(rows)


def detect_vector_outliers(
    x: list[float] | np.ndarray,
    y: list[float] | np.ndarray,
    method: Literal["zscore", "iqr"] = "zscore",
    threshold: float = 3.0,
    window: int = 5,
) -> dict[str, Any]:
    """
    Détecte les outliers d'une seule courbe vectorielle x/y.

    Méthodes
    --------
    zscore:
        Résidu par rapport à une médiane glissante, normalisé par MAD.
        Bon pour détecter un spike local.

    iqr:
        IQR sur les différences successives.
        Bon pour détecter les sauts brutaux.

    Returns
    -------
    dict
        {
            "has_outlier": bool,
            "indices": list[int],
            "x": list[float],
            "y": list[float],
            "scores": list[float],
            "error": str | None,
        }
    """
    try:
        x_arr = np.asarray(x, dtype=float)
        y_arr = np.asarray(y, dtype=float)
    except Exception as exc:
        return {
            "has_outlier": False,
            "indices": [],
            "x": [],
            "y": [],
            "scores": [],
            "error": f"conversion_error: {exc}",
        }

    if len(x_arr) != len(y_arr):
        return {
            "has_outlier": False,
            "indices": [],
            "x": [],
            "y": [],
            "scores": [],
            "error": f"size_mismatch: len(x)={len(x_arr)} len(y)={len(y_arr)}",
        }

    if len(y_arr) < 5:
        return {
            "has_outlier": False,
            "indices": [],
            "x": [],
            "y": [],
            "scores": [],
            "error": None,
        }

    if method == "zscore":
        s = pd.Series(y_arr)

        half_w = max(2, window // 2)

        rolling_median = (
            s.rolling(
                window=2 * half_w + 1,
                center=True,
                min_periods=3,
            )
            .median()
            .bfill()
            .ffill()
        )

        residuals = (s - rolling_median).abs()

        mad = float(residuals.median())

        if mad < 1e-12:
            mad = float(residuals.mean())

        if mad < 1e-12:
            mad = 1e-12

        scores = residuals / (1.4826 * mad)
        mask = scores > threshold

    elif method == "iqr":
        diffs = np.abs(np.diff(y_arr, prepend=y_arr[0]))

        q1, q3 = np.percentile(diffs, [25, 75])
        iqr = q3 - q1

        fence = q3 + threshold * iqr

        if fence < 1e-12:
            fence = 1e-12

        scores = pd.Series(diffs / fence)
        mask = diffs > fence

    else:
        return {
            "has_outlier": False,
            "indices": [],
            "x": [],
            "y": [],
            "scores": [],
            "error": f"unknown_method: {method}",
        }

    indices = np.where(np.asarray(mask))[0].tolist()

    return {
        "has_outlier": len(indices) > 0,
        "indices": indices,
        "x": x_arr[indices].tolist(),
        "y": y_arr[indices].tolist(),
        "scores": np.asarray(scores)[indices].tolist(),
        "error": None,
    }


def add_curve_outlier_flag(
    df: pd.DataFrame,
    x_col: str = "I",
    y_col: str = "EQE",
    method: Literal["zscore", "iqr"] = "zscore",
    threshold: float = 3.0,
    window: int = 5,
    outlier_col: str | None = None,
) -> pd.DataFrame:
    """
    Applique la détection d'outlier de courbe sur toutes les lignes.

    Chaque ligne doit contenir :
    - df[x_col] : liste X
    - df[y_col] : liste Y

    Ajoute :
    - {outlier_col} : True/False
    - {outlier_col}_indices
    - {outlier_col}_x
    - {outlier_col}_y
    - {outlier_col}_scores
    - {outlier_col}_error
    """
    result = df.copy()

    if outlier_col is None:
        outlier_col = f"{y_col}_outlier"

    detections = result.apply(
        lambda row: detect_vector_outliers(
            x=row[x_col],
            y=row[y_col],
            method=method,
            threshold=threshold,
            window=window,
        ),
        axis=1,
    )

    result[outlier_col] = detections.apply(lambda d: d["has_outlier"])
    result[f"{outlier_col}_indices"] = detections.apply(lambda d: d["indices"])
    result[f"{outlier_col}_x"] = detections.apply(lambda d: d["x"])
    result[f"{outlier_col}_y"] = detections.apply(lambda d: d["y"])
    result[f"{outlier_col}_scores"] = detections.apply(lambda d: d["scores"])
    result[f"{outlier_col}_error"] = detections.apply(lambda d: d["error"])
    result[f"{outlier_col}_n"] = result[f"{outlier_col}_indices"].apply(len)

    return result


def check_monotonic_curve(
    x: list[float] | np.ndarray,
    y: list[float] | np.ndarray,
    direction: Literal["increasing", "decreasing"] = "increasing",
    tolerance: float = 0.0,
) -> dict[str, Any]:
    """
    Vérifie si une courbe y(x) est monotone.

    Parameters
    ----------
    x:
        Vecteur X.
    y:
        Vecteur Y.
    direction:
        "increasing" ou "decreasing".
    tolerance:
        Tolérance numérique.
        Exemple : tolerance=1e-6 autorise des micro baisses.

    Returns
    -------
    dict
        {
            "is_monotone": bool,
            "violation_indices": list[int],
            "n_violations": int,
            "max_violation": float,
            "error": str | None,
        }

    Note
    ----
    violation_indices contient l'indice i tel que y[i] viole la monotonie
    par rapport à y[i-1].
    """
    try:
        x_arr = np.asarray(x, dtype=float)
        y_arr = np.asarray(y, dtype=float)
    except Exception as exc:
        return {
            "is_monotone": False,
            "violation_indices": [],
            "n_violations": 0,
            "max_violation": np.nan,
            "error": f"conversion_error: {exc}",
        }

    if len(x_arr) != len(y_arr):
        return {
            "is_monotone": False,
            "violation_indices": [],
            "n_violations": 0,
            "max_violation": np.nan,
            "error": f"size_mismatch: len(x)={len(x_arr)} len(y)={len(y_arr)}",
        }

    if len(y_arr) < 2:
        return {
            "is_monotone": True,
            "violation_indices": [],
            "n_violations": 0,
            "max_violation": 0.0,
            "error": None,
        }

    dy = np.diff(y_arr)

    if direction == "increasing":
        violations = dy < -abs(tolerance)
        violation_magnitude = np.where(violations, -dy, 0.0)

    elif direction == "decreasing":
        violations = dy > abs(tolerance)
        violation_magnitude = np.where(violations, dy, 0.0)

    else:
        return {
            "is_monotone": False,
            "violation_indices": [],
            "n_violations": 0,
            "max_violation": np.nan,
            "error": f"unknown_direction: {direction}",
        }

    # +1 car dy[i] compare y[i+1] à y[i]
    violation_indices = (np.where(violations)[0] + 1).tolist()

    return {
        "is_monotone": len(violation_indices) == 0,
        "violation_indices": violation_indices,
        "n_violations": int(len(violation_indices)),
        "max_violation": float(np.max(violation_magnitude)) if len(violation_magnitude) else 0.0,
        "error": None,
    }


def add_monotonicity_flags(
    df: pd.DataFrame,
    x_col: str = "I",
    y_col: str = "V",
    direction: Literal["increasing", "decreasing"] = "increasing",
    tolerance: float = 0.0,
    prefix: str | None = None,
) -> pd.DataFrame:
    """
    Applique un contrôle de monotonie sur toutes les lignes du DataFrame.

    Exemple
    -------
    V(I) doit être croissante :

    >>> df = add_monotonicity_flags(df, x_col="I", y_col="V", prefix="V_vs_I")

    L(I) doit être croissante :

    >>> df = add_monotonicity_flags(df, x_col="I", y_col="L", prefix="L_vs_I")

    Colonnes ajoutées
    -----------------
    - {prefix}_monotone
    - {prefix}_non_monotone
    - {prefix}_violation_indices
    - {prefix}_n_violations
    - {prefix}_max_violation
    - {prefix}_error
    """
    result = df.copy()

    if prefix is None:
        prefix = f"{y_col}_vs_{x_col}"

    checks = result.apply(
        lambda row: check_monotonic_curve(
            x=row[x_col],
            y=row[y_col],
            direction=direction,
            tolerance=tolerance,
        ),
        axis=1,
    )

    result[f"{prefix}_monotone"] = checks.apply(lambda d: d["is_monotone"])
    result[f"{prefix}_non_monotone"] = ~result[f"{prefix}_monotone"]
    result[f"{prefix}_violation_indices"] = checks.apply(lambda d: d["violation_indices"])
    result[f"{prefix}_n_violations"] = checks.apply(lambda d: d["n_violations"])
    result[f"{prefix}_max_violation"] = checks.apply(lambda d: d["max_violation"])
    result[f"{prefix}_error"] = checks.apply(lambda d: d["error"])

    return result


def add_scalar_outlier_flag(
    df: pd.DataFrame,
    col: str,
    group_col: str | None = None,
    k: float = 1.5,
    output_col: str | None = None,
) -> pd.DataFrame:
    """
    Flags les valeurs scalaires aberrantes par la méthode IQR.

    Ajoute une colonne entière (0/1) qui vaut 1 si la valeur de `col`
    est en dehors de [Q1 - k*IQR, Q3 + k*IQR].

    Si `group_col` est fourni, le calcul IQR est fait par groupe
    (ex: par wafer), ce qui permet de détecter des outliers relatifs
    à la distribution intra-wafer.

    Parameters
    ----------
    col        : colonne scalaire à analyser (ex: "EQE_max")
    group_col  : colonne de regroupement (ex: "wafername") ou None pour global
    k          : facteur IQR (1.5 = outlier standard, 3.0 = outlier extrême)
    output_col : nom de la colonne résultat (défaut: "{col}_outlier")
    """
    out_col = output_col or f"{col}_outlier"
    df = df.copy()

    if group_col and group_col in df.columns:
        def _flag(g: pd.Series) -> pd.Series:
            q1, q3 = g.quantile(0.25), g.quantile(0.75)
            iqr = q3 - q1
            return ((g < q1 - k * iqr) | (g > q3 + k * iqr)).astype(int)
        df[out_col] = df.groupby(group_col)[col].transform(_flag)
    else:
        q1, q3 = df[col].quantile(0.25), df[col].quantile(0.75)
        iqr = q3 - q1
        df[out_col] = ((df[col] < q1 - k * iqr) | (df[col] > q3 + k * iqr)).astype(int)

    return df


def add_quality_flags(
    df: pd.DataFrame,
    eqe_threshold: float = 3.0,
    eqe_window: int = 5,
    monotonic_tolerance: float = 0.0,
) -> pd.DataFrame:
    """
    Ajoute tous les flags qualité principaux au DataFrame.

    Ajoute :
    - EQE_outlier          — outlier dans la courbe EQE(I) (z-score sur vecteur)
    - EQE_max_outlier      — EQE_max scalaire aberrant au niveau global (IQR 1.5×)
    - V_vs_I_monotone / V_vs_I_non_monotone
    - L_vs_I_monotone / L_vs_I_non_monotone
    - has_any_curve_issue

    Returns
    -------
    pd.DataFrame
    """
    result = df.copy()

    result = add_curve_outlier_flag(
        result,
        x_col="I",
        y_col="EQE",
        method="zscore",
        threshold=eqe_threshold,
        window=eqe_window,
        outlier_col="EQE_outlier",
    )

    result = add_scalar_outlier_flag(
        result,
        col="EQE_max",
        group_col=None,
        k=1.5,
        output_col="EQE_max_outlier",
    )

    result = add_monotonicity_flags(
        result,
        x_col="I",
        y_col="V",
        direction="increasing",
        tolerance=monotonic_tolerance,
        prefix="V_vs_I",
    )

    result = add_monotonicity_flags(
        result,
        x_col="I",
        y_col="L",
        direction="increasing",
        tolerance=monotonic_tolerance,
        prefix="L_vs_I",
    )

    result["has_any_curve_issue"] = (
        result["EQE_outlier"]
        | result["V_vs_I_non_monotone"]
        | result["L_vs_I_non_monotone"]
    )

    return result


def summarize_quality_flags(df: pd.DataFrame) -> dict[str, Any]:
    """
    Résume rapidement les flags qualité si les colonnes existent.
    """
    summary: dict[str, Any] = {
        "n_rows": int(len(df)),
    }

    for col in [
        "EQE_outlier",
        "V_vs_I_non_monotone",
        "L_vs_I_non_monotone",
        "has_any_curve_issue",
        "injected_EQE_outlier",
        "injected_V_non_monotone",
        "injected_L_non_monotone",
    ]:
        if col in df.columns:
            summary[col] = {
                "count": int(df[col].sum()),
                "rate_pct": float(100 * df[col].mean()),
            }

    return summary


if __name__ == "__main__":
    # Exemple d'utilisation rapide.
    df = generate_mock_led_dataset(
        n_wafers=3,
        points_per_wafer=100,
        n_iv_points=15,
        n_wavelengths=201,
        n_params=20,
        seed=42,
        inject_eqe_outliers=True,
        eqe_outlier_probability=0.10,
        inject_v_non_monotone=True,
        v_non_monotone_probability=0.05,
        inject_l_non_monotone=True,
        l_non_monotone_probability=0.05,
    )

    df_checked = add_quality_flags(
        df,
        eqe_threshold=3.0,
        eqe_window=5,
        monotonic_tolerance=0.0,
    )

    print(df_checked.shape)
    print(summarize_quality_flags(df_checked))

    # Optionnel : export pickle, recommandé car les colonnes contiennent des listes.
    df_checked.to_pickle("mock_led_dataset_checked.pkl")

    # Optionnel : export parquet peut marcher selon l'environnement pyarrow,
    # mais pickle reste le plus simple pour des colonnes avec listes imbriquées.
    # df_checked.to_parquet("mock_led_dataset_checked.parquet")
