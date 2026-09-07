"""
lot_summary_table.py
────────────────────
LotSummaryTable — Bloc LUMIÈRE : tableau récap du lot en cours.

Prend un DataFrame **agrégé** (main_mean ou main_median, une ligne par wafer),
affiche les N premières lignes + une ligne MOYENNE, et propose un bouton
« Voir toutes les données disponibles → » qui fait un goto vers l'onglet
Raw Data via le TabView parent.

Usage
-----
    from .lot_summary_table import LotSummaryTable

    tab_rapport = Tab("Rapport")
    tab_rapport.add(
        LotSummaryTable(
            data="main_mean",          # clé DataStore OU DataFrame agrégé
            title="TABLE DES WAFERS – LOT EN COURS",
            wafer_id_col="wafername",  # colonne servant d'identifiant de ligne
            cols=[                     # colonnes à afficher (ordre conservé)
                ("Yield (%)",       "Yield",        "{:.1f}"),
                ("Peak WL (nm)",    "PeakWL",       "{:.1f}"),
                ("PL Intensity",    "PLIntensity",  "{:.1f}k"),
                ("EQE (%)",         "EQE",          "{:.1f}"),
                ("Bin Yield (%)",   "BinYield",     "{:.1f}"),
            ],
            status_col="Status",       # colonne booléenne / 0-1 / "OK"/"KO" (optionnel)
            preview_rows=4,            # nb de wafers affichés avant "..."
            goto_tab_label="Données",  # label exact de l'onglet cible (TabView)
            goto_tab_index=None,       # ou forcer l'index (0-based) directement
        )
    )

Notes
-----
- `data` peut être une clé DataStore (str) ou un DataFrame passé directement.
- Si `status_col` est fourni, la dernière colonne affiche ✓ (vert) ou ✗ (rouge).
- Le bouton « goto » cherche l'onglet par son label dans le TabView parent ;
  si `goto_tab_index` est fourni il est utilisé en priorité.
- Le bloc émet du CSS inline scopé à son identifiant — pas de pollution globale.
"""

from __future__ import annotations

import html as _h
import json
from typing import Any

import pandas as pd

try:
    from ..._helpers import Block
    from ..data.data_mixin import DataMixin, DataArg
except ImportError:
    DataArg = "DataArg"

    class Block:
        needs_plotly = False
        needs_marked = False

    class DataMixin:
        def _init_data(self, data):
            self._data_arg = data

        def resolve_df(self, store=None):
            if isinstance(self._data_arg, pd.DataFrame):
                return self._data_arg
            if isinstance(self._data_arg, str):
                if store is None:
                    raise RuntimeError(
                        f"Block references data key {self._data_arg!r} but no DataStore was provided "
                        f"to resolve_df(). Pass store=report.data when calling render()."
                    )
                return store.resolve(self._data_arg)
            raise TypeError(f"_data_arg must be str or pd.DataFrame, got {type(self._data_arg).__name__}")

        @property
        def has_local_data(self):
            return isinstance(self._data_arg, pd.DataFrame)

        @property
        def data_key(self):
            return self._data_arg if isinstance(self._data_arg, str) else None

        @staticmethod
        def store_js_expr(key):
            import json
            return f'(window.__DATA_STORE__||{{}})[{json.dumps(key)}]||[]'


# ─────────────────────────────────────────────────────────────────────────────
#  Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _fmt_value(v: Any, fmt: str | None = None) -> str:
    """Formate une valeur avec fmt type '.2f' OU '{:.2f}'."""
    if v is None:
        return "—"

    try:
        if pd.isna(v):
            return "—"
    except Exception:
        pass

    try:
        fv = float(v)
    except (TypeError, ValueError):
        return str(v)

    if not fmt:
        return str(v)

    # Support suffixe k :
    # "{:.1f}k" ou ".1fk" -> valeur / 1000
    try:
        if fmt.endswith("k"):
            base_fmt = fmt[:-1]

            if base_fmt.startswith("{"):
                return base_fmt.format(fv / 1000) + "k"
            else:
                return format(fv / 1000, base_fmt) + "k"

        # Format style "{:.2f}"
        if fmt.startswith("{"):
            return fmt.format(fv)

        # Format style ".2f"
        return format(fv, fmt)

    except Exception:
        return str(v)


