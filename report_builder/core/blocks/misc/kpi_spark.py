"""
kpi_spark_block.py — KPI avec tendance historique, bande ±std, nouveaux wafers en étoiles.
voir docstring complète dans le fichier.
"""
from __future__ import annotations
import html as _h, json, datetime
import numpy as np, pandas as pd
from ..._helpers import Block, _safe_json, _is_vector_col
from ..data.data_mixin import DataMixin, DataArg


# ─────────────────────────────────────────────────────────────────────────────
# Helpers publics
# ─────────────────────────────────────────────────────────────────────────────

def make_hist_df(df_raw, kpi_cols, date_col, n_periods=None):
    """
    Agrège df_raw par date_col → DataFrame pré-agrégé avec colonnes
    date, {kpi}_median, {kpi}_mean, {kpi}_std, {kpi}_min, {kpi}_max
    """
    frames = []
    for kpi in kpi_cols:
        if kpi not in df_raw.columns:
            continue
        df2 = df_raw[[date_col, kpi]].copy()
        df2[kpi] = pd.to_numeric(df2[kpi], errors="coerce")
        g = df2.groupby(date_col)[kpi].agg(
            **{f"{kpi}_median": "median", f"{kpi}_mean": "mean",
               f"{kpi}_std": "std", f"{kpi}_min": "min", f"{kpi}_max": "max"}
        ).reset_index().rename(columns={date_col: "date"})
        g[f"{kpi}_std"] = g[f"{kpi}_std"].fillna(0)
        frames.append(g.set_index("date"))
    if not frames:
        return pd.DataFrame(columns=["date"])
    out = pd.concat(frames, axis=1).reset_index().rename(columns={"index": "date"})
    try:
        out = out.sort_values("date")
    except Exception:
        pass
    if n_periods:
        out = out.tail(n_periods)
    return out.reset_index(drop=True)


def make_demo_hist_df(kpi_cols, n_periods=8, freq="month", trend=0.4, seed=42):
    """
    Génère un historique démo avec progression linéaire.

    Params
    ------
    kpi_cols  : {nom_col: (lo, hi)}
    n_periods : nombre de périodes
    freq      : "month" | "week" | "year" | "quarter"
    trend     : progression totale sur la série (fraction de la plage)
    seed      : reproductibilité

    Retourne un DataFrame avec:
    date, {kpi}_median, {kpi}_mean, {kpi}_std, {kpi}_min, {kpi}_max
    """
    rng  = np.random.default_rng(seed)
    today = datetime.date.today()

    # Génère les labels de période
    if freq == "month":
        dates = []
        d = today.replace(day=1)
        for _ in range(n_periods):
            dates.insert(0, d.strftime("%b %Y"))
            m = d.month - 1 or 12
            y = d.year - (1 if d.month == 1 else 0)
            d = d.replace(year=y, month=m)
    elif freq == "week":
        dates = [(today - datetime.timedelta(weeks=n_periods-1-i)).strftime("W%V %Y")
                 for i in range(n_periods)]
    elif freq == "year":
        base = today.year - n_periods + 1
        dates = [str(base + i) for i in range(n_periods)]
    elif freq == "quarter":
        dates = []
        d = today.replace(day=1)
        for _ in range(n_periods):
            q = (d.month - 1) // 3 + 1
            dates.insert(0, f"Q{q} {d.year}")
            m = d.month - 3
            if m <= 0:
                d = d.replace(year=d.year-1, month=m+12)
            else:
                d = d.replace(month=m)
    else:
        dates = [str(i) for i in range(n_periods)]

    rows = []
    for i, date in enumerate(dates):
        t   = i / max(n_periods - 1, 1)
        row = {"date": date}
        for kpi, (lo, hi) in kpi_cols.items():
            span    = float(hi - lo)
            center  = lo + span * 0.20 + span * trend * t
            spread  = span * 0.05
            samples = np.clip(rng.normal(center, spread, 20), lo, hi)
            row[f"{kpi}_median"] = float(np.median(samples))
            row[f"{kpi}_mean"]   = float(np.mean(samples))
            row[f"{kpi}_std"]    = float(np.std(samples))
            row[f"{kpi}_min"]    = float(np.min(samples))
            row[f"{kpi}_max"]    = float(np.max(samples))
        rows.append(row)
    return pd.DataFrame(rows)


