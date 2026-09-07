"""
build.py
--------
Entry point for Graph Builder v2.
Loads data, reads HTML/JS/CSS partials, assembles a single self-contained HTML file.

Usage:
    python build.py                          # fake data → graph_builder_v2.html
    python build.py --out my_report.html     # custom output path
    python build.py --data path/to/data.py   # custom data module (must expose make_dataframe())

Architecture:
    html/layout.html          ← skeleton with __SLOT_xxx__ and <!-- __JS_xxx__ --> markers
    html/sidebar/*.html       ← sidebar panel fragments
    html/table_view.html      ← full-width table tab
    html/canvas.html          ← plot area + status bar
    html/modals/axes_modal.html
    css/styles.css            ← all CSS
    js/core.js                ← globals, palette, mergePrefs, gbReact
    js/init.js                ← selects init, symbol picker, mode switch
    js/filters.js             ← filter UI + applyFilters
    js/axes_modal.js          ← axes config modal
    js/table.js               ← table engine
    js/charts/scalar.js       ← buildScalar
    js/charts/kde2d.js        ← buildKDE2D
    js/charts/vector.js       ← buildVector + ridge plot
    js/charts/cie.js          ← buildCIE
    js/charts/facet.js        ← buildFacet
"""

import argparse
import importlib.util
import sys
from pathlib import Path

HERE = Path(__file__).parent


# ─────────────────────────────────────────────────────────────────────────────
#  Read helpers
# ─────────────────────────────────────────────────────────────────────────────

def read(rel: str) -> str:
    """Read a file relative to the graph_builder/ root."""
    return (HERE / rel).read_text(encoding="utf-8")


def read_js(*parts: str) -> str:
    """Read a JS file and wrap in a section comment."""
    path = Path(*parts)
    src = (HERE / path).read_text(encoding="utf-8")
    name = path.name
    bar = "─" * (60 - len(name))
    return f"// ── {name} {bar}\n{src}"


# ─────────────────────────────────────────────────────────────────────────────
#  CIE constants (static, not generated from data)
# ─────────────────────────────────────────────────────────────────────────────

CIE_CONSTANTS = """var LOCUS_X = [0.175596,0.172787,0.170806,0.170085,0.160343,0.146958,0.139149,0.133536,
               0.126688,0.11583,0.109616,0.099146,0.09131,0.07813,0.068717,0.054675,
               0.040763,0.027497,0.01627,0.008169,0.004876,0.003983,0.003859,0.004646,
               0.007988,0.01387,0.022244,0.027273,0.03282,0.038851,0.045327,0.052175,
               0.059323,0.066713,0.074299,0.089937,0.114155,0.138695,0.154714,0.192865,
               0.229607,0.26576,0.301588,0.337346,0.373083,0.408717,0.444043,0.478755,
               0.512467,0.544767,0.575132,0.602914,0.627018,0.648215,0.665746,0.680061,
               0.691487,0.700589,0.707901,0.714015,0.719017,0.723016,0.734674,0.175596];
var LOCUS_Y = [0.005295,0.0048,0.005472,0.005976,0.014496,0.026643,0.035211,0.042704,
               0.053441,0.073601,0.086866,0.112037,0.132737,0.170464,0.200773,0.254155,
               0.317049,0.387997,0.463035,0.538504,0.587196,0.610526,0.654897,0.67597,
               0.715407,0.750246,0.779682,0.792153,0.802971,0.812059,0.81943,0.8252,
               0.82946,0.832306,0.833833,0.833316,0.826231,0.814796,0.805884,0.781648,
               0.754347,0.724342,0.692326,0.658867,0.62447,0.589626,0.554734,0.520222,
               0.486611,0.454454,0.424252,0.396516,0.37251,0.351413,0.334028,0.319765,
               0.308359,0.299317,0.292044,0.285945,0.280951,0.276964,0.265326,0.005295];
var PLANCK_X=[0.2400,0.2738,0.3221,0.3805,0.4406,0.4939,0.5253,0.5289,0.5289];
var PLANCK_Y=[0.2340,0.2832,0.3318,0.3769,0.4030,0.4082,0.4128,0.4154,0.4140];"""


