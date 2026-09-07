"""
data/fake_leds.py
-----------------
Fake LED characterization data for Graph Builder v2 testing.
Replace make_dataframe() with your real Aledia data loader.
"""
import sys
sys.path.insert(0, str(__import__('pathlib').Path(__file__).parent.parent))

import numpy as np
import pandas as pd


def _is_vector_col(series):
    sample = series.dropna()
    if len(sample) == 0: return False
    return isinstance(sample.iloc[0], (list, np.ndarray))

def _col_analysis(df):
    scalar_num, scalar_cat, vector = [], [], []
    for col in df.columns:
        if _is_vector_col(df[col]): vector.append(col)
        elif pd.api.types.is_numeric_dtype(df[col]): scalar_num.append(col)
        else: scalar_cat.append(col)
    return {"scalar_num": scalar_num, "scalar_cat": scalar_cat, "vector": vector,
            "scalar": scalar_num + scalar_cat, "all": list(df.columns)}

def _safe_json(v):
    if isinstance(v, float) and np.isnan(v): return None
    if isinstance(v, np.integer): return int(v)
    if isinstance(v, np.floating): return float(v)
    if isinstance(v, np.ndarray): return v.tolist()
    return v


"""
graph_builder_v2.py
-------------------
Standalone dev file for GraphBuilder v2.
Generates fake LED data and renders an enhanced interactive explorer.
"""
import sys
sys.path.insert(0, "/home/claude")

import numpy as np
import pandas as pd
import json

# ─────────────────────────────────────────────────────────────────────────────
#  Fake LED data generation
# ─────────────────────────────────────────────────────────────────────────────
np.random.seed(42)

def make_led(name, wafer, mocvd_mbe, qt, peak_lambda, peak_eqe, area_um2):
    n_pts = 20
    I = np.logspace(-9, -3, n_pts)
    area_cm2 = area_um2 * 1e-8
    J = I / area_cm2

    # EQE curve — bell shape
    J_peak = peak_eqe * 0.3 + np.random.uniform(-0.05, 0.05)
    eqe = peak_eqe * np.exp(-0.5 * ((np.log10(J) - np.log10(max(J_peak,1e-4))) / 1.2)**2)
    eqe += np.random.normal(0, 0.002, n_pts)
    eqe = np.clip(eqe, 0, 1)

    # JV curve
    V = 2.4 + np.log10(J / 1e-4 + 1) * 0.3 + np.random.normal(0, 0.02, n_pts)
    V = np.clip(V, 0, 6)

    # Spectra — gaussian around peak_lambda, varies with current
    wl = np.linspace(380, 780, 150)
    spectra = []
    for j in J:
        sigma = 15 + np.log10(max(j, 1e-9) + 1e-9) * 3
        sp = np.exp(-0.5 * ((wl - peak_lambda) / sigma)**2)
        sp *= (0.5 + j / J.max() * 0.5)  # brighter at higher J
        spectra.append(sp.tolist())

    # CIE coordinates — vary with current (slight blue shift at low J)
    ciex_peak = 0.1 + (peak_lambda - 380) / 400 * 0.55
    ciey_peak = 0.05 + (peak_lambda - 380) / 400 * 0.7
    ciex = [ciex_peak + np.random.normal(0, 0.005) - (1 - j/J.max()) * 0.01 for j in J]
    ciey = [ciey_peak + np.random.normal(0, 0.005) for j in J]

    # sRGB from lambda
    def lambda_to_hex(lam):
        l = lam
        if   l < 440: r,g,b = -(l-440)/60, 0, 1
        elif l < 490: r,g,b = 0, (l-440)/50, 1
        elif l < 510: r,g,b = 0, 1, -(l-510)/20
        elif l < 580: r,g,b = (l-510)/70, 1, 0
        elif l < 645: r,g,b = 1, -(l-645)/65, 0
        else:          r,g,b = 1, 0, 0
        r,g,b = (max(0,min(1,x))**0.8 for x in (r,g,b))
        return "#{:02x}{:02x}{:02x}".format(int(r*255), int(g*255), int(b*255))

    srgb = [lambda_to_hex(peak_lambda + np.random.normal(0, 3)) for _ in J]
    lambda_dom = [peak_lambda + np.random.normal(0, 3) for _ in J]

    return {
        "Led_Name":      name,
        "wafername":     wafer,
        "MOCVD_MBE":     mocvd_mbe,
        "QT":            qt,
        "size_x_um":     int(np.sqrt(area_um2)),
        "size_y_um":     int(np.sqrt(area_um2)),
        "X":             np.random.randint(-5, 5),
        "Y":             np.random.randint(-5, 5),
        "max_EQE":       float(eqe.max()),
        "V_at_MaxEQE":   float(V[eqe.argmax()]),
        "peak_lambda":   float(peak_lambda),
        "I":             I.tolist(),
        "J":             J.tolist(),
        "V":             V.tolist(),
        "EQE":           eqe.tolist(),
        "Spectra":       spectra,
        "Wavelength":    wl.tolist(),
        "CIEx":          ciex,
        "CIEy":          ciey,
        "srgb":          srgb,
        "Lambda_Dominant": lambda_dom,
    }

