from __future__ import annotations
import json
import html as _h
import numpy as np
import pandas as pd
from ..._helpers import Block, _safe_json, _is_vector_col
from ..data.data_mixin import DataMixin, DataArg

class SummaryBoxPlots(DataMixin, Block):
    """
    Box-plots de métriques scalaires, groupés par une colonne catégorielle.

    metrics : dict { "Titre affiché": ("col_df", "unité") }
               ou liste de str (noms de colonnes)
    targets : dict { "col_df": (lo, hi) } → zone target mise en valeur
    process_col : colonne pour la couleur (ex: "MOCVD_MBE")
    cols_per_row : 1, 2 ou 3
    height_per_row : hauteur px d'une ligne de plots
    """
    needs_plotly = True

    def __init__(
        self,
        data: DataArg,
        group_col: str,
        metrics: dict[str, tuple] | list[str],
        targets: dict[str, tuple] | None = None,
        process_col: str = "",
        cols_per_row: int = 2,
        height_per_row: int = 300,
        num: str = "00",
        title: str = "Summary",
        subtitle: str = "",
    ):
        self._init_data(data)
        self.group_col = group_col
        if isinstance(metrics, list):
            self.metrics = {m: (m, "") for m in metrics}
        else:
            self.metrics = metrics
        self.targets = targets or {}
        self.process_col = process_col
        self.cols_per_row = cols_per_row
        self.height_per_row = height_per_row
        self.num = num
        self.title = title
        self.subtitle = subtitle
        self._id = f"sbp_{id(self)}"

    def render(self, store=None) -> str:
        bid = self._id

        if self.has_local_data:
            # Df local : groupby Python, sérialisation inline
            df = self.resolve_df()
            groups_py = df[self.group_col].unique()
            out: dict = {}
            for g in sorted(str(x) for x in groups_py if pd.notna(x)):
                sub = df[df[self.group_col].astype(str) == g]
                rec: dict = {}
                for label, (col, unit) in self.metrics.items():
                    if col in sub.columns and not _is_vector_col(sub[col]):
                        rec[col] = [_safe_json(v) for v in sub[col].dropna().tolist()]
                if self.process_col and self.process_col in sub.columns:
                    mode = sub[self.process_col].mode()
                    rec["_process"] = str(mode.iloc[0]) if len(mode) > 0 else "?"
                out[g] = rec
            sumdata_init = f"var SUMDATA={json.dumps(out)};"
        else:
            # Clé store : groupby JS, zéro copie
            key = self._data_arg
            if store is None:
                raise RuntimeError(
                    f"SummaryBoxPlots references store key {key!r} but no DataStore was provided."
                )
            store.resolve(key)  # valide que la clé existe
            proc_col_js = json.dumps(self.process_col)
            group_col_js = json.dumps(self.group_col)
            sumdata_init = (
                f"var _raw=(window.__DATA_STORE__||{{}})[{json.dumps(key)}]||[],"
                f"_gc={group_col_js},_pc={proc_col_js};"
                f"var SUMDATA={{}};"
                f"_raw.forEach(function(row){{"
                f"  var g=String(row[_gc]!=null?row[_gc]:'?');"
                f"  if(!SUMDATA[g])SUMDATA[g]={{}};"
                f"  var rec=SUMDATA[g];"
                f"  Object.keys(METRICS).forEach(function(lbl){{"
                f"    var col=METRICS[lbl].col;"
                f"    if(row[col]!=null&&!Array.isArray(row[col]))"
                f"      {{if(!rec[col])rec[col]=[];rec[col].push(row[col]);}}"
                f"  }});"
                f"  if(_pc&&row[_pc]!=null){{if(!rec._pfreq)rec._pfreq={{}};var _pv=String(row[_pc]);rec._pfreq[_pv]=(rec._pfreq[_pv]||0)+1;}}"
                f"}});"
                # Après l'accumulation : calculer le mode de _process pour chaque groupe
                f"Object.keys(SUMDATA).forEach(function(g){{"
                f"  var rec=SUMDATA[g];"
                f"  if(rec._pfreq){{var _best=null,_bv=0;Object.keys(rec._pfreq).forEach(function(k){{if(rec._pfreq[k]>_bv){{_bv=rec._pfreq[k];_best=k;}}}});rec._process=_best;delete rec._pfreq;}}"
                f"}});"
            )

        def _mentry(spec):
            col = spec[0]; unit = spec[1]
            return {"col": col, "unit": unit, "y_label": spec[2] if len(spec) > 2 else ""}
        metrics_json = json.dumps({lbl: _mentry(spec) for lbl, spec in self.metrics.items()})
        targets_json = json.dumps(self.targets)
        grid_cls     = f"summary-grid-{min(self.cols_per_row, 3)}"
        h_px         = self.height_per_row

        plot_divs = ""
        for i, (lbl, (col, unit)) in enumerate(self.metrics.items()):
            safe_id = f"{bid}_p{i}"
            plot_divs += (f'<div class="summary-plot-card">'
                          f'<span class="summary-plot-label">{_h.escape(lbl)}'
                          f'{"  (" + unit + ")" if unit else ""}</span>'
                          f'<div id="{safe_id}" style="height:{h_px}px;padding-top:24px;"></div></div>\n')

        return f"""
<div class="led-block">
  <div class="led-block-header">
    <span class="led-block-num">{_h.escape(self.num)}</span>
    <span class="led-block-title">{_h.escape(self.title)}</span>
    <span class="led-block-sub">{_h.escape(self.subtitle)}</span>
  </div>
  <div class="led-block-rule"></div>
  <div style="padding:16px;">
    <div class="summary-grid {grid_cls}">{plot_divs}</div>
  </div>
</div>

<script>
(function(){{
  var METRICS  = {metrics_json};
  var TARGETS  = {targets_json};
  var bid      = "{bid}";
  {sumdata_init}
  var groups   = Object.keys(SUMDATA).sort();

  var PROC_COLORS = {{
    "MOCVD":"#3B82F6","MBE":"#EF4444",
    "default":"#8B97BF"
  }};
  var PROC_LIGHT = {{
    "MOCVD":"rgba(59,130,246,.4)","MBE":"rgba(239,68,68,.4)",
    "default":"rgba(139,151,191,.4)"
  }};

  var PLYCFG = {{responsive:true,displaylogo:false,modeBarButtonsToRemove:["autoScale2d","toggleSpikelines","sendDataToCloud"],}};
  var GSTYLE = {{gridcolor:"#E4E8F4",linecolor:"#E4E8F4",zerolinecolor:"#E4E8F4"}};

  function boxLayout(yTitle, targetLo, targetHi){{
    var shapes=[], annots=[];
    if(targetLo!=null && targetHi!=null){{
      shapes.push({{type:"rect",x0:0,x1:1,xref:"paper",y0:targetLo,y1:targetHi,yref:"y",
        fillcolor:"rgba(212,175,55,.12)",line:{{width:0}},layer:"below"}});
      annots.push({{x:1,xref:"paper",xanchor:"right",y:(targetLo+targetHi)/2,yref:"y",
        text:"TARGET",showarrow:false,font:{{family:"IBM Plex Mono",size:9,color:"rgba(212,175,55,.8)"}},
        bgcolor:"rgba(255,255,255,.7)",borderpad:2}});
    }}
    return {{
      paper_bgcolor:"rgba(0,0,0,0)",plot_bgcolor:"#F8F9FD",
      font:{{family:"IBM Plex Mono,monospace",color:"#4A5580",size:10}},
      margin:{{t:28,r:14,b:80,l:52}},
      xaxis:Object.assign({{}},GSTYLE,{{tickfont:{{size:8}},tickangle:-40}}),
      yaxis:Object.assign({{}},GSTYLE,{{title:{{text:yTitle,font:{{size:11,color:"#0A2463"}}}},tickfont:{{size:9}}}}),
      showlegend:true, legend:{{font:{{size:9}},orientation:"h",x:.5,xanchor:"center",y:1.04}},
      shapes:shapes, annotations:annots,
    }};
  }}

  var metricKeys = Object.keys(METRICS);
  metricKeys.forEach(function(lbl,i){{
    var info = METRICS[lbl];
    var col  = info.col, unit = info.unit;
    var yAxisLabel = info.y_label || (lbl + (unit?" ("+unit+")":""));
    var tgt  = TARGETS[col];
    var tLo  = tgt?tgt[0]:null, tHi=tgt?tgt[1]:null;
    var seen = {{}};
    var traces = groups.map(function(g){{
      var rec  = SUMDATA[g];
      var proc = rec._process||"default";
      var col2 = PROC_COLORS[proc]||PROC_COLORS.default;
      var colL = PROC_LIGHT[proc]||PROC_LIGHT.default;
      var showLeg = !seen[proc]; seen[proc]=true;
      return {{
        y: rec[col]||[], type:"box", name:proc, legendgroup:proc, showlegend:showLeg,
        x:(rec[col]||[]).map(function(){{return g+" ("+proc+")";}}) ,
        marker:{{color:col2,size:4,opacity:.7}}, line:{{color:col2}},
        fillcolor:colL, boxmean:"sd", jitter:.3, pointpos:-1.5, boxpoints:"all",
      }};
    }});
    Plotly.newPlot(bid+"_p"+i, traces,
      boxLayout(yAxisLabel, tLo, tHi), PLYCFG);
  }});
}})();
</script>
"""


