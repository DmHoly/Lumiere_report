"""
graph_builder_block.py
----------------------
GraphBuilderV2 — Block compatible avec le report_builder Aledia.

Usage dans un rapport:
    from graph_builder_block import GraphBuilderV2

    tab_explore = Tab("Exploration")
    tab_explore.add(GraphBuilderV2(
        df,
        exclude_cols=["Spectra", "Wavelength"],
        max_vector_pts=50,
    ))
    report.add(TabView([..., tab_explore]))

Architecture JS séparée (optionnel):
    Si les fichiers js/ et html/ sont disponibles, GraphBuilderV2 les lit
    dynamiquement via load_from_files(). Sinon il embarque le JS inline
    (mode self-contained, par défaut).
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import numpy as np
import pandas as pd

try:
    from ._helpers import Block
    from .blocks.data.data_mixin import DataMixin, DataArg
    _HAS_CORE = True
except ImportError:
    # Standalone mode : on définit des stubs minimalistes
    DataArg = "DataArg"
    class Block:
        needs_plotly = False
        needs_marked = False
    class DataMixin:
        def _init_data(self, data): self._data_arg = data
        def resolve_df(self, store=None):
            import pandas as pd
            if isinstance(self._data_arg, pd.DataFrame):
                return self._data_arg
            if store is not None:
                return store.resolve(self._data_arg)
            raise RuntimeError(f"No store to resolve key {self._data_arg!r}")
        @property
        def data_key(self): return self._data_arg if isinstance(self._data_arg, str) else None
        @property
        def has_local_data(self): return isinstance(self._data_arg, pd.DataFrame)
    _HAS_CORE = False

# ─────────────────────────────────────────────────────────────────────────────
#  Helpers (standalone, no Core dependency)
# ─────────────────────────────────────────────────────────────────────────────

def _is_vector_col(series: pd.Series) -> bool:
    sample = series.dropna()
    if len(sample) == 0:
        return False
    return isinstance(sample.iloc[0], (list, np.ndarray))


def _col_analysis(df: pd.DataFrame) -> dict:
    scalar_num, scalar_cat, vector = [], [], []
    for col in df.columns:
        if _is_vector_col(df[col]):
            vector.append(col)
        elif pd.api.types.is_numeric_dtype(df[col]):
            scalar_num.append(col)
        else:
            scalar_cat.append(col)
    return {
        "scalar_num": scalar_num,
        "scalar_cat": scalar_cat,
        "vector":     vector,
        "scalar":     scalar_num + scalar_cat,
        "all":        list(df.columns),
    }


def _safe_json(v):
    if isinstance(v, float) and np.isnan(v):
        return None
    if isinstance(v, np.integer):
        return int(v)
    if isinstance(v, np.floating):
        return float(v)
    if isinstance(v, np.ndarray):
        return v.tolist()
    return v


def _lambda_to_srgb(lam: float) -> str:
    l = lam
    if   l < 380: r, g, b = 0, 0, 0
    elif l < 440: r, g, b = -(l-440)/60, 0, 1
    elif l < 490: r, g, b = 0, (l-440)/50, 1
    elif l < 510: r, g, b = 0, 1, -(l-510)/20
    elif l < 580: r, g, b = (l-510)/70, 1, 0
    elif l < 645: r, g, b = 1, -(l-645)/65, 0
    elif l <= 700: r, g, b = 1, 0, 0
    else:          r, g, b = 0, 0, 0
    r, g, b = (max(0, min(1, x)) ** 0.8 for x in (r, g, b))
    return "#{:02x}{:02x}{:02x}".format(int(r*255), int(g*255), int(b*255))


# ─────────────────────────────────────────────────────────────────────────────
#  Static assets (CSS + JS) — inlined at class definition time
#  Can be refreshed at runtime via GraphBuilderV2.load_from_files(base_dir)
# ─────────────────────────────────────────────────────────────────────────────

_HERE = Path(__file__).parent

def _try_read(path: Path) -> str | None:
    try:
        return path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return None


def _load_assets(base: Path) -> tuple[str, str, dict]:
    """Load CSS, JS modules, and HTML partials from a graph_builder/ directory."""
    css = (base / "css" / "styles.css").read_text(encoding="utf-8")

    js_order = [
        base / "js" / "core.js",
        base / "js" / "init.js",
        base / "js" / "filters.js",
        base / "js" / "axes_modal.js",
        base / "js" / "table.js",
        base / "js" / "charts" / "scalar.js",
        base / "js" / "charts" / "kde2d.js",
        base / "js" / "charts" / "vector.js",
        base / "js" / "charts" / "cie.js",
        base / "js" / "charts" / "facet.js",
    ]
    js = "\n\n".join(p.read_text(encoding="utf-8") for p in js_order)

    html_parts = {
        "table_view":   (base / "html" / "table_view.html").read_text(encoding="utf-8"),
        "scalar_panel": (base / "html" / "sidebar" / "scalar_panel.html").read_text(encoding="utf-8"),
        "vector_panel": (base / "html" / "sidebar" / "vector_panel.html").read_text(encoding="utf-8"),
        "cie_panel":    (base / "html" / "sidebar" / "cie_panel.html").read_text(encoding="utf-8"),
        "facet_panel":  (base / "html" / "sidebar" / "facet_panel.html").read_text(encoding="utf-8"),
        "filters":      (base / "html" / "sidebar" / "filters.html").read_text(encoding="utf-8"),
        "canvas":       (base / "html" / "canvas.html").read_text(encoding="utf-8"),
        "axes_modal":   (base / "html" / "modals" / "axes_modal.html").read_text(encoding="utf-8"),
    }
    return css, js, html_parts


# Try to load from adjacent graph_builder/ directory
_GB_DIR = _HERE / "graph_builder"
if _GB_DIR.exists():
    _CSS, _JS_MODULES, _HTML_PARTS = _load_assets(_GB_DIR)
else:
    # Fallback: empty — render() will raise a clear error
    _CSS, _JS_MODULES, _HTML_PARTS = "", "", {}


_CIE_CONSTANTS = (
    "var LOCUS_X = [0.175596,0.172787,0.170806,0.170085,0.160343,0.146958,"
    "0.139149,0.133536,0.126688,0.11583,0.109616,0.099146,0.09131,0.07813,"
    "0.068717,0.054675,0.040763,0.027497,0.01627,0.008169,0.004876,0.003983,"
    "0.003859,0.004646,0.007988,0.01387,0.022244,0.027273,0.03282,0.038851,"
    "0.045327,0.052175,0.059323,0.066713,0.074299,0.089937,0.114155,0.138695,"
    "0.154714,0.192865,0.229607,0.26576,0.301588,0.337346,0.373083,0.408717,"
    "0.444043,0.478755,0.512467,0.544767,0.575132,0.602914,0.627018,0.648215,"
    "0.665746,0.680061,0.691487,0.700589,0.707901,0.714015,0.719017,0.723016,"
    "0.734674,0.175596];\n"
    "var LOCUS_Y = [0.005295,0.0048,0.005472,0.005976,0.014496,0.026643,"
    "0.035211,0.042704,0.053441,0.073601,0.086866,0.112037,0.132737,0.170464,"
    "0.200773,0.254155,0.317049,0.387997,0.463035,0.538504,0.587196,0.610526,"
    "0.654897,0.67597,0.715407,0.750246,0.779682,0.792153,0.802971,0.812059,"
    "0.81943,0.8252,0.82946,0.832306,0.833833,0.833316,0.826231,0.814796,"
    "0.805884,0.781648,0.754347,0.724342,0.692326,0.658867,0.62447,0.589626,"
    "0.554734,0.520222,0.486611,0.454454,0.424252,0.396516,0.37251,0.351413,"
    "0.334028,0.319765,0.308359,0.299317,0.292044,0.285945,0.280951,0.276964,"
    "0.265326,0.005295];\n"
    "var PLANCK_X=[0.2400,0.2738,0.3221,0.3805,0.4406,0.4939,0.5253,0.5289,0.5289];\n"
    "var PLANCK_Y=[0.2340,0.2832,0.3318,0.3769,0.4030,0.4082,0.4128,0.4154,0.4140];"
)


# ─────────────────────────────────────────────────────────────────────────────
#  GraphBuilderV2 Block
# ─────────────────────────────────────────────────────────────────────────────

class GraphBuilderV2(DataMixin, Block):
    """
    Graph Builder v2 interactif — 5 modes (Scalaire, Vectoriel, CIE, Facet, Table).

    Compatible avec le système Block de report_builder + DataStore :
        # df direct (comportement original)
        tab.add(GraphBuilderV2(df, exclude_cols=["Spectra"]))

        # clé DataStore (0 octets de données supplémentaires)
        report.data.register("main", df)
        tab.add(GraphBuilderV2("main", exclude_cols=["Spectra"]))

    Peut aussi être placé directement dans TabView (sans passer par Tab) :
        report.add(TabView([gb]))   # render_content() + panel_css_class gérés

    Params
    ------
    data            : pd.DataFrame direct OU clé str vers le DataStore
    exclude_cols    : colonnes à exclure de la sérialisation
    max_vector_pts  : downsampling des vecteurs (défaut 50)
    title           : titre affiché dans le header (défaut "Graph Builder v2")
    """

    needs_plotly = True   # signals report_builder to include Plotly CDN

    def __init__(
        self,
        data:            "DataArg",
        exclude_cols:    list[str] | None = None,
        max_vector_pts:  int = 50,
        title:           str = "Graph Builder v2",
    ):
        self._init_data(data)
        self.exclude_cols   = set(exclude_cols or [])
        self.max_vector_pts = max_vector_pts
        self.title          = title

    # ── Assets reload (call once per session if you edit the JS files) ─────────

    @classmethod
    def load_from_files(cls, base_dir: str | Path | None = None) -> None:
        """Reload CSS/JS/HTML from disk. Call after editing JS files."""
        global _CSS, _JS_MODULES, _HTML_PARTS
        base = Path(base_dir) if base_dir else _GB_DIR
        _CSS, _JS_MODULES, _HTML_PARTS = _load_assets(base)

    # ── Serialization ─────────────────────────────────────────────────────────

    def _serialize(self, df: pd.DataFrame, full: bool = False) -> str:
        """
        Serialize df to JSON.
        full=True  → include all vector cols (for CIE / spectra)
        full=False → exclude heavy cols + downsample vectors
        """
        exclude = self.exclude_cols if not full else set()
        df = df.drop(
            columns=[c for c in exclude if c in df.columns],
            errors="ignore",
        )
        records = []
        for _, row in df.iterrows():
            rec: dict = {}
            for col in df.columns:
                if col in exclude:
                    continue
                v = row[col]
                if isinstance(v, (list, np.ndarray)):
                    arr = list(v)
                    if not full and len(arr) > self.max_vector_pts:
                        step = max(1, len(arr) // self.max_vector_pts)
                        arr = arr[::step]
                    rec[col] = [_safe_json(x) for x in arr]
                elif isinstance(v, float) and np.isnan(v):
                    rec[col] = None
                else:
                    rec[col] = _safe_json(v)
            records.append(rec)
        return json.dumps(records)

    def _build_lambda_colorscale(self) -> str:
        steps = list(range(400, 701, 5))
        scale = [[i / (len(steps) - 1), _lambda_to_srgb(lam)] for i, lam in enumerate(steps)]
        return json.dumps(scale)

    # ── HTML helpers ──────────────────────────────────────────────────────────

    def _statsbar(self, df: pd.DataFrame, cols: dict, len_vector: int) -> str:
        return (
            '<div class="gb-statsbar">'
            f'<span class="gb-stat">LEDs: <strong>{len(df)}</strong></span>'
            f'<span class="gb-stat">Scalar num: <strong>{len(cols["scalar_num"])}</strong></span>'
            f'<span class="gb-stat">Vectoriel: <strong>{len_vector}</strong></span>'
            "</div>"
        )

    @staticmethod
    def _header(title: str) -> str:
        return (
            '<header class="gb-header">'
            f'<span class="gb-logo">ALEDIA</span>'
            '<div class="gb-sep"></div>'
            f'<span class="gb-title">{title}</span>'
            '<div class="gb-mode-tabs">'
            '<button class="gb-mode-tab active" id="tab-scalar" onclick="switchMode(\'scalar\')">◈ Scalaire</button>'
            '<button class="gb-mode-tab" id="tab-vector" onclick="switchMode(\'vector\')">∿ Vectoriel</button>'
            '<button class="gb-mode-tab" id="tab-cie" onclick="switchMode(\'cie\')">◉ CIE 1931</button>'
            '<button class="gb-mode-tab" id="tab-facet" onclick="switchMode(\'facet\')">⊞ Facet Grid</button>'
            '<button class="gb-mode-tab" id="tab-table" onclick="switchMode(\'table\')">⊟ Table</button>'
            "</div>"
            "</header>"
        )

    @staticmethod
    def _build_btn() -> str:
        return (
            '<div class="gb-build-wrap">'
            '  <button class="gb-build-btn" onclick="build()">'
            '    <svg viewBox="0 0 16 16" width="12" height="12" fill="white"><path d="M6 3l8 5-8 5V3z"/></svg>'
            "    Construire"
            "  </button>"
            "</div>"
        )

    # ── Render ────────────────────────────────────────────────────────────────

    def render_standalone(self, store=None) -> str:
        if not _HTML_PARTS:
            raise RuntimeError(
                "GraphBuilderV2: HTML partials not loaded. "
                f"Expected graph_builder/ directory next to {__file__}. "
                "Or call GraphBuilderV2.load_from_files('/path/to/graph_builder/')."
            )

        df = self.resolve_df(store)

        cols       = _col_analysis(df)
        data_json       = self._serialize(df, full=False)
        data_full_json  = self._serialize(df, full=True)
        wafers_json     = json.dumps(
            sorted(df["wafername"].unique().tolist())
            if "wafername" in df.columns else []
        )
        scalar_num_json = json.dumps(cols["scalar_num"])
        scalar_cat_json = json.dumps(cols["scalar_cat"])
        vector_json     = json.dumps([c for c in cols["vector"] if c not in self.exclude_cols])
        lambda_cs       = self._build_lambda_colorscale()
        len_vector      = len([c for c in cols["vector"] if c not in self.exclude_cols])

        # ── Assemble HTML ────────────────────────────────────────────────────
        parts = _HTML_PARTS

        html = "\n".join([
            # ── <head> inline ────────────────────────────────────────────────
            "<!DOCTYPE html>",
            "<html lang='fr'>",
            "<head>",
            "<meta charset='UTF-8'>",
            "<meta name='viewport' content='width=device-width,initial-scale=1'>",
            f"<title>{self.title}</title>",
            "<link rel='preconnect' href='https://fonts.googleapis.com'>",
            "<link href='https://fonts.googleapis.com/css2?family=Syne:wght@400;600;700;800"
            "&family=DM+Sans:wght@300;400;500"
            "&family=IBM+Plex+Mono:wght@300;400;500&display=swap' rel='stylesheet'>",
            "<script src='https://cdn.plot.ly/plotly-2.35.2.min.js'></script>",
            "<style>",
            _CSS,
            "</style>",
            "</head>",
            "<body>",
            '<div class="gb-app gb-standalone">',

            # ── Header + mode tabs ───────────────────────────────────────────
            self._header(self.title),

            # ── Table view (full-width tab) ──────────────────────────────────
            parts["table_view"],

            # ── Main layout ──────────────────────────────────────────────────
            '<div class="gb-main">',

            # Sidebar
            '<div class="gb-sidebar" id="sidebar">',
            self._statsbar(df, cols, len_vector),
            parts["scalar_panel"],
            parts["vector_panel"],
            parts["cie_panel"],
            parts["facet_panel"],
            parts["filters"],
            self._build_btn(),
            "</div><!-- /sidebar -->",

            # Canvas
            parts["canvas"],

            "</div><!-- /gb-main -->",

            # Axes modal
            parts["axes_modal"],
            "</div><!-- /gb-app -->",

            # ── Script block ─────────────────────────────────────────────────
            "<script>",

            # 1. Data (injected from Python)
            f"var DATA       = {data_json};",
            f"var DATA_FULL  = {data_full_json};",
            f"var WAFERS     = {wafers_json};",
            f"var SCALAR_NUM = {scalar_num_json};",
            f"var SCALAR_CAT = {scalar_cat_json};",
            f"var VECTORS    = {vector_json};",
            f"var LAMBDA_CS  = {lambda_cs};",

            # 2. CIE static constants
            _CIE_CONSTANTS,

            # 3. JS modules (core → init → filters → modal → table → charts)
            _JS_MODULES,

            "</script>",
            "</body>",
            "</html>",
        ])

        return html

    # Classe CSS additionnelle pour le panneau dans TabView (quand placé directement)
    panel_css_class = "gb-panel"

    def render(self, store=None) -> str:
        """Conforme contrat Block — délègue à render_fragment pour l'embedding."""
        return self.render_fragment(store=store)

    def render_content(self, store=None) -> str:
        """Protocole Tab-item : TabView appelle render_content() sur tous ses items."""
        return self.render_fragment(store=store)

    def render_fragment(self, store=None) -> str:
        """
        Render just the <div>+<script> fragment (no <html>/<head>/<body>),
        for embedding inside an existing report_builder page that already
        has Plotly + fonts loaded.
        """
        if not _HTML_PARTS:
            raise RuntimeError("GraphBuilderV2: HTML partials not loaded.")

        df = self.resolve_df(store)

        cols            = _col_analysis(df)
        wafers_json     = json.dumps(
            sorted(df["wafername"].unique().tolist())
            if "wafername" in df.columns else []
        )
        scalar_num_json = json.dumps(cols["scalar_num"])
        scalar_cat_json = json.dumps(cols["scalar_cat"])
        vector_json     = json.dumps([c for c in cols["vector"] if c not in self.exclude_cols])
        lambda_cs       = self._build_lambda_colorscale()
        len_vector      = len([c for c in cols["vector"] if c not in self.exclude_cols])

        if self.has_local_data:
            data_init = (f"var DATA      = {self._serialize(df, full=False)};\n"
                         f"var DATA_FULL = {self._serialize(df, full=True)};")
        else:
            key = self._data_arg
            mvp = self.max_vector_pts
            vec_cols_json = json.dumps([c for c in cols["vector"] if c not in self.exclude_cols])
            data_init = (
                f"var DATA_FULL=(window.__DATA_STORE__||{{}})[{json.dumps(key)}]||[];"
                f"var DATA=DATA_FULL;"
                f"(function(){{if({mvp}>0){{"
                f"DATA=DATA_FULL.map(function(r){{"
                f"var c=Object.assign({{}},r);"
                f"{vec_cols_json}.forEach(function(k){{"
                f"if(Array.isArray(c[k]))c[k]=c[k].slice(0,{mvp});"
                f"}});"
                f"return c;}});"
                f"}}}})();"
            )

        parts = _HTML_PARTS

        return "\n".join([
            f"<!-- GraphBuilderV2 — {len(df)} LEDs -->",
            "<style>", _CSS, "</style>",
            # Override the standalone html/body rules so the outer report page keeps scrolling.
            # Also re-enforce .gb-main display:flex so V3's global .gb-main{display:none} can't hide it.
            "<style>html,body{height:auto!important;overflow:auto!important;}"
            ".gb-app.gb-embedded .gb-main{display:flex!important;flex:1 1 auto!important;"
            "height:100%!important;min-height:0!important;overflow:hidden!important;}</style>",
            '<div class="gb-app gb-embedded">',
            self._header(self.title),
            parts["table_view"],
            '<div class="gb-main">',
            '<div class="gb-sidebar" id="sidebar">',
            self._statsbar(df, cols, len_vector),
            parts["scalar_panel"],
            parts["vector_panel"],
            parts["cie_panel"],
            parts["facet_panel"],
            parts["filters"],
            self._build_btn(),
            "</div>",
            parts["canvas"],
            "</div>",
            parts["axes_modal"],
            "</div><!-- /gb-app -->",
            "<script>",
            # Height-fit: keep the embedded app filling the viewport below its top offset
            "(function(){function fit(){document.querySelectorAll('.gb-app.gb-embedded').forEach(function(el){var r=el.getBoundingClientRect();if(r.width===0&&r.height===0)return;var h=Math.max(420,window.innerHeight-r.top-12);el.style.height=h+'px';});}window.addEventListener('resize',fit);requestAnimationFrame(fit);})();",
            data_init,
            f"var WAFERS     = {wafers_json};",
            f"var SCALAR_NUM = {scalar_num_json};",
            f"var SCALAR_CAT = {scalar_cat_json};",
            f"var VECTORS    = {vector_json};",
            f"var LAMBDA_CS  = {lambda_cs};",
            _CIE_CONSTANTS,
            _JS_MODULES,
            "</script>",
        ])