rows = []
configs = [
    # (wafer, mocvd_mbe, qt, peak_lambda, peak_eqe, area)
    ("W_MOCVD_A", "MOCVD", "QT1", 450, 0.25, 125*125),
    ("W_MOCVD_A", "MOCVD", "QT1", 452, 0.22, 125*125),
    ("W_MOCVD_A", "MOCVD", "QT1", 448, 0.27, 50*50),
    ("W_MOCVD_B", "MOCVD", "QT2", 455, 0.18, 125*125),
    ("W_MOCVD_B", "MOCVD", "QT2", 453, 0.20, 125*125),
    ("W_MBE_A",   "MBE",   "QT1", 445, 0.15, 125*125),
    ("W_MBE_A",   "MBE",   "QT1", 447, 0.17, 50*50),
    ("W_MBE_B",   "MBE",   "QT2", 460, 0.12, 125*125),
]

for i, (wafer, proc, qt, lam, eqe, area) in enumerate(configs):
    rows.append(make_led(f"LED_{i+1:02d}", wafer, proc, qt, lam + np.random.normal(0,2), eqe + np.random.normal(0,0.02), area))

df = pd.DataFrame(rows)
print(f"Dataset: {len(df)} LEDs · {df['wafername'].nunique()} wafers")
print(f"Scalar cols: max_EQE, V_at_MaxEQE, peak_lambda, X, Y, size_x_um...")
print(f"Vector cols: I, J, V, EQE, Spectra, Wavelength, CIEx, CIEy, srgb...")

# ─────────────────────────────────────────────────────────────────────────────
#  Serialize data to JSON
# ─────────────────────────────────────────────────────────────────────────────

cols = _col_analysis(df)
print(f"\nScalar num: {cols['scalar_num']}")
print(f"Scalar cat: {cols['scalar_cat']}")
print(f"Vector:     {cols['vector']}")

# Serialize (exclude heavy cols for GraphBuilder)
EXCLUDE = {"Spectra", "Wavelength", "CIEx", "CIEy", "srgb"}
MAX_VEC = 20  # downsample vectors

records = []
for _, row in df.iterrows():
    rec = {}
    for col in df.columns:
        if col in EXCLUDE:
            continue
        v = row[col]
        if isinstance(v, (list, np.ndarray)):
            arr = list(v)
            if len(arr) > MAX_VEC:
                step = max(1, len(arr) // MAX_VEC)
                arr = arr[::step]
            rec[col] = [_safe_json(x) for x in arr]
        elif isinstance(v, float) and np.isnan(v):
            rec[col] = None
        else:
            rec[col] = _safe_json(v)
    records.append(rec)

data_json = json.dumps(records)
scalar_num_json = json.dumps([c for c in cols['scalar_num'] if c not in EXCLUDE])
scalar_cat_json = json.dumps([c for c in cols['scalar_cat'] if c not in EXCLUDE])
vector_json     = json.dumps([c for c in cols['vector']     if c not in EXCLUDE])

# Also serialize full data (with Spectra/Wavelength/CIE) for CIE diagram
records_full = []
for _, row in df.iterrows():
    rec = {}
    for col in df.columns:
        v = row[col]
        if col == "Spectra":
            sp = list(v)
            def ds(s, t=120):
                if len(s) <= t: return [_safe_json(x) for x in s]
                step = max(1, len(s)//t); return [_safe_json(s[i]) for i in range(0,len(s),step)]
            rec["Spectra"] = [ds(s) for s in sp]
        elif isinstance(v, (list, np.ndarray)):
            arr = list(v)
            if len(arr) > MAX_VEC:
                step = max(1, len(arr) // MAX_VEC)
                arr = arr[::step]
            rec[col] = [_safe_json(x) for x in arr]
        elif isinstance(v, float) and np.isnan(v):
            rec[col] = None
        else:
            rec[col] = _safe_json(v)
    records_full.append(rec)

data_full_json = json.dumps(records_full)
wafers_json    = json.dumps(sorted(df['wafername'].unique().tolist()))

# Lambda colorscale
def lambda_to_srgb(lam):
    l = lam
    if   l < 380: r,g,b = 0,0,0
    elif l < 440: r,g,b = -(l-440)/60, 0, 1
    elif l < 490: r,g,b = 0, (l-440)/50, 1
    elif l < 510: r,g,b = 0, 1, -(l-510)/20
    elif l < 580: r,g,b = (l-510)/70, 1, 0
    elif l < 645: r,g,b = 1, -(l-645)/65, 0
    elif l <= 700: r,g,b = 1,0,0
    else:          r,g,b = 0,0,0
    r,g,b = (max(0,min(1,x))**0.8 for x in (r,g,b))
    return "#{:02x}{:02x}{:02x}".format(int(r*255), int(g*255), int(b*255))

lambda_colorscale = json.dumps([[i/(60), lambda_to_srgb(400 + i*5)] for i in range(61)])


# ─────────────────────────────────────────────────────────────────────────────
#  Public API
# ─────────────────────────────────────────────────────────────────────────────

def make_dataframe():
    """
    Returns
    -------
    df        : pd.DataFrame with scalar + vector columns
    cols      : dict with keys scalar_num, scalar_cat, vector, scalar, all
    data_vars : dict of JSON strings ready for HTML injection
    """
    return df, cols, {
        "data_json":         data_json,
        "data_full_json":    data_full_json,
        "wafers_json":       wafers_json,
        "scalar_num_json":   scalar_num_json,
        "scalar_cat_json":   scalar_cat_json,
        "vector_json":       vector_json,
        "lambda_colorscale": lambda_colorscale,
        "len_df":            str(len(df)),
        "len_scalar_num":    str(len(cols["scalar_num"])),
        "len_vector":        str(len([c for c in cols["vector"] if c not in EXCLUDE])),
    }