def _status_icon(v: Any) -> str:
    """Retourne l'icône HTML status selon la valeur de la cellule."""
    if pd.isna(v):
        return '<span class="lst-status-na">—</span>'
    sv = str(v).strip().lower()
    ok = sv in ("1", "true", "ok", "pass", "✓", "oui", "yes")
    if ok:
        return (
            '<span class="lst-status-ok">'
            '<svg viewBox="0 0 20 20" width="16" height="16" fill="none">'
            '<circle cx="10" cy="10" r="9" fill="#22c55e"/>'
            '<path d="M6 10l3 3 5-5" stroke="#fff" stroke-width="1.8" '
            'stroke-linecap="round" stroke-linejoin="round"/>'
            "</svg></span>"
        )
    return (
        '<span class="lst-status-ko">'
        '<svg viewBox="0 0 20 20" width="16" height="16" fill="none">'
        '<circle cx="10" cy="10" r="9" fill="#ef4444"/>'
        '<path d="M7 7l6 6M13 7l-6 6" stroke="#fff" stroke-width="1.8" '
        'stroke-linecap="round" stroke-linejoin="round"/>'
        "</svg></span>"
    )


# ─────────────────────────────────────────────────────────────────────────────
#  Block
# ─────────────────────────────────────────────────────────────────────────────

