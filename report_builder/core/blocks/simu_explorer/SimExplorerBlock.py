from __future__ import annotations
import json
import html as _h
import numpy as np
import pandas as pd
from ..._helpers import Block, _safe_json
from ..data.data_mixin import DataMixin
from ..types import DataArg


class SimExplorerBlock(DataMixin, Block):
    """
    Explorateur de résultats de simulation paramétrique.

    Chaque ligne du DataFrame correspond à une combinaison de paramètres.
    Le bloc génère :
      - des sliders discrets (snap sur les valeurs uniques) pour chaque colonne de ``slider_cols``
      - une card affichant les valeurs de ``card_cols`` pour la ligne sélectionnée
      - un graphe Plotly du vecteur ``vector_col`` (ex : far-field, spectre)

    Parameters
    ----------
    data          : DataArg      — DataFrame ou clé registre
    slider_cols   : list[str]    — colonnes scalaires → sliders (sweep params)
    card_cols     : list[str]    — colonnes scalaires affichées dans la card résultat
    vector_col    : str          — colonne contenant le vecteur à tracer (obligatoire)
    vector_x_col  : str          — colonne contenant les abscisses du vecteur (optionnel)
    vector_x_label: str          — label axe X du graphe
    vector_y_label: str          — label axe Y du graphe
    log_y         : bool         — échelle log sur Y (défaut False)
    height        : int          — hauteur du graphe en px
    num / title / subtitle       — identifiant visuel du bloc
    """

    needs_plotly = True

    def __init__(
        self,
        data: DataArg,
        slider_cols: list[str],
        card_cols: list[str],
        vector_col: str,
        vector_x_col: str = "",
        vector_x_label: str = "",
        vector_y_label: str = "",
        log_y: bool = False,
        height: int = 380,
        num: str = "01",
        title: str = "Simulation Explorer",
        subtitle: str = "",
    ):
        self._init_data(data)
        self.slider_cols   = slider_cols
        self.card_cols     = card_cols
        self.vector_col    = vector_col
        self.vector_x_col  = vector_x_col
        self.vector_x_label = vector_x_label or vector_x_col or "Index"
        self.vector_y_label = vector_y_label or vector_col
        self.log_y         = log_y
        self.height        = height
        self.num           = num
        self.title         = title
        self.subtitle      = subtitle
        self._id           = f"simex_{id(self)}"

    # ── sérialisation ────────────────────────────────────────────────────────

    def _build_js_data(self, df: pd.DataFrame) -> str:
        records = []
        for _, row in df.iterrows():
            rec: dict = {}
            # sliders
            for c in self.slider_cols:
                if c in row.index:
                    rec[c] = _safe_json(row[c])
            # card
            for c in self.card_cols:
                if c in row.index:
                    v = row[c]
                    if isinstance(v, (list, np.ndarray)):
                        rec[c] = _safe_json(v[0]) if len(v) else None
                    else:
                        rec[c] = _safe_json(v)
            # vecteur Y
            if self.vector_col in row.index:
                v = row[self.vector_col]
                rec["_vy"] = [_safe_json(x) for x in v] if isinstance(v, (list, np.ndarray)) else []
            else:
                rec["_vy"] = []
            # vecteur X
            if self.vector_x_col and self.vector_x_col in row.index:
                v = row[self.vector_x_col]
                rec["_vx"] = [_safe_json(x) for x in v] if isinstance(v, (list, np.ndarray)) else []
            else:
                rec["_vx"] = []
            records.append(rec)
        return json.dumps(records)

    def _build_slider_meta(self, df: pd.DataFrame) -> str:
        """Valeurs uniques triées pour chaque slider_col."""
        meta: dict = {}
        for c in self.slider_cols:
            if c not in df.columns:
                continue
            vals = sorted(df[c].dropna().unique().tolist())
            meta[c] = [_safe_json(v) for v in vals]
        return json.dumps(meta)

    # ── rendu ────────────────────────────────────────────────────────────────

    def render(self, store=None) -> str:
        df        = self.resolve_df(store)
        sid       = self._id
        _data     = self._build_js_data(df)
        data_init = f"var DATA = {_data};"
        meta_json = self._build_slider_meta(df)
        log_y_js  = "true" if self.log_y else "false"
        h         = self.height
        title_h   = _h.escape(self.title)
        sub_h     = _h.escape(self.subtitle)
        num_h     = _h.escape(self.num)
        xl        = _h.escape(self.vector_x_label)
        yl        = _h.escape(self.vector_y_label)

        # labels card_cols sérialisés pour JS
        card_cols_js   = json.dumps(self.card_cols)
        slider_cols_js = json.dumps(self.slider_cols)

        return f"""
<div class="led-block" id="{sid}_wrap">
  <div class="led-block-header">
    <span class="led-block-num">{num_h}</span>
    <span class="led-block-title">{title_h}</span>
    <span class="led-block-sub">{sub_h}</span>
  </div>
  <div class="led-block-rule"></div>

  <div class="simex-layout" id="{sid}_layout">

    <!-- ── Colonne gauche : sliders ─────────────────────── -->
    <div class="simex-sliders" id="{sid}_sliders_col">
      <div class="simex-sliders-title">PARAMÈTRES</div>
      <div id="{sid}_sliders_inner"></div>
    </div>

    <!-- ── Colonne droite : card + graphe ───────────────── -->
    <div class="simex-right">

      <!-- card résultat -->
      <div class="simex-card" id="{sid}_card">
        <div class="simex-card-header">
          <span class="led-block-num">↳</span>
          <span class="simex-card-label" id="{sid}_card_label">— sélection —</span>
          <span class="simex-match-badge" id="{sid}_match_badge"></span>
        </div>
        <div class="simex-kpis" id="{sid}_kpis"></div>
      </div>

      <!-- bouton ajouter à la comparaison -->
      <div style="margin-top:8px; display:flex; gap:8px; align-items:center;">
        <button class="slt-btn slt-btn--gold" id="{sid}_btn_add" onclick="{sid}_addToCompare()">
          ＋ AJOUTER À LA COMPARAISON
        </button>
        <span class="simex-cmp-hint" id="{sid}_cmp_hint"></span>
      </div>

      <!-- graphe vecteur -->
      <div id="{sid}_plot" style="height:{h}px; margin-top:10px;"></div>

    </div>
  </div>

  <!-- ── Panneau comparaison ── -->
  <div class="simex-compare-panel" id="{sid}_cmp_panel" style="display:none; margin-top:18px;">
    <div class="simex-compare-header">
      <span class="led-block-num">⇄</span>
      <span class="simex-sliders-title" style="margin:0;">COMPARAISON</span>
      <button class="slt-btn" style="margin-left:auto;" onclick="{sid}_clearCompare()">✕ TOUT EFFACER</button>
    </div>
    <div class="simex-compare-body">
      <div class="simex-compare-legend" id="{sid}_cmp_legend"></div>
      <div id="{sid}_cmp_plot" style="height:{h}px; flex:1;"></div>
    </div>
  </div>
</div>

<style>
/* ── SimExplorerBlock layout ── */
#{sid}_wrap .simex-layout {{
  display: grid;
  grid-template-columns: 260px 1fr;
  gap: 18px;
  margin-top: 12px;
}}
@media (max-width: 900px) {{
  #{sid}_wrap .simex-layout {{ grid-template-columns: 1fr; }}
}}
#{sid}_wrap .simex-sliders {{
  background: #F8F9FD;
  border: 1px solid #E4E8F4;
  border-radius: 8px;
  padding: 14px 16px;
}}
#{sid}_wrap .simex-sliders-title {{
  font-family: "IBM Plex Mono", monospace;
  font-size: 10px;
  font-weight: 700;
  letter-spacing: .12em;
  color: #0A2463;
  margin-bottom: 14px;
}}
#{sid}_wrap .simex-slider-group {{
  margin-bottom: 16px;
}}
#{sid}_wrap .simex-slider-label {{
  font-family: "IBM Plex Mono", monospace;
  font-size: 10px;
  color: #4A5580;
  margin-bottom: 4px;
  display: flex;
  justify-content: space-between;
}}
#{sid}_wrap .simex-slider-label span {{
  color: #D4AF37;
  font-weight: 700;
}}
#{sid}_wrap .simex-slider-input {{
  width: 100%;
  accent-color: #D4AF37;
  cursor: pointer;
}}
#{sid}_wrap .simex-slider-ticks {{
  display: flex;
  justify-content: space-between;
  font-family: "IBM Plex Mono", monospace;
  font-size: 8px;
  color: #9AA3BF;
  margin-top: 2px;
}}
#{sid}_wrap .simex-str-btns {{
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
  margin-top: 4px;
}}
#{sid}_wrap .simex-str-btn {{
  font-family: "IBM Plex Mono", monospace;
  font-size: 9px;
  padding: 3px 8px;
  border-radius: 4px;
  border: 1px solid #E4E8F4;
  background: #fff;
  color: #4A5580;
  cursor: pointer;
  transition: all .15s;
}}
#{sid}_wrap .simex-str-btn:hover {{
  border-color: #D4AF37;
  color: #D4AF37;
}}
#{sid}_wrap .simex-str-btn.active {{
  background: #D4AF3722;
  border-color: #D4AF37;
  color: #D4AF37;
  font-weight: 700;
}}
/* card */
#{sid}_wrap .simex-card {{
  background: #F8F9FD;
  border: 1px solid #E4E8F4;
  border-radius: 8px;
  padding: 12px 16px;
}}
#{sid}_wrap .simex-card-header {{
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 10px;
}}
#{sid}_wrap .simex-card-label {{
  font-family: "IBM Plex Mono", monospace;
  font-size: 11px;
  color: #0A2463;
  font-weight: 600;
  flex: 1;
}}
#{sid}_wrap .simex-match-badge {{
  font-family: "IBM Plex Mono", monospace;
  font-size: 9px;
  padding: 2px 8px;
  border-radius: 12px;
  background: #D4AF3722;
  color: #D4AF37;
  font-weight: 700;
}}
#{sid}_wrap .simex-kpis {{
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
}}
#{sid}_wrap .simex-kpi {{
  background: #fff;
  border: 1px solid #E4E8F4;
  border-radius: 6px;
  padding: 7px 12px;
  min-width: 100px;
  flex: 1;
}}
#{sid}_wrap .simex-kpi-label {{
  font-family: "IBM Plex Mono", monospace;
  font-size: 9px;
  color: #9AA3BF;
  letter-spacing: .06em;
  text-transform: uppercase;
  margin-bottom: 3px;
}}
#{sid}_wrap .simex-kpi-value {{
  font-family: "IBM Plex Mono", monospace;
  font-size: 15px;
  font-weight: 700;
  color: #0A2463;
}}
#{sid}_wrap .simex-kpi-value.highlight {{
  color: #D4AF37;
}}
#{sid}_wrap .simex-compare-panel {{
  background: #F8F9FD;
  border: 1px solid #E4E8F4;
  border-radius: 8px;
  padding: 14px 16px;
}}
#{sid}_wrap .simex-compare-header {{
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 12px;
}}
#{sid}_wrap .simex-compare-body {{
  display: grid;
  grid-template-columns: 220px 1fr;
  gap: 14px;
  align-items: start;
}}
@media (max-width: 700px) {{
  #{sid}_wrap .simex-compare-body {{ grid-template-columns: 1fr; }}
}}
#{sid}_wrap .simex-compare-legend {{
  display: flex;
  flex-direction: column;
  gap: 6px;
}}
#{sid}_wrap .simex-cmp-entry {{
  display: flex;
  align-items: center;
  gap: 8px;
  background: #fff;
  border: 1px solid #E4E8F4;
  border-radius: 6px;
  padding: 6px 10px;
  font-family: "IBM Plex Mono", monospace;
  font-size: 9px;
  color: #4A5580;
}}
#{sid}_wrap .simex-cmp-swatch {{
  width: 12px; height: 12px;
  border-radius: 2px;
  flex-shrink: 0;
}}
#{sid}_wrap .simex-cmp-entry-label {{
  flex: 1;
  line-height: 1.4;
}}
#{sid}_wrap .simex-cmp-del {{
  background: none;
  border: none;
  cursor: pointer;
  color: #9AA3BF;
  font-size: 11px;
  padding: 0 2px;
  line-height: 1;
}}
#{sid}_wrap .simex-cmp-del:hover {{ color: #EF4444; }}
#{sid}_wrap .simex-cmp-hint {{
  font-family: "IBM Plex Mono", monospace;
  font-size: 9px;
  color: #9AA3BF;
}}
#{sid}_wrap .slt-btn--gold {{
  background: #D4AF3722;
  color: #D4AF37;
  border-color: #D4AF3755;
  font-weight: 700;
}}
#{sid}_wrap .slt-btn--gold:hover {{
  background: #D4AF3733;
}}
</style>

<script>
(function(){{
  {data_init}
  var SMETA       = {meta_json};    /* col → [val0, val1, …] */
  var CARD_COLS   = {card_cols_js};
  var SLIDER_COLS = {slider_cols_js};
  var sid         = "{sid}";
  var logY        = {log_y_js};

  var GSTYLE = {{gridcolor:"#E4E8F4",linecolor:"#E4E8F4",zerolinecolor:"#E4E8F4"}};
  var PLYCFG = {{responsive:true,displaylogo:false,
    modeBarButtonsToRemove:["autoScale2d","toggleSpikelines","sendDataToCloud"]}};

  /* ── État courant des sliders : col → index dans SMETA[col] ── */
  var sliderState = {{}};
  SLIDER_COLS.forEach(function(c) {{
    sliderState[c] = 0;   /* démarre sur la première valeur */
  }});

  /* ── Construire les sliders ── */
  /* ── Détecter si une colonne est numérique ── */
  function isNumericCol(col) {{
    var vals = SMETA[col];
    if (!vals || !vals.length) return false;
    return vals.every(function(v) {{ return v !== null && v !== "" && !isNaN(+v); }});
  }}

  (function buildSliders() {{
    var container = document.getElementById(sid + "_sliders_inner");
    SLIDER_COLS.forEach(function(col) {{
      var vals = SMETA[col];
      if (!vals || !vals.length) return;
      var grp = document.createElement("div");
      grp.className = "simex-slider-group";

      /* label */
      var lbl = document.createElement("div");
      lbl.className = "simex-slider-label";
      lbl.innerHTML = col + ' <span id="' + sid + '_lbl_' + col + '">' + vals[0] + '</span>';
      grp.appendChild(lbl);

      if (isNumericCol(col)) {{
        /* ── Numérique : input range ── */
        var inp = document.createElement("input");
        inp.type  = "range";
        inp.className = "simex-slider-input";
        inp.min   = 0;
        inp.max   = vals.length - 1;
        inp.step  = 1;
        inp.value = 0;
        inp.id    = sid + "_sl_" + col;
        inp.oninput = (function(c, v) {{
          return function() {{
            sliderState[c] = +this.value;
            document.getElementById(sid + "_lbl_" + c).textContent = v[+this.value];
            updateDisplay();
          }};
        }})(col, vals);
        grp.appendChild(inp);

        /* ticks min/max */
        var ticks = document.createElement("div");
        ticks.className = "simex-slider-ticks";
        var tickCount = Math.min(vals.length, 5);
        var step = tickCount > 1 ? (vals.length - 1) / (tickCount - 1) : 0;
        var ticksHTML = "";
        for (var t = 0; t < tickCount; t++) {{
          ticksHTML += "<span>" + vals[Math.round(t * step)] + "</span>";
        }}
        ticks.innerHTML = ticksHTML;
        grp.appendChild(ticks);

      }} else {{
        /* ── Catégoriel : boutons toggle ── */
        var btnWrap = document.createElement("div");
        btnWrap.className = "simex-str-btns";
        vals.forEach(function(v, vi) {{
          var btn = document.createElement("button");
          btn.className = "simex-str-btn" + (vi === 0 ? " active" : "");
          btn.textContent = v;
          btn.onclick = (function(c, idx, vlist) {{
            return function() {{
              sliderState[c] = idx;
              document.getElementById(sid + "_lbl_" + c).textContent = vlist[idx];
              btnWrap.querySelectorAll(".simex-str-btn").forEach(function(b, bi) {{
                b.classList.toggle("active", bi === idx);
              }});
              updateDisplay();
            }};
          }})(col, vi, vals);
          btnWrap.appendChild(btn);
        }});
        grp.appendChild(btnWrap);
      }}

      container.appendChild(grp);
    }});
  }})();

  /* ── Trouver la ligne la plus proche des valeurs slider ── */
  function findBestRow() {{
    var bestIdx   = 0;
    var bestScore = Infinity;
    DATA.forEach(function(row, ri) {{
      var score = 0;
      SLIDER_COLS.forEach(function(col) {{
        if (!SMETA[col] || !SMETA[col].length) return;  /* col absente du df */
        var target = SMETA[col][sliderState[col] || 0];
        var val    = row[col];
        if (val == null || target == null) return;
        if (isNumericCol(col)) {{
          var diff = Math.abs(+val - +target);
          score += diff * diff;
        }} else {{
          /* catégoriel : pénalité binaire */
          if (String(val) !== String(target)) score += 1e6;
        }}
      }});
      if (score < bestScore) {{ bestScore = score; bestIdx = ri; }}
    }});
    return {{ idx: bestIdx, score: bestScore }};
  }}

  /* ── Mise à jour card + graphe ── */
  function updateDisplay() {{
    var result = findBestRow();
    var row    = DATA[result.idx];

    /* label */
    var parts = SLIDER_COLS.filter(function(c) {{
      return SMETA[c] && SMETA[c].length;
    }}).map(function(c) {{
      return c + "=" + SMETA[c][sliderState[c] || 0];
    }});
    document.getElementById(sid + "_card_label").textContent = parts.join("  ·  ");
    document.getElementById(sid + "_match_badge").textContent =
      result.score < 1e-9 ? "EXACT" : "≈ PROCHE";

    /* KPIs */
    var kpiWrap = document.getElementById(sid + "_kpis");
    kpiWrap.innerHTML = "";
    CARD_COLS.forEach(function(col, ci) {{
      var v = row[col];
      if (v == null) return;
      var kpi = document.createElement("div");
      kpi.className = "simex-kpi";
      /* formatter */
      var disp = (typeof v === "number")
        ? (Math.abs(v) >= 100 ? v.toFixed(2) : v.toPrecision(4))
        : String(v);
      kpi.innerHTML =
        '<div class="simex-kpi-label">' + _h(col) + '</div>' +
        '<div class="simex-kpi-value' + (ci < 3 ? " highlight" : "") + '">' + disp + '</div>';
      kpiWrap.appendChild(kpi);
    }});

    /* graphe polaire */
    var vy = row._vy || [];
    var vx = row._vx && row._vx.length ? row._vx : vy.map(function(_, i) {{ return i; }});
    /* conversion rad → deg si les valeurs sont dans [-π, π] */
    var thetaDeg = vx.map(function(v) {{
      return (Math.abs(v) <= Math.PI + 0.01) ? v * 180 / Math.PI : v;
    }});

    /* ── Symétrie + clip [-90°, 90°] ──
       physique : -90=gauche  0=haut  +90=droite
       Plotly   :   0=droite 90=haut  180=gauche  (counterclockwise, rotation=0)
       mapping  : plotly_theta = 90 - physics_theta
       On moyenne r(+θ) et r(-θ) pour forcer la symétrie.              */
    var posMap = {{}}, negMap = {{}};
    for (var i = 0; i < thetaDeg.length; i++) {{
      var td = thetaDeg[i], rv = vy[i];
      if (Math.abs(td) > 90.5) continue;
      var key = Math.round(Math.abs(td));
      if (td >= 0) posMap[key] = rv;
      else         negMap[key] = rv;
    }}
    var allKeys = Array.from(new Set(
      Object.keys(posMap).concat(Object.keys(negMap))
    )).map(Number).sort(function(a,b){{return a-b;}});

    /* reconstructions : -90→0→+90 en physique → 180→90→0 en Plotly */
    var thetaPlotly = [], rSym = [];
    /* côté gauche : physique -90 → -5  (plotly 180 → 95) */
    for (var ki = allKeys.length-1; ki >= 1; ki--) {{
      var k = allKeys[ki];
      var rP = posMap[k] != null ? posMap[k] : 0;
      var rN = negMap[k] != null ? negMap[k] : 0;
      var rAvg = (posMap[k] != null && negMap[k] != null) ? (rP+rN)/2 : (rP||rN);
      thetaPlotly.push(90 + k);   /* physique -k → plotly 90+k */
      rSym.push(rAvg);
    }}
    /* centre : physique 0 → plotly 90 */
    var r0 = posMap[0] != null ? posMap[0] : 0;
    thetaPlotly.push(90); rSym.push(r0);
    /* côté droit : physique 5 → 90  (plotly 85 → 0) */
    for (var ki = 1; ki < allKeys.length; ki++) {{
      var k = allKeys[ki];
      var rP = posMap[k] != null ? posMap[k] : 0;
      var rN = negMap[k] != null ? negMap[k] : 0;
      var rAvg = (posMap[k] != null && negMap[k] != null) ? (rP+rN)/2 : (rP||rN);
      thetaPlotly.push(90 - k);   /* physique +k → plotly 90-k */
      rSym.push(rAvg);
    }}

    /* cache pour le bouton "ajouter à la comparaison" */
    _lastTheta = thetaPlotly.slice();
    _lastR     = rSym.slice();

    var traces = [{{
      type: "scatterpolar", mode: "lines",
      theta: thetaPlotly, r: rSym,
      line: {{ color: "#D4AF37", width: 2 }},
      fill: "toself",
      fillcolor: "rgba(212,175,55,0.10)",
      hovertemplate: "θ: %{{theta:.0f}}°<br>{yl}: %{{r:.4f}}<extra></extra>",
    }}];
    var layout = {{
      paper_bgcolor: "rgba(0,0,0,0)",
      font: {{ family: "IBM Plex Mono, monospace", color: "#4A5580", size: 10 }},
      margin: {{ t: 20, r: 20, b: 20, l: 20 }},
      showlegend: false,
      polar: {{
        bgcolor: "#F8F9FD",
        sector: [0, 180],   /* demi-cercle supérieur en coordonnées Plotly */
        angularaxis: {{
          direction: "counterclockwise",
          rotation: 0,
          tickfont: {{ size: 9, family: "IBM Plex Mono" }},
          gridcolor: "#E4E8F4",
          linecolor: "#E4E8F4",
          thetaunit: "degrees",
          /* ticks en degrés physiques : 90-plotly */
          tickvals: [0, 30, 60, 90, 120, 150, 180],
          ticktext: ["90°","60°","30°","0°","-30°","-60°","-90°"],
        }},
        radialaxis: {{
          tickfont: {{ size: 9, family: "IBM Plex Mono" }},
          gridcolor: "#E4E8F4",
          linecolor: "#E4E8F4",
          angle: 90,
          tickangle: -90,
        }},
      }},
      hoverlabel: {{
        bgcolor: "#0A2463", bordercolor: "#D4AF37",
        font: {{ family: "IBM Plex Mono", size: 10, color: "white" }},
      }},
    }};
    if (document.getElementById(sid + "_plot").data) {{
      Plotly.react(sid + "_plot", traces, layout, PLYCFG);
    }} else {{
      Plotly.newPlot(sid + "_plot", traces, layout, PLYCFG);
    }}
  }}

  /* escape helper (inline, évite dépendance) */
  function _h(s) {{
    return String(s)
      .replace(/&/g,"&amp;").replace(/</g,"&lt;")
      .replace(/>/g,"&gt;").replace(/"/g,"&quot;");
  }}

  /* ── Comparaison ── */
  var CMP_COLORS = ["#3B82F6","#EF4444","#10B981","#8B5CF6","#F59E0B","#EC4899","#06B6D4","#F97316","#84CC16","#6366F1"];
  var cmpStore = [];   /* [{{ label, theta, r, color }}] */

  var _lastTheta = [], _lastR = [];   /* cache de la courbe courante */

  function polarLayout() {{
    return {{
      paper_bgcolor: "rgba(0,0,0,0)",
      font: {{ family: "IBM Plex Mono, monospace", color: "#4A5580", size: 10 }},
      margin: {{ t: 20, r: 20, b: 20, l: 20 }},
      showlegend: false,
      polar: {{
        bgcolor: "#F8F9FD",
        sector: [0, 180],
        angularaxis: {{
          direction: "counterclockwise", rotation: 0,
          tickfont: {{ size: 9, family: "IBM Plex Mono" }},
          gridcolor: "#E4E8F4", linecolor: "#E4E8F4",
          thetaunit: "degrees",
          tickvals: [0,30,60,90,120,150,180],
          ticktext: ["90°","60°","30°","0°","-30°","-60°","-90°"],
        }},
        radialaxis: {{
          tickfont: {{ size: 9, family: "IBM Plex Mono" }},
          gridcolor: "#E4E8F4", linecolor: "#E4E8F4",
          angle: 90, tickangle: -90,
        }},
      }},
      hoverlabel: {{
        bgcolor: "#0A2463", bordercolor: "#D4AF37",
        font: {{ family: "IBM Plex Mono", size: 10, color: "white" }},
      }},
    }};
  }}

  function renderComparePanel() {{
    var panel  = document.getElementById(sid + "_cmp_panel");
    var legend = document.getElementById(sid + "_cmp_legend");
    if (!cmpStore.length) {{ panel.style.display = "none"; return; }}
    panel.style.display = "block";

    /* légende */
    legend.innerHTML = "";
    cmpStore.forEach(function(entry, i) {{
      var div = document.createElement("div");
      div.className = "simex-cmp-entry";
      var swatch = document.createElement("div");
      swatch.className = "simex-cmp-swatch";
      swatch.style.background = entry.color;
      var lbl = document.createElement("span");
      lbl.className = "simex-cmp-entry-label";
      lbl.textContent = entry.label;
      var del = document.createElement("button");
      del.className = "simex-cmp-del";
      del.textContent = "✕";
      del.title = "Retirer";
      del.onclick = (function(idx) {{
        return function() {{ cmpStore.splice(idx, 1); renderComparePanel(); }};
      }})(i);
      div.appendChild(swatch); div.appendChild(lbl); div.appendChild(del);
      legend.appendChild(div);
    }});

    /* traces */
    var traces = cmpStore.map(function(entry) {{
      return {{
        type: "scatterpolar", mode: "lines",
        theta: entry.theta, r: entry.r,
        line: {{ color: entry.color, width: 2 }},
        fill: "none",
        name: entry.label,
        hovertemplate: entry.label + "<br>θ: %{{theta:.0f}}°<br>r: %{{r:.4f}}<extra></extra>",
      }};
    }});
    var plotEl = document.getElementById(sid + "_cmp_plot");
    if (plotEl.data) Plotly.react(sid + "_cmp_plot", traces, polarLayout(), PLYCFG);
    else             Plotly.newPlot(sid + "_cmp_plot", traces, polarLayout(), PLYCFG);

    var hint = document.getElementById(sid + "_cmp_hint");
    hint.textContent = cmpStore.length + " courbe" + (cmpStore.length > 1 ? "s" : "");
  }}

  window[sid + "_addToCompare"] = function() {{
    if (!_lastTheta.length) return;
    var color = CMP_COLORS[cmpStore.length % CMP_COLORS.length];
    /* label = valeurs courantes des sliders */
    var label = SLIDER_COLS.filter(function(c) {{
      return SMETA[c] && SMETA[c].length;
    }}).map(function(c) {{
      return c + "=" + SMETA[c][sliderState[c] || 0];
    }}).join(" · ");
    cmpStore.push({{ label: label, theta: _lastTheta.slice(), r: _lastR.slice(), color: color }});
    renderComparePanel();
    var hint = document.getElementById(sid + "_cmp_hint");
    hint.textContent = cmpStore.length + " courbe" + (cmpStore.length > 1 ? "s" : "");
  }};

  window[sid + "_clearCompare"] = function() {{
    cmpStore = [];
    renderComparePanel();
    document.getElementById(sid + "_cmp_hint").textContent = "";
  }};

  /* ── Init ── */
  updateDisplay();

  window.addEventListener("resize", function() {{
    var el = document.getElementById(sid + "_plot");
    if (el && el.data) Plotly.Plots.resize(sid + "_plot");
    var el2 = document.getElementById(sid + "_cmp_plot");
    if (el2 && el2.data) Plotly.Plots.resize(sid + "_cmp_plot");
  }});
}})();
</script>
"""

