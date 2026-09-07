"""
best_wafer_map_block.py — Bloc « Meilleure Wafer Map du lot en cours »
"""

from __future__ import annotations

import html as _h
import json

import numpy as np
import pandas as pd

from ..._helpers import Block, _safe_json, _is_vector_col
from ..data.data_mixin import DataMixin, DataArg


def _fmt(v, pct: bool = False) -> str:
    if v is None or (isinstance(v, float) and np.isnan(v)):
        return "—"
    if pct:
        return f"{v:.1f}%"
    if abs(v) >= 1000:
        return f"{v:,.0f}"
    if abs(v) >= 10:
        return f"{v:.2f}"
    return f"{v:.3f}"


class BestWaferMapBlock(DataMixin, Block):
    """Heatmap de la meilleure wafer du lot avec stats et navigation."""

    needs_plotly = True

    def __init__(
        self,
        data: DataArg,
        x_col: str = "X",
        y_col: str = "Y",
        wafer_col: str = "wafername",
        kpi_cols: list[str] | None = None,
        default_kpi: str = "",
        id_col: str = "",
        best_by: str = "max",
        goto_tab: str | None = "Mapping",
        colorscale: str = "Jet",
        height: int = 420,
        num: str = "—",
        title: str = "Meilleure Wafer Map – Lot en cours",
        subtitle: str = "",
    ):
        self._init_data(data)
        self.x_col         = x_col
        self.y_col         = y_col
        self.wafer_col     = wafer_col
        self._kpi_cols_arg = kpi_cols
        self.default_kpi   = default_kpi
        self.id_col        = id_col
        self.best_by       = best_by
        self.goto_tab      = goto_tab
        self.colorscale    = colorscale
        self.height        = height
        self.num           = num
        self.title         = title
        self.subtitle      = subtitle
        self._id           = f"bwm_{id(self)}"

    def _resolve_kpi_cols(self, df: pd.DataFrame) -> list[str]:
        if self._kpi_cols_arg:
            return [c for c in self._kpi_cols_arg if c in df.columns]
        return [
            c for c in df.columns
            if pd.api.types.is_numeric_dtype(df[c]) and not _is_vector_col(df[c])
        ][:8]

    def _best_wafer(self, df: pd.DataFrame, kpi: str) -> str:
        agg = df.groupby(self.wafer_col)[kpi].mean()
        if self.best_by == "min":
            return agg.idxmin()
        return agg.idxmax()

    def _build_js_data(self, df: pd.DataFrame, kpi_cols: list[str]) -> str:
        scalar_kpis = [
            c for c in kpi_cols
            if c in df.columns and not _is_vector_col(df[c])
        ]
        out = {}
        for wafer, grp in df.groupby(self.wafer_col):
            leds = []
            for _, row in grp.iterrows():
                rec: dict = {
                    "x": _safe_json(row.get(self.x_col, 0)),
                    "y": _safe_json(row.get(self.y_col, 0)),
                }
                if self.id_col and self.id_col in row.index:
                    rec["_id"] = str(row[self.id_col])
                for c in scalar_kpis:
                    try:
                        rec[c] = _safe_json(row[c])
                    except Exception:
                        pass
                leds.append(rec)
            out[str(wafer)] = {"leds": leds}
        return json.dumps(out, ensure_ascii=False)

    def _build_best_map(self, df: pd.DataFrame, kpi_cols: list[str]) -> dict:
        result = {}
        agg_fn = "max" if self.best_by == "max" else "min"
        for kpi in kpi_cols:
            if kpi not in df.columns:
                continue
            agg = df.groupby(self.wafer_col)[kpi].agg(agg_fn)
            best_w = agg.idxmax() if self.best_by == "max" else agg.idxmin()
            result[kpi] = str(best_w)
        return result

    def render(self, store=None) -> str:
        df       = self.resolve_df(store)
        sid      = self._id
        kpi_cols = self._resolve_kpi_cols(df)

        if not kpi_cols:
            return (
                f'<div class="led-block"><div class="led-block-header">'
                f'<span class="led-block-title">{_h.escape(self.title)}</span></div>'
                f'<p style="padding:16px;color:#888;font-size:11px;">Aucun KPI numérique trouvé.</p></div>'
            )

        default_kpi = self.default_kpi if self.default_kpi in kpi_cols else kpi_cols[0]
        best_map    = self._build_best_map(df, kpi_cols)
        js_data     = self._build_js_data(df, kpi_cols)

        _CS_MAP: dict[str, tuple[str, bool]] = {
            "viridis":  ("Viridis",  False),
            "plasma":   ("Plasma",   False),
            "inferno":  ("Inferno",  False),
            "magma":    ("Magma",    False),
            "cividis":  ("Cividis",  False),
            "turbo":    ("Turbo",    False),
            "hot":      ("Hot",      True),
            "cool":     ("Bluered",  False),
            "rainbow":  ("Rainbow",  False),
            "spectral": ("Spectral", False),
            "rdylgn":   ("RdYlGn",  False),
            "rdylbu":   ("RdYlBu",  False),
            "bwr":      ("RdBu",    False),
            "coolwarm": ("RdBu",    True),
            "jet":      ("Jet",     True),
            "blues":    ("Blues",   False),
            "reds":     ("Reds",    False),
            "greens":   ("Greens",  False),
            "ylgnbu":   ("YlGnBu",  False),
            "ylorrd":   ("YlOrRd",  False),
            "portland": ("Portland",False),
            "electric": ("Electric",False),
            "picnic":   ("Picnic",  False),
        }
        cs_raw   = self.colorscale.strip()
        cs_lower = cs_raw.lower()
        if cs_lower in _CS_MAP:
            cs_name, cs_reverse = _CS_MAP[cs_lower]
        else:
            cs_name, cs_reverse = cs_raw, False

        cs_js     = json.dumps(cs_name)
        cs_rev_js = "true" if cs_reverse else "false"

        num_h   = _h.escape(str(self.num))
        title_h = _h.escape(self.title)
        sub_h   = _h.escape(self.subtitle)

        kpi_opts_h = "".join(
            f'<option value="{_h.escape(k)}" {"selected" if k == default_kpi else ""}>'
            f'{_h.escape(k)}</option>'
            for k in kpi_cols
        )

        goto_btn_h = ""
        if self.goto_tab:
            goto_label = _h.escape(self.goto_tab)
            goto_btn_h = f"""
  <div style="text-align:center;padding:12px 0 4px;">
    <button
      onclick="lumiere_goto_tab('{goto_label}')"
      style="font-family:'IBM Plex Mono',monospace;font-size:11px;font-weight:500;
             color:#0A2463;background:transparent;border:1px solid rgba(10,36,99,.3);
             border-radius:6px;padding:7px 20px;cursor:pointer;
             transition:background .15s,color .15s;letter-spacing:.04em;"
      onmouseover="this.style.background='rgba(10,36,99,.07)'"
      onmouseout="this.style.background='transparent'">
      Voir toutes les wafer maps &nbsp;→
    </button>
  </div>"""

        compact      = self.height <= 350
        header_h     = 48
        stats_band_h = 44 if compact else 0
        goto_h       = 44 if self.goto_tab else 0
        map_h        = max(self.height - header_h - stats_band_h - goto_h, 100)

        # ── f-string JS : TOUT le JS est à l'intérieur de ce bloc ────────────
        js = f"""<script>
(function(){{
  var sid      = {json.dumps(sid)};
  var DATA     = {js_data};
  var BEST_MAP = {json.dumps(best_map)};
  var kpiCols  = {json.dumps(kpi_cols)};
  var CS       = {cs_js};
  var CS_REV   = {cs_rev_js};

  // ── Stats display ────────────────────────────────────────────────
  function fmt(v) {{
    if (v == null || isNaN(v)) return "—";
    var a = Math.abs(v);
    if (a >= 1000) return v.toFixed(0).replace(/\\B(?=(\\d{{3}})+(?!\\d))/g, ",");
    if (a >= 10)   return v.toFixed(2);
    return v.toFixed(3);
  }}

  function setStats(wafer, kpi) {{
    var leds = (DATA[wafer] || {{}}).leds || [];
    var vals = leds.map(function(d) {{ return d[kpi]; }}).filter(function(v) {{
      return v != null && !isNaN(v);
    }});
    var el = function(id) {{ return document.getElementById(sid + id); }};
    el("_stat_wafer").textContent = wafer;
    el("_stat_kpi").textContent   = kpi;
    if (!vals.length) {{
      el("_stat_mean").textContent = "—";
      el("_stat_min").textContent  = "—";
      el("_stat_max").textContent  = "—";
      el("_stat_std").textContent  = "—";
      return;
    }}
    var mean = vals.reduce(function(a, b) {{ return a + b; }}, 0) / vals.length;
    var mn   = Math.min.apply(null, vals);
    var mx   = Math.max.apply(null, vals);
    var std  = Math.sqrt(vals.reduce(function(s, v) {{
      return s + (v - mean) * (v - mean);
    }}, 0) / vals.length);
    el("_stat_mean").textContent = fmt(mean);
    el("_stat_min").textContent  = fmt(mn);
    el("_stat_max").textContent  = fmt(mx);
    el("_stat_std").textContent  = fmt(std);
  }}

  // ── Plotly scatter carrés (remplace heatmap) ─────────────────────
  function drawMap(wafer, kpi) {{
    var leds = (DATA[wafer] || {{}}).leds || [];
    var xs   = leds.map(function(d) {{ return d.x; }});
    var ys   = leds.map(function(d) {{ return d.y; }});
    var zs   = leds.map(function(d) {{ return d[kpi]; }});

    // Détection du pas de grille minimal (pitch)
    function minStep(arr) {{
      var uniq = arr.filter(function(v,i,a){{ return a.indexOf(v)===i; }})
                    .sort(function(a,b){{ return a-b; }});
      var step = Infinity;
      for (var i=1; i<uniq.length; i++) step = Math.min(step, uniq[i]-uniq[i-1]);
      return isFinite(step) ? step : 1;
    }}
    var xStep = minStep(xs);
    var yStep = minStep(ys);
    var pitch = Math.min(xStep, yStep);

    // customdata : [id, x, y, autresKpis...]
    var otherKpis = kpiCols.filter(function(k) {{ return k !== kpi; }});
    var customdata = leds.map(function(d) {{
      var row = [d._id || "", d.x, d.y];
      otherKpis.forEach(function(k) {{
        var v = d[k];
        row.push((v != null && !isNaN(v)) ? v : null);
      }});
      return row;
    }});

    // hovertemplate — marker.color au lieu de z (mode scatter)
    var tpl = "<b>%{{customdata[0]}}</b><br>";
    tpl += "X: %{{customdata[1]}} · Y: %{{customdata[2]}}<br>";
    tpl += "─────────────────<br>";
    tpl += "<b>" + kpi + ":</b> %{{marker.color:.4g}}<br>";
    otherKpis.forEach(function(k, i) {{
      tpl += k + ": %{{customdata[" + (3 + i) + "]:.4g}}<br>";
    }});
    tpl += "<extra></extra>";

    // Cercle wafer
    var xmin = Math.min.apply(null, xs), xmax = Math.max.apply(null, xs);
    var ymin = Math.min.apply(null, ys), ymax = Math.max.apply(null, ys);
    var cx   = (xmin + xmax) / 2, cy = (ymin + ymax) / 2;
    var rx   = (xmax - xmin) / 2 + pitch * 0.5;
    var ry   = (ymax - ymin) / 2 + pitch * 0.5;
    var wrad = Math.max(rx, ry);

    var trace = {{
      type: "scatter",
      mode: "markers",
      x: xs, y: ys,
      marker: {{
        symbol:       "square",
        size:         8,
        color:        zs,
        colorscale:   CS,
        reversescale: CS_REV,
        showscale:    true,
        line:         {{ width: 0 }},
        colorbar: {{
          thickness:    10,
          len:          0.85,
          x:            1.01,
          tickfont:     {{ family: "IBM Plex Mono,monospace", size: 9, color: "#4A5580" }},
          outlinewidth: 0,
          tickformat:   ".3g",
        }},
      }},
      customdata:    customdata,
      hovertemplate: tpl,
    }};

    var layout = {{
      paper_bgcolor: "rgba(0,0,0,0)",
      plot_bgcolor:  "rgba(0,0,0,0)",
      margin: {{ t: 10, b: 10, l: 10, r: 40 }},
      xaxis: {{
        range: [xmin - pitch, xmax + pitch],
        visible: false, showgrid: false, zeroline: false,
        fixedrange: true,
      }},
      yaxis: {{
        range: [ymin - pitch, ymax + pitch],
        visible: false, showgrid: false, zeroline: false,
        fixedrange: true,
      }},
      shapes: [{{
        // Cercle en coordonnées paper (0-1) → toujours rond quelle que soit l'échelle
        type: "circle", xref: "paper", yref: "paper",
        x0: 0.02, y0: 0.02, x1: 0.98, y1: 0.98,
        line: {{ color: "rgba(10,36,99,0.45)", width: 2, dash: "solid" }},
        fillcolor: "rgba(0,0,0,0)",
        layer: "above",
      }}],
      hoverlabel: {{
        bgcolor:     "#0A2463",
        bordercolor: "rgba(10,36,99,0.2)",
        font:        {{ family: "IBM Plex Mono,monospace", size: 11, color: "#fff" }},
        align:       "left",
      }},
    }};

    var cfg = {{
      responsive: true, displaylogo: false,
      modeBarButtonsToRemove: ["autoScale2d","toggleSpikelines","sendDataToCloud","lasso2d","select2d"],
    }};

    // Taille des marqueurs : px disponibles / nb de cellules sur chaque axe
    // Axes indépendants → on calcule séparément X et Y, on prend le min
    function calcSize(gd) {{
      var plotW = gd.offsetWidth  - 10 - 40;
      var plotH = gd.offsetHeight - 10 - 10;
      if (plotW <= 0 || plotH <= 0) return 8;
      var xRange = (xmax - xmin) + 2 * pitch;
      var yRange = (ymax - ymin) + 2 * pitch;
      var szX = plotW / xRange * pitch;
      var szY = plotH / yRange * pitch;
      return Math.max(3, Math.min(szX, szY) * 0.92);
    }}

    Plotly.react(sid + "_plot", [trace], layout, cfg).then(function() {{
      var gd = document.getElementById(sid + "_plot");
      if (!gd) return;
      Plotly.restyle(sid + "_plot", {{ "marker.size": calcSize(gd) }}, [0]);

      if (window[sid + "_resizeObs"]) window[sid + "_resizeObs"].disconnect();
      window[sid + "_resizeObs"] = new ResizeObserver(function() {{
        var gd2 = document.getElementById(sid + "_plot");
        if (gd2) Plotly.restyle(sid + "_plot", {{ "marker.size": calcSize(gd2) }}, [0]);
      }});
      window[sid + "_resizeObs"].observe(gd);
    }});
  }}

  // ── KPI switch ───────────────────────────────────────────────────
  window[sid + "_onKpiChange"] = function(kpi) {{
    var bestWafer = BEST_MAP[kpi] || Object.keys(DATA)[0] || "";
    setStats(bestWafer, kpi);
    drawMap(bestWafer, kpi);
  }};

  // ── Init ─────────────────────────────────────────────────────────
  var defaultKpi = {json.dumps(default_kpi)};
  var initWafer  = BEST_MAP[defaultKpi] || Object.keys(DATA)[0] || "";
  setStats(initWafer, defaultKpi);
  drawMap(initWafer, defaultKpi);

  // ── lumiere_goto_tab (idempotent) ────────────────────────────────
  if (!window.lumiere_goto_tab) {{
    window.lumiere_goto_tab = function(label) {{
      var lower = label.toLowerCase();
      var found = false;
      document.querySelectorAll('.rb-tab-btn').forEach(function(btn) {{
        if (!found && btn.textContent.trim().toLowerCase().indexOf(lower) !== -1) {{
          found = true;
          btn.click();
          setTimeout(function() {{
            btn.scrollIntoView({{ behavior: 'smooth', block: 'nearest' }});
          }}, 50);
        }}
      }});
    }};
  }}
}})();
</script>"""

        # ── Stats HTML ────────────────────────────────────────────────────────
        _lbl      = ("font-family:'IBM Plex Mono',monospace;font-size:8px;font-weight:500;"
                     "color:var(--slate-400);text-transform:uppercase;letter-spacing:.12em;"
                     "margin-bottom:3px;")
        _val_name = ("font-family:'Syne',sans-serif;font-weight:700;font-size:13px;"
                     "color:var(--navy);line-height:1.2;")
        _val_kpi  = ("font-family:'IBM Plex Mono',monospace;font-size:10px;color:var(--navy);")
        _val_mean = ("font-family:'Syne',sans-serif;font-weight:700;font-size:20px;"
                     "color:var(--navy);line-height:1.1;")
        _val_sm   = ("font-family:'IBM Plex Mono',monospace;font-size:11px;color:var(--navy);")

        if compact:
            stats_html = f"""
  <div style="display:flex;align-items:stretch;border-bottom:1px solid var(--border);flex-wrap:wrap;">
    <div style="padding:6px 14px;border-right:1px solid var(--border);min-width:0;flex:0 0 auto;">
      <div style="{_lbl}">Wafer</div>
      <div id="{sid}_stat_wafer" style="{_val_name}font-size:11px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;max-width:90px;">—</div>
    </div>
    <div style="padding:6px 14px;border-right:1px solid var(--border);flex:0 0 auto;">
      <div style="{_lbl}">Metric</div>
      <div id="{sid}_stat_kpi" style="{_val_kpi}white-space:nowrap;overflow:hidden;text-overflow:ellipsis;max-width:80px;">—</div>
    </div>
    <div style="padding:6px 14px;border-right:1px solid var(--border);flex:0 0 auto;">
      <div style="{_lbl}">Moyenne</div>
      <div id="{sid}_stat_mean" style="{_val_sm}font-weight:700;">—</div>
    </div>
    <div style="padding:6px 14px;border-right:1px solid var(--border);flex:0 0 auto;">
      <div style="{_lbl}">Min / Max</div>
      <div style="{_val_sm}"><span id="{sid}_stat_min">—</span>&nbsp;/&nbsp;<span id="{sid}_stat_max">—</span></div>
    </div>
    <div style="padding:6px 14px;flex:0 0 auto;">
      <div style="{_lbl}">Std Dev</div>
      <div id="{sid}_stat_std" style="{_val_sm}">—</div>
    </div>
  </div>"""
            body_html = f"""
  {stats_html}
  <div style="padding:4px 2px 2px 2px;">
    <div id="{sid}_plot" style="width:100%;height:{map_h}px;"></div>
  </div>"""
        else:
            body_html = f"""
  <div style="display:grid;grid-template-columns:148px 1fr;gap:0;">
    <div style="padding:20px 16px 20px 20px;display:flex;flex-direction:column;
                gap:18px;border-right:1px solid var(--border);">
      <div>
        <div style="{_lbl}">Wafer</div>
        <div id="{sid}_stat_wafer" style="{_val_name}word-break:break-all;">—</div>
      </div>
      <div>
        <div style="{_lbl}">Metric</div>
        <div id="{sid}_stat_kpi" style="{_val_kpi}">—</div>
      </div>
      <div>
        <div style="{_lbl}">Moyenne</div>
        <div id="{sid}_stat_mean" style="{_val_mean}">—</div>
      </div>
      <div>
        <div style="{_lbl}">Min / Max</div>
        <div style="{_val_sm}">
          <span id="{sid}_stat_min">—</span>&nbsp;/&nbsp;<span id="{sid}_stat_max">—</span>
        </div>
      </div>
      <div>
        <div style="{_lbl}">Std Dev</div>
        <div id="{sid}_stat_std" style="{_val_sm}">—</div>
      </div>
    </div>
    <div style="min-height:{map_h}px;overflow:hidden;">
      <div id="{sid}_plot" style="width:100%;height:{map_h}px;"></div>
    </div>
  </div>"""

        html = f"""
<div class="led-block" id="{sid}_wrap">
  <div class="led-block-header">
    <span class="led-block-num">{num_h}</span>
    <span class="led-block-title">{title_h}</span>
    <span class="led-block-sub">{sub_h}</span>
    <div style="margin-left:auto;display:flex;align-items:center;gap:6px;">
      <select
        id="{sid}_kpi_sel"
        onchange="window['{sid}_onKpiChange'](this.value)"
        style="font-family:'IBM Plex Mono',monospace;font-size:10px;
               border:0.5px solid rgba(10,36,99,.25);border-radius:5px;
               padding:3px 22px 3px 8px;background:#fff;color:#0A2463;
               cursor:pointer;appearance:auto;">
        {kpi_opts_h}
      </select>
    </div>
  </div>
  <div class="led-block-rule"></div>
  {body_html}
  {goto_btn_h}
</div>
{js}
"""
        return html