# ─────────────────────────────────────────────────────────────────────────────
#  Assembler
# ─────────────────────────────────────────────────────────────────────────────

def assemble(data_vars: dict) -> str:
    """
    Read all partials, inject data + fragments, return the final HTML string.
    data_vars must contain:
        data_json, data_full_json, wafers_json,
        scalar_num_json, scalar_cat_json, vector_json,
        lambda_colorscale, len_df, len_scalar_num, len_vector
    """
    html = read("html/layout.html")

    # ── 1. CSS ────────────────────────────────────────────────────────────────
    html = html.replace("<!-- __CSS__ -->", read("css/styles.css"))

    # ── 2. HTML slots ─────────────────────────────────────────────────────────
    slot_map = {
        "__SLOT_HEADER__":       _build_header(),
        "__SLOT_TABLE_VIEW__":   read("html/table_view.html"),
        "__SLOT_STATSBAR__":     _statsbar(data_vars),
        "__SLOT_PANEL_SCALAR__": read("html/sidebar/scalar_panel.html"),
        "__SLOT_PANEL_VECTOR__": read("html/sidebar/vector_panel.html"),
        "__SLOT_PANEL_CIE__":    read("html/sidebar/cie_panel.html"),
        "__SLOT_PANEL_FACET__":  read("html/sidebar/facet_panel.html"),
        "__SLOT_FILTERS__":      read("html/sidebar/filters.html"),
        "__SLOT_CANVAS__":       read("html/canvas.html"),
        "__SLOT_AXES_MODAL__":   read("html/modals/axes_modal.html"),
        "__SLOT_CIE_CONSTANTS__": CIE_CONSTANTS,
    }
    for slot, fragment in slot_map.items():
        html = html.replace(f"<!-- {slot} -->", fragment)
        html = html.replace(slot, fragment)         # also handle non-comment form

    # ── 3. Data placeholders ──────────────────────────────────────────────────
    for key, val in data_vars.items():
        html = html.replace(f"__{key}__", str(val))

    # ── 4. JS modules ─────────────────────────────────────────────────────────
    js_slots = {
        "<!-- __JS_CORE__ -->":       read_js("js/core.js"),
        "<!-- __JS_INIT__ -->":       read_js("js/init.js"),
        "<!-- __JS_FILTERS__ -->":    read_js("js/filters.js"),
        "<!-- __JS_AXES_MODAL__ -->": read_js("js/axes_modal.js"),
        "<!-- __JS_TABLE__ -->":      read_js("js/table.js"),
        "<!-- __JS_HELPERS__ -->":    "",   # already included in core.js
        "<!-- __JS_SCALAR__ -->":     read_js("js/charts/scalar.js"),
        "<!-- __JS_KDE2D__ -->":      read_js("js/charts/kde2d.js"),
        "<!-- __JS_VECTOR__ -->":     read_js("js/charts/vector.js"),
        "<!-- __JS_CIE__ -->":        read_js("js/charts/cie.js"),
        "<!-- __JS_FACET__ -->":      read_js("js/charts/facet.js"),
    }
    for slot, js_src in js_slots.items():
        html = html.replace(slot, js_src)

    return html


# ─────────────────────────────────────────────────────────────────────────────
#  Small HTML fragments generated in Python (cleaner than storing in files)
# ─────────────────────────────────────────────────────────────────────────────

def _build_header() -> str:
    return """<header class="gb-header">
  <span class="gb-logo">ALEDIA</span>
  <div class="gb-sep"></div>
  <span class="gb-title">Graph Builder v2</span>
  <div class="gb-mode-tabs">
    <button class="gb-mode-tab active" id="tab-scalar" onclick="switchMode('scalar')">◈ Scalaire</button>
    <button class="gb-mode-tab" id="tab-vector" onclick="switchMode('vector')">∿ Vectoriel</button>
    <button class="gb-mode-tab" id="tab-cie" onclick="switchMode('cie')">◉ CIE 1931</button>
    <button class="gb-mode-tab" id="tab-facet" onclick="switchMode('facet')">⊞ Facet Grid</button>
    <button class="gb-mode-tab" id="tab-table" onclick="switchMode('table')">⊟ Table</button>
  </div>
</header>"""


