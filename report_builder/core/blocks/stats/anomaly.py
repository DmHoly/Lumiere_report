"""
anomaly_block.py
────────────────
AnomalyBlock — Bloc « Alertes & Anomalies » pour le système de rapport LUMIÈRE.

Le bloc lit la clé "anomalies" du DataStore (ou un DataFrame passé directement).

Format attendu du DataFrame
───────────────────────────
Colonnes obligatoires :
  wafer      (str)   — identifiant du wafer, ex. "WAFER-07"
  metric     (str)   — nom de la métrique, ex. "PL Intensity"
  message    (str)   — description de l'anomalie, ex. "PL Intensity sous le seuil (13.2k < 14.0k)"
  timestamp  (str)   — horodatage lisible, ex. "Aujourd'hui, 09:41"
  severity   (str)   — "critical" | "warning" | "info"   (défaut : "warning" si absent)

Usage
─────
    from anomaly_block import AnomalyBlock

    # Via store (recommandé)
    report.data.register("anomalies", df_anomalies)
    tab.add(AnomalyBlock(data="anomalies"))

    # Via DataFrame direct
    tab.add(AnomalyBlock(data=df_anomalies))

    # Avec lien « Voir toutes les alertes »
    tab.add(AnomalyBlock(data="anomalies", goto_tab="Alertes complètes"))

Paramètres
──────────
    data        : str | pd.DataFrame  — clé store ou df direct
    title       : str                  — titre du bloc (défaut : "Alertes & Anomalies")
    max_shown   : int                  — nb max d'anomalies affichées (défaut : 5)
    goto_tab    : str | None           — nom de l'onglet cible du bouton goto
                                         (None = bouton désactivé / placeholder)
    goto_label  : str                  — libellé du bouton (défaut : "Voir toutes les alertes")
    show_empty  : bool                 — afficher le bloc même si 0 anomalies (défaut : True)
"""
from __future__ import annotations

import json
import html as _h

import pandas as pd

try:
    from ..._helpers import Block
    from ..data.data_mixin import DataMixin, DataArg
except ImportError:
    # ── Mode standalone / tests unitaires ────────────────────────────────────
    DataArg = "DataArg"

    class Block:
        needs_plotly = False
        needs_marked = False
        def render(self, store=None) -> str:
            raise NotImplementedError

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
        def data_key(self):
            return self._data_arg if isinstance(self._data_arg, str) else None

        @property
        def has_local_data(self):
            return isinstance(self._data_arg, pd.DataFrame)

        @staticmethod
        def store_js_expr(key):
            import json
            return f'(window.__DATA_STORE__||{{}})[{json.dumps(key)}]||[]'


# ─────────────────────────────────────────────────────────────────────────────
#  Constantes visuelles
# ─────────────────────────────────────────────────────────────────────────────

_SEVERITY_CFG = {
    "critical": {
        "dot":    "#e85d4a",
        "badge":  "background:#fff0ee;color:#c0392b;border:1px solid #f5c6c2;",
        "label":  "Critique",
    },
    "warning": {
        "dot":    "#f5a623",
        "badge":  "background:#fff8ec;color:#b07800;border:1px solid #f5dfa0;",
        "label":  "Avertissement",
    },
    "info": {
        "dot":    "#3e92cc",
        "badge":  "background:#eef4fb;color:#1a5a8a;border:1px solid #b8d4ef;",
        "label":  "Info",
    },
}
_SEVERITY_DEFAULT = "warning"


# ─────────────────────────────────────────────────────────────────────────────
#  AnomalyBlock
# ─────────────────────────────────────────────────────────────────────────────

