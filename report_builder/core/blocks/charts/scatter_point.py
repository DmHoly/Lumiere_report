from __future__ import annotations
import json
import html as _h
import numpy as np
import pandas as pd
from ..._helpers import Block, _safe_json, _is_vector_col
from ..data.data_mixin import DataMixin, DataArg


class ScatterPoint(DataMixin, Block):
    """
    Scatter scalaire : chaque ligne du df = une LED = UN point (x, y scalaires).

    Paramètres
    ----------
    x_col / y_col     : colonnes scalaires tracées sur le scatter principal
    color_col         : colonne scalaire pour colorier les points
    hover_cols        : colonnes scalaires ou vectorielles (résumé auto si vectoriel)
    eqe_x / eqe_y    : colonnes vectorielles → panel "eqe_y vs eqe_x" dans le détail
                        ex: eqe_x="J", eqe_y="Lambda_Dominant"  →  Lambda vs J
    curve_x / curve_y : colonnes vectorielles → panel "curve_y vs curve_x" dans le détail
                        ex: curve_x="V", curve_y="J"              →  J vs V
    spectra_col       : colonne vectorielle 2D (liste de spectres par courant)
    wavelength_col    : colonne vectorielle longueurs d'onde
    ref_val           : valeur scalaire de référence commune aux deux panels de courbe
                        (ex: 25 si J=25 A/cm²). Affichée comme :
                          - ligne verticale  sur le panel eqe   (axe eqe_x)
                          - ligne horizontale sur le panel curve (axe curve_y)
                        Le spectre affiché est celui dont l'index dans eqe_x est le
                        plus proche de ref_val.
    ref_val_col       : si ref_val varie par LED, passer le nom de la colonne scalaire.
                        Prend le dessus sur ref_val.
    ref_label         : étiquette de la ligne de référence (ex: "25 A/cm²")
    """
    needs_plotly = True

    def __init__(
        self,
        data: DataArg,
        x_col: str,
        y_col: str,
        color_col: str = "",
        hover_cols: list[str] | None = None,
        log_x: bool = False,
        log_y: bool = False,
        height: int = 480,
        curve_x: str = "",
        curve_y: str = "",
        eqe_x: str = "",
        eqe_y: str = "",
        spectra_col: str = "",
        wavelength_col: str = "",
        ref_val: float | None = None,
        ref_val_col: str = "",
        ref_label: str = "",
        id_col: str = "",
        num: str = "01",
        title: str = "",
        subtitle: str = "",
        x_range: tuple | None = None,
        y_range: tuple | None = None,
        x_label: str = "",
        y_label: str = "",
    ):
        self._init_data(data)
        self.x_col = x_col
        self.y_col = y_col
        self.color_col = color_col
        self.hover_cols = hover_cols or []
        self.log_x = log_x
        self.log_y = log_y
        self.height = height
        self.curve_x = curve_x
        self.curve_y = curve_y
        self.eqe_x = eqe_x
        self.eqe_y = eqe_y
        self.spectra_col = spectra_col
        self.wavelength_col = wavelength_col
        self.ref_val = ref_val
        self.ref_val_col = ref_val_col
        self.ref_label = ref_label or (str(ref_val) if ref_val is not None else "")
        self.id_col = id_col
        self.num = num
        self.title = title or f"{y_col} vs {x_col}"
        self.subtitle = subtitle
        self.x_range = x_range
        self.y_range = y_range
        self.x_label = x_label or x_col
        self.y_label = y_label or y_col
        self._id = f"spt_{id(self)}"

    # ── helpers ───────────────────────────────────────────────────────────────

    @staticmethod
    def _vec_summary(v) -> str:
        try:
            arr = np.asarray(v, dtype=float)
            arr = arr[np.isfinite(arr)]
            if len(arr) == 0:
                return "—"
            return f"min {arr.min():.3g} / max {arr.max():.3g} / mean {arr.mean():.3g}"
        except Exception:
            return str(v)[:40]

    @staticmethod
    def _downsample(arr, target=120):
        if not isinstance(arr, (list, np.ndarray)) or len(arr) <= target:
            return [_safe_json(x) for x in arr]
        step = max(1, len(arr) // target)
        return [_safe_json(arr[i]) for i in range(0, len(arr), step)]

    def _lambda_to_srgb(self, lam_nm: float) -> str:
        l = lam_nm
        if   l < 380: r, g, b = 0, 0, 0
        elif l < 440: r, g, b = -(l - 440) / 60, 0, 1
        elif l < 490: r, g, b = 0, (l - 440) / 50, 1
        elif l < 510: r, g, b = 0, 1, -(l - 510) / 20
        elif l < 580: r, g, b = (l - 510) / 70, 1, 0
        elif l < 645: r, g, b = 1, -(l - 645) / 65, 0
        elif l <= 700: r, g, b = 1, 0, 0
        else:          r, g, b = 0, 0, 0
        r, g, b = (max(0, min(1, x)) ** 0.8 for x in (r, g, b))
        return "#{:02x}{:02x}{:02x}".format(int(r * 255), int(g * 255), int(b * 255))

    def _build_lambda_colorscale(self) -> str:
        steps = list(range(400, 701, 5))
        scale = []
        for i, lam in enumerate(steps):
            t = i / (len(steps) - 1)
            scale.append([t, self._lambda_to_srgb(lam)])
        return json.dumps(scale)

    # ── data serialisation ────────────────────────────────────────────────────

    def _build_js_data(self, df: pd.DataFrame) -> str:
        records = []
        for _, row in df.iterrows():
            xv = _safe_json(row[self.x_col]) if self.x_col in row.index else None
            yv = _safe_json(row[self.y_col]) if self.y_col in row.index else None
            rec: dict = {"x": xv, "y": yv}

            if self.color_col and self.color_col in row.index:
                rec["color"] = _safe_json(row[self.color_col])

            for c in self.hover_cols:
                if c not in row.index:
                    continue
                v = row[c]
                rec[c] = self._vec_summary(v) if isinstance(v, (list, np.ndarray)) else _safe_json(v)

            for lam_col in ("Lambda_Dominant", "Lambda_peak", "lambda", "Lambda"):
                if lam_col in row.index and lam_col != self.color_col:
                    v = row[lam_col]
                    if not isinstance(v, (list, np.ndarray)):
                        rec["_lambda"] = _safe_json(v)
                    break

            for attr, col in (("cx", self.curve_x), ("cy", self.curve_y),
                               ("ex", self.eqe_x),  ("ey", self.eqe_y)):
                if col and col in row.index:
                    v = row[col]
                    rec[attr] = self._downsample(v) if isinstance(v, (list, np.ndarray)) else []

            if self.spectra_col and self.spectra_col in row.index:
                sp = row[self.spectra_col]
                if isinstance(sp, (list, np.ndarray)) and len(sp) > 0:
                    rec["spectra_all"] = [self._downsample(sp[i]) for i in range(len(sp))]

            if self.wavelength_col and self.wavelength_col in row.index:
                wl = row[self.wavelength_col]
                if isinstance(wl, (list, np.ndarray)):
                    rec["wl"] = self._downsample(wl)

            # Valeur de référence pour les barres (verticale sur EQE, horizontale sur JV)
            if self.ref_val_col and self.ref_val_col in row.index:
                rec["ref"] = _safe_json(row[self.ref_val_col])
            elif self.ref_val is not None:
                rec["ref"] = self.ref_val
            # sinon rec["ref"] absent → pas de barre affichée

            rec["_id"] = str(row[self.id_col]) if self.id_col and self.id_col in row.index \
                         else str(len(records))
            records.append(rec)
        return json.dumps(records)

    # ── render ────────────────────────────────────────────────────────────────

    def render(self, store=None) -> str:
        df = self.resolve_df(store)
        sid           = self._id
        data_json     = self._build_js_data(df)
        log_x_js      = "true"  if self.log_x else "false"
        log_y_js      = "true"  if self.log_y else "false"
        h             = self.height
        x_label       = _h.escape(self.x_label)
        y_label       = _h.escape(self.y_label)
        title_h       = _h.escape(self.title)
        sub_h         = _h.escape(self.subtitle)
        has_jv        = "true"  if self.curve_x  and self.curve_y  else "false"
        has_eqe       = "true"  if self.eqe_x    and self.eqe_y    else "false"
        has_spec      = "true"  if self.spectra_col                else "false"
        lambda_cs     = self._build_lambda_colorscale()
        x_range_js    = f"[{self.x_range[0]}, {self.x_range[1]}]" if self.x_range else "null"
        y_range_js    = f"[{self.y_range[0]}, {self.y_range[1]}]" if self.y_range else "null"
        hover_js      = self._hover_fields_js()
        eqe_x_esc     = _h.escape(self.eqe_x)
        eqe_y_esc     = _h.escape(self.eqe_y)
        curve_x_esc   = _h.escape(self.curve_x)
        curve_y_esc   = _h.escape(self.curve_y)
        fx_label      = _h.escape(self.x_col)
        fy_label      = _h.escape(self.y_col)
        ref_label_esc = _h.escape(self.ref_label)

        return f"""
<div class="led-block" id="{sid}_wrap">
  <div class="led-block-header">
    <span class="led-block-num">{_h.escape(self.num)}</span>
    <span class="led-block-title">{title_h}</span>
    <span class="led-block-sub">{sub_h}</span>
  </div>
  <div class="led-block-rule"></div>

  <!-- barre unifiée : sélection + filtres -->
  <div class="spt-combined-toolbar">
    <div class="spt-toolbar-group">
      <button class="slt-btn active" id="{sid}_btn_click" onclick="{sid}_setMode('click')">✦ CLIC</button>
      <button class="slt-btn" id="{sid}_btn_lasso" onclick="{sid}_setMode('lasso')">⬡ LASSO</button>
      <button class="slt-btn" id="{sid}_btn_box"   onclick="{sid}_setMode('box')">▣ ZONE</button>
      <button class="slt-btn" onclick="{sid}_clearSel()">✕</button>
      <span class="slt-count spt-selcount" id="{sid}_selcount">—</span>
    </div>
    <div class="spt-toolbar-divider"></div>
    <div class="spt-toolbar-group spt-filter-group">
      <span class="spt-filter-label">FILTRES</span>
      <span class="spt-filter-axis-tag">{fx_label}</span>
      <select class="spt-filter-op" id="{sid}_fx_op">
        <option value="">—</option>
        <option value="gt">&gt;</option><option value="gte">&ge;</option>
        <option value="lt">&lt;</option><option value="lte">&le;</option>
        <option value="eq">==</option><option value="neq">!=</option>
      </select>
      <input class="spt-filter-val" type="number" id="{sid}_fx_val" placeholder="—">
      <span class="spt-filter-sep">·</span>
      <span class="spt-filter-axis-tag">{fy_label}</span>
      <select class="spt-filter-op" id="{sid}_fy_op">
        <option value="">—</option>
        <option value="gt">&gt;</option><option value="gte">&ge;</option>
        <option value="lt">&lt;</option><option value="lte">&le;</option>
        <option value="eq">==</option><option value="neq">!=</option>
      </select>
      <input class="spt-filter-val" type="number" id="{sid}_fy_val" placeholder="—">
      <button class="slt-btn slt-btn--gold" onclick="{sid}_applyFilters()">▶ OK</button>
      <button class="slt-btn" onclick="{sid}_resetFilters()" title="Réinitialiser">↺</button>
      <span class="spt-filt-count" id="{sid}_filtcount"></span>
    </div>
  </div>

  <!-- layout principal -->
  <div class="sled-layout" id="{sid}_layout">
    <div class="sled-main" id="{sid}_main_col">
      <div id="{sid}_scatter" style="height:{h}px;"></div>
    </div>
    <div class="sled-detail-col" id="{sid}_detail">
      <div class="led-detail-inner">
        <div class="led-detail-header">
          <span class="led-block-num">↳</span>
          <span class="led-detail-label" id="{sid}_detlabel"><span>—</span></span>
          <button class="led-detail-close" onclick="{sid}_closeDetail()">✕ FERMER</button>
        </div>
        <div class="led-detail-plots" id="{sid}_detplots">

          <!-- Panel 1 : eqe_y vs eqe_x + barre verticale @ ref -->
          <div class="led-sub-wrap" id="{sid}_eqe_wrap">
            <div class="led-sub-hdr">
              <span class="led-sub-title">{eqe_y_esc} vs {eqe_x_esc}</span>
              <span class="led-sub-axes">courbe · barre @ {ref_label_esc}</span>
            </div>
            <div class="led-sub-body"><div id="{sid}_det_eqe"></div></div>
          </div>

          <!-- Panel 2 : curve_y vs curve_x + barre horizontale @ ref -->
          <div class="led-sub-wrap" id="{sid}_jv_wrap">
            <div class="led-sub-hdr">
              <span class="led-sub-title">{curve_y_esc} vs {curve_x_esc}</span>
              <span class="led-sub-axes">courbe · barre @ {ref_label_esc}</span>
            </div>
            <div class="led-sub-body"><div id="{sid}_det_jv"></div></div>
          </div>

          <!-- Panel 3 : spectre @ index le plus proche de ref -->
          <div class="led-sub-wrap" id="{sid}_spec_wrap">
            <div class="led-sub-hdr">
              <span class="led-sub-title">Spectre</span>
              <span class="led-sub-axes">@ {eqe_x_esc} ≈ {ref_label_esc}</span>
            </div>
            <div class="led-sub-body"><div id="{sid}_det_spec"></div></div>
          </div>

        </div>
      </div>
    </div>
  </div>
</div>

<script>
(function(){{
  var DATA = {data_json};
  var sid  = "{sid}";
  var logX = {log_x_js}, logY = {log_y_js};
  var hasJV   = {has_jv};
  var hasEQE  = {has_eqe};
  var hasSpec = {has_spec};
  var mode = "click";
  var selIdx = [];
  var highlightRi  = null;
  var filteredIndices = null;

  var MULTI_COLORS = ["#D4AF37","#3B82F6","#EF4444","#8B5CF6","#10B981","#F59E0B","#EC4899","#06B6D4","#84CC16","#F97316"];
  var PLYCFG = {{responsive:true,displaylogo:false,modeBarButtonsToRemove:["autoScale2d","toggleSpikelines","sendDataToCloud"]}};
  var GSTYLE = {{gridcolor:"#E4E8F4",linecolor:"#E4E8F4",zerolinecolor:"#E4E8F4"}};

  function subLayout(xt,yt,xl,yl){{
    return {{
      paper_bgcolor:"rgba(0,0,0,0)",plot_bgcolor:"#F8F9FD",
      font:{{family:"IBM Plex Mono,monospace",color:"#4A5580",size:10}},
      margin:{{t:6,r:8,b:36,l:48}},showlegend:false,
      xaxis:Object.assign({{}},GSTYLE,{{title:{{text:xt,font:{{size:10,color:"#0A2463"}},standoff:4}},type:xl?"log":"linear",tickfont:{{size:9}}}}),
      yaxis:Object.assign({{}},GSTYLE,{{title:{{text:yt,font:{{size:10,color:"#0A2463"}},standoff:4}},type:yl?"log":"linear",tickfont:{{size:9}}}}),
      hoverlabel:{{bgcolor:"#0A2463",bordercolor:"#D4AF37",font:{{family:"IBM Plex Mono",size:9,color:"white"}}}},
    }};
  }}

  var LAMBDA_COLORSCALE = {lambda_cs};
  var colorIsLambda=(function(){{
    var vals=DATA.map(function(r){{return r.color;}}).filter(function(v){{return v!=null&&!isNaN(v)&&v>=380&&v<=780;}});
    return vals.length>DATA.length*0.5;
  }})();

  /* ── Filtre scalaire ── */
  function evalFilter(val,op,thr){{
    if(!op||thr===""||thr==null||isNaN(+thr)) return true;
    var v=+val,t=+thr;
    if(isNaN(v)) return false;
    switch(op){{
      case"gt":return v>t;case"gte":return v>=t;
      case"lt":return v<t;case"lte":return v<=t;
      case"eq":return Math.abs(v-t)<1e-9;
      case"neq":return Math.abs(v-t)>=1e-9;
      default:return true;
    }}
  }}

  /* ── Index le plus proche de refVal dans arr ── */
  function closestIdx(arr,refVal){{
    if(refVal==null||isNaN(refVal)||!arr||!arr.length) return 0;
    var minD=Infinity,bi=0;
    arr.forEach(function(v,i){{var d=Math.abs(v-refVal);if(d<minD){{minD=d;bi=i;}}}});
    return bi;
  }}

  /* ── Calcul des plages pour rescale axes ── */
  function computeRange(vals,logScale){{
    var fv=vals.filter(function(v){{return v!=null&&!isNaN(v)&&isFinite(v)&&(!logScale||v>0);}});
    if(!fv.length) return null;
    var mn=Math.min.apply(null,fv),mx=Math.max.apply(null,fv);
    if(logScale){{
      var lm=Math.log10(mn),lM=Math.log10(mx),p=Math.max((lM-lm)*0.08,0.15);
      return[lm-p,lM+p];
    }}
    var p=(mx-mn)*0.06||Math.abs(mx)*0.05||0.01;
    return[mn-p,mx+p];
  }}

  /* ── Construction des traces scatter ── */
  function buildTraces(focusSet,hlRi){{
    var xs=[],ys=[],colors=[],sizes=[],texts=[],customdata=[];
    var hxs=[],hys=[];
    var redX=null,redY=null,redLabel=null;

    DATA.forEach(function(r,ri){{
      if(r.x==null||r.y==null||isNaN(r.x)||isNaN(r.y)) return;
      var pf=(filteredIndices===null||filteredIndices.has(ri));

      if(ri===hlRi&&pf){{redX=r.x;redY=r.y;redLabel=r._id;return;}}
      if(!pf){{hxs.push(r.x);hys.push(r.y);return;}}

      var focused=(focusSet===null||focusSet[ri]===true);
      if(focused){{
        xs.push(r.x);ys.push(r.y);
        colors.push(r.color!=null?r.color:"#D4AF37");
        sizes.push(focusSet!==null?10:9);
        customdata.push(ri);
        var htxt="<b>"+r._id+"</b>";
        htxt+="<br>{x_label}: "+r.x+"<br>{y_label}: "+r.y;
        {hover_js}
        if(r._lambda!=null) htxt+="<br>λ: "+r._lambda.toFixed(1)+" nm";
        texts.push(htxt);
      }}else{{hxs.push(r.x);hys.push(r.y);}}
    }});

    var traces=[];
    if(hxs.length) traces.push({{type:"scatter",mode:"markers",x:hxs,y:hys,
      marker:{{color:"rgba(0,0,0,0)",size:1,opacity:0}},hoverinfo:"skip",showlegend:false}});

    var mk=colorIsLambda?{{
      color:colors,colorscale:LAMBDA_COLORSCALE,showscale:true,cmin:400,cmax:700,
      size:sizes,opacity:0.92,line:{{width:focusSet!==null?1.2:0.5,color:"rgba(0,0,0,.2)"}},
      colorbar:{{title:{{text:"λ (nm)",font:{{size:10,color:"#0A2463"}},side:"right"}},
        thickness:12,len:0.75,x:1.01,tickfont:{{size:9,family:"IBM Plex Mono"}},
        tickvals:[400,450,500,550,600,650,700]}},
    }}:{{color:colors,size:sizes,opacity:0.92,
      line:{{width:focusSet!==null?1.2:0.5,color:"rgba(0,0,0,.2)"}}}};

    traces.push({{type:"scatter",mode:"markers",x:xs,y:ys,marker:mk,
      text:texts,hovertemplate:"%{{text}}<extra></extra>",customdata:customdata,showlegend:false}});

    if(redX!==null) traces.push({{
      type:"scatter",mode:"markers",x:[redX],y:[redY],
      marker:{{size:14,color:"#EF4444",symbol:"circle",line:{{width:2.5,color:"white"}}}},
      text:["<b>"+redLabel+"</b><br>{x_label}: "+redX+"<br>{y_label}: "+redY],
      hovertemplate:"%{{text}}<extra></extra>",showlegend:false}});

    return traces;
  }}

  /* ── Plages initiales (avant tout filtre) ── */
  var _aX=[],_aY=[];
  DATA.forEach(function(r){{if(r.x!=null&&!isNaN(r.x))_aX.push(r.x);if(r.y!=null&&!isNaN(r.y))_aY.push(r.y);}});
  function toRange(forced,log,vals){{
    if(forced!==null) return log?[Math.log10(forced[0]),Math.log10(forced[1])]:forced;
    return computeRange(vals,log);
  }}
  var xRange=toRange({x_range_js},logX,_aX);
  var yRange=toRange({y_range_js},logY,_aY);

  /* ── Tracé initial ── */
  Plotly.newPlot(sid+"_scatter",buildTraces(null,null),{{
    paper_bgcolor:"rgba(0,0,0,0)",plot_bgcolor:"#F8F9FD",
    font:{{family:"IBM Plex Mono,monospace",color:"#4A5580",size:11}},
    margin:{{t:10,r:colorIsLambda?60:16,b:48,l:64}},
    xaxis:Object.assign({{}},GSTYLE,{{
      title:{{text:"{x_label}",font:{{size:13,color:"#0A2463"}},standoff:8}},
      type:logX?"log":"linear",tickfont:{{size:11}},range:xRange,
      showspikes:true,spikecolor:"rgba(10,36,99,.3)",spikemode:"across",spikethickness:1,spikedash:"dot",
    }}),
    yaxis:Object.assign({{}},GSTYLE,{{
      title:{{text:"{y_label}",font:{{size:13,color:"#0A2463"}},standoff:8}},
      type:logY?"log":"linear",tickfont:{{size:11}},range:yRange,
      showspikes:true,spikecolor:"rgba(10,36,99,.3)",spikemode:"across",spikethickness:1,spikedash:"dot",
    }}),
    clickmode:"event+select",dragmode:false,hovermode:"closest",
    hoverlabel:{{bgcolor:"#0A2463",bordercolor:"#D4AF37",font:{{family:"IBM Plex Mono",size:10,color:"white"}}}},
    showlegend:false,
  }},PLYCFG);

  /* ── Rescale axes selon les données visibles ── */
  function rescaleToVisible(){{
    /* range forcé par Python → ne pas toucher */
    if({x_range_js}!==null && {y_range_js}!==null) return;
    var vx=[],vy=[];
    DATA.forEach(function(r,ri){{
      if(filteredIndices!==null&&!filteredIndices.has(ri)) return;
      if(r.x!=null&&!isNaN(r.x)) vx.push(r.x);
      if(r.y!=null&&!isNaN(r.y)) vy.push(r.y);
    }});
    var upd={{}};
    if({x_range_js}===null){{var rx=computeRange(vx,logX);if(rx)"xaxis.range"in upd||(upd["xaxis.range"]=rx);}}
    if({y_range_js}===null){{var ry=computeRange(vy,logY);if(ry)"yaxis.range"in upd||(upd["yaxis.range"]=ry);}}
    if(Object.keys(upd).length) Plotly.relayout(sid+"_scatter",upd);
  }}

  function openDetail(){{document.getElementById(sid+"_detail").classList.add("open");setTimeout(function(){{Plotly.Plots.resize(sid+"_scatter");}},400);}}
  function closeDetailPanel(){{document.getElementById(sid+"_detail").classList.remove("open");setTimeout(function(){{Plotly.Plots.resize(sid+"_scatter");}},400);}}

  window[sid+"_setMode"]=function(m){{
    mode=m;
    ["click","lasso","box"].forEach(function(x){{document.getElementById(sid+"_btn_"+x).classList.toggle("active",x===m);}});
    Plotly.relayout(sid+"_scatter",{{dragmode:m==="lasso"?"lasso":m==="box"?"select":false}});
  }};

  window[sid+"_clearSel"]=function(){{
    selIdx=[];highlightRi=null;
    document.getElementById(sid+"_selcount").textContent="—";
    document.getElementById(sid+"_selcount").classList.remove("has-sel");
    closeDetailPanel();
    Plotly.react(sid+"_scatter",buildTraces(null,null),document.getElementById(sid+"_scatter").layout,PLYCFG);
  }};
  window[sid+"_closeDetail"]=function(){{closeDetailPanel();}};

  /* ── Filtres ── */
  window[sid+"_applyFilters"]=function(){{
    var fxOp=document.getElementById(sid+"_fx_op").value;
    var fxVal=document.getElementById(sid+"_fx_val").value;
    var fyOp=document.getElementById(sid+"_fy_op").value;
    var fyVal=document.getElementById(sid+"_fy_val").value;
    if(!fxOp&&!fyOp){{window[sid+"_resetFilters"]();return;}}
    filteredIndices=new Set();
    DATA.forEach(function(r,ri){{if(evalFilter(r.x,fxOp,fxVal)&&evalFilter(r.y,fyOp,fyVal))filteredIndices.add(ri);}});
    var cnt=filteredIndices.size;
    var el=document.getElementById(sid+"_filtcount");
    el.textContent=cnt+" / "+DATA.length;
    el.className="spt-filt-count "+(cnt<DATA.length?"spt-filt-active":"spt-filt-ok");
    selIdx=[];highlightRi=null;closeDetailPanel();
    document.getElementById(sid+"_selcount").textContent="—";
    document.getElementById(sid+"_selcount").classList.remove("has-sel");
    var layout=document.getElementById(sid+"_scatter").layout;
    Plotly.react(sid+"_scatter",buildTraces(null,null),layout,PLYCFG);
    rescaleToVisible();
  }};

  window[sid+"_resetFilters"]=function(){{
    filteredIndices=null;
    ["fx_op","fx_val","fy_op","fy_val"].forEach(function(k){{document.getElementById(sid+"_"+k).value="";}});
    document.getElementById(sid+"_filtcount").textContent="";
    selIdx=[];highlightRi=null;closeDetailPanel();
    document.getElementById(sid+"_selcount").textContent="—";
    document.getElementById(sid+"_selcount").classList.remove("has-sel");
    var layout=document.getElementById(sid+"_scatter").layout;
    Plotly.react(sid+"_scatter",buildTraces(null,null),layout,PLYCFG);
    /* restaurer les plages initiales */
    var upd={{}};
    if({x_range_js}===null&&xRange) upd["xaxis.range"]=xRange;
    if({y_range_js}===null&&yRange) upd["yaxis.range"]=yRange;
    if(Object.keys(upd).length) Plotly.relayout(sid+"_scatter",upd);
  }};

  ["_fx_val","_fy_val"].forEach(function(sfx){{
    var el=document.getElementById(sid+sfx);
    if(el) el.addEventListener("keydown",function(e){{if(e.key==="Enter")window[sid+"_applyFilters"]();}});
  }});

  /* ── Shape Plotly pour les barres de référence ──
     On utilise des shapes (paper/data coords) plutôt que des traces
     pour ne pas perturber les axes. ── */
  function shapeVline(refVal, label){{
    /* ligne verticale x=refVal, s'étend sur toute la hauteur du plot */
    return {{
      type:"line",
      xref:"x", yref:"paper",        /* x en coordonnées data, y en [0,1] du plot */
      x0:refVal, y0:0, x1:refVal, y1:1,
      line:{{color:"rgba(212,175,55,0.85)", width:1.5, dash:"dash"}},
    }};
  }}

  function shapeHline(refVal, label){{
    /* ligne horizontale y=refVal, s'étend sur toute la largeur du plot */
    return {{
      type:"line",
      xref:"paper", yref:"y",        /* x en [0,1] du plot, y en coordonnées data */
      x0:0, y0:refVal, x1:1, y1:refVal,
      line:{{color:"rgba(212,175,55,0.85)", width:1.5, dash:"dash"}},
    }};
  }}

  function annotRef(refVal, label, axis){{
    /* petite annotation texte pour étiqueter la barre */
    var isV = (axis==="x");
    return {{
      xref: isV?"x":"paper", yref: isV?"paper":"y",
      x: isV?refVal:1, y: isV?1:refVal,
      xanchor: isV?"left":"right", yanchor: isV?"top":"middle",
      text: label||(""+refVal),
      showarrow:false,
      font:{{family:"IBM Plex Mono",size:9,color:"rgba(180,140,20,1)"}},
      bgcolor:"rgba(255,255,255,0.7)", borderpad:2,
    }};
  }}

  function renderDetail(ledIndices){{
    var isSingle=ledIndices.length===1;
    var refV=(ledIndices.length&&DATA[ledIndices[0]].ref!=null)?DATA[ledIndices[0]].ref:null;
    var refLbl="{ref_label_esc}";

    /* ── Panel 1 : eqe_y vs eqe_x + barre verticale @ ref ── */
    if(hasEQE){{
      var t=[];
      ledIndices.forEach(function(ri,ci){{
        var r=DATA[ri],col=MULTI_COLORS[ci%MULTI_COLORS.length];
        if(!r.ex||!r.ey||!r.ex.length) return;
        t.push({{x:r.ex,y:r.ey,type:"scatter",mode:"lines+markers",
          marker:{{size:3,color:col}},line:{{color:col,width:1.5}},
          name:r._id,hoverinfo:"x+y"}});
      }});
      if(t.length){{
        var lay=subLayout("{eqe_x_esc}","{eqe_y_esc}",logX,false);
        if(refV!=null){{
          lay.shapes=[shapeVline(refV,refLbl)];
          lay.annotations=[annotRef(refV,refLbl,"x")];
        }}
        Plotly.newPlot(sid+"_det_eqe",t,lay,PLYCFG);
      }}else{{
        document.getElementById(sid+"_det_eqe").innerHTML='<div class="no-data-msg">Pas de courbe</div>';
      }}
    }}

    /* ── Panel 2 : curve_y vs curve_x + barre horizontale @ ref ── */
    if(hasJV){{
      var t=[];
      ledIndices.forEach(function(ri,ci){{
        var r=DATA[ri],col=MULTI_COLORS[ci%MULTI_COLORS.length];
        if(!r.cx||!r.cy||!r.cx.length) return;
        t.push({{x:r.cx,y:r.cy,type:"scatter",mode:"lines+markers",
          marker:{{size:3,color:col}},line:{{color:col,width:1.5}},
          name:r._id,hoverinfo:"x+y",showlegend:false}});
      }});
      if(t.length){{
        var lay=subLayout("{curve_x_esc}","{curve_y_esc}",false,true);
        if(refV!=null){{
          lay.shapes=[shapeHline(refV,refLbl)];
          lay.annotations=[annotRef(refV,refLbl,"y")];
        }}
        Plotly.newPlot(sid+"_det_jv",t,lay,PLYCFG);
      }}else{{
        document.getElementById(sid+"_det_jv").innerHTML='<div class="no-data-msg">Pas de courbe JV</div>';
      }}
    }}

    /* Panel 3 : spectre @ index eqe_x le plus proche de ref */
    if(hasSpec){{
      var t=[];
      var actualJVals=[];
      ledIndices.forEach(function(ri,ci){{
        var r=DATA[ri],col=MULTI_COLORS[ci%MULTI_COLORS.length];
        if(!r.spectra_all||!r.wl) return;
        var refV=(r.ref!=null)?r.ref:null;
        var bi=closestIdx(r.ex,refV);
        var actualJ=(r.ex&&r.ex[bi]!=null)?r.ex[bi]:null;
        if(actualJ!=null) actualJVals.push(actualJ);
        var sp=r.spectra_all[Math.min(bi,r.spectra_all.length-1)];
        if(!sp||!sp.length) return;
        t.push({{x:r.wl,y:sp,type:"scatter",mode:"lines",
          line:{{color:col,width:1.5}},
          fill:isSingle?"tozeroy":"none",fillcolor:"rgba(139,92,246,.1)",
          name:r._id}});
      }});
      if(t.length){{
        var specAxesEl=document.querySelector("#"+sid+"_spec_wrap .led-sub-axes");
        if(specAxesEl&&actualJVals.length){{
          var jMin=Math.min.apply(null,actualJVals);
          var jMax=Math.max.apply(null,actualJVals);
          var jStr=(Math.abs(jMax-jMin)<0.01*Math.abs(jMax||1))
            ? jMin.toFixed(2)+" {eqe_x_esc}"
            : jMin.toFixed(2)+"–"+jMax.toFixed(2)+" {eqe_x_esc}";
          specAxesEl.textContent="@ "+jStr+" (réf: {ref_label_esc})";
        }}
        Plotly.newPlot(sid+"_det_spec",t,subLayout("λ (nm)","Intensity",false,false),PLYCFG);
      }}else{{
        document.getElementById(sid+"_det_spec").innerHTML='<div class="no-data-msg">Pas de spectre</div>';
      }}
    }}
  }}

  /* ── Événements Plotly ── */
  document.getElementById(sid+"_scatter").on("plotly_click",function(evt){{
    if(mode!=="click") return;
    var ri=evt.points[0].customdata;
    if(ri==null) return;
    selIdx=[ri];highlightRi=ri;
    var r=DATA[ri];
    document.getElementById(sid+"_selcount").textContent="● "+r._id;
    document.getElementById(sid+"_selcount").classList.add("has-sel");
    document.getElementById(sid+"_detlabel").innerHTML="<span>▸</span>"+r._id;
    openDetail();
    var fs={{}};fs[ri]=true;
    Plotly.react(sid+"_scatter",buildTraces(fs,ri),document.getElementById(sid+"_scatter").layout,PLYCFG);
    renderDetail([ri]);
  }});

  document.getElementById(sid+"_scatter").on("plotly_selected",function(evt){{
    if(!evt||!evt.points||!evt.points.length) return;
    var seen={{}};
    evt.points.forEach(function(p){{if(p.customdata!=null)seen[p.customdata]=true;}});
    selIdx=Object.keys(seen).map(Number);
    if(!selIdx.length) return;
    highlightRi=null;
    var cnt=selIdx.length;
    document.getElementById(sid+"_selcount").textContent=cnt+" LED"+(cnt>1?"s":"");
    document.getElementById(sid+"_selcount").classList.add("has-sel");
    document.getElementById(sid+"_detlabel").innerHTML="<span>▸</span>"+cnt+" LEDs";
    openDetail();
    var fs={{}};selIdx.forEach(function(i){{fs[i]=true;}});
    Plotly.react(sid+"_scatter",buildTraces(fs,null),document.getElementById(sid+"_scatter").layout,PLYCFG);
    renderDetail(selIdx.slice(0,12));
  }});

  document.getElementById(sid+"_scatter").on("plotly_deselect",function(){{window[sid+"_clearSel"]();}});
  document.getElementById(sid+"_scatter").addEventListener("dblclick",function(){{window[sid+"_clearSel"]();}});

  window.addEventListener("resize",function(){{
    Plotly.Plots.resize(sid+"_scatter");
    [sid+"_det_eqe",sid+"_det_jv",sid+"_det_spec"].forEach(function(eid){{
      var el=document.getElementById(eid);if(el&&el.data)Plotly.Plots.resize(eid);
    }});
  }});

  if(!hasEQE)  document.getElementById(sid+"_eqe_wrap").style.display="none";
  if(!hasJV)   document.getElementById(sid+"_jv_wrap").style.display="none";
  if(!hasSpec) document.getElementById(sid+"_spec_wrap").style.display="none";
  var vp=[hasEQE,hasJV,hasSpec].filter(Boolean).length;
  if(vp===1) document.getElementById(sid+"_detplots").style.gridTemplateColumns="1fr";
  if(vp===2) document.getElementById(sid+"_detplots").style.gridTemplateColumns="1fr 1fr";

}})();
</script>
"""

    def _hover_fields_js(self) -> str:
        lines = []
        for c in self.hover_cols:
            safe = c.replace('"', '\\"')
            lines.append(f'if(r["{safe}"]!=null) htxt+="<br>{safe}: "+r["{safe}"]')
        return (";\n        ".join(lines) + ";") if lines else ""