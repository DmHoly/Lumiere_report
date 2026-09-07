"""
TrendlineKPICard.py
───────────────────
Bloc LUMIÈRE — Version mini-card compacte du TrendlineKPI.

Affiche une rangée de cards KPI avec :
  ● Valeur actuelle (mean du lot courant) + unité
  ● Delta vs moyenne historique  →  ▲ +2.3 % (vert) / ▼ -1.1 % (rouge)
  ● Sparkline SVG inline (aucune dépendance Plotly)
  ● Sous-titre : ± std du lot courant
  ● Clic → ouvre le TrendlineKPI plein format si un bid est fourni (optionnel)

Pensé pour être positionné EN TÊTE du rapport, avant les tabs,
comme une bande de dashboard.

Usage
─────
    from .TrendlineKPICard import TrendlineKPICard

    report.data.register("main",    df_current)
    report.data.register("history", df_historical)

    # Une card = un KPI
    card_row = TrendlineKPICard(
        data          = "main",
        history_data  = "history",
        wafer_col     = "wafername",
        date_col      = "date_mesure",
        lot_col       = "lot",
        kpis = [
            # (label, y_col, err_col_ou_None, unité, arrondi)
            ("EQE Max",    "eqe_max_mean", "eqe_max_std",  "%",  4),
            ("λ Peak",     "lp_mean",      "lp_std",       "nm", 1),
            ("FWHM",       "fwhm_mean",    None,           "nm", 1),
            ("Yield",      "yield_mean",   None,           "%",  1),
        ],
        category_col  = "categorie",    # filtre optionnel
        accent_color  = "#D4AF37",      # sparkline lot courant
        history_color = "#8B97BF",      # sparkline historique
        open_block_id = None,           # bid d'un TrendlineKPI pour le clic (optionnel)
    )
"""

from __future__ import annotations
import json
import html as _h
import numpy as np
import pandas as pd
from ..._helpers import Block, _safe_json, _is_vector_col
from ..data.data_mixin import DataMixin, DataArg