# ─────────────────────────────────────────────────────────────────────────────
# WaferMaps
# ─────────────────────────────────────────────────────────────────────────────
# ─────────────────────────────────────────────────────────────────────────────
# ScatterSummary  — scatter statique scalaire avec zones target
# ─────────────────────────────────────────────────────────────────────────────
class ScatterSummary(DataMixin, Block):
    """
    Scatter statique : X et Y = colonnes scalaires libres.
    Équivalent d'un GraphBuilder figé, avec zones target optionnelles.

    Params:
        data        : clé DataStore str ou pd.DataFrame
        x_col       : colonne scalaire axe X
        y_col       : colonne scalaire axe Y
        color_col   : scalaire catégoriel ou numérique → couleur
        size_col    : scalaire numérique → taille des points
        hover_cols  : colonnes supplémentaires dans le tooltip
        targets     : {"x": (lo, hi), "y": (lo, hi)} → zones target
        palette     : "aledia" | "D3" | "G10" | "process" (bleu/rouge MOCVD/MBE)
        process_col : si palette="process", cette colonne donne MOCVD/MBE
        log_x/log_y : échelle log
        height      : hauteur px
        trendline   : afficher droite OLS par groupe
    """
    needs_plotly = True

    def __init__(
        self,
        data: DataArg,
        x_col: str,
        y_col: str,
        color_col: str = "",
        size_col: str = "",
        hover_cols: list[str] | None = None,
        targets: dict | None = None,
        palette: str = "aledia",
        process_col: str = "",
        log_x: bool = False,
        log_y: bool = False,
        height: int = 400,
        trendline: bool = False,
        num: str = "—",
        title: str = "",
        subtitle: str = "",
        x_label: str = "",
        y_label: str = "",
    ):
        self._init_data(data)
        self.x_col = x_col; self.y_col = y_col
        self.color_col = color_col; self.size_col = size_col
        self.hover_cols = hover_cols or []
        self.targets = targets or {}
        self.palette = palette; self.process_col = process_col
        self.log_x = log_x; self.log_y = log_y
        self.height = height; self.trendline = trendline
        self.num = num
        self.title = title or f"{y_col} vs {x_col}"
        self.subtitle = subtitle
        self.x_label = x_label or x_col
        self.y_label = y_label or y_col
        self._id = f"ss_{id(self)}"

    def render(self, store=None) -> str:
        sid = self._id

        if self.has_local_data:
            # Df local : sérialisation inline des colonnes nécessaires uniquement
            df   = self.resolve_df()
            need = [self.x_col, self.y_col]
            for c in [self.color_col, self.size_col] + self.hover_cols:
                if c and c in df.columns and not _is_vector_col(df[c]):
                    need.append(c)
            need = list(dict.fromkeys(c for c in need if c in df.columns))
            recs = [{c: _safe_json(row[c]) for c in need}
                    for _, row in df[need].iterrows()]
            data_expr = json.dumps(recs)
        else:
            # Clé store : zéro copie — JS lit directement les records
            key = self._data_arg
            if store is None:
                raise RuntimeError(
                    f"ScatterSummary references store key {key!r} but no DataStore was provided."
                )
            store.resolve(key)  # valide que la clé existe
            data_expr = f"(window.__DATA_STORE__||{{}})[{json.dumps(key)}]||[]"

        targets_json = json.dumps(self.targets)
        log_x_js = "true" if self.log_x else "false"
        log_y_js = "true" if self.log_y else "false"
        trend_js = "true" if self.trendline else "false"
        x_esc = _h.escape(self.x_col); y_esc = _h.escape(self.y_col)
        x_label_esc = _h.escape(self.x_label); y_label_esc = _h.escape(self.y_label)
        hover_json = json.dumps(self.hover_cols)
        cc = _h.escape(self.color_col); sc = _h.escape(self.size_col)
        proc_col_js = json.dumps(self.process_col)

        return f"""
<div class="ss-wrap">
  <div class="ss-header">
    <span class="led-block-num">{_h.escape(self.num)}</span>
    <span class="led-block-title">{_h.escape(self.title)}</span>
    <span class="led-block-sub">{_h.escape(self.subtitle)}</span>
  </div>
  <div id="{sid}_plot" style="height:{self.height}px;"></div>
</div>

<script>
(function(){{
  var DATA      = {data_expr};
  var TARGETS   = {targets_json};
  var logX={log_x_js}, logY={log_y_js}, trendline={trend_js};
  var xCol="{x_esc}", yCol="{y_esc}", cCol="{cc}", sCol="{sc}";
  var xLabel="{x_label_esc}", yLabel="{y_label_esc}";
  var hoverCols = {hover_json};
  var procCol   = {proc_col_js};

  var PALETTES = {{
    aledia:["#0A2463","#D4AF37","#3e92cc","#e85d4a","#2dc653","#9b5de5"],
    D3:["#1F77B4","#FF7F0E","#2CA02C","#D62728","#9467BD","#8C564B"],
    G10:["#3366CC","#DC3912","#FF9900","#109618","#990099","#0099C6"],
    process:{{"MOCVD":"#3B82F6","MBE":"#EF4444","default":"#8B97BF"}},
  }};
  var GSTYLE={{gridcolor:"#E4E8F4",linecolor:"#E4E8F4",zerolinecolor:"#E4E8F4"}};
  var PLYCFG={{responsive:true,displaylogo:false,modeBarButtonsToRemove:["autoScale2d","toggleSpikelines","sendDataToCloud"]}};

  function groupBy(arr,key){{
    return arr.reduce(function(acc,r){{var k=r[key]!=null?String(r[key]):"?";(acc[k]=acc[k]||[]).push(r);return acc;}},{{}});
  }}
  function normSize(vals,mn,mx){{
    var c=vals.map(parseFloat).filter(function(v){{return !isNaN(v);}});
    if(!c.length) return Array(vals.length).fill((mn+mx)/2);
    var vi=Math.min.apply(null,c),va=Math.max.apply(null,c);
    return vals.map(function(v){{var n=parseFloat(v);return isNaN(n)?(mn+mx)/2:vi===va?(mn+mx)/2:mn+(n-vi)/(va-vi)*(mx-mn);}});
  }}
  function linReg(xs,ys){{
    var n=xs.length,sx=0,sy=0,sxy=0,sx2=0;
    for(var i=0;i<n;i++){{sx+=xs[i];sy+=ys[i];sxy+=xs[i]*ys[i];sx2+=xs[i]*xs[i];}}
    var sl=(n*sxy-sx*sy)/(n*sx2-sx*sx)||0;
    return {{slope:sl,intercept:(sy-sl*sx)/n}};
  }}

  /* Build target shapes & annotations */
  var shapes=[],annots=[];
  if(TARGETS.x){{
    shapes.push({{type:"rect",y0:0,y1:1,yref:"paper",x0:TARGETS.x[0],x1:TARGETS.x[1],xref:"x",
      fillcolor:"rgba(212,175,55,.1)",line:{{width:0}},layer:"below"}});
    annots.push({{y:1,yref:"paper",yanchor:"top",x:(TARGETS.x[0]+TARGETS.x[1])/2,xref:"x",
      text:"TARGET X",showarrow:false,font:{{family:"IBM Plex Mono",size:9,color:"rgba(212,175,55,.8)"}},bgcolor:"rgba(255,255,255,.7)",borderpad:2}});
  }}
  if(TARGETS.y){{
    shapes.push({{type:"rect",x0:0,x1:1,xref:"paper",y0:TARGETS.y[0],y1:TARGETS.y[1],yref:"y",
      fillcolor:"rgba(212,175,55,.1)",line:{{width:0}},layer:"below"}});
    annots.push({{x:1,xref:"paper",xanchor:"right",y:(TARGETS.y[0]+TARGETS.y[1])/2,yref:"y",
      text:"TARGET Y",showarrow:false,font:{{family:"IBM Plex Mono",size:9,color:"rgba(212,175,55,.8)"}},bgcolor:"rgba(255,255,255,.7)",borderpad:2}});
  }}

  /* Build traces */
  var useProcPal = (procCol && PALETTES.process);
  var pal = PALETTES["{self.palette}"] || PALETTES.aledia;
  var groups = cCol ? groupBy(DATA,cCol) : {{"":DATA}};
  var traces = [];
  Object.keys(groups).forEach(function(gk,gi){{
    var gdata=groups[gk];
    var color = useProcPal ? (PALETTES.process[gk]||PALETTES.process.default) : (Array.isArray(pal)?pal[gi%pal.length]:pal);
    var xs=gdata.map(function(r){{return r[xCol];}});
    var ys=gdata.map(function(r){{return r[yCol];}});
    var sz=sCol?normSize(gdata.map(function(r){{return r[sCol]||0;}}),5,24):8;
    var htxt=gdata.map(function(r){{
      var t="<b>"+(cCol?gk:"pt")+"</b><br>"+xCol+": "+r[xCol]+"<br>"+yCol+": "+r[yCol];
      hoverCols.forEach(function(c){{if(r[c]!=null)t+="<br>"+c+": "+r[c];}});
      return t;
    }});
    traces.push({{
      type:"scatter",mode:"markers",name:gk||"données",
      x:xs,y:ys,
      marker:{{color:color,size:sz,opacity:.85,line:{{width:.5,color:"rgba(0,0,0,.15)"}}}},
      text:htxt,hovertemplate:"%{{text}}<extra></extra>",
    }});
    if(trendline && xs.length>1){{
      var reg=linReg(xs.map(Number),ys.map(Number));
      var xs2=xs.slice().sort(function(a,b){{return a-b;}});
      traces.push({{type:"scatter",mode:"lines",name:"↗ "+gk,showlegend:false,
        x:[xs2[0],xs2[xs2.length-1]],
        y:[reg.slope*xs2[0]+reg.intercept,reg.slope*xs2[xs2.length-1]+reg.intercept],
        line:{{color:color,width:1.5,dash:"dash"}},hoverinfo:"skip"}});
    }}
  }});

  Plotly.newPlot("{sid}_plot", traces, {{
    paper_bgcolor:"rgba(0,0,0,0)",plot_bgcolor:"#F8F9FD",
    font:{{family:"IBM Plex Mono,monospace",color:"#4A5580",size:11}},
    margin:{{t:16,r:16,b:52,l:60}},
    xaxis:Object.assign({{}},GSTYLE,{{title:{{text:xLabel,font:{{size:12,color:"#0A2463"}},standoff:8}},type:logX?"log":"linear",tickfont:{{size:10}}}}),
    yaxis:Object.assign({{}},GSTYLE,{{title:{{text:yLabel,font:{{size:12,color:"#0A2463"}},standoff:8}},type:logY?"log":"linear",tickfont:{{size:10}}}}),
    legend:{{bgcolor:"rgba(0,0,0,0)",font:{{size:10}}}},
    hovermode:"closest",
    hoverlabel:{{bgcolor:"#0A2463",bordercolor:"#D4AF37",font:{{family:"IBM Plex Mono",size:10,color:"white"}}}},
    shapes:shapes, annotations:annots,
  }}, PLYCFG);
}})();
</script>
"""