class SimMapBlock(DataMixin, Block):
    """
    Carte 2D d'un sweep de simulation.

    - Sélecteurs X / Y parmi les colonnes scalaires
    - Les paramètres restants deviennent des sliders de filtrage
    - Scatter coloré par une colonne KPI (ex : LEE in 20°)
    - Clic sur un point → far-field polaire dans le panneau latéral

    Parameters
    ----------
    data          : DataArg
    param_cols    : list[str]   — toutes les colonnes scalaires du sweep
    kpi_col       : str         — colonne colorée par défaut (ex : "LEE in 20°")
    vector_col    : str         — colonne vecteur far-field
    vector_x_col  : str         — colonne angles (rad ou deg)
    vector_y_label: str         — label Y du far-field
    height        : int         — hauteur scatter + far-field
    num / title / subtitle
    """

    needs_plotly = True

    def __init__(
        self,
        data: DataArg,
        param_cols: list[str],
        kpi_col: str,
        vector_col: str,
        vector_x_col: str = "",
        vector_y_label: str = "Intensity",
        height: int = 420,
        num: str = "02",
        title: str = "Simulation Map",
        subtitle: str = "",
    ):
        self._init_data(data)
        self.param_cols    = param_cols
        self.kpi_col       = kpi_col
        self.vector_col    = vector_col
        self.vector_x_col  = vector_x_col
        self.vector_y_label = vector_y_label
        self.height        = height
        self.num           = num
        self.title         = title
        self.subtitle      = subtitle
        self._id           = f"simmap_{id(self)}"

    # ── sérialisation ─────────────────────────────────────────────────────────

    def _build_js_data(self, df: pd.DataFrame) -> str:
        records = []
        for _, row in df.iterrows():
            rec: dict = {}
            for c in self.param_cols:
                if c in row.index:
                    v = row[c]
                    rec[c] = _safe_json(v) if not isinstance(v, (list, np.ndarray)) else None
            if self.kpi_col in row.index:
                v = row[self.kpi_col]
                rec["_kpi"] = _safe_json(v) if not isinstance(v, (list, np.ndarray)) else None
            if self.vector_col in row.index:
                v = row[self.vector_col]
                rec["_vy"] = [_safe_json(x) for x in v] if isinstance(v, (list, np.ndarray)) else []
            if self.vector_x_col and self.vector_x_col in row.index:
                v = row[self.vector_x_col]
                rec["_vx"] = [_safe_json(x) for x in v] if isinstance(v, (list, np.ndarray)) else []
            records.append(rec)
        return json.dumps(records)

    def _build_param_meta(self, df: pd.DataFrame) -> str:
        meta: dict = {}
        for c in self.param_cols:
            if c not in df.columns:
                continue
            vals = sorted(df[c].dropna().unique().tolist())
            meta[c] = [_safe_json(v) for v in vals]
        return json.dumps(meta)

    # ── rendu ─────────────────────────────────────────────────────────────────

    def render(self, store=None) -> str:
        df        = self.resolve_df(store)
        sid       = self._id
        _data     = self._build_js_data(df)
        data_init = f"var DATA = {_data};"
        meta_json = self._build_param_meta(df)
        h         = self.height
        title_h   = _h.escape(self.title)
        sub_h     = _h.escape(self.subtitle)
        num_h     = _h.escape(self.num)
        yl        = _h.escape(self.vector_y_label)
        kpi_h     = _h.escape(self.kpi_col)
        param_cols_js = json.dumps(self.param_cols)
        default_kpi   = _h.escape(self.kpi_col)

        return f"""
<div class="led-block" id="{sid}_wrap">
  <div class="led-block-header">
    <span class="led-block-num">{num_h}</span>
    <span class="led-block-title">{title_h}</span>
    <span class="led-block-sub">{sub_h}</span>
  </div>
  <div class="led-block-rule"></div>

  <!-- ── Toolbar axes + couleur ── -->
  <div class="smm-toolbar">
    <div class="smm-toolbar-group">
      <span class="smm-tlabel">AXE X</span>
      <select class="smm-sel" id="{sid}_sel_x"></select>
    </div>
    <div class="smm-toolbar-group">
      <span class="smm-tlabel">AXE Y</span>
      <select class="smm-sel" id="{sid}_sel_y"></select>
    </div>
    <div class="smm-toolbar-group">
      <span class="smm-tlabel">COULEUR</span>
      <select class="smm-sel" id="{sid}_sel_kpi"></select>
    </div>
    <button class="slt-btn" onclick="{sid}_build()">▶ APPLIQUER</button>
  </div>

  <!-- ── Sliders dynamiques ── -->
  <div class="smm-sliders-bar" id="{sid}_sliders_bar"></div>

  <!-- ── Layout principal : scatter + far-field ── -->
  <div class="smm-main-layout">
    <div id="{sid}_scatter" style="height:{h}px; flex:1; min-width:0;"></div>
    <div class="smm-ff-panel" id="{sid}_ff_panel">
      <div class="smm-ff-header">
        <span class="led-block-num">↳</span>
        <span class="smm-ff-label" id="{sid}_ff_label">— cliquer un point —</span>
      </div>
      <div class="smm-ff-kpis" id="{sid}_ff_kpis"></div>
      <div id="{sid}_ff_plot" style="height:{h - 80}px;"></div>
    </div>
  </div>
</div>

<style>
#{sid}_wrap .smm-toolbar {{
  display: flex;
  flex-wrap: wrap;
  align-items: flex-end;
  gap: 12px;
  margin-bottom: 12px;
}}
#{sid}_wrap .smm-toolbar-group {{
  display: flex;
  flex-direction: column;
  gap: 3px;
}}
#{sid}_wrap .smm-tlabel {{
  font-family: "IBM Plex Mono", monospace;
  font-size: 9px;
  font-weight: 700;
  letter-spacing: .1em;
  color: #9AA3BF;
}}
#{sid}_wrap .smm-sel {{
  font-family: "IBM Plex Mono", monospace;
  font-size: 11px;
  color: #0A2463;
  background: #F8F9FD;
  border: 1px solid #E4E8F4;
  border-radius: 4px;
  padding: 4px 8px;
  cursor: pointer;
  min-width: 140px;
}}
#{sid}_wrap .smm-sel:focus {{ outline: none; border-color: #D4AF37; }}

/* sliders bar */
#{sid}_wrap .smm-sliders-bar {{
  display: flex;
  flex-wrap: wrap;
  gap: 16px;
  padding: 10px 14px;
  background: #F8F9FD;
  border: 1px solid #E4E8F4;
  border-radius: 6px;
  margin-bottom: 12px;
  min-height: 0;
}}
#{sid}_wrap .smm-sliders-bar:empty {{ display: none; }}
#{sid}_wrap .smm-sg {{
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-width: 140px;
  flex: 1;
}}
#{sid}_wrap .smm-sg-label {{
  font-family: "IBM Plex Mono", monospace;
  font-size: 9px;
  color: #4A5580;
  display: flex;
  justify-content: space-between;
}}
#{sid}_wrap .smm-sg-label span {{ color: #D4AF37; font-weight: 700; }}
#{sid}_wrap .smm-sg input[type=range] {{
  width: 100%;
  accent-color: #D4AF37;
  cursor: pointer;
}}

/* layout scatter + FF */
#{sid}_wrap .smm-main-layout {{
  display: flex;
  gap: 14px;
  align-items: stretch;
}}
#{sid}_wrap .smm-ff-panel {{
  width: 300px;
  flex-shrink: 0;
  background: #F8F9FD;
  border: 1px solid #E4E8F4;
  border-radius: 8px;
  padding: 10px 12px;
  display: flex;
  flex-direction: column;
  gap: 8px;
}}
#{sid}_wrap .smm-ff-header {{
  display: flex;
  align-items: center;
  gap: 6px;
}}
#{sid}_wrap .smm-ff-label {{
  font-family: "IBM Plex Mono", monospace;
  font-size: 10px;
  color: #0A2463;
  font-weight: 600;
}}
#{sid}_wrap .smm-ff-kpis {{
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}}
#{sid}_wrap .smm-ff-kpi {{
  background: #fff;
  border: 1px solid #E4E8F4;
  border-radius: 4px;
  padding: 4px 8px;
  font-family: "IBM Plex Mono", monospace;
}}
#{sid}_wrap .smm-ff-kpi-label {{
  font-size: 8px;
  color: #9AA3BF;
  text-transform: uppercase;
}}
#{sid}_wrap .smm-ff-kpi-val {{
  font-size: 12px;
  font-weight: 700;
  color: #0A2463;
}}
</style>

<script>
(function(){{
  {data_init}
  var PMETA       = {meta_json};    /* col → [val0, val1, …] */
  var PARAM_COLS  = {param_cols_js};
  var DEFAULT_KPI = "{default_kpi}";
  var sid         = "{sid}";

  var PLYCFG = {{responsive:true,displaylogo:false,
    modeBarButtonsToRemove:["autoScale2d","toggleSpikelines","sendDataToCloud"]}};
  var GSTYLE = {{gridcolor:"#E4E8F4",linecolor:"#E4E8F4",zerolinecolor:"#E4E8F4"}};

  var axisX   = PARAM_COLS[0] || "";
  var axisY   = PARAM_COLS[1] || "";
  var kpiCol  = DEFAULT_KPI;
  var sliderState = {{}};   /* col → index */

  /* ── Peupler les selects ── */
  function fillSelect(id, cols, selected) {{
    var sel = document.getElementById(id);
    sel.innerHTML = "";
    cols.forEach(function(c) {{
      var o = document.createElement("option");
      o.value = c; o.textContent = c;
      if (c === selected) o.selected = true;
      sel.appendChild(o);
    }});
  }}
  fillSelect(sid+"_sel_x",   PARAM_COLS, axisX);
  fillSelect(sid+"_sel_y",   PARAM_COLS, axisY);
  /* couleur : param_cols + _kpi s'il est différent */
  var kpiCols = PARAM_COLS.slice();
  if (kpiCols.indexOf(DEFAULT_KPI) < 0) kpiCols.push(DEFAULT_KPI);
  fillSelect(sid+"_sel_kpi", kpiCols, DEFAULT_KPI);

  /* ── Sliders pour les cols non-axe ── */
  function rebuildSliders() {{
    axisX  = document.getElementById(sid+"_sel_x").value;
    axisY  = document.getElementById(sid+"_sel_y").value;
    kpiCol = document.getElementById(sid+"_sel_kpi").value;
    var bar = document.getElementById(sid+"_sliders_bar");
    bar.innerHTML = "";
    PARAM_COLS.forEach(function(col) {{
      if (col === axisX || col === axisY) return;
      var vals = PMETA[col];
      if (!vals || !vals.length) return;
      if (sliderState[col] == null) sliderState[col] = 0;
      var grp = document.createElement("div");
      grp.className = "smm-sg";
      var lbl = document.createElement("div");
      lbl.className = "smm-sg-label";
      lbl.innerHTML = col + ' <span id="' + sid+'_slbl_'+col+'">' + vals[sliderState[col]] + '</span>';
      var inp = document.createElement("input");
      inp.type = "range"; inp.min = 0; inp.max = vals.length-1;
      inp.step = 1; inp.value = sliderState[col];
      inp.oninput = (function(c,v) {{
        return function() {{
          sliderState[c] = +this.value;
          document.getElementById(sid+'_slbl_'+c).textContent = v[+this.value];
        }};
      }})(col, vals);
      grp.appendChild(lbl); grp.appendChild(inp);
      bar.appendChild(grp);
    }});
  }}

  /* ── Filtrer les lignes selon les sliders ── */
  function filteredRows() {{
    return DATA.map(function(row, ri) {{ return {{row: row, ri: ri}}; }})
      .filter(function(obj) {{
        return PARAM_COLS.every(function(col) {{
          if (col === axisX || col === axisY) return true;
          var vals = PMETA[col];
          if (!vals || !vals.length) return true;
          var target = vals[sliderState[col] || 0];
          var v = obj.row[col];
          if (v == null || target == null) return true;
          return Math.abs(+v - +target) < 1e-9;
        }});
      }});
  }}

  /* ── Build scatter ── */
  function buildScatter() {{
    var rows = filteredRows();
    var xs=[], ys=[], cs=[], texts=[], cdata=[];
    rows.forEach(function(obj) {{
      var r = obj.row;
      if (r[axisX] == null || r[axisY] == null) return;
      xs.push(r[axisX]);
      ys.push(r[axisY]);
      cs.push(r["_kpi"] != null ? r["_kpi"] : (r[kpiCol] != null ? r[kpiCol] : 0));
      var tip = "<b>"+axisX+"="+r[axisX]+"  "+axisY+"="+r[axisY]+"</b>";
      PARAM_COLS.forEach(function(c) {{
        if (c!==axisX && c!==axisY && r[c]!=null)
          tip += "<br>"+c+": "+r[c];
      }});
      if (r["_kpi"] != null) tip += "<br><b>{kpi_h}: "+r["_kpi"]+"</b>";
      texts.push(tip);
      cdata.push(obj.ri);
    }});

    var traces = [{{
      type: "scatter", mode: "markers",
      x: xs, y: ys,
      marker: {{
        color: cs,
        colorscale: "Viridis",
        showscale: true,
        size: 12,
        opacity: 0.9,
        line: {{width: 0.5, color: "#fff"}},
        colorbar: {{
          title: {{text: kpiCol, font: {{size:10, color:"#0A2463"}}, side:"right"}},
          thickness: 12, len: 0.75, x: 1.01,
          tickfont: {{size:9, family:"IBM Plex Mono"}},
        }},
      }},
      text: texts,
      hovertemplate: "%{{text}}<extra></extra>",
      customdata: cdata,
    }}];

    var layout = {{
      paper_bgcolor:"rgba(0,0,0,0)", plot_bgcolor:"#F8F9FD",
      font:{{family:"IBM Plex Mono,monospace", color:"#4A5580", size:11}},
      margin:{{t:10, r:80, b:52, l:64}},
      xaxis: Object.assign({{}}, GSTYLE, {{
        title:{{text:axisX, font:{{size:13,color:"#0A2463"}}, standoff:8}},
        tickfont:{{size:10}},
      }}),
      yaxis: Object.assign({{}}, GSTYLE, {{
        title:{{text:axisY, font:{{size:13,color:"#0A2463"}}, standoff:8}},
        tickfont:{{size:10}},
      }}),
      clickmode:"event",
      hovermode:"closest",
      hoverlabel:{{bgcolor:"#0A2463",bordercolor:"#D4AF37",
        font:{{family:"IBM Plex Mono",size:10,color:"white"}}}},
      showlegend:false,
    }};

    if (document.getElementById(sid+"_scatter").data)
      Plotly.react(sid+"_scatter", traces, layout, PLYCFG);
    else
      Plotly.newPlot(sid+"_scatter", traces, layout, PLYCFG);

    /* clic → far-field */
    document.getElementById(sid+"_scatter").on("plotly_click", function(evt) {{
      var pt = evt.points[0];
      if (pt == null) return;
      var ri = pt.customdata;
      showFarField(ri);
    }});
  }}

  /* ── Far-field polaire ── */
  function symmetrizePolar(vx, vy) {{
    /* rad → deg */
    var thetaDeg = vx.map(function(v) {{
      return (Math.abs(v) <= Math.PI+0.01) ? v*180/Math.PI : v;
    }});
    var posMap={{}}, negMap={{}};
    for (var i=0; i<thetaDeg.length; i++) {{
      var td=thetaDeg[i], rv=vy[i];
      if (Math.abs(td)>90.5) continue;
      var key=Math.round(Math.abs(td));
      if (td>=0) posMap[key]=rv; else negMap[key]=rv;
    }}
    var allKeys=Array.from(new Set(
      Object.keys(posMap).concat(Object.keys(negMap))
    )).map(Number).sort(function(a,b){{return a-b;}});
    var thetaP=[], rS=[];
    for (var ki=allKeys.length-1;ki>=1;ki--) {{
      var k=allKeys[ki];
      var rAvg=((posMap[k]!=null)&&(negMap[k]!=null))?(posMap[k]+negMap[k])/2:(posMap[k]||negMap[k]||0);
      thetaP.push(90+k); rS.push(rAvg);
    }}
    var r0=posMap[0]!=null?posMap[0]:0;
    thetaP.push(90); rS.push(r0);
    for (var ki=1;ki<allKeys.length;ki++) {{
      var k=allKeys[ki];
      var rAvg=((posMap[k]!=null)&&(negMap[k]!=null))?(posMap[k]+negMap[k])/2:(posMap[k]||negMap[k]||0);
      thetaP.push(90-k); rS.push(rAvg);
    }}
    return {{theta:thetaP, r:rS}};
  }}

  function showFarField(ri) {{
    var row = DATA[ri];
    if (!row) return;

    /* label */
    var parts = PARAM_COLS.filter(function(c){{return row[c]!=null;}})
      .map(function(c){{return c+"="+row[c];}}).join("  ·  ");
    document.getElementById(sid+"_ff_label").textContent = parts;

    /* KPIs */
    var kpiWrap = document.getElementById(sid+"_ff_kpis");
    kpiWrap.innerHTML = "";
    PARAM_COLS.forEach(function(col) {{
      var v = row[col]; if (v==null) return;
      var div=document.createElement("div"); div.className="smm-ff-kpi";
      var disp=(typeof v==="number")?(Math.abs(v)>=100?v.toFixed(2):v.toPrecision(4)):String(v);
      div.innerHTML='<div class="smm-ff-kpi-label">'+col+'</div>'
                  + '<div class="smm-ff-kpi-val">'+disp+'</div>';
      kpiWrap.appendChild(div);
    }});

    /* far-field */
    var vy = row._vy || [];
    var vx = row._vx && row._vx.length ? row._vx : vy.map(function(_,i){{return i;}});
    var sym = symmetrizePolar(vx, vy);

    var traces = [{{
      type:"scatterpolar", mode:"lines",
      theta:sym.theta, r:sym.r,
      line:{{color:"#D4AF37", width:2}},
      fill:"toself",
      fillcolor:"rgba(212,175,55,0.10)",
      hovertemplate:"θ: %{{theta:.0f}}°<br>{yl}: %{{r:.4f}}<extra></extra>",
    }}];
    var layout = {{
      paper_bgcolor:"rgba(0,0,0,0)",
      font:{{family:"IBM Plex Mono,monospace", color:"#4A5580", size:9}},
      margin:{{t:10,r:10,b:10,l:10}},
      showlegend:false,
      polar:{{
        bgcolor:"#F8F9FD",
        sector:[0,180],
        angularaxis:{{
          direction:"counterclockwise", rotation:0,
          tickfont:{{size:8,family:"IBM Plex Mono"}},
          gridcolor:"#E4E8F4", linecolor:"#E4E8F4",
          thetaunit:"degrees",
          tickvals:[0,30,60,90,120,150,180],
          ticktext:["90°","60°","30°","0°","-30°","-60°","-90°"],
        }},
        radialaxis:{{
          tickfont:{{size:8,family:"IBM Plex Mono"}},
          gridcolor:"#E4E8F4", linecolor:"#E4E8F4",
          angle:90, tickangle:-90,
        }},
      }},
      hoverlabel:{{bgcolor:"#0A2463",bordercolor:"#D4AF37",
        font:{{family:"IBM Plex Mono",size:9,color:"white"}}}},
    }};
    if (document.getElementById(sid+"_ff_plot").data)
      Plotly.react(sid+"_ff_plot", traces, layout, PLYCFG);
    else
      Plotly.newPlot(sid+"_ff_plot", traces, layout, PLYCFG);
  }}

  /* ── Action bouton APPLIQUER ── */
  window[sid+"_build"] = function() {{
    rebuildSliders();
    buildScatter();
  }};

  /* ── Changement de select → reconstruire sliders ── */
  [sid+"_sel_x", sid+"_sel_y", sid+"_sel_kpi"].forEach(function(id) {{
    document.getElementById(id).onchange = function() {{
      rebuildSliders();
      buildScatter();
    }};
  }});

  /* ── Init ── */
  rebuildSliders();
  buildScatter();

  window.addEventListener("resize", function() {{
    var el = document.getElementById(sid+"_scatter");
    if (el && el.data) Plotly.Plots.resize(sid+"_scatter");
    var el2 = document.getElementById(sid+"_ff_plot");
    if (el2 && el2.data) Plotly.Plots.resize(sid+"_ff_plot");
  }});
}})();
</script>
"""