class AnomalyBlock(DataMixin, Block):
    """
    Bloc Alertes & Anomalies — design cohérent avec la palette LUMIÈRE.

    Trie les anomalies par sévérité (critical > warning > info),
    affiche les `max_shown` premières, et propose un bouton de navigation.
    """

    def __init__(
        self,
        data: "DataArg",
        title: str = "Alertes & Anomalies",
        max_shown: int = 5,
        goto_tab: str | None = None,
        goto_label: str = "Voir toutes les alertes",
        show_empty: bool = True,
    ):
        self._init_data(data)
        self.title      = title
        self.max_shown  = max_shown
        self.goto_tab   = goto_tab
        self.goto_label = goto_label
        self.show_empty = show_empty
        self._id        = f"anomaly_{id(self)}"

    # ── helpers ───────────────────────────────────────────────────────────────

    @staticmethod
    def _severity_order(sev: str) -> int:
        return {"critical": 0, "warning": 1, "info": 2}.get(sev, 1)

    def _build_rows(self, df: pd.DataFrame) -> list[dict]:
        """Normalise le df et retourne une liste de dicts triés."""
        rows = []
        for _, r in df.iterrows():
            sev = str(r.get("severity", _SEVERITY_DEFAULT)).lower()
            if sev not in _SEVERITY_CFG:
                sev = _SEVERITY_DEFAULT
            rows.append({
                "wafer":     str(r.get("wafer",     "—")),
                "metric":    str(r.get("metric",    "")),
                "message":   str(r.get("message",   "")),
                "timestamp": str(r.get("timestamp", "")),
                "severity":  sev,
            })
        rows.sort(key=lambda x: self._severity_order(x["severity"]))
        return rows

    # ── HTML helpers ──────────────────────────────────────────────────────────

    def _dot(self, color: str) -> str:
        return (
            f'<span style="display:inline-block;width:10px;height:10px;'
            f'border-radius:50%;background:{color};flex-shrink:0;'
            f'margin-top:3px;"></span>'
        )

    def _badge(self, text: str, style: str) -> str:
        return (
            f'<span style="display:inline-block;padding:2px 9px;border-radius:12px;'
            f'font-family:var(--fm,\'IBM Plex Mono\',monospace);font-size:.63rem;'
            f'font-weight:500;letter-spacing:.4px;{style}">'
            f'{_h.escape(text)}</span>'
        )

    def _row_html(self, row: dict) -> str:
        cfg   = _SEVERITY_CFG[row["severity"]]
        dot   = self._dot(cfg["dot"])
        badge = self._badge(row["metric"], cfg["badge"])
        wafer = _h.escape(row["wafer"])
        msg   = _h.escape(row["message"])
        ts    = _h.escape(row["timestamp"])

        return f"""
<div style="display:flex;gap:12px;align-items:flex-start;
  padding:13px 0;border-bottom:1px solid var(--border,#e2e6f0);">
  {dot}
  <div style="flex:1;min-width:0;">
    <div style="display:flex;align-items:center;gap:10px;flex-wrap:wrap;margin-bottom:5px;">
      <span style="font-family:var(--fm,'IBM Plex Mono',monospace);font-size:.78rem;
        font-weight:500;color:var(--text,#0d1b3e);">{wafer}</span>
      {badge}
    </div>
    <div style="font-family:var(--fb,'DM Sans',sans-serif);font-size:.83rem;
      color:var(--text,#0d1b3e);line-height:1.45;margin-bottom:3px;">{msg}</div>
    <div style="font-family:var(--fm,'IBM Plex Mono',monospace);font-size:.65rem;
      color:var(--slate-400,#8892aa);">{ts}</div>
  </div>
</div>"""

    def _goto_js(self) -> str:
        """Génère le onclick de navigation vers un onglet par son libellé."""
        if self.goto_tab is None:
            return ""
        tab_name = json.dumps(self.goto_tab)
        return (
            f"(function(){{"
            f"var tabs=document.querySelectorAll('.rb-tab-btn');"
            f"for(var i=0;i<tabs.length;i++){{"
            f"if(tabs[i].textContent.trim()==={tab_name}){{"
            f"tabs[i].click();window.scrollTo(0,0);return;}}}}"
            f"}})()"
        )

    # ── render ────────────────────────────────────────────────────────────────

    def render(self, store=None) -> str:
        df   = self.resolve_df(store)
        rows = self._build_rows(df)

        total    = len(rows)
        shown    = rows[: self.max_shown]
        hidden   = total - len(shown)

        if total == 0 and not self.show_empty:
            return ""

        # ── Badge compteur dans le titre ──────────────────────────────────────
        counter_html = ""
        if total > 0:
            badge_color = "#e85d4a" if any(r["severity"] == "critical" for r in rows) else "#f5a623"
            counter_html = (
                f'<span style="display:inline-flex;align-items:center;justify-content:center;'
                f'width:26px;height:26px;border-radius:50%;'
                f'background:{badge_color}22;border:1.5px solid {badge_color};'
                f'font-family:var(--fm,\'IBM Plex Mono\',monospace);font-size:.75rem;'
                f'font-weight:600;color:{badge_color};">{total}</span>'
            )

        # ── Lignes anomalies ──────────────────────────────────────────────────
        if total == 0:
            rows_html = (
                '<div style="padding:24px 0;text-align:center;'
                'font-family:var(--fm,\'IBM Plex Mono\',monospace);font-size:.75rem;'
                'color:var(--slate-400,#8892aa);">✓ Aucune anomalie détectée</div>'
            )
        else:
            rows_html = "".join(self._row_html(r) for r in shown)
            # Dernier séparateur supprimé (la div elle-même a border-bottom)
            # Message « +N autres » si tronqué
            if hidden > 0:
                rows_html += (
                    f'<div style="padding:10px 0 2px;'
                    f'font-family:var(--fm,\'IBM Plex Mono\',monospace);font-size:.65rem;'
                    f'color:var(--slate-400,#8892aa);text-align:center;">'
                    f'+ {hidden} autre{"s" if hidden > 1 else ""} anomalie{"s" if hidden > 1 else ""}'
                    f'</div>'
                )

        # ── Bouton goto ───────────────────────────────────────────────────────
        if self.goto_tab is not None:
            onclick    = f' onclick="{_h.escape(self._goto_js())}"'
            btn_style  = "cursor:pointer;"
            btn_title  = f'title="Aller à l\'onglet {_h.escape(self.goto_tab)}"'
        else:
            # Placeholder : bouton visible mais inactif avec style atténué
            onclick   = ""
            btn_style = "opacity:.45;cursor:not-allowed;"
            btn_title = 'title="Destination non configurée — passez goto_tab=\'Nom onglet\'"'

        goto_btn = f"""
<div style="margin-top:16px;text-align:center;">
  <button {btn_title}
    style="background:none;border:1.5px solid var(--navy,#0d1b3e);
      border-radius:8px;padding:9px 24px;
      font-family:var(--fb,'DM Sans',sans-serif);font-size:.82rem;
      font-weight:600;color:var(--navy,#0d1b3e);
      transition:background .18s,color .18s;{btn_style}"
    onmouseover="if({'true' if self.goto_tab else 'false'}){{this.style.background='var(--navy,#0d1b3e)';this.style.color='#fff';}}"
    onmouseout="this.style.background='none';this.style.color='var(--navy,#0d1b3e)';"
    {onclick}>
    {_h.escape(self.goto_label)} →
  </button>
</div>"""

        # ── Assemblage final ──────────────────────────────────────────────────
        return f"""
<div id="{self._id}" style="
  background:var(--surface,#ffffff);
  border:1px solid var(--border,#e2e6f0);
  border-radius:var(--radius,8px);
  box-shadow:var(--shadow,0 1px 3px rgba(13,27,62,.08));
  padding:20px 22px 18px;
  max-width:520px;
">
  <!-- En-tête -->
  <div style="display:flex;align-items:center;justify-content:space-between;
    margin-bottom:14px;">
    <span style="font-family:var(--fb,'DM Sans',sans-serif);font-size:.82rem;
      font-weight:700;letter-spacing:.8px;text-transform:uppercase;
      color:var(--text,#0d1b3e);">{_h.escape(self.title)}</span>
    {counter_html}
  </div>
  <!-- Séparateur -->
  <div style="height:1px;background:var(--border,#e2e6f0);margin-bottom:2px;"></div>
  <!-- Lignes -->
  {rows_html}
  <!-- Bouton navigation -->
  {goto_btn}
</div>"""