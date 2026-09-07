"""
graph_builder_v3_block.py
--------------------------
GraphBuilderV3 — Block report_builder autonome.

Porte exactement l'UX de app/pages/graph_builder/ dans un HTML self-contained.
  • Pas de serveur, pas de DAG à exécuter
  • Glisser-déposer des colonnes sur X / Y / Y2 / Couleur / Taille / Tooltip
  • Système d'extensions (scatter, line, bar, boxplot, histogram, wafer_map, curves, linked_views)
  • Filtres avancés (histogram drag + checkbox, persistés en localStorage)
  • Tableau intégré avec stats par colonne
  • Config inline (titres, polices, grille, log, opacité…)
  • Vues sauvegardées en localStorage
  • Support multi-datasets

Usage:
    from report_builder.core.graph_builder_v3.graph_builder_v3_block import GraphBuilderV3

    # DataFrame unique
    block = GraphBuilderV3(df, title="Mon Analyse")
    html  = block.render()           # HTML complet standalone

    # Plusieurs datasets
    block = GraphBuilderV3({'mesures': df1, 'spectres': df2}, title="Dashboard")
    html  = block.render()

    # Embedding dans un rapport existant (Plotly déjà chargé)
    frag  = block.render_fragment()
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Union

import numpy as np
import pandas as pd

# ── Paths ──────────────────────────────────────────────────────────────────────

_HERE       = Path(__file__).parent
# JS/CSS du Graph Builder — vendorisés depuis app/pages/graph_builder/static
# de lumiere-suite lors de l'extraction du report builder en dépôt standalone.
_APP_STATIC = _HERE / "static"
_ADAPTER    = _HERE / "_gb3_standalone.js"


def _read(p: Path) -> str:
    return p.read_text(encoding="utf-8")


def _app_js(*parts: str) -> str:
    return _read(_APP_STATIC.joinpath(*parts))


def _ext_js(filename: str) -> str:
    return _read(_APP_STATIC / "extensions" / filename)


def _read_css() -> str:
    return _read(_APP_STATIC / "graph_builder.css")


def _read_adapter() -> str:
    return _read(_ADAPTER)


# ── Data helpers ───────────────────────────────────────────────────────────────

def _safe_val(v):
    if isinstance(v, float) and (np.isnan(v) or np.isinf(v)):
        return None
    if isinstance(v, np.integer):
        return int(v)
    if isinstance(v, np.floating):
        return float(v)
    if isinstance(v, np.ndarray):
        return [_safe_val(x) for x in v.tolist()]
    if isinstance(v, (list, tuple)):
        return [_safe_val(x) for x in v]
    return v


def _df_to_records(
    df: pd.DataFrame,
    exclude: set,
    max_vector_pts: int,
) -> list[dict]:
    """Sérialise un DataFrame en liste de records JSON."""
    cols = [c for c in df.columns if c not in exclude]
    rows = []
    for _, row in df.iterrows():
        rec: dict = {}
        for col in cols:
            v = row[col]
            if isinstance(v, (list, np.ndarray)):
                arr = list(v)
                if max_vector_pts and len(arr) > max_vector_pts:
                    step = max(1, len(arr) // max_vector_pts)
                    arr  = arr[::step]
                rec[col] = [_safe_val(x) for x in arr]
            elif isinstance(v, float) and (np.isnan(v) or np.isinf(v)):
                rec[col] = None
            else:
                rec[col] = _safe_val(v)
        rows.append(rec)
    return rows


def _build_datasets(
    data: Union[pd.DataFrame, dict],
    exclude: set,
    max_vector_pts: int,
) -> dict:
    """Retourne {nom_dataset: [records]} depuis un DataFrame ou un dict."""
    if isinstance(data, pd.DataFrame):
        return {"main": _df_to_records(data, exclude, max_vector_pts)}
    if isinstance(data, dict):
        out = {}
        for k, v in data.items():
            if isinstance(v, pd.DataFrame):
                out[str(k)] = _df_to_records(v, exclude, max_vector_pts)
        return out
    raise TypeError(f"Expected DataFrame or dict[str, DataFrame], got {type(data)}")


# ── HTML template ──────────────────────────────────────────────────────────────

_HTML_TEMPLATE = """\
<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="UTF-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>__TITLE__</title>
<script src="https://cdn.plot.ly/plotly-2.32.0.min.js"></script>
<link href="https://fonts.googleapis.com/css2?family=Syne:wght@400;600;700;800&family=IBM+Plex+Mono:wght@400;500&family=DM+Sans:wght@300;400;500;600;700&display=swap" rel="stylesheet">
<style>
:root{
  --gb-navy:#08152f;--gb-muted:#7a8499;
  --gb-body:'DM Sans',sans-serif;--gb-mono:'IBM Plex Mono',monospace;
  --navy:#071a3d;--blue:#0A2463;--gold:#D4AF37;--gold2:#f0d47d;
  --ink:#102039;--muted:#6b7891;--bg:#f4f6fb;--panel:#fff;
  --line:rgba(10,36,99,.10);--line2:rgba(10,36,99,.16);--soft:#eef2fa;
  --ok:#10b981;--err:#ef4444;
  --fm:'IBM Plex Mono',monospace;--fs:'Syne',sans-serif;--fd:'DM Sans',sans-serif;
  --top:48px;
}
__CSS__
</style>
</head>
<body class="gb-runtime">

