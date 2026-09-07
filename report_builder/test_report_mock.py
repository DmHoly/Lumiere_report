"""
test_report_mock.py — Rapport de test basé sur les données mock LED.

Usage :
    cd report_builder
    python test_report_mock.py
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pandas as pd
import plotly.express as px

from report_builder.core import (
    ReportBuilder, Tab, TabView,
    Section, Text, KPIRow, KPI, PlotlyChart, DataTable,
    ScatterLED, SummaryBoxPlots, ScatterSummary, WaferMaps,
    StatAnalysis, ScatterPoint, RawDataTableBlock,
    GraphBuilderV2, GraphBuilderV3,
)
from report_builder.core.mock_led_dataset import (
    generate_mock_led_dataset,
    add_quality_flags,
    add_monotonicity_flags,
)

# ─────────────────────────────────────────────────────────────────────────────
# 1. Génération des données mock
# ─────────────────────────────────────────────────────────────────────────────
print("Génération des données mock...")
df = generate_mock_led_dataset(
    n_wafers=4,
    points_per_wafer=150,
    n_iv_points=20,
    n_wavelengths=101,
    n_params=5,
    seed=42,
)
df = add_monotonicity_flags(df)
df = add_quality_flags(df)

print(f"  → {len(df)} LEDs · {df['wafername'].nunique()} wafers")
print(f"  → colonnes : {list(df.columns)}")

# Dataset agrégé par wafer pour les KPI summary
df_wafer = df.groupby("wafername").agg(
    n_leds=("Led_Name", "count"),
    EQE_max_median=("EQE_max", "median"),
    EQE_max_p90=("EQE_max", lambda x: x.quantile(0.9)),
    Lambda_median=("Lambda_peak_at_max_EQE", "median"),
    V_median=("V_at_max_EQE", "median"),
    outlier_rate=("injected_EQE_outlier", "mean"),
).reset_index()

# ─────────────────────────────────────────────────────────────────────────────
# 2. Initialisation du rapport
# ─────────────────────────────────────────────────────────────────────────────
report = ReportBuilder(
    title    = "LED Explorer — Mock Data",
    subtitle = f"Test report · {df['wafername'].nunique()} wafers · {len(df)} LEDs · seed=42",
    author   = "Report Builder Test",
    date     = "2026-06-14",
)

# Enregistrement des datasets (une seule fois)
report.data.register("main", df)
report.data.register("wafer_summary", df_wafer)

# ─────────────────────────────────────────────────────────────────────────────
# 3. Onglet 1 — Vue d'ensemble
# ─────────────────────────────────────────────────────────────────────────────
tab_overview = Tab("Vue d'ensemble")

tab_overview.add(Section("Dataset"))
tab_overview.add(Text(
    f"Rapport généré à partir du générateur mock LED.\n\n"
    f"- **{len(df)} LEDs** réparties sur **{df['wafername'].nunique()} wafers**\n"
    f"- Splits : {', '.join(df['split_str'].unique())}\n"
    f"- Réacteurs : {', '.join(sorted(df['reactor'].unique()))}\n"
    f"- Outliers EQE injectés : {df['injected_EQE_outlier'].sum()} ({df['injected_EQE_outlier'].mean()*100:.1f}%)\n"
))

tab_overview.add(Section("KPI globaux"))
tab_overview.add(KPIRow([
    KPI("LEDs totales",    len(df),                          unit=""),
    KPI("Wafers",          df["wafername"].nunique(),         unit=""),
    KPI("EQE max médiane", f"{df['EQE_max'].median():.2f}",  unit="%"),
    KPI("Lambda médiane",  f"{df['Lambda_peak_at_max_EQE'].median():.1f}", unit="nm"),
    KPI("V @ EQE max",     f"{df['V_at_max_EQE'].median():.2f}", unit="V"),
    KPI("Outliers EQE",    df["injected_EQE_outlier"].sum(), unit="LEDs",
        delta=f"+{df['injected_EQE_outlier'].mean()*100:.1f}%"),
]))

tab_overview.add(Section("Résumé par wafer"))
tab_overview.add(DataTable(
    data      = "wafer_summary",
    title     = "KPI par wafer",
    page_size = 10,
    fmt       = {
        "EQE_max_median": "{:.2f}",
        "EQE_max_p90":    "{:.2f}",
        "Lambda_median":  "{:.1f}",
        "V_median":       "{:.3f}",
        "outlier_rate":   "{:.3f}",
    },
))

# ─────────────────────────────────────────────────────────────────────────────
# 4. Onglet 2 — Scatter EQE
# ─────────────────────────────────────────────────────────────────────────────
tab_scatter = Tab("Scatter EQE")

tab_scatter.add(Section("EQE max vs Lambda Peak", subtitle="couleur = split_str · clic = détail"))
tab_scatter.add(ScatterLED(
    data           = "main",
    x_col          = "I",
    y_col          = "EQE",
    color_col      = "split_str",
    hover_cols     = ["Led_Name", "wafername", "X", "Y", "EQE_max", "split_str"],
    log_x          = False,
    log_y          = False,
    height         = 500,
    curve_x        = "V",
    curve_y        = "I",
    spectra_col    = "Spectra",
    wavelength_col = "WL",
    id_col         = "Led_Name",
    num            = "01",
    title          = "Courbes EQE(I)",
    subtitle       = "couleur = split_str",
    x_label        = "Courant I (mA)",
    y_label        = "EQE (%)",
    filter_cols    = ["wafername", "split_str", "reactor", "EQE_max", "Lambda_peak_at_max_EQE"],
))

tab_scatter.add(Section("EQE max vs Lambda — vue synthétique"))
tab_scatter.add(ScatterSummary(
    data        = "main",
    x_col       = "Lambda_peak_at_max_EQE",
    y_col       = "EQE_max",
    color_col   = "wafername",
    hover_cols  = ["Led_Name", "wafername", "split_str", "reactor"],
    trendline   = True,
    height      = 420,
    num         = "02",
    title       = "EQE max vs Lambda Peak",
))

tab_scatter.add(Section("EQE max vs V @ EQE max"))
tab_scatter.add(ScatterSummary(
    data        = "main",
    x_col       = "V_at_max_EQE",
    y_col       = "EQE_max",
    color_col   = "split_str",
    hover_cols  = ["Led_Name", "wafername"],
    targets     = {"x": (2.5, 3.5)},
    trendline   = False,
    height      = 420,
    num         = "03",
    title       = "EQE max vs V @ EQE max",
))

# ─────────────────────────────────────────────────────────────────────────────
# 5. Onglet 3 — Résumé par wafer
# ─────────────────────────────────────────────────────────────────────────────
tab_summary = Tab("Résumé wafer")

tab_summary.add(Section("Boxplots par wafer"))
tab_summary.add(SummaryBoxPlots(
    data           = "main",
    group_col      = "wafername",
    metrics        = {
        "EQE max":         ("EQE_max",               "%"),
        "Lambda Peak":     ("Lambda_peak_at_max_EQE", "nm"),
        "V @ EQE max":     ("V_at_max_EQE",           "V"),
        "EQE drop":        ("EQE_drop_pct",            "%"),
    },
    targets        = {"V_at_max_EQE": (2.5, 3.5)},
    cols_per_row   = 2,
    height_per_row = 420,
    num            = "04",
    title          = "Distribution par wafer",
))

# ─────────────────────────────────────────────────────────────────────────────
# 6. Onglet 4 — Wafer Maps
# ─────────────────────────────────────────────────────────────────────────────
tab_wafermaps = Tab("Wafer Maps")

tab_wafermaps.add(Section("Cartographie spatiale", subtitle="EQE max · filtre split_str"))
tab_wafermaps.add(WaferMaps(
    data           = "main",
    x_col          = "X",
    y_col          = "Y",
    wafer_col      = "wafername",
    color_col      = "EQE_max",
    colormap_cols  = ["EQE_max", "Lambda_peak_at_max_EQE", "V_at_max_EQE", "EQE_drop_pct", "thickness_nm"],
    filter_cols    = ["split_str", "reactor", "injected_EQE_outlier"],
    id_col         = "Led_Name",
    kpi_cols       = ["EQE_max", "Lambda_peak_at_max_EQE", "V_at_max_EQE"],
    curve_cols     = {
        "EQE":  {"x": "I", "y": "EQE",  "log_y": False, "xlabel": "I (mA)", "ylabel": "EQE (%)"},
    },
    spectra_col    = "Spectra",
    wavelength_col = "WL",
    num            = "05",
    title          = "Wafer Maps — EQE max",
    subtitle       = "colormap dropdown · clic = détail · lasso = région",
))

# ─────────────────────────────────────────────────────────────────────────────
# 7. Onglet 5 — Stat Analysis
# ─────────────────────────────────────────────────────────────────────────────
tab_lambda = Tab("Stat Analysis")

# ─────────────────────────────────────────────────────────────────────────────
# 8. Onglet 6 — Raw Data
# ─────────────────────────────────────────────────────────────────────────────
tab_raw = Tab("Données brutes")
tab_raw.add(RawDataTableBlock(
    data  = "main",
    title = "Dataset complet",
    num   = "07",
))

# ─────────────────────────────────────────────────────────────────────────────
# 9. Assemblage et export
# ─────────────────────────────────────────────────────────────────────────────
tab_lambda.add(Section("Analyse statistique — EQE max par split"))
tab_lambda.add(StatAnalysis(
    data      = "main",
    targets   = ["EQE_max", "Lambda_peak_at_max_EQE", "V_at_max_EQE"],
    features  = ["temperature_c", "thickness_nm", "doping_cm3", "param_1", "param_2"],
    split_col = "split_str",
    wafer_col = "wafername",
    site_col  = None,
    num       = "06",
    title     = "Analyse des splits — EQE, Lambda, V",
))

# ─────────────────────────────────────────────────────
# ─────────────────────────────────────────────────────────────────────────────
tab_gbv2 = Tab("Graph Builder V2")
tab_gbv2.add(GraphBuilderV2("main"))

tab_gbv3 = Tab("Graph Builder V3 ✦")
tab_gbv3.add(GraphBuilderV3(
    data           = "main",
    title          = "Graph Builder V3 — Mock LED",
    exclude_cols   = [],  # colonnes vectorielles exclues
    max_vector_pts = 50,
    height=1000,
))

report.add(TabView([
    tab_overview,
    tab_scatter,
    tab_summary,
    tab_wafermaps,
    tab_lambda,
    tab_gbv2,
    tab_gbv3,
    tab_raw,
]))

output_path = os.path.join(os.path.dirname(__file__), "output", "test_report_mock.html")
os.makedirs(os.path.dirname(output_path), exist_ok=True)

print(f"\nGénération du rapport → {output_path}")
report.save(output_path)
print(f"OK — {os.path.getsize(output_path) / 1024:.0f} KB")