def _statsbar(data_vars: dict) -> str:
    return f"""<div class="gb-statsbar">
  <span class="gb-stat">LEDs: <strong>{data_vars['len_df']}</strong></span>
  <span class="gb-stat">Scalar num: <strong>{data_vars['len_scalar_num']}</strong></span>
  <span class="gb-stat">Vectoriel: <strong>{data_vars['len_vector']}</strong></span>
</div>"""



# ─────────────────────────────────────────────────────────────────────────────
#  Validation
# ─────────────────────────────────────────────────────────────────────────────

def validate(html: str) -> bool:
    import re
    ok = True
    js_match = re.search(r'<script>(.*?)</script>', html, re.DOTALL)
    if not js_match:
        print("  ✗ No <script> block found")
        return False
    js = js_match.group(1)
    lines = js.splitlines()

    # Brace balance
    depth = 0
    for line in lines:
        for ch in line:
            if ch == '{': depth += 1
            elif ch == '}': depth -= 1
    if depth != 0:
        print(f"  ✗ JS brace imbalance: {depth:+d}")
        ok = False
    else:
        print(f"  ✓ JS braces balanced")

    # Unreplaced placeholders
    remaining = re.findall(r'__[a-zA-Z_]+__', html)
    if remaining:
        print(f"  ✗ Unreplaced placeholders: {set(remaining)}")
        ok = False
    else:
        print(f"  ✓ All placeholders replaced")

    # Unclosed string check (simplified)
    probs = []
    for i, line in enumerate(lines):
        if line.strip().startswith('//'): continue
        in_dq = False
        sq = 0
        for j, ch in enumerate(line):
            if ch == '"' and (j == 0 or line[j-1] != '\\'): in_dq = not in_dq
            if ch == "'" and not in_dq and (j == 0 or line[j-1] != '\\'): sq += 1
        if sq % 2 != 0:
            probs.append(i + 1)
    if probs:
        print(f"  ✗ Unclosed strings on lines: {probs[:5]}")
        ok = False
    else:
        print(f"  ✓ No unclosed strings")

    return ok


# ─────────────────────────────────────────────────────────────────────────────
#  Main
# ─────────────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Graph Builder v2 — HTML assembler")
    parser.add_argument("--out",  default="/mnt/user-data/outputs/graph_builder_v2.html",
                        help="Output HTML path")
    parser.add_argument("--data", default=None,
                        help="Custom data module path (must expose make_dataframe())")
    parser.add_argument("--no-validate", action="store_true",
                        help="Skip JS validation")
    args = parser.parse_args()

    # ── Load data ─────────────────────────────────────────────────────────────
    if args.data:
        spec = importlib.util.spec_from_file_location("custom_data", args.data)
        mod  = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        df, cols, data_vars = mod.make_dataframe()
    else:
        sys.path.insert(0, str(HERE))
        from data.fake_leds import make_dataframe
        df, cols, data_vars = make_dataframe()

    print(f"Dataset: {len(df)} LEDs · {df['wafername'].nunique()} wafers")

    # ── Assemble ──────────────────────────────────────────────────────────────
    print("Assembling...")
    html = assemble(data_vars)

    # ── Validate ──────────────────────────────────────────────────────────────
    if not args.no_validate:
        print("Validating:")
        validate(html)

    # ── Write ─────────────────────────────────────────────────────────────────
    out = Path(args.out)
    out.write_text(html, encoding="utf-8")
    sz = len(html) // 1024
    print(f"✓  {out}  ({sz} KB)")


if __name__ == "__main__":
    main()