<!-- ── Topbar (standalone : pas de Run, pas de Params, pas d'Asset) ── -->
<header class="gbr-topbar">
  <div class="gbr-topbar-left">
    <a href="#" style="display:flex;align-items:center;gap:8px;text-decoration:none;color:#fff;font-family:var(--fs);font-weight:800;letter-spacing:.08em;font-size:15px;padding:4px 8px;border-radius:7px"
       onmouseenter="this.style.background='rgba(255,255,255,.08)'" onmouseleave="this.style.background='transparent'">
      <span style="width:18px;height:18px;border-radius:50%;background:radial-gradient(circle at 35% 30%,#fff8d6,#D4AF37 58%,#9a6d17);box-shadow:0 0 14px rgba(212,175,55,.5);flex-shrink:0"></span>
      <span>LUMI<span style="color:#D4AF37">&Egrave;</span>RE<small style="font-size:7px;margin-left:5px;color:rgba(255,255,255,.36);letter-spacing:.22em">SUITE</small></span>
    </a>
    <span class="gbr-sep">›</span>
    <span class="gbr-crumb current" id="gb3-title">Graph Builder V3</span>
    <span class="gbr-source-pill" id="source-pill"></span>
  </div>
  <div class="gbr-topbar-right">
    <span class="gbr-tbtn-wrap">
      <button class="gbr-tbtn" id="btn-open-filters">⊟ Filtres</button>
      <span class="gbr-filter-badge" id="filter-badge" style="display:none">0</span>
    </span>
    <button class="gbr-tbtn" id="btn-export-csv">⬇ CSV</button>
    <button class="gbr-tbtn" id="btn-open-views">📋 Vues</button>
  </div>
</header>

<!-- ── Type strip ────────────────────────────────────────────────────── -->
<nav class="gbr-type-strip" id="type-strip"></nav>

<!-- ── Workspace ─────────────────────────────────────────────────────── -->
<div class="gbr-workspace">

  <!-- Colonne palette -->
  <aside class="gbr-col-panel">
    <div class="gbr-col-top">
      <div class="gbr-col-ds-wrap">
        <div class="gbr-col-label">Dataset</div>
        <select class="gbr-col-select" id="dataset-select"></select>
        <div class="gbr-col-meta" id="dataset-meta">—</div>
      </div>
      <input class="gbr-col-search" id="col-search" type="text" placeholder="🔍 Filtrer colonnes…">
    </div>
    <div class="gbr-col-groups" id="col-groups">
      <div class="gbr-col-empty">Chargement…</div>
    </div>
    <button class="gbr-col-collapse-btn" id="btn-collapse-col" title="Réduire/étendre">‹</button>
  </aside>

  <!-- Centre -->
  <div class="gbr-center">

    <!-- Toolbar graphe -->
    <div class="gbr-chart-toolbar">
      <div class="gbr-chart-toolbar-left">
        <span class="gbr-toolbar-label" id="chart-row-count"></span>
      </div>
      <div class="gbr-chart-toolbar-right">
        <button class="gbr-tbtn sm" id="btn-refresh">↺ Refresh</button>
        <button class="gbr-tbtn sm" id="btn-toggle-table">▤ Table</button>
        <button class="gbr-tbtn sm" id="btn-toggle-config">⚙ Config</button>
        <button class="gbr-tbtn sm" id="btn-clear-axes">✕ Clear</button>
        <span class="gbr-hidden-info" id="hidden-info"></span>
        <button class="gbr-tbtn sm" id="btn-unhide-all" disabled>↩ Unhide</button>
      </div>
    </div>

    <!-- Graphe + config inline -->
    <div class="gbr-chart-config-row">

      <div class="gbr-chart-zone">

        <!-- Y · Graphe · Y2 -->
        <div class="gbr-yx-row">

          <div class="gbr-drop-y-vert" id="drop-y" data-channel="y">
            <span class="gbr-axis-y-label" id="y-label-text" title="Double-clic pour renommer l'axe Y" data-axis="y">Y</span>
            <div class="gbr-y-chips" id="slots-y">
              <span class="gbr-y-hint">Glisser ici</span>
            </div>
          </div>

          <div class="gbr-chart-canvas" id="chart-canvas">
            <div class="gbr-chart-empty" id="chart-empty">
              <div class="gbr-ce-icon">📊</div>
              <div class="gbr-ce-msg">Associez des colonnes aux axes X et Y</div>
            </div>
            <div id="chart-plot" style="width:100%;height:100%"></div>
          </div>

          <div class="gbr-drop-y2-vert" id="drop-y2" data-channel="y2">
            <span class="gbr-axis-y2-label" id="y2-label-text" title="Double-clic pour renommer l'axe Y2" data-axis="y2">Y2</span>
            <div class="gbr-y-chips" id="slots-y2">
              <span class="gbr-y-hint">Glisser</span>
            </div>
          </div>

        </div>

        <!-- X drop zone -->
        <div class="gbr-drop-x-horiz" id="drop-x" data-channel="x">
          <span class="gbr-axis-x-label" id="x-label-text" title="Double-clic pour renommer l'axe X" data-axis="x">X</span>
          <div class="gbr-x-chips" id="slots-x">
            <span class="gbr-slot-hint">Glisser une colonne — 2ème = facette</span>
          </div>
        </div>

        <!-- Canaux secondaires -->
        <div class="gbr-channels">
          <div class="gbr-channel" data-channel="color">
            <span class="gbr-ch-lbl">🎨 Couleur</span>
            <div class="gbr-ch-slot" id="slot-color"><span class="gbr-slot-hint">Glisser…</span></div>
          </div>
          <div class="gbr-channel" data-channel="size">
            <span class="gbr-ch-lbl">⊙ Taille</span>
            <div class="gbr-ch-slot" id="slot-size"><span class="gbr-slot-hint">Glisser…</span></div>
          </div>
          <div class="gbr-channel" data-channel="tooltip">
            <span class="gbr-ch-lbl">💬 Tooltip</span>
            <div class="gbr-ch-slot" id="slots-tooltip"><span class="gbr-slot-hint">Glisser…</span></div>
          </div>
        </div>

      </div>

      <!-- Config panel inline -->
      <aside class="gbr-config-side" id="config-panel">
        <div class="gbr-config-hd">
          <span>⚙ Configuration</span>
          <button id="config-close" class="gbr-modal-close">✕</button>
        </div>
        <div class="gbr-config-body" id="config-body"></div>
      </aside>

    </div>

    <!-- Splitter tableau / graphe -->
    <div class="gbr-table-splitter" id="table-splitter" style="display:none">
      <div class="gbr-splitter-handle"></div>
    </div>

    <!-- Tableau de données -->
    <div class="gbr-table-panel" id="table-panel">
      <div class="gbr-table-toolbar">
        <div class="gbr-table-toolbar-left">
          <span class="gbr-table-info" id="table-info">—</span>
          <select class="gbr-table-pagesize" id="table-pagesize">
            <option value="25">25 / page</option>
            <option value="50" selected>50 / page</option>
            <option value="100">100 / page</option>
            <option value="500">500 / page</option>
            <option value="0">Tout</option>
          </select>
        </div>
        <div class="gbr-table-toolbar-right">
          <input class="gbr-table-search" id="table-search" type="text" placeholder="🔍 Chercher…">
          <button class="gbr-tbtn sm" id="btn-table-col-toggle">⊞ Colonnes</button>
          <button class="gbr-tbtn sm" id="btn-table-clear-filters">✕ Filtres</button>
          <button class="gbr-tbtn sm" id="btn-close-table">✕</button>
        </div>
      </div>
      <div class="gbr-col-visibility-pop" id="col-visibility-pop" style="display:none"></div>
      <div class="gbr-table-scroll" id="table-scroll">
        <table class="gbr-data-table" id="data-table">
          <thead id="data-thead"></thead>
          <tbody id="data-tbody"></tbody>
        </table>
      </div>
      <div class="gbr-table-pagination" id="table-pagination"></div>
    </div>

  </div>
</div>

<!-- ── Modal : Vues sauvegardées ─────────────────────────────────────── -->
<div class="gbr-modal-backdrop" id="views-backdrop"></div>
<div class="gbr-modal-center" id="views-panel">
  <div class="gbr-modal-hd">
    <span>📋 Vues sauvegardées</span>
    <button class="gbr-modal-close" id="views-close">✕</button>
  </div>
  <div class="gbr-modal-body">
    <div class="gbr-views-actions">
      <button class="gbr-btn-save-view" id="btn-save-view">💾 Sauvegarder</button>
      <button class="gbr-btn-import-view" id="btn-import-view">⬆ Importer</button>
      <input type="file" id="import-view-input" accept=".json" style="display:none">
    </div>
    <div id="views-list" class="gbr-views-list"></div>
  </div>
</div>

<!-- ── Modal : Filtres ────────────────────────────────────────────────── -->
<div class="gbr-filter-backdrop" id="filter-modal-backdrop"></div>
<div class="gbr-filter-modal" id="filter-modal">
  <div class="gbr-fm-hd">
    <div class="gbr-fm-hd-left">
      <span class="gbr-fm-title">⊟ Filtres</span>
      <div class="gbr-logic-grp">
        <button class="gbr-logic-btn active" id="fm-logic-and">AND</button>
        <button class="gbr-logic-btn" id="fm-logic-or">OR</button>
      </div>
    </div>
    <div class="gbr-fm-hd-right">
      <button class="gbr-fm-save-btn" id="fm-save">💾 Sauver</button>
      <button class="gbr-fm-save-btn" id="fm-clear" style="color:#ef4444">✕ Effacer</button>
      <button class="gbr-fm-close-btn" id="fm-close">✕</button>
    </div>
  </div>
  <div class="gbr-fm-chips" id="fm-active-filters">
    <span class="gbr-fm-chips-empty">Aucun filtre actif.</span>
  </div>
  <div class="gbr-fm-body">
    <div class="gbr-fm-cols">
      <input class="gbr-fm-col-search" id="fm-col-search" type="text" placeholder="🔍 Colonnes…">
      <div class="gbr-fm-col-list" id="fm-col-list"></div>
    </div>
    <div class="gbr-fm-editor" id="fm-editor">
      <div class="gbr-fm-ed-empty">
        <div class="gbr-fm-ed-icon">⊟</div>
        <div>Sélectionnez une colonne pour créer un filtre</div>
      </div>
    </div>
  </div>
</div>

<div class="toast" id="toast"></div>

<!-- ── Scripts ───────────────────────────────────────────────────────── -->
<script>
window.LUMIERE_MODE   = 'standalone';
window.LUMIERE_DAG_ID = null;
window.LUMIERE_ASSET  = null;
</script>
__SCRIPTS__
<script>
window.GB3_TITLE   = __GB3_TITLE__;
window.GB3_CONTEXT = __GB3_CONTEXT__;
window.GB3_DATA    = __GB3_DATA__;
window.addEventListener('DOMContentLoaded', () => window.LumiereGraphBuilder.boot());
</script>
</body>
</html>"""


# ── Script building order ──────────────────────────────────────────────────────

_JS_ORDER = [
    # 1. Core global
    ("file", "graph_builder.core.js"),
    # 2. Standalone adapter (override Storage / DAG / Assets / boot)
    ("adapter", None),
    # 3. Data, Filters, PlotlyBridge, Table
    ("file", "graph_builder.data.js"),
    ("file", "graph_builder.filters.js"),
    ("file", "graph_builder.plotly.js"),
    ("file", "graph_builder.table.js"),
    # 4. UI v2 (override UI)
    ("file", "graph_builder.ui2.js"),
    # 5. Extensions
    ("ext",  "scatter.js"),
    ("ext",  "line.js"),
    ("ext",  "bar.js"),
    ("ext",  "boxplot.js"),
    ("ext",  "histogram.js"),
    ("ext",  "wafer_map.js"),
    ("ext",  "curves.js"),
    ("ext",  "linked_views.js"),
]

# Extensions optionnelles (ne bloquent pas si manquantes)
_OPTIONAL_EXTS = {"wafer_map.js", "curves.js", "linked_views.js"}


def _build_scripts() -> str:
    parts = []
    adapter_src = _read_adapter()
    for kind, name in _JS_ORDER:
        if kind == "adapter":
            src = adapter_src
        elif kind == "file":
            src = _app_js(name)
        else:  # ext
            try:
                src = _ext_js(name)
            except FileNotFoundError:
                if name in _OPTIONAL_EXTS:
                    continue
                raise
        bar  = "─" * max(0, 56 - len(name or "adapter"))
        head = f"// ── {name or '_gb3_standalone'} {bar}"
        parts.append(f"<script>\n{head}\n{src}\n</script>")
    return "\n".join(parts)


# ── Block class ────────────────────────────────────────────────────────────────

class GraphBuilderV3:
    """
    Graph Builder V3 — Block autonome pour report_builder.

    Reprend exactement l'UX de app/pages/graph_builder/ :
    glisser-déposer, extensions, filtres avancés, config inline,
    tableau avec stats, vues localStorage.

    Paramètres
    ----------
    data            : DataFrame unique ou dict {nom: DataFrame}
    title           : Titre affiché dans la topbar et l'onglet
    exclude_cols    : Colonnes à exclure de la sérialisation
    max_vector_pts  : Downsampling des colonnes vectorielles (0 = pas de limite)
    context_key     : Clé localStorage pour isoler les vues par rapport (défaut : slug du titre)
    """

    needs_plotly     = True
    needs_marked     = False
    panel_css_class  = "gb-panel"
    needs_full_panel = True

    def __init__(
        self,
        data: Union[pd.DataFrame, dict],
        title: str = "Graph Builder V3",
        exclude_cols: list[str] | None = None,
        max_vector_pts: int = 200,
        context_key: str | None = None,
        height: int = 700,
    ):
        self.data           = data
        self.title          = title
        self.height         = height
        self.exclude        = set(exclude_cols or [])
        self.max_vector_pts = max_vector_pts
        self.context_key    = context_key or re.sub(r"\W+", "_", title.lower()).strip("_")

    # ── Contrat Block ──────────────────────────────────────────────────────

    def to_dict(self) -> dict:
        raise NotImplementedError(
            "GraphBuilderV3.to_dict() n'est pas supporté : "
            "ce bloc contient des données non-sérialisables en JSON."
        )

    # ── Sérialisation ──────────────────────────────────────────────────────

    def _datasets_json(self) -> str:
        datasets = _build_datasets(self.data, self.exclude, self.max_vector_pts)
        return json.dumps(datasets, ensure_ascii=False, separators=(",", ":"))

    # ── Render ─────────────────────────────────────────────────────────────

    def _fill_template(self, store=None) -> str:
        """Remplit le template avec CSS, scripts et données."""
        css     = _read_css()
        scripts = _build_scripts()
        title_e = self.title.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        html = _HTML_TEMPLATE
        html = html.replace("__TITLE__",       title_e)
        html = html.replace("__CSS__",         css)
        html = html.replace("__SCRIPTS__",     scripts)
        html = html.replace("__GB3_TITLE__",   json.dumps(self.title))
        html = html.replace("__GB3_CONTEXT__", json.dumps(self.context_key))
        if isinstance(self.data, str):
            if store is None:
                raise RuntimeError(
                    f"GraphBuilderV3 references store key {self.data!r} but no DataStore was "
                    f"provided to render(). Pass store=report.data when calling render()."
                )
            key = self.data
            gb3_data_js = (
                f'(function(){{'
                f'var _raw=(window.__DATA_STORE__||{{}})[{json.dumps(key)}]||[];'
                f'return {{"main":_raw}};}})()'
            )
            html = html.replace("__GB3_DATA__", gb3_data_js)
        else:
            html = html.replace("__GB3_DATA__", self._datasets_json())
        return html

    def render(self, store=None) -> str:
        """
        Fragment HTML pour embedding dans un rapport (conforme contrat Block).
        - Extrait le CSS du <head> et le contenu du <body>
        - Wrapping dans un div qui joue le rôle de body.gb-runtime
        - Override CSS pour layout embedded (height fixe au lieu de 100vh)
        - DOMContentLoaded remplacé par appel direct (DOM déjà présent)
        """
        filled = self._fill_template(store=store)
        uid = re.sub(r"\W+", "", self.context_key)

        # CSS du <head>
        style_start  = filled.index("<style>")
        style_end    = filled.index("</style>") + len("</style>")
        style_block  = filled[style_start:style_end]

        # Contenu du <body>
        body_start   = filled.index("<body")
        body_start   = filled.index(">", body_start) + 1
        body_end     = filled.rindex("</body>")
        body_content = filled[body_start:body_end]

        # DOMContentLoaded a déjà tiré quand le fragment s'insère
        body_content = body_content.replace(
            "window.addEventListener('DOMContentLoaded', () => window.LumiereGraphBuilder.boot());",
            "window.LumiereGraphBuilder.boot();"
        )

        # Override layout : le div wrapper joue le rôle de body.gb-runtime
        embed_css = f"""
<style id="gb3-embed-{uid}">
  #gb3-embed-{uid}-root {{
    height: {self.height}px;
    display: flex !important;
    flex-direction: column !important;
    overflow: hidden !important;
    position: relative;
  }}
  #gb3-embed-{uid}-root .gbr-workspace {{
    flex: 1 !important;
    min-height: 0 !important;
  }}
  #gb3-embed-{uid}-root body.gb-runtime {{
    height: auto !important;
    overflow: visible !important;
  }}