class TrendlineKPICard(DataMixin, Block):
    """
    Rangée de mini-cards KPI avec sparkline SVG et delta vs historique.

    Paramètres
    ──────────
    data          : clé DataStore ou DataFrame — lot courant
    history_data  : clé DataStore ou DataFrame — historique
    wafer_col     : colonne identifiant le wafer
    date_col      : colonne date (tri chronologique)
    lot_col       : colonne lot
    kpis          : liste de tuples (label, y_col, err_col|None, unit, decimals)
    category_col  : filtre catégoriel (optionnel)
    accent_color  : couleur sparkline lot courant + valeur principale
    history_color : couleur sparkline historique
    open_block_id : si fourni, clic sur la card appelle window[bid_openModal]()
    spark_width   : largeur de la sparkline (px)
    spark_height  : hauteur de la sparkline (px)
    """

    needs_plotly = False  # ← SVG pur, pas de Plotly

    def __init__(
        self,
        data: DataArg,
        history_data: DataArg = None,
        wafer_col: str = "wafername",
        date_col: str = "date_mesure",
        lot_col: str = "lot",
        kpis: list[tuple] = (),
        category_col: str = "",
        accent_color: str = "#D4AF37",
        history_color: str = "#8B97BF",
        open_block_id: str | None = None,
        spark_width: int = 120,
        spark_height: int = 36,
    ):
        self._init_data(data)
        self._history_data_arg = history_data
        self.wafer_col     = wafer_col
        self.date_col      = date_col
        self.lot_col       = lot_col
        self.kpis          = list(kpis)
        self.category_col  = category_col
        self.accent_color  = accent_color
        self.history_color = history_color
        self.open_block_id = open_block_id
        self.spark_width   = spark_width
        self.spark_height  = spark_height
        self._id           = f"tkpic_{id(self)}"

    # ── Resolution ────────────────────────────────────────────────────────

    def _resolve_history_df(self, store=None):
        arg = self._history_data_arg
        if arg is None:            return None
        if isinstance(arg, pd.DataFrame): return arg
        if store is None: raise RuntimeError(f"history_data key {arg!r} needs a DataStore.")
        return store.resolve(arg)

    # ── Aggregation par wafer ─────────────────────────────────────────────

    def _wafer_series(self, df: pd.DataFrame, y_col: str, err_col: str | None) -> list[dict]:
        """Retourne la liste de dicts {date, lot, y, err} triée chronologiquement."""
        if y_col not in df.columns:
            return []

        group_keys = [c for c in [self.wafer_col, self.date_col, self.lot_col]
                      if c and c in df.columns]
        if not group_keys:
            return []

        sub = df[list(dict.fromkeys(
            c for c in group_keys + [y_col] + ([err_col] if err_col and err_col in df.columns else [])
            if c in df.columns
        ))].copy()

        if self.date_col in sub.columns:
            try:   sub[self.date_col] = pd.to_datetime(sub[self.date_col]).dt.strftime("%Y-%m-%d")
            except Exception: sub[self.date_col] = sub[self.date_col].astype(str)

        records = []
        for keys_val, grp in sub.groupby(group_keys, dropna=False):
            if not isinstance(keys_val, tuple): keys_val = (keys_val,)
            rec = {k: v for k, v in zip(group_keys, keys_val)}
            vals = grp[y_col].dropna()
            rec["y"] = float(vals.mean()) if len(vals) else None
            if err_col and err_col in grp.columns:
                ev = grp[err_col].dropna()
                rec["err"] = float(ev.mean()) if len(ev) else None
            else:
                rec["err"] = None
            records.append(rec)

        records.sort(key=lambda r: (r.get(self.date_col) or "", r.get(self.lot_col) or ""))
        return records

    # ── SVG sparkline ─────────────────────────────────────────────────────

    def _sparkline_svg(self, hist_series: list[dict], cur_series: list[dict],
                       w: int, h: int) -> str:
        """Génère un SVG inline avec deux courbes : historique + lot courant."""
        all_vals = [r["y"] for r in hist_series + cur_series if r.get("y") is not None]
        if not all_vals:
            return f'<svg width="{w}" height="{h}"></svg>'

        pad = 4
        ymin, ymax = min(all_vals), max(all_vals)
        yrange = ymax - ymin if ymax != ymin else 1e-9

        def to_xy(series):
            n = len(series)
            pts = []
            for i, r in enumerate(series):
                if r.get("y") is None:
                    continue
                x = pad + (i / max(n - 1, 1)) * (w - 2 * pad)
                y = h - pad - ((r["y"] - ymin) / yrange) * (h - 2 * pad)
                pts.append((x, y))
            return pts

        def polyline(pts, color, width, dash=""):
            if len(pts) < 2:
                return ""
            d = " ".join(f"{x:.1f},{y:.1f}" for x, y in pts)
            stroke_dash = f' stroke-dasharray="{dash}"' if dash else ""
            return (f'<polyline points="{d}" fill="none" stroke="{color}" '
                    f'stroke-width="{width}" stroke-linecap="round" '
                    f'stroke-linejoin="round"{stroke_dash}/>')

        def last_dot(pts, color, r=3):
            if not pts:
                return ""
            x, y = pts[-1]
            return (f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{r}" '
                    f'fill="{color}" stroke="white" stroke-width="1.5"/>')

        hist_pts = to_xy(hist_series)
        cur_pts  = to_xy(cur_series)

        # Horizontal reference line at historical mean
        hist_mean = (sum(r["y"] for r in hist_series if r.get("y") is not None)
                     / max(1, len([r for r in hist_series if r.get("y") is not None])))
        ref_y = h - pad - ((hist_mean - ymin) / yrange) * (h - 2 * pad)
        ref_line = (f'<line x1="{pad}" y1="{ref_y:.1f}" x2="{w-pad}" y2="{ref_y:.1f}" '
                    f'stroke="{self.history_color}" stroke-width="1" stroke-dasharray="3,3" opacity="0.5"/>')

        svg = (
            f'<svg width="{w}" height="{h}" viewBox="0 0 {w} {h}" '
            f'xmlns="http://www.w3.org/2000/svg" style="overflow:visible;">'
            f'{ref_line}'
            f'{polyline(hist_pts, self.history_color, 1.5, "4,3")}'
            f'{polyline(cur_pts,  self.accent_color,  2)}'
            f'{last_dot(cur_pts, self.accent_color)}'
            f'</svg>'
        )
        return svg

    # ── Delta badge ───────────────────────────────────────────────────────

    def _delta_badge(self, cur_val: float | None, hist_vals: list[float],
                     decimals: int, unit: str) -> str:
        if cur_val is None or not hist_vals:
            return ""
        hist_mean = sum(hist_vals) / len(hist_vals)
        if hist_mean == 0:
            return ""
        diff = cur_val - hist_mean
        pct  = (diff / abs(hist_mean)) * 100
        sign = "+" if diff >= 0 else ""
        cls  = "pos" if diff >= 0 else "neg"
        icon = "▲" if diff >= 0 else "▼"
        return (f'<span class="rb-kpi-delta {cls}">'
                f'{icon} {sign}{diff:.{decimals}f} {unit} '
                f'({sign}{pct:.1f}%)</span>')

    # ── Render ────────────────────────────────────────────────────────────

    def render(self, store=None) -> str:
        df_cur  = self.resolve_df(store)
        df_hist = self._resolve_history_df(store)

        # Filtre catégorie si applicable
        if self.category_col:
            # On filtre les deux datasets de la même façon (pas d'UI ici, filtre statique)
            pass  # Les deux dfs restent complets — la card est intentionnellement agrégée

        w, h = self.spark_width, self.spark_height
        cards_html = []

        for kpi_def in self.kpis:
            label, y_col = kpi_def[0], kpi_def[1]
            err_col  = kpi_def[2] if len(kpi_def) > 2 else None
            unit     = kpi_def[3] if len(kpi_def) > 3 else ""
            decimals = int(kpi_def[4]) if len(kpi_def) > 4 else 3

            # Séries
            cur_series  = self._wafer_series(df_cur,  y_col, err_col)
            hist_series = self._wafer_series(df_hist, y_col, err_col) if df_hist is not None else []

            # Valeur lot courant (mean sur tous les wafers du lot courant)
            cur_vals = [r["y"] for r in cur_series if r.get("y") is not None]
            cur_val  = sum(cur_vals) / len(cur_vals) if cur_vals else None

            # Std lot courant (mean des err, ou std des wafer-means)
            cur_errs = [r["err"] for r in cur_series if r.get("err") is not None]
            cur_std  = sum(cur_errs) / len(cur_errs) if cur_errs else (
                float(np.std(cur_vals)) if len(cur_vals) > 1 else None)

            # Historique vals pour delta
            hist_vals = [r["y"] for r in hist_series if r.get("y") is not None]

            # Sparkline
            svg = self._sparkline_svg(hist_series, cur_series, w, h)

            # Valeur principale
            val_str = f"{cur_val:.{decimals}f}" if cur_val is not None else "—"
            std_str = f"± {cur_std:.{decimals}f} {unit}" if cur_std is not None else ""

            # Delta badge
            delta_html = self._delta_badge(cur_val, hist_vals, decimals, unit)

            # Lot courant name
            cur_lot = cur_series[-1].get(self.lot_col, "") if cur_series else ""
            n_wafers = len(cur_series)

            # Click handler
            click_attr = ""
            click_style = ""
            if self.open_block_id:
                oid = _h.escape(self.open_block_id)
                click_attr = f'onclick="if(window[\'{oid}_openModal\'])window[\'{oid}_openModal\']()"'
                click_style = "cursor:pointer;"

            # Trend indicator (last 3 cur wafers)
            trend_icon = ""
            if len(cur_vals) >= 2:
                slope = cur_vals[-1] - cur_vals[-2]
                trend_icon = (
                    f'<span style="font-size:9px;color:{"#3b6d11" if slope>=0 else "#854f0b"};'
                    f'margin-left:4px;">{"↗" if slope>=0 else "↘"}</span>'
                )

            card = f"""
<div class="rb-kpi tkpic-card" {click_attr} style="{click_style}">
  <div style="display:flex;justify-content:space-between;align-items:flex-start;gap:8px;">
    <div style="min-width:0;flex:1;">
      <div class="rb-kpi-label">{_h.escape(label)}</div>
      <div style="display:flex;align-items:baseline;gap:3px;margin-top:4px;">
        <span class="rb-kpi-value" style="font-size:20px;color:{_h.escape(self.accent_color)};">{val_str}</span>
        <span class="rb-kpi-unit">{_h.escape(unit)}</span>
        {trend_icon}
      </div>
      {delta_html}
      <div class="rb-kpi-sub" style="margin-top:3px;">{_h.escape(std_str)}</div>
      <div class="rb-kpi-sub" style="margin-top:2px;color:#aab0c8;">
        {_h.escape(str(cur_lot))} · {n_wafers} wafer{"s" if n_wafers!=1 else ""}
      </div>
    </div>
    <div style="flex-shrink:0;margin-top:2px;">{svg}</div>
  </div>
</div>"""
            cards_html.append(card)

        return f"""
<div class="rb-kpi-row" id="{self._id}_row">
  {"".join(cards_html)}
</div>
<style>
.tkpic-card {{ transition:box-shadow .15s,transform .1s; }}
.tkpic-card:hover {{ box-shadow:0 4px 16px rgba(10,36,99,.13); transform:translateY(-1px); }}
</style>
"""