class LotSummaryTable(DataMixin, Block):
    """
    Tableau récapitulatif du lot en cours (vue agrégée).

    Parameters
    ----------
    data            : DataArg — clé DataStore (str) ou DataFrame agrégé.
    title           : Titre affiché en haut de la card.
    subtitle        : Sous-titre optionnel (ex : "lot en cours").
    wafer_id_col    : Nom de la colonne servant d'identifiant (affiché en 1re col).
    cols            : Liste de tuples (header_label, df_col_name, fmt_str).
                      fmt_str est un format Python, ex "{:.1f}" ou "{:.1f}k".
    status_col      : Nom de la colonne booléenne/textuelle de statut (optionnel).
    preview_rows    : Nombre de wafers affichés avant la ligne "…".
    goto_tab_label  : Label exact de l'onglet cible (ex "Données").
    goto_tab_index  : Index 0-based direct de l'onglet (priorité sur le label).
    show_mean_row   : Afficher une ligne MOYENNE en pied de tableau (défaut True).
    mean_label      : Libellé de la ligne moyenne (défaut "MOYENNE").
    """

    needs_plotly = False
    needs_marked = False

    def __init__(
        self,
        data: "DataArg",
        title: str = "TABLE DES WAFERS – LOT EN COURS",
        subtitle: str = "",
        wafer_id_col: str = "wafername",
        cols: list[tuple[str, str, str]] | None = None,
        status_col: str | None = None,
        preview_rows: int = 4,
        goto_tab_label: str = "Données",
        goto_tab_index: int | None = None,
        show_mean_row: bool = True,
        mean_label: str = "MOYENNE",
    ):
        self._init_data(data)
        self.title = title
        self.subtitle = subtitle
        self.wafer_id_col = wafer_id_col
        self.cols = cols or []
        self.status_col = status_col
        self.preview_rows = preview_rows
        self.goto_tab_label = goto_tab_label
        self.goto_tab_index = goto_tab_index
        self.show_mean_row = show_mean_row
        self.mean_label = mean_label
        self._id = f"lst_{id(self)}"

    # ── Build helpers ─────────────────────────────────────────────────────────

    def _build_header_row(self) -> str:
        cells = [f'<th class="lst-th lst-th-id">{_h.escape(self.wafer_id_col)}</th>']
        for header, _, _ in self.cols:
            cells.append(f'<th class="lst-th">{_h.escape(header)}</th>')
        if self.status_col:
            cells.append('<th class="lst-th lst-th-status">Status</th>')
        return "<tr>" + "".join(cells) + "</tr>"

    def _build_data_row(self, row: pd.Series, css_class: str = "") -> str:
        wafer_id = row.get(self.wafer_id_col, "—") if self.wafer_id_col in row.index else "—"
        cells = [
            f'<td class="lst-td lst-td-id{" " + css_class if css_class else ""}">'
            f'{_h.escape(str(wafer_id))}</td>'
        ]
        for _, col_name, fmt in self.cols:
            v = row.get(col_name) if col_name in row.index else None
            cells.append(f'<td class="lst-td lst-num">{_h.escape(_fmt_value(v, fmt))}</td>')
        if self.status_col:
            sv = row.get(self.status_col) if self.status_col in row.index else None
            cells.append(f'<td class="lst-td lst-td-status">{_status_icon(sv)}</td>')
        return f"<tr>{' '.join(cells)}</tr>"

    def _build_ellipsis_row(self) -> str:
        ncols = 1 + len(self.cols) + (1 if self.status_col else 0)
        dots = "".join(f'<td class="lst-td lst-dots">…</td>' for _ in range(ncols))
        return f"<tr>{dots}</tr>"

    def _build_mean_row(self, df: pd.DataFrame) -> str:
        cells = [f'<td class="lst-td lst-td-mean">{_h.escape(self.mean_label)}</td>']
        for _, col_name, fmt in self.cols:
            if col_name in df.columns and pd.api.types.is_numeric_dtype(df[col_name]):
                v = df[col_name].mean()
            else:
                v = None
            cells.append(
                f'<td class="lst-td lst-num lst-td-mean">{_h.escape(_fmt_value(v, fmt))}</td>'
            )
        if self.status_col:
            cells.append('<td class="lst-td lst-td-mean">—</td>')
        return f"<tr>{''.join(cells)}</tr>"

    # ── CSS (scopé) ───────────────────────────────────────────────────────────

    def _css(self) -> str:
        bid = self._id
        return f"""
<style>
/* ── LotSummaryTable #{bid} ─────────────────────────────── */
#{bid} {{
  background: var(--surface, #fff);
  border: 1px solid var(--border, #e2e6f0);
  border-radius: var(--radius, 8px);
  box-shadow: var(--shadow, 0 1px 3px rgba(13,27,62,.08));
  overflow: hidden;
}}
#{bid} .lst-header {{
  padding: 16px 20px 12px;
  border-bottom: 1px solid var(--border, #e2e6f0);
  background: var(--surface, #fff);
}}
#{bid} .lst-title {{
  font-family: var(--fd, 'DM Sans', sans-serif);
  font-weight: 700;
  font-size: 13px;
  color: var(--navy, #0d1b3e);
  text-transform: uppercase;
  letter-spacing: .06em;
}}
#{bid} .lst-subtitle {{
  font-family: var(--fm, 'IBM Plex Mono', monospace);
  font-size: 10px;
  color: var(--slate-400, #8892aa);
  margin-top: 2px;
}}
#{bid} .lst-scroll {{
  overflow-x: auto;
}}
#{bid} table {{
  width: 100%;
  border-collapse: collapse;
}}
#{bid} .lst-th {{
  font-family: var(--fd, 'DM Sans', sans-serif);
  font-weight: 500;
  font-size: 11px;
  color: var(--slate-400, #8892aa);
  padding: 10px 16px;
  text-align: right;
  white-space: nowrap;
  border-bottom: 1px solid var(--border, #e2e6f0);
  background: var(--surface, #fff);
}}
#{bid} .lst-th-id {{
  text-align: left;
}}
#{bid} .lst-th-status {{
  text-align: center;
}}
#{bid} .lst-td {{
  font-family: var(--fm, 'IBM Plex Mono', monospace);
  font-size: 12px;
  color: var(--text, #0d1b3e);
  padding: 11px 16px;
  text-align: right;
  border-bottom: 1px solid var(--slate-100, #eef0f6);
  white-space: nowrap;
}}
#{bid} .lst-td-id {{
  font-family: var(--fd, 'DM Sans', sans-serif);
  font-weight: 600;
  font-size: 12px;
  text-align: left;
  color: var(--navy, #0d1b3e);
}}
#{bid} .lst-num {{
  font-variant-numeric: tabular-nums;
}}
#{bid} .lst-dots {{
  text-align: center;
  color: var(--slate-400, #8892aa);
  font-family: var(--fm, 'IBM Plex Mono', monospace);
  font-size: 11px;
  padding: 6px 16px;
  border-bottom: 1px solid var(--slate-100, #eef0f6);
}}
#{bid} .lst-td-status {{
  text-align: center;
}}
#{bid} .lst-status-ok,
#{bid} .lst-status-ko,
#{bid} .lst-status-na {{
  display: inline-flex;
  align-items: center;
  justify-content: center;
}}
#{bid} .lst-td-mean {{
  font-family: var(--fd, 'DM Sans', sans-serif);
  font-weight: 700;
  font-size: 12px;
  color: var(--navy-l, #1a2f6a);
  border-top: 2px solid var(--border, #e2e6f0);
  border-bottom: none;
  background: var(--slate-50, #f8f9fc);
}}
#{bid} .lst-footer {{
  padding: 14px 20px;
  display: flex;
  justify-content: center;
  border-top: 1px solid var(--border, #e2e6f0);
  background: var(--surface, #fff);
}}
#{bid} .lst-goto-btn {{
  display: inline-flex;
  align-items: center;
  gap: 8px;
  font-family: var(--fd, 'DM Sans', sans-serif);
  font-weight: 500;
  font-size: 12px;
  color: var(--navy-l, #1a2f6a);
  background: var(--slate-50, #f8f9fc);
  border: 1px solid var(--border, #e2e6f0);
  border-radius: 20px;
  padding: 8px 22px;
  cursor: pointer;
  transition: background .15s, border-color .15s, color .15s;
  text-decoration: none;
}}
#{bid} .lst-goto-btn:hover {{
  background: var(--navy, #0d1b3e);
  border-color: var(--navy, #0d1b3e);
  color: #fff;
}}
#{bid} .lst-goto-btn svg {{
  transition: transform .15s;
}}
#{bid} .lst-goto-btn:hover svg {{
  transform: translateX(3px);
}}
</style>"""

    # ── goto JS ───────────────────────────────────────────────────────────────

    def _goto_js(self) -> str:
        bid = self._id
        if self.goto_tab_index is not None:
            # Index direct — on cherche le TabView parent et on appelle _show(n)
            idx = int(self.goto_tab_index)
            return f"""
<script>
function {bid}_goto() {{
  /* Stratégie 1 : cherche un TabView dont le bouton porte l'index {idx} */
  var allBtns = document.querySelectorAll('.rb-tab-btn');
  if (allBtns.length > {idx}) {{
    allBtns[{idx}].click();
    return;
  }}
  /* Fallback : cherche par data-tab-index */
  var el = document.querySelector('[data-tab-index="{idx}"]');
  if (el) el.click();
}}
</script>"""
        # Sinon cherche par label
        label_json = json.dumps(self.goto_tab_label)
        return f"""
<script>
function {bid}_goto() {{
  var label = {label_json}.toLowerCase();
  var btns  = Array.from(document.querySelectorAll('.rb-tab-btn'));
  var found = btns.find(function(b) {{
    return b.textContent.trim().toLowerCase().includes(label);
  }});
  if (found) found.click();
}}
</script>"""

    # ── render ────────────────────────────────────────────────────────────────

    def render(self, store=None) -> str:
        df = self.resolve_df(store)
        bid = self._id

        # Titre / sous-titre
        sub_html = (
            f'<div class="lst-subtitle">{_h.escape(self.subtitle)}</div>'
            if self.subtitle
            else ""
        )
        header_html = (
            f'<div class="lst-header">'
            f'<div class="lst-title">{_h.escape(self.title)}</div>'
            f"{sub_html}"
            f"</div>"
        )

        # Lignes du tableau
        rows_html = ""
        n = min(self.preview_rows, len(df))
        for i in range(n):
            rows_html += self._build_data_row(df.iloc[i])

        if len(df) > self.preview_rows:
            rows_html += self._build_ellipsis_row()

        if self.show_mean_row:
            rows_html += self._build_mean_row(df)

        table_html = (
            f'<div class="lst-scroll">'
            f"<table>"
            f"<thead>{self._build_header_row()}</thead>"
            f"<tbody>{rows_html}</tbody>"
            f"</table>"
            f"</div>"
        )

        # Bouton goto
        arrow_svg = (
            '<svg viewBox="0 0 20 20" width="14" height="14" fill="none">'
            '<path d="M4 10h12M11 5l5 5-5 5" stroke="currentColor" '
            'stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"/>'
            "</svg>"
        )
        btn_label = "Voir toutes les données disponibles"
        footer_html = (
            f'<div class="lst-footer">'
            f'<button class="lst-goto-btn" onclick="{bid}_goto()">'
            f"{btn_label} {arrow_svg}"
            f"</button>"
            f"</div>"
        )

        return (
            self._css()
            + self._goto_js()
            + f'<div class="led-block" id="{bid}">'
            + header_html
            + table_html
            + footer_html
            + "</div>"
        )