</style>"""

        return (
            style_block
            + embed_css
            + f'\n<div id="gb3-embed-{uid}-root" class="gb-runtime">\n'
            + body_content
            + "\n</div>"
        )

    def render_standalone(self) -> str:
        """HTML complet standalone (avec <html>/<head>/<body>)."""
        return self._fill_template()


# ── CLI helper ─────────────────────────────────────────────────────────────────

def _demo() -> None:
    """Génère un HTML démo avec des données aléatoires."""
    import argparse
    parser = argparse.ArgumentParser(description="GraphBuilderV3 — démo")
    parser.add_argument("--out",  default="/tmp/gb3_demo.html")
    parser.add_argument("--rows", type=int, default=500)
    args = parser.parse_args()

    rng = np.random.default_rng(42)
    df  = pd.DataFrame({
        "x":       rng.normal(0, 1, args.rows),
        "y":       rng.normal(0, 1, args.rows),
        "z":       rng.normal(0, 1, args.rows),
        "groupe":  rng.choice(["A", "B", "C", "D"], args.rows),
        "valeur":  rng.uniform(0, 100, args.rows),
        "spectre": [list(rng.random(64)) for _ in range(args.rows)],
    })

    block = GraphBuilderV3(df, title="Graph Builder V3 — Démo", max_vector_pts=64)
    out   = Path(args.out)
    out.write_text(block.render(), encoding="utf-8")
    print(f"✓  {out}  ({len(out.read_bytes()) // 1024} KB)")


if __name__ == "__main__":
    _demo()