# ─────────────────────────────────────────────────────────────────────────────
# Helpers internes
# ─────────────────────────────────────────────────────────────────────────────

def _fmt_val(v, decimals=None):
    if v is None or (isinstance(v, float) and np.isnan(v)):
        return "—"
    if decimals is not None:
        return f"{v:.{decimals}f}"
    a = abs(v)
    if a >= 100: return f"{v:.1f}"
    if a >= 10:  return f"{v:.2f}"
    if a >= 1:   return f"{v:.3f}"
    return f"{v:.4f}"


def _resolve_hist_stats(df_hist, kpi_col, date_col, n_periods):
    if df_hist is None or df_hist.empty:
        return pd.DataFrame()
    pre    = {s: f"{kpi_col}_{s}" for s in ("median","mean","std","min","max")}
    has_pre = all(c in df_hist.columns for c in pre.values())
    date_c  = "date" if "date" in df_hist.columns else date_col

    if has_pre and date_c in df_hist.columns:
        out = df_hist[[date_c] + list(pre.values())].drop_duplicates(date_c).copy()
        out = out.rename(columns={v: k for k, v in pre.items()})
        out = out.rename(columns={date_c: "date"})
    elif kpi_col in df_hist.columns and date_c in df_hist.columns:
        df2 = df_hist[[date_c, kpi_col]].copy()
        df2[kpi_col] = pd.to_numeric(df2[kpi_col], errors="coerce")
        grp = df2.groupby(date_c)[kpi_col].agg(
            median="median", mean="mean", std="std", min="min", max="max"
        ).reset_index()
        grp["std"] = grp["std"].fillna(0)
        out = grp.rename(columns={date_c: "date"})
    else:
        return pd.DataFrame()

    try:
        out = out.sort_values("date")
    except Exception:
        pass
    if n_periods:
        out = out.tail(n_periods)
    return out.reset_index(drop=True)


# ─────────────────────────────────────────────────────────────────────────────
# Block
# ─────────────────────────────────────────────────────────────────────────────

