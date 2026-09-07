from __future__ import annotations
import json
import html as _h
import numpy as np
import pandas as pd
from ..._helpers import Block, _safe_json
from ..data.data_mixin import DataMixin, DataArg

class CIEDiagram(DataMixin, Block):
    """
    Diagramme CIE 1931 interactif.

    - 1 point par (LED, niveau de courant) aux coordonnées (CIEx[i], CIEy[i])
    - Taille des points ∝ J[i] (densité de courant)
    - Couleur = sRGB de la LED à ce niveau
    - Filtre wafer dropdown
    - Clic → overlay : spectre + J, V, EQE du point + focus sur la LED
    - Locus spectral CIE tracé en fond

    Params:
        df             : DataFrame vectoriel (1 ligne = 1 LED)
        ciex_col       : colonne CIEx (vecteur)
        ciey_col       : colonne CIEy (vecteur)
        j_col          : colonne J (vecteur) pour la taille
        eqe_col        : colonne EQE (vecteur)
        v_col          : colonne V (vecteur)
        color_col      : colonne srgb (vecteur hex)
        spectra_col    : colonne Spectra (2D)
        wavelength_col : colonne Wavelength
        wafer_col      : colonne wafername (filtre)
        id_col         : colonne identifiant LED
        hover_cols     : colonnes scalaires supplémentaires dans le tooltip
    """
    needs_plotly = True

    def __init__(
        self,
        data: DataArg,
        ciex_col: str = "CIEx",
        ciey_col: str = "CIEy",
        j_col: str = "J",
        eqe_col: str = "EQE",
        v_col: str = "V",
        color_col: str = "srgb",
        spectra_col: str = "Spectra",
        wavelength_col: str = "Wavelength",
        wafer_col: str = "wafername",
        id_col: str = "Led_Name",
        hover_cols: list[str] | None = None,
        height: int = 520,
        num: str = "04",
        title: str = "Diagramme CIE 1931",
        subtitle: str = "trajectoire chromatique · taille = J",
    ):
        self._init_data(data)
        self.ciex_col = ciex_col; self.ciey_col = ciey_col
        self.j_col = j_col; self.eqe_col = eqe_col; self.v_col = v_col
        self.color_col = color_col
        self.spectra_col = spectra_col; self.wavelength_col = wavelength_col
        self.wafer_col = wafer_col; self.id_col = id_col
        self.hover_cols = hover_cols or []
        self.height = height
        self.num = num; self.title = title; self.subtitle = subtitle
        self._id = f"cie_{id(self)}"

    def _build_data(self, df: pd.DataFrame) -> str:
        records = []
        for _, row in df.iterrows():
            def _vec(col):
                if col and col in row.index:
                    v = row[col]
                    if isinstance(v, (list, np.ndarray)):
                        return [_safe_json(x) for x in v]
                return []

            rec = {
                "_id":    str(row[self.id_col]) if self.id_col in row.index else str(len(records)),
                "_wafer": str(row[self.wafer_col]) if self.wafer_col in row.index else "",
                "cx":     _vec(self.ciex_col),
                "cy":     _vec(self.ciey_col),
                "j":      _vec(self.j_col),
                "eqe":    _vec(self.eqe_col),
                "v":      _vec(self.v_col),
                "color":  _vec(self.color_col),
            }
            # Spectra — downsampled
            if self.spectra_col and self.spectra_col in row.index:
                sp = row[self.spectra_col]
                if isinstance(sp, (list, np.ndarray)) and len(sp) > 0:
                    def _ds(s, t=120):
                        if not isinstance(s,(list,np.ndarray)) or len(s)<=t: return [_safe_json(x) for x in s]
                        step = max(1,len(s)//t); return [_safe_json(s[i]) for i in range(0,len(s),step)]
                    rec["spectra"] = [_ds(sp[i]) for i in range(len(sp)) if isinstance(sp[i],(list,np.ndarray))]
            if self.wavelength_col and self.wavelength_col in row.index:
                wl = row[self.wavelength_col]
                if isinstance(wl, (list, np.ndarray)):
                    step = max(1, len(wl)//120)
                    rec["wl"] = [_safe_json(wl[i]) for i in range(0,len(wl),step)]
            for c in self.hover_cols:
                if c in row.index: rec[c] = _safe_json(row[c])
            records.append(rec)
        return json.dumps(records)

    def render(self, store=None) -> str:
        df = self.resolve_df(store)
        cid = self._id
        data_json = self._build_data(df)
        h = self.height
        wafers_json = json.dumps(sorted(df[self.wafer_col].dropna().unique().tolist())
                                  if self.wafer_col in df.columns else [])

        return f"""
<div class="led-block" id="{cid}_wrap">
  <div class="led-block-header">
    <span class="led-block-num">{_h.escape(self.num)}</span>
    <span class="led-block-title">{_h.escape(self.title)}</span>
    <span class="led-block-sub">{_h.escape(self.subtitle)}</span>
  </div>
  <div class="led-block-rule"></div>
  <!-- toolbar -->
  <div class="scatter-led-toolbar">
    <span style="font-family:var(--fm);font-size:9px;color:var(--slate-400);letter-spacing:.06em;text-transform:uppercase;">Wafer</span>
    <div style="position:relative;display:inline-flex;">
      <select class="gb-select" id="{cid}_wfilter" onchange="{cid}_filterWafer(this.value)"
        style="height:26px;width:180px;font-size:10px;">
        <option value="">Tous les wafers</option>
      </select>
      <span style="position:absolute;right:7px;top:50%;transform:translateY(-50%);pointer-events:none;border-left:4px solid transparent;border-right:4px solid transparent;border-top:5px solid var(--slate-400);width:0;height:0;"></span>
    </div>
    <div class="slt-sep"></div>
    <button class="slt-btn" onclick="{cid}_clearSel()">✕ EFFACER</button>
    <span class="slt-count" id="{cid}_selcount">Aucune sélection</span>
  </div>
  <!-- CIE plot + detail side panel -->
  <div style="display:flex;gap:0;min-height:{h}px;">
    <!-- CIE diagram -->
    <div style="flex:1;min-width:0;">
      <div id="{cid}_plot" style="height:{h}px;"></div>
    </div>
    <!-- Detail panel (hidden until click) -->
    <div id="{cid}_detail" style="display:none;width:320px;border-left:2px solid var(--border);background:var(--slate-50);flex-shrink:0;overflow:hidden;position:relative;">
      <div style="position:absolute;top:0;left:0;bottom:0;width:2px;background:linear-gradient(180deg,var(--gold),rgba(212,175,55,.2) 50%,transparent);"></div>
      <div style="padding:10px 14px;height:{h}px;display:flex;flex-direction:column;gap:8px;overflow:hidden;">
        <!-- Header -->
        <div style="display:flex;align-items:center;gap:8px;flex-shrink:0;">
          <span class="led-block-num">↳</span>
          <span id="{cid}_detlabel" style="font-family:var(--fm);font-size:10px;color:var(--navy);flex:1;"></span>
          <button class="led-detail-close" onclick="{cid}_closeDetail()">✕</button>
        </div>
        <!-- KPIs -->
        <div id="{cid}_kpis" style="display:grid;grid-template-columns:1fr 1fr;gap:6px;flex-shrink:0;"></div>
        <!-- Spectre -->
        <div style="flex:1;min-height:0;background:var(--surface);border:1px solid var(--border);">
          <div style="padding:4px 10px 0;font-family:var(--fd);font-weight:700;font-size:9px;color:var(--navy);text-transform:uppercase;letter-spacing:.08em;">Spectre</div>
          <div id="{cid}_spec" style="height:calc(100% - 22px);"></div>
        </div>
      </div>
    </div>
  </div>
</div>

<script>
(function(){{
  var DATA   = {data_json};
  var WAFERS = {wafers_json};
  var cid    = "{cid}";
  var activeWafer = "";
  var focusId = null;   /* _id of focused LED */

  var PLYCFG = {{responsive:true,displaylogo:false,modeBarButtonsToRemove:["autoScale2d","toggleSpikelines","sendDataToCloud"]}};
  var GSTYLE = {{gridcolor:"rgba(0,0,0,.06)",linecolor:"rgba(0,0,0,.15)",zerolinecolor:"rgba(0,0,0,.1)"}};

  /* ── Populate wafer filter ── */
  var sel = document.getElementById(cid+"_wfilter");
  WAFERS.forEach(function(w){{
    var o=document.createElement("option"); o.value=w; o.textContent=w; sel.appendChild(o);
  }});

  window[cid+"_filterWafer"] = function(w){{ activeWafer=w; buildPlot(); }};

  /* ── CIE 1931 spectral locus (sampled at ~10nm) ── */
  var LOCUS_X = [0.175596,0.172787,0.170806,0.170085,0.160343,0.146958,0.139149,0.133536,
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
  /* Planckian locus (white point region) */
  var PLANCK_X=[0.2400,0.2738,0.3221,0.3805,0.4406,0.4939,0.5253,0.5289,0.5289];
  var PLANCK_Y=[0.2340,0.2832,0.3318,0.3769,0.4030,0.4082,0.4128,0.4154,0.4140];

  /* ── Normalize J for size ── */
  function normJ(vals){{
    var clean=vals.map(parseFloat).filter(function(v){{return !isNaN(v)&&v>1e-12;}});
    if(!clean.length) return vals.map(function(){{return 5;}});
    var mn=Math.log10(Math.min.apply(null,clean)), mx=Math.log10(Math.max.apply(null,clean));
    return vals.map(function(v){{
      var n=parseFloat(v);
      if(isNaN(n)||n<=1e-12) return 3;
      if(mx===mn) return 8;
      return 4 + (Math.log10(n)-mn)/(mx-mn)*16;  /* 4px → 20px */
    }});
  }}

  /* ── Build all J values for global normalization ── */
  var _allJ=[];
  DATA.forEach(function(r){{(r.j||[]).forEach(function(v){{if(v>1e-12)_allJ.push(v);}});}});
  var _jMin=_allJ.length?Math.log10(Math.min.apply(null,_allJ)):0;
  var _jMax=_allJ.length?Math.log10(Math.max.apply(null,_allJ)):1;
  function jToSize(v){{
    if(!v||v<=1e-12) return 3;
    if(_jMax===_jMin) return 8;
    return 4+(Math.log10(v)-_jMin)/(_jMax-_jMin)*16;
  }}

  /* ── hex color → rgba string ── */
  function hexToRgba(hex, alpha){{
    hex = hex.replace('#','');
    if(hex.length===3) hex=hex[0]+hex[0]+hex[1]+hex[1]+hex[2]+hex[2];
    var r=parseInt(hex.slice(0,2),16), g=parseInt(hex.slice(2,4),16), b=parseInt(hex.slice(4,6),16);
    if(isNaN(r)||isNaN(g)||isNaN(b)) return "rgba(212,175,55,"+alpha+")";
    return "rgba("+r+","+g+","+b+","+(alpha||1)+")";
  }}

  /* ── Build plot ── */
  function buildPlot(){{
    var filtered = activeWafer
      ? DATA.filter(function(r){{return r._wafer===activeWafer;}})
      : DATA;

    var traces = [];

    /* Locus spectral */
    traces.push({{
      type:"scatter", mode:"lines", x:LOCUS_X, y:LOCUS_Y,
      line:{{color:"rgba(0,0,0,.35)",width:1.5}},
      hoverinfo:"skip", showlegend:false,
    }});
    /* Planckian locus */
    traces.push({{
      type:"scatter", mode:"lines", x:PLANCK_X, y:PLANCK_Y,
      line:{{color:"rgba(180,120,0,.5)",width:1,dash:"dot"}},
      hoverinfo:"skip", showlegend:false,
    }});
    /* D65 white point */
    traces.push({{
      type:"scatter", mode:"markers+text", x:[0.3127], y:[0.3290],
      marker:{{color:"white",size:8,line:{{color:"#555",width:1.5}}}},
      text:["D65"], textposition:"top right",
      textfont:{{family:"IBM Plex Mono",size:8,color:"#555"}},
      hoverinfo:"skip", showlegend:false,
    }});

    /* LED data points — une seule trace pour tous les points (perf) */
    var allX=[], allY=[], allCol=[], allSz=[], allTxt=[], allCd=[];

    filtered.forEach(function(r){{
      var cx=r.cx||[], cy=r.cy||[], jv=r.j||[], eqv=r.eqe||[], vv=r.v||[];
      var cols=r.color||[];
      var isFocus = (focusId!==null);
      var isThis  = (r._id===focusId);

      cx.forEach(function(x,i){{
        if(x==null||cy[i]==null||isNaN(x)||isNaN(cy[i])) return;
        if(isFocus && !isThis) return;  /* skip other LEDs entirely when focused */
        allX.push(x); allY.push(cy[i]);
        /* Parse hex color and apply opacity via rgba */
        var hex = cols[i]||"#D4AF37";
        var op  = isFocus ? 0.95 : 0.85;
        allCol.push(hexToRgba(hex, op));
        allSz.push(jToSize(jv[i]));
        var htxt = "<b>"+r._id+"</b><br>CIE x: "+x.toFixed(4)+"<br>CIE y: "+cy[i].toFixed(4);
        if(jv[i])  htxt += "<br>J: "+Number(jv[i]).toExponential(2)+" A/cm²";
        if(eqv[i]) htxt += "<br>EQE: "+Number(eqv[i]).toFixed(2)+"%";
        if(vv[i])  htxt += "<br>V: "+Number(vv[i]).toFixed(3)+" V";
        allTxt.push(htxt);
        allCd.push([r._id, i]);
      }});
    }});

    if(allX.length){{
      traces.push({{
        type:"scatter", mode:"markers",
        x:allX, y:allY,
        marker:{{
          color:allCol, size:allSz,
          line:{{width:0.5, color:"rgba(0,0,0,.2)"}},
        }},
        text:allTxt, hovertemplate:"%{{text}}<extra></extra>",
        customdata:allCd, showlegend:false,
      }});
    }}

    var layout = {{
      paper_bgcolor:"rgba(0,0,0,0)", plot_bgcolor:"white",
      font:{{family:"IBM Plex Mono,monospace",color:"#4A5580",size:10}},
      margin:{{t:10,r:16,b:48,l:56}},
      xaxis:Object.assign({{}},GSTYLE,{{title:{{text:"CIE x",font:{{size:12,color:"#0A2463"}},standoff:8}},range:[0,0.8],tickfont:{{size:10}}}}),
      yaxis:Object.assign({{}},GSTYLE,{{title:{{text:"CIE y",font:{{size:12,color:"#0A2463"}},standoff:8}},range:[0,0.9],tickfont:{{size:10}},scaleanchor:"x",scaleratio:1}}),
      clickmode:"event",
      hoverlabel:{{bgcolor:"#0A2463",bordercolor:"#D4AF37",font:{{family:"IBM Plex Mono",size:10,color:"white"}}}},
      showlegend:false,
    }};

    Plotly.react(cid+"_plot", traces, layout, PLYCFG);

    /* Bind click */
    var el=document.getElementById(cid+"_plot");
    el.removeAllListeners && el.removeAllListeners("plotly_click");
    el.on("plotly_click", function(evt){{
      if(!evt.points||!evt.points.length) return;
      var cd=evt.points[0].customdata;
      if(!cd) return;
      var ledId=cd[0], ptIdx=cd[1];
      var r=DATA.find(function(d){{return d._id===ledId;}});
      if(!r) return;
      focusId = ledId;
      buildPlot();
      showDetail(r, ptIdx);
      document.getElementById(cid+"_selcount").textContent=ledId;
      document.getElementById(cid+"_selcount").classList.add("has-sel");
    }});
  }}

  /* ── Show detail panel ── */
  function showDetail(r, ptIdx){{
    document.getElementById(cid+"_detail").style.display="block";
    document.getElementById(cid+"_detlabel").textContent=r._id;

    /* KPIs */
    var jv=r.j||[], eqv=r.eqe||[], vv=r.v||[], cx=r.cx||[], cy=r.cy||[];
    var kpiData=[
      ["CIE x",   cx[ptIdx]!=null?cx[ptIdx].toFixed(4):"—",    ""],
      ["CIE y",   cy[ptIdx]!=null?cy[ptIdx].toFixed(4):"—",    ""],
      ["J",       jv[ptIdx]!=null?Number(jv[ptIdx]).toExponential(2):"—", "A/cm²"],
      ["EQE",     eqv[ptIdx]!=null?Number(eqv[ptIdx]).toFixed(2)+"":"—",   "%"],
      ["V",       vv[ptIdx]!=null?Number(vv[ptIdx]).toFixed(3):"—",       "V"],
    ];
    var kpis=document.getElementById(cid+"_kpis");
    kpis.innerHTML=kpiData.map(function(k){{
      return '<div style="background:var(--surface);border:1px solid var(--border);border-radius:4px;padding:6px 8px;position:relative;overflow:hidden;">'+
        '<div style="position:absolute;top:0;left:0;right:0;height:2px;background:var(--gold);"></div>'+
        '<div style="font-family:var(--fm);font-size:8px;color:var(--slate-400);letter-spacing:.08em;text-transform:uppercase;margin-bottom:3px;">'+k[0]+'</div>'+
        '<div style="font-family:var(--fd);font-size:16px;font-weight:800;color:var(--navy);">'+k[1]+
        '<span style="font-family:var(--fm);font-size:9px;color:var(--slate-400);margin-left:2px;">'+k[2]+'</span></div>'+
        '</div>';
    }}).join("");

    /* Spectre à ce niveau de courant */
    if(r.spectra&&r.wl&&r.spectra[ptIdx]){{
      /* Show ONLY the spectrum at the clicked current level */
      var sp = r.spectra[ptIdx];
      var jv = r.j||[];
      var jLabel = jv[ptIdx]!=null ? "J = "+Number(jv[ptIdx]).toExponential(2)+" A/cm²" : "pt "+(ptIdx+1);
      Plotly.newPlot(cid+"_spec", [{{
        x:r.wl, y:sp, type:"scatter", mode:"lines",
        line:{{color:"#8B5CF6", width:2}},
        fill:"tozeroy", fillcolor:"rgba(139,92,246,.1)",
        hoverinfo:"x+y", showlegend:false,
        name:jLabel,
      }}], {{
        paper_bgcolor:"rgba(0,0,0,0)", plot_bgcolor:"#F8F9FD",
        font:{{family:"IBM Plex Mono",size:9,color:"#4A5580"}},
        margin:{{t:4,r:6,b:28,l:38}},
        showlegend:false,
        title:{{text:jLabel,font:{{size:8,color:"#8B97BF"}}}},
        xaxis:Object.assign({{}},GSTYLE,{{title:{{text:"λ (nm)",font:{{size:9}},standoff:3}},tickfont:{{size:8}}}}),
        yaxis:Object.assign({{}},GSTYLE,{{title:{{text:"Intensité",font:{{size:9}},standoff:3}},tickfont:{{size:8}}}}),
      }}, PLYCFG);
    }} else {{
      document.getElementById(cid+"_spec").innerHTML='<div class="no-data-msg">—</div>';
    }}

    setTimeout(function(){{Plotly.Plots.resize(cid+"_plot");}},50);
  }}

  window[cid+"_closeDetail"] = function(){{
    document.getElementById(cid+"_detail").style.display="none";
    focusId=null;
    document.getElementById(cid+"_selcount").textContent="Aucune sélection";
    document.getElementById(cid+"_selcount").classList.remove("has-sel");
    buildPlot();
    setTimeout(function(){{Plotly.Plots.resize(cid+"_plot");}},50);
  }};

  window[cid+"_clearSel"] = window[cid+"_closeDetail"];

  buildPlot();
}})();
</script>
"""


# ─────────────────────────────────────────────────────────────────────────────
# StatAnalysis — placeholder onglet "Analyse statistique du Split"
# ─────────────────────────────────────────────────────────────────────────────
class StatAnalysis(Block):
    """
    Onglet placeholder pour l'analyse statistique du split.
    Affiche un message "Coming Soon" élégant avec le plan prévu.

    Usage :
        tab_stat = Tab("Analyse Split")
        tab_stat.add(StatAnalysis())
    """
    needs_plotly = False

    def __init__(self, planned_features: list[str] | None = None):
        self.planned = planned_features or [
            "Kruskal-Wallis test sur max_EQE par groupe",
            "ANOVA one-way + post-hoc Tukey HSD",
            "Pairwise Welch t-tests avec correction Bonferroni",
            "Cohen's d (effect size) par paire de groupes",
            "Visualisation : volcano plot p-value vs delta",
            "Export tableau statistique CSV",
        ]
        self._id = f"stat_{id(self)}"

    def render(self) -> str:
        features_html = "".join(
            f'<div class="stat-ph-item"><span class="stat-ph-bullet">◎</span>{_h.escape(f)}</div>'
            for f in self.planned
        )
        return f"""
<div style="
  min-height:60vh; display:flex; flex-direction:column;
  align-items:center; justify-content:center; gap:32px;
  padding:60px 40px; text-align:center;
">
  <!-- Icon -->
  <div style="
    width:72px; height:72px; border-radius:50%;
    background:rgba(10,36,99,.06); border:2px solid var(--border);
    display:flex; align-items:center; justify-content:center;
    font-size:28px;
  ">📊</div>

  <!-- Title -->
  <div>
    <div style="
      font-family:var(--fd); font-weight:800; font-size:28px;
      color:var(--navy); margin-bottom:10px; letter-spacing:-.01em;
    ">Analyse Statistique du Split</div>
    <div style="
      font-family:var(--fm); font-size:12px; color:var(--slate-400);
      letter-spacing:.1em; text-transform:uppercase;
    ">⌛ Waiting · Planned · Coming Soon :-)</div>
  </div>

  <!-- Planned features -->
  <div style="
    background:var(--surface); border:1px solid var(--border);
    border-radius:var(--radius); padding:24px 32px;
    max-width:560px; width:100%; text-align:left;
    box-shadow:var(--shadow);
    position:relative; overflow:hidden;
  ">
    <div style="
      position:absolute; top:0; left:0; right:0; height:2px;
      background:linear-gradient(90deg,var(--gold),rgba(212,175,55,.2),transparent);
    "></div>
    <div style="
      font-family:var(--fm); font-size:9px; letter-spacing:.12em;
      text-transform:uppercase; color:var(--gold); margin-bottom:16px;
    ">FONCTIONNALITÉS PRÉVUES</div>
    <div style="display:flex; flex-direction:column; gap:10px;">
      {features_html}
    </div>
  </div>

  <!-- Badge -->
  <div style="
    font-family:var(--fm); font-size:10px; color:var(--slate-400);
    padding:6px 16px; border:1px dashed var(--border); border-radius:20px;
    letter-spacing:.06em;
  ">Module en cours de développement — prochaine release</div>
</div>

<style>
.stat-ph-item {{
  display:flex; align-items:flex-start; gap:10px;
  font-family:var(--fb); font-size:13px; color:var(--slate-600);
  line-height:1.5;
}}
.stat-ph-bullet {{
  font-size:14px; color:var(--gold); flex-shrink:0; margin-top:1px;
}}
</style>
"""