class KPISparkBlock(DataMixin, Block):
    """
    KPI card avec :
    - grande valeur lot en cours + delta coloré vs historique
    - courbe tendance historique + bande ±std
    - nouveaux wafers en étoiles oranges (hover riche)
    - dropdown median / mean / max / min
    """
    needs_plotly = True

    def __init__(
        self,
        data: DataArg,
        hist_data: DataArg | None = None,
        kpi_col: str = "",
        date_col: str = "date",
        wafer_col: str | None = "wafername",
        hover_cols: list[str] | None = None,
        unit: str = "",
        label: str = "",
        delta_label: str = "vs historique",
        n_periods: int = 8,
        default_stat: str = "median",
        spread_wafers: bool = True,
        height: int = 260,
        decimals: int | None = None,
    ):
        self._init_data(data)
        self._hist_data   = hist_data
        self.kpi_col      = kpi_col
        self.date_col     = date_col
        self.wafer_col    = wafer_col
        self.hover_cols   = hover_cols or []
        self.unit         = unit
        self.label        = label or kpi_col
        self.delta_label  = delta_label
        self.n_periods    = n_periods
        self.default_stat = default_stat
        self.spread_wafers = spread_wafers
        self.height       = height
        self.decimals     = decimals
        self._id          = f"ksb_{id(self)}"

    def _resolve_hist_df(self, store):
        if self._hist_data is None:
            return None
        if isinstance(self._hist_data, pd.DataFrame):
            return self._hist_data
        if isinstance(self._hist_data, str) and store is not None:
            try:
                return store.resolve(self._hist_data)
            except Exception:
                return None
        return None

    def render(self, store=None) -> str:
        df      = self.resolve_df(store)
        df_hist = self._resolve_hist_df(store)
        sid     = self._id

        # Résolution kpi_col
        kpi = self.kpi_col
        if not kpi or kpi not in df.columns:
            for c in df.columns:
                if pd.api.types.is_numeric_dtype(df[c]) and not _is_vector_col(df[c]):
                    kpi = c; break

        # Historique
        hist = _resolve_hist_stats(df_hist, kpi, self.date_col, self.n_periods)

        # Valeur lot en cours
        cur_vals   = pd.to_numeric(df[kpi] if kpi in df.columns else pd.Series(dtype=float),
                                   errors="coerce").dropna()
        cur_median = float(cur_vals.median()) if len(cur_vals) else float("nan")

        # Référence historique = dernière période, médiane
        hist_ref = float("nan")
        if not hist.empty and "median" in hist.columns:
            last = hist["median"].dropna()
            if len(last):
                hist_ref = float(last.iloc[-1])

        delta = (cur_median - hist_ref
                 if not (np.isnan(cur_median) or np.isnan(hist_ref)) else None)

        # Points wafers (hover)
        all_hover = [kpi] + [c for c in self.hover_cols if c in df.columns and c != kpi]
        if self.wafer_col and self.wafer_col in df.columns:
            all_hover = [self.wafer_col] + [c for c in all_hover if c != self.wafer_col]
        all_hover = [c for c in all_hover
                     if c in df.columns and not _is_vector_col(df[c])]

        wafer_pts = []
        for i, (_, row) in enumerate(df.iterrows()):
            v = _safe_json(row.get(kpi))
            if v is None:
                continue
            pt = {"y": v, "i": i}
            for c in all_hover:
                raw = row.get(c)
                pt[c] = str(raw) if isinstance(raw, str) else _safe_json(raw)
            wafer_pts.append(pt)

        # Sérialisation
        hist_json    = json.dumps([] if hist.empty else [
            {"date": str(r["date"]),
             "median": _safe_json(r.get("median")),
             "mean":   _safe_json(r.get("mean")),
             "std":    _safe_json(r.get("std", 0)),
             "min":    _safe_json(r.get("min")),
             "max":    _safe_json(r.get("max"))}
            for _, r in hist.iterrows()
        ])
        wafer_json   = json.dumps(wafer_pts)
        hover_cols_j = json.dumps(all_hover)

        # ── HTML ─────────────────────────────────────────────────────
        label_h  = _h.escape(self.label)
        unit_h   = _h.escape(self.unit)
        cur_str  = _fmt_val(cur_median, self.decimals)
        unit_span = (f'<span style="font-family:\'IBM Plex Mono\',monospace;'
                     f'font-size:14px;color:#4A5580;margin-left:3px;">{unit_h}</span>'
                     if unit_h else "")

        if delta is not None:
            sign  = "+" if delta >= 0 else ""
            d_str = f"{sign}{_fmt_val(delta, self.decimals)} pts"
            d_col = "#1D9E75" if delta >= 0 else "#D85A30"
            d_ico = "↑" if delta >= 0 else "↓"
            delta_h = f"""
    <div style="display:flex;flex-direction:column;justify-content:center;
                margin-left:14px;">
      <div style="font-family:'Syne',sans-serif;font-weight:700;font-size:14px;
                  color:{d_col};line-height:1.2;">{d_ico} {_h.escape(d_str)}</div>
      <div style="font-family:'IBM Plex Mono',monospace;font-size:9px;
                  color:#8B97BF;margin-top:2px;">{_h.escape(self.delta_label)}</div>
    </div>"""
        else:
            delta_h = ""

        stat_opts = [("median","Médiane"),("mean","Moyenne"),
                     ("max","Maximum"),("min","Minimum")]
        opts_h = "".join(
            f'<option value="{s}" {"selected" if s==self.default_stat else ""}>{lbl}</option>'
            for s, lbl in stat_opts
        )

        spark_h = max(self.height - 36 - 50 - 20 - 16, 80)

        js = f"""<script>
(function(){{
  var sid        = {json.dumps(sid)};
  var HIST       = {hist_json};
  var WAFERS     = {wafer_json};
  var HOVER_COLS = {hover_cols_j};
  var kpi        = {json.dumps(kpi)};
  var unit       = {json.dumps(self.unit)};
  var spreadW    = {json.dumps(self.spread_wafers)};
  var sparkH     = {spark_h};
  var nHist      = HIST.length;
  var nWaf       = WAFERS.length;

  function waferX(i) {{
    if (!spreadW || nWaf <= 1) return nHist + 0.5;
    return nHist + 0.15 + (i / Math.max(nWaf-1,1)) * 0.7;
  }}
  function fmtV(v) {{
    if (v==null||isNaN(v)) return "—";
    var a=Math.abs(v);
    if(a>=100) return v.toFixed(1);
    if(a>=10)  return v.toFixed(2);
    if(a>=1)   return v.toFixed(3);
    return v.toFixed(4);
  }}

  function draw(stat) {{
    if (!nHist && !nWaf) return;
    var traces = [];

    if (nHist) {{
      var xs     = HIST.map(function(_,i){{ return i; }});
      var yCtr   = HIST.map(function(d){{ return d[stat]; }});
      var yUp    = HIST.map(function(d){{ return d[stat]!=null ? d[stat]+d.std : null; }});
      var yDn    = HIST.map(function(d){{ return d[stat]!=null ? d[stat]-d.std : null; }});
      var xDates = HIST.map(function(d){{ return d.date; }});

      // Bande ±std
      traces.push({{ x:xs, y:yUp, type:"scatter", mode:"lines",
        line:{{width:0}}, showlegend:false, hoverinfo:"skip" }});
      traces.push({{ x:xs, y:yDn, type:"scatter", mode:"lines",
        fill:"tonexty", fillcolor:"rgba(24,95,165,0.10)",
        line:{{width:0}}, showlegend:false, hoverinfo:"skip" }});

      // Courbe historique
      var htpl = "<b>%{{customdata}}</b><br>"
        + stat + " : <b>%{{y:.4g}}</b>" + (unit?" "+unit:"")
        + "<br>± std : %{{text:.4g}}<extra>Historique</extra>";
      traces.push({{
        x:xs, y:yCtr,
        text: HIST.map(function(d){{ return d.std; }}),
        customdata: xDates,
        type:"scatter", mode:"lines+markers", name:"Historique",
        line:   {{color:"#185FA5", width:2.2, shape:"spline", smoothing:0.5}},
        marker: {{color:"#185FA5", size:5, symbol:"circle"}},
        hovertemplate: htpl,
      }});
    }}

    // Étoiles wafers
    if (nWaf) {{
      var wx  = WAFERS.map(function(_,i){{ return waferX(i); }});
      var wy  = WAFERS.map(function(d){{ return d.y; }});
      var wcd = WAFERS.map(function(d){{
        return HOVER_COLS.map(function(c){{
          var v=d[c];
          return (v!=null && typeof v==="number") ? fmtV(v) : (v||"—");
        }});
      }});
      var wtpl = HOVER_COLS.map(function(c,ci){{
        return "<b>"+c+":</b> %{{customdata["+ci+"]}}<br>";
      }}).join("") + "<extra>Lot en cours</extra>";

      traces.push({{
        x:wx, y:wy, customdata:wcd,
        type:"scatter", mode:"markers", name:"Lot en cours",
        marker:{{ symbol:"star", size:14, color:"#E8973A",
                  line:{{color:"#C97020", width:1}} }},
        hovertemplate: wtpl,
      }});
    }}

    // Ticks X
    var tickvals = HIST.map(function(_,i){{ return i; }});
    var ticktext = HIST.map(function(d){{ return d.date; }});
    if (nWaf) {{ tickvals.push(nHist+0.5); ticktext.push("Lot actuel"); }}

    // Plage Y
    var allY=[];
    HIST.forEach(function(d){{
      if(d[stat]!=null){{ allY.push(d[stat]+d.std); allY.push(d[stat]-d.std); }}
    }});
    WAFERS.forEach(function(d){{ if(d.y!=null) allY.push(d.y); }});
    var ymin=Math.min.apply(null,allY), ymax=Math.max.apply(null,allY);
    var pad=(ymax-ymin)*0.15||1;

    var shapes=[], annots=[];
    if (nHist && nWaf) {{
      shapes.push({{
        type:"line", xref:"x", yref:"paper",
        x0:nHist-0.3, y0:0, x1:nHist-0.3, y1:1,
        line:{{color:"rgba(10,36,99,0.18)", width:1, dash:"dot"}},
      }});
      annots.push({{
        x:nHist-0.2, y:0.98, xref:"x", yref:"paper",
        text:"lot actuel ▶", showarrow:false,
        font:{{family:"IBM Plex Mono,monospace", size:8, color:"rgba(10,36,99,0.35)"}},
        xanchor:"left", yanchor:"top",
      }});
    }}

    Plotly.react(sid+"_spark", traces, {{
      paper_bgcolor:"rgba(0,0,0,0)", plot_bgcolor:"rgba(0,0,0,0)",
      margin:{{t:4,b:34,l:38,r:8}}, height:sparkH,
      showlegend:false,
      xaxis:{{
        showgrid:false, zeroline:false, fixedrange:true,
        tickvals:tickvals, ticktext:ticktext,
        tickfont:{{family:"IBM Plex Mono,monospace",size:9,color:"#8B97BF"}},
        tickangle: -30,
      }},
      yaxis:{{
        showgrid:true, gridcolor:"rgba(180,190,210,0.22)",
        zeroline:false, tickfont:{{family:"IBM Plex Mono,monospace",size:9,color:"#8B97BF"}},
        tickformat:".3g", range:[ymin-pad, ymax+pad], fixedrange:true,
      }},
      shapes:shapes, annotations:annots,
      hoverlabel:{{
        bgcolor:"#0A2463", bordercolor:"rgba(10,36,99,0.2)",
        font:{{family:"IBM Plex Mono,monospace",size:11,color:"#fff"}},
        align:"left",
      }},
    }}, {{responsive:true, displaylogo:false, displayModeBar:false}});
  }}

  var sel=document.getElementById(sid+"_stat_sel");
  if(sel) sel.addEventListener("change", function(){{ draw(this.value); }});
  draw({json.dumps(self.default_stat)});
}})();
</script>"""

        return f"""
<div class="led-block" id="{sid}_wrap"
     style="padding:14px 16px 10px;display:flex;flex-direction:column;
            min-height:{self.height}px;box-sizing:border-box;">

  <!-- Label + dropdown -->
  <div style="display:flex;align-items:center;justify-content:space-between;
              margin-bottom:6px;">
    <div style="font-family:'IBM Plex Mono',monospace;font-size:9px;font-weight:600;
                color:#4A5580;text-transform:uppercase;letter-spacing:.12em;">
      {label_h}
      <span style="color:#1D9E75;font-size:10px;margin-left:3px;">▶</span>
    </div>
    <select id="{sid}_stat_sel"
      style="font-family:'IBM Plex Mono',monospace;font-size:9px;
             border:0.5px solid rgba(10,36,99,.2);border-radius:4px;
             padding:2px 18px 2px 6px;background:#fff;color:#0A2463;
             cursor:pointer;appearance:auto;">
      {opts_h}
    </select>
  </div>

  <!-- Grande valeur + delta -->
  <div style="display:flex;align-items:flex-end;gap:0;margin-bottom:8px;">
    <div style="font-family:'Syne',sans-serif;font-weight:700;font-size:30px;
                color:#0A2463;letter-spacing:-.02em;line-height:1;">
      {_h.escape(cur_str)}{unit_span}
    </div>
    {delta_h}
  </div>

  <!-- Sparkline -->
  <div style="flex:1;min-height:{spark_h}px;">
    <div id="{sid}_spark" style="width:100%;height:{spark_h}px;"></div>
  </div>

</div>
{js}
"""