from __future__ import annotations
import json
import html as _h
import numpy as np
import pandas as pd
from ..._helpers import Block, _safe_json, _is_vector_col
from ..data.data_mixin import DataMixin, DataArg


class ScatterDrillDown(DataMixin, Block):
    """
    Scatter scalaire (un point par LED) avec panneau de détail vectoriel sur clic.

    x_col / y_col    : colonnes scalaires — un point par ligne du DataFrame
    color_col        : colonne scalaire pour la couleur (catégoriel ou numérique)
    hover_cols       : colonnes scalaires affichées dans le tooltip
    filter_cols      : colonnes scalaires pour la barre de filtres dynamique
    curves           : liste de dicts définissant les courbes vectorielles dans le panneau détail
                       {"label": str, "x": str, "y": str,
                        "log_x": bool, "log_y": bool, "x_label": str, "y_label": str}
    spectra_col      : colonne de spectres 2D (liste de listes, une par point de mesure)
    wavelength_col   : colonne des longueurs d'onde (1D)
    spectra_idx_col  : colonne scalaire → index du spectre à afficher (ex: "Idx at Max EQE")
    id_col           : colonne identifiant chaque LED
    palette          : "aledia" | "D3" | "G10"
    """

    needs_plotly = True

    def __init__(
        self,
        data: DataArg,
        x_col: str,
        y_col: str,
        color_col: str = "",
        hover_cols: list[str] | None = None,
        filter_cols: list[str] | None = None,
        curves: list[dict] | None = None,
        spectra_col: str = "",
        wavelength_col: str = "",
        spectra_idx_col: str = "",
        id_col: str = "",
        log_x: bool = False,
        log_y: bool = False,
        height: int = 480,
        palette: str = "aledia",
        num: str = "—",
        title: str = "",
        subtitle: str = "",
        x_label: str = "",
        y_label: str = "",
        x_range: tuple | None = None,
        y_range: tuple | None = None,
    ):
        self._init_data(data)
        self.x_col = x_col
        self.y_col = y_col
        self.color_col = color_col
        self.hover_cols = hover_cols or []
        self.filter_cols = filter_cols or []
        self.curves = curves or []
        self.spectra_col = spectra_col
        self.wavelength_col = wavelength_col
        self.spectra_idx_col = spectra_idx_col
        self.id_col = id_col
        self.log_x = log_x
        self.log_y = log_y
        self.height = height
        self.palette = palette
        self.num = num
        self.title = title or f"{y_col} vs {x_col}"
        self.subtitle = subtitle
        self.x_label = x_label or x_col
        self.y_label = y_label or y_col
        self.x_range = x_range
        self.y_range = y_range
        self._id = f"sdd_{id(self)}"

    # ── helpers ──────────────────────────────────────────────────────────────

    def _build_filter_meta(self, df: pd.DataFrame) -> str:
        meta = {}
        for col in self.filter_cols:
            if col not in df.columns:
                continue
            series = df[col].dropna()
            try:
                pd.to_numeric(series)
                meta[col] = {"type": "numeric"}
            except (ValueError, TypeError):
                uniq = sorted(series.astype(str).unique().tolist())
                meta[col] = {"type": "string", "values": uniq}
        return json.dumps(meta)

    def _build_filter_data(self, df: pd.DataFrame) -> str:
        records = []
        for _, row in df.iterrows():
            rec = {}
            for col in self.filter_cols:
                if col in row.index:
                    v = row[col]
                    if isinstance(v, (list, np.ndarray)):
                        continue
                    rec[col] = _safe_json(v)
            records.append(rec)
        return json.dumps(records)

    def _build_color_cfg(self, df: pd.DataFrame) -> dict:
        if not self.color_col or self.color_col not in df.columns:
            return {"type": "none"}
        series = df[self.color_col].dropna()
        try:
            num_series = pd.to_numeric(series)
            return {"type": "numeric", "min": float(num_series.min()), "max": float(num_series.max())}
        except (ValueError, TypeError):
            cats = sorted(series.astype(str).unique().tolist())
            return {"type": "categorical", "cats": cats}

    def _ds(self, v, target: int = 120) -> list:
        if not isinstance(v, (list, np.ndarray)) or len(v) <= target:
            return [_safe_json(x) for x in v]
        step = max(1, len(v) // target)
        return [_safe_json(v[i]) for i in range(0, len(v), step)]

    def _build_js_data(self, df: pd.DataFrame) -> str:
        records = []
        for _, row in df.iterrows():
            rec: dict = {
                "x": _safe_json(row[self.x_col]) if self.x_col in row.index else None,
                "y": _safe_json(row[self.y_col]) if self.y_col in row.index else None,
            }
            if self.color_col and self.color_col in row.index:
                rec["color"] = _safe_json(row[self.color_col])
            for c in self.hover_cols:
                if c in row.index:
                    rec[c] = _safe_json(row[c])
            crv = []
            for cv in self.curves:
                xk, yk = cv.get("x", ""), cv.get("y", "")
                vx = row[xk] if xk in row.index else []
                vy = row[yk] if yk in row.index else []
                crv.append({
                    "x": self._ds(vx) if isinstance(vx, (list, np.ndarray)) else [],
                    "y": self._ds(vy) if isinstance(vy, (list, np.ndarray)) else [],
                })
            rec["crv"] = crv
            if self.spectra_col and self.spectra_col in row.index:
                sp = row[self.spectra_col]
                if isinstance(sp, (list, np.ndarray)) and len(sp) > 0:
                    spec_idx = 0
                    if self.spectra_idx_col and self.spectra_idx_col in row.index:
                        idx_val = row[self.spectra_idx_col]
                        if pd.notna(idx_val):
                            spec_idx = max(0, min(int(idx_val), len(sp) - 1))
                    rec["sp"] = self._ds(sp[spec_idx])
            if self.wavelength_col and self.wavelength_col in row.index:
                wl = row[self.wavelength_col]
                if isinstance(wl, (list, np.ndarray)):
                    rec["wl"] = self._ds(wl)
            rec["_id"] = str(row[self.id_col]) if (self.id_col and self.id_col in row.index) else str(len(records))
            records.append(rec)
        return json.dumps(records)

    def _hover_js(self) -> str:
        lines = []
        for c in self.hover_cols:
            safe = c.replace('"', '\\"')
            lines.append(f'if(r["{safe}"]!=null)htxt+="<br>{safe}: "+r["{safe}"]')
        return ";\n        ".join(lines) if lines else ""

    # ── render ────────────────────────────────────────────────────────────────

    def render(self, store=None) -> str:
        sid = self._id

        if self.has_local_data:
            df = self.resolve_df()
            data_json        = self._build_js_data(df)
            filter_meta_json = self._build_filter_meta(df)
            filter_data_json = self._build_filter_data(df)
            color_cfg_json   = json.dumps(self._build_color_cfg(df))
            init_js = (
                f"var DATA={data_json};\n"
                f"  var FDATA={filter_data_json};\n"
                f"  var FMETA={filter_meta_json};\n"
                f"  var COLOR_CFG={color_cfg_json};"
            )
        else:
            key = self._data_arg
            if store is None:
                raise RuntimeError(
                    f"ScatterDrillDown references store key {key!r} but no DataStore was provided."
                )
            df = store.resolve(key)
            filter_meta = json.loads(self._build_filter_meta(df))
            color_cfg   = self._build_color_cfg(df)
            cfg = {
                "key":          key,
                "xCol":         self.x_col,
                "yCol":         self.y_col,
                "colorCol":     self.color_col or None,
                "idCol":        self.id_col or None,
                "hoverCols":    self.hover_cols,
                "filterCols":   self.filter_cols,
                "fmeta":        filter_meta,
                "colorCfg":     color_cfg,
                "curves":       [{"xk": cv.get("x",""), "yk": cv.get("y","")} for cv in self.curves],
                "spectraCol":   self.spectra_col or None,
                "wlCol":        self.wavelength_col or None,
                "specIdxCol":   self.spectra_idx_col or None,
            }
            cfg_json = json.dumps(cfg)
            init_js = (
                f"var _CFG={cfg_json};"
                f"var _raw=(window.__DATA_STORE__||{{}})[_CFG.key]||[];"
                f"var _ds=function(v,t){{if(!Array.isArray(v)||v.length<=t)return v;var s=Math.max(1,Math.floor(v.length/t)),r=[];for(var i=0;i<v.length;i+=s)r.push(v[i]);return r;}};"
                f"var DATA=_raw.map(function(r,i){{"
                f"  var rec={{x:r[_CFG.xCol]!=null?r[_CFG.xCol]:null,y:r[_CFG.yCol]!=null?r[_CFG.yCol]:null,"
                f"  color:_CFG.colorCol?r[_CFG.colorCol]:null,"
                f"  _id:(_CFG.idCol&&r[_CFG.idCol]!=null)?String(r[_CFG.idCol]):String(i)}};"
                f"  (_CFG.hoverCols||[]).forEach(function(c){{if(r[c]!=null)rec[c]=r[c];}});"
                f"  rec.crv=(_CFG.curves||[]).map(function(cv){{"
                f"    return {{x:_ds(r[cv.xk]||[],120),y:_ds(r[cv.yk]||[],120)}};}});"
                f"  if(_CFG.spectraCol&&r[_CFG.spectraCol]){{var sp=r[_CFG.spectraCol],"
                f"    si=_CFG.specIdxCol?(r[_CFG.specIdxCol]||0):0;"
                f"    si=Math.max(0,Math.min(Math.floor(si),sp.length-1));"
                f"    rec.sp=_ds(sp[si],120);}}"
                f"  if(_CFG.wlCol&&r[_CFG.wlCol])rec.wl=_ds(r[_CFG.wlCol],120);"
                f"  return rec;}});"
                f"var FDATA=_raw.map(function(r){{var fd={{}};"
                f"  (_CFG.filterCols||[]).forEach(function(c){{if(r[c]!=null)fd[c]=r[c];}});return fd;}});"
                f"var FMETA=_CFG.fmeta||{{}};"
                f"var COLOR_CFG=_CFG.colorCfg||{{type:'none'}};"
            )

        # ── HTML for curve sub-panels ──────────────────────────────────────────
        curves_html = ""
        for i, cv in enumerate(self.curves):
            lbl = _h.escape(cv.get("label", f"Courbe {i + 1}"))
            xl  = _h.escape(cv.get("x_label", cv.get("x", "")))
            yl  = _h.escape(cv.get("y_label", cv.get("y", "")))
            curves_html += (
                f'<div class="sdd-sub-wrap">'
                f'<div class="led-sub-hdr">'
                f'<span class="led-sub-title">{lbl}</span>'
                f'<span class="led-sub-axes">{xl} / {yl}</span>'
                f'</div>'
                f'<div class="led-sub-body"><div id="{sid}_crv{i}"></div></div>'
                f'</div>'
            )

        spec_html = ""
        if self.spectra_col:
            spec_html = (
                f'<div class="sdd-sub-wrap">'
                f'<div class="led-sub-hdr">'
                f'<span class="led-sub-title">Spectre</span>'
                f'<span class="led-sub-axes">@ pt optimal</span>'
                f'</div>'
                f'<div class="led-sub-body"><div id="{sid}_spec"></div></div>'
                f'</div>'
            )

        n_panels = len(self.curves) + (1 if self.spectra_col else 0)
        grid_cols = min(max(n_panels, 1), 3)

        # ── JS config ─────────────────────────────────────────────────────────
        curves_cfg_js = json.dumps([{
            "label":   cv.get("label", f"Courbe {i+1}"),
            "xk":      cv.get("x", ""),
            "yk":      cv.get("y", ""),
            "log_x":   bool(cv.get("log_x", False)),
            "log_y":   bool(cv.get("log_y", False)),
            "x_label": cv.get("x_label", cv.get("x", "")),
            "y_label": cv.get("y_label", cv.get("y", "")),
        } for i, cv in enumerate(self.curves)])

        has_spec_js    = "true" if self.spectra_col else "false"
        has_filters_js = "true" if self.filter_cols else "false"
        log_x_js       = "true" if self.log_x else "false"
        log_y_js       = "true" if self.log_y else "false"
        x_range_js     = json.dumps(list(self.x_range)) if self.x_range else "null"
        y_range_js     = json.dumps(list(self.y_range)) if self.y_range else "null"
        hover_js       = self._hover_js()
        pal_key        = self.palette if self.palette in ("aledia", "D3", "G10") else "aledia"

        return f"""
<div class="led-block" id="{sid}_wrap">
  <div class="led-block-header">
    <span class="led-block-num">{_h.escape(self.num)}</span>
    <span class="led-block-title">{_h.escape(self.title)}</span>
    <span class="led-block-sub">{_h.escape(self.subtitle)}</span>
  </div>
  <div class="led-block-rule"></div>

  <!-- toolbar mode -->
  <div class="scatter-led-toolbar">
    <button class="slt-btn active" id="{sid}_btn_click" onclick="{sid}_setMode('click')">✦ CLIC</button>
    <button class="slt-btn" id="{sid}_btn_lasso" onclick="{sid}_setMode('lasso')">⬡ LASSO</button>
    <button class="slt-btn" id="{sid}_btn_box"   onclick="{sid}_setMode('box')">▣ ZONE</button>
    <div class="slt-sep"></div>
    <button class="slt-btn" onclick="{sid}_clearSel()">✕ EFFACER</button>
    <span class="slt-count" id="{sid}_selcount">Aucune sélection</span>
  </div>

  <!-- barre de filtres -->
  <div class="sled-filter-bar" id="{sid}_filterbar" style="display:none">
    <div class="sled-filter-header">
      <span class="spt-filter-label">FILTRES</span>
      <button class="slt-btn slt-btn--gold" onclick="{sid}_addFilter()">+ AJOUTER</button>
      <button class="slt-btn" onclick="{sid}_applyFilters()">▶ APPLIQUER</button>
      <button class="slt-btn" onclick="{sid}_resetFilters()">↺ RESET</button>
      <span class="spt-filt-count" id="{sid}_filtcount"></span>
    </div>
    <div class="sled-filter-rows" id="{sid}_filterrows"></div>
  </div>

  <!-- layout principal -->
  <div class="sled-layout" id="{sid}_layout">
    <div class="sled-main" id="{sid}_main_col">
      <div id="{sid}_scatter" style="height:{self.height}px;"></div>
    </div>
    <div class="sled-detail-col" id="{sid}_detail">
      <div class="led-detail-inner">
        <div class="led-detail-header">
          <span class="led-block-num">↳</span>
          <span class="led-detail-label" id="{sid}_detlabel"><span>—</span></span>
          <button class="led-detail-close" onclick="{sid}_closeDetail()">✕ FERMER</button>
        </div>
        <!-- KPI scalaires du point sélectionné -->
        <div id="{sid}_det_kpi" style="display:none;padding:6px 12px;font-family:'IBM Plex Mono',monospace;font-size:11px;color:#4A5580;border-bottom:1px solid #E4E8F4;flex-wrap:wrap;gap:10px;"></div>
        <!-- grille de courbes + spectre -->
        <div class="led-detail-plots" id="{sid}_detplots" style="grid-template-columns:repeat({grid_cols},1fr);">
          {curves_html}
          {spec_html}
        </div>
      </div>
    </div>
  </div>
</div>

<script>
(function(){{
  {init_js}

  var sid       = "{sid}";
  var logX      = {log_x_js}, logY = {log_y_js};
  var hasSpec   = {has_spec_js};
  var hasFilters= {has_filters_js};
  var CURVES_CFG= {curves_cfg_js};
  var mode      = "click";
  var selIdx    = [];
  var filteredIndices = null;
  var filterRowCount  = 0;

  var PALETTES = {{
    aledia:["#0A2463","#D4AF37","#3e92cc","#e85d4a","#2dc653","#9b5de5","#F59E0B","#EC4899","#06B6D4","#84CC16"],
    D3:["#1F77B4","#FF7F0E","#2CA02C","#D62728","#9467BD","#8C564B"],
    G10:["#3366CC","#DC3912","#FF9900","#109618","#990099","#0099C6"],
  }};
  var PAL = PALETTES["{pal_key}"] || PALETTES.aledia;
  var MULTI_COLORS = PAL;

  var GSTYLE = {{gridcolor:"#E4E8F4",linecolor:"#E4E8F4",zerolinecolor:"#E4E8F4"}};
  var PLYCFG = {{responsive:true,displaylogo:false,modeBarButtonsToRemove:["autoScale2d","toggleSpikelines","sendDataToCloud"]}};

  if(hasFilters) document.getElementById(sid+"_filterbar").style.display="block";

  /* ── Color mapping ─────────────────────────────────────────────────────── */
  var catMap = {{}};
  if(COLOR_CFG.type==="categorical"){{
    (COLOR_CFG.cats||[]).forEach(function(c,i){{catMap[c]=PAL[i%PAL.length];}});
  }}
  function getColor(r){{
    if(COLOR_CFG.type==="none") return "#D4AF37";
    if(COLOR_CFG.type==="categorical"){{
      var k=r.color!=null?String(r.color):"?";
      if(!catMap[k])catMap[k]=PAL[Object.keys(catMap).length%PAL.length];
      return catMap[k];
    }}
    if(COLOR_CFG.type==="numeric"){{
      var mn=COLOR_CFG.min,mx=COLOR_CFG.max,v=parseFloat(r.color);
      if(isNaN(v)||mx===mn) return PAL[0];
      var t=(v-mn)/(mx-mn);
      /* blue→gold gradient */
      var r1=Math.round((10+(212-10)*t)),g1=Math.round((36+(175-36)*t)),b1=Math.round((99+(55-99)*t));
      return "rgb("+r1+","+g1+","+b1+")";
    }}
    return "#D4AF37";
  }}

  /* ── Sub-layout helper ─────────────────────────────────────────────────── */
  function subLayout(xl,yl,lx,ly){{
    return {{
      paper_bgcolor:"rgba(0,0,0,0)",plot_bgcolor:"#F8F9FD",
      font:{{family:"IBM Plex Mono,monospace",color:"#4A5580",size:10}},
      margin:{{t:6,r:8,b:36,l:48}},showlegend:false,
      xaxis:Object.assign({{}},GSTYLE,{{title:{{text:xl,font:{{size:10,color:"#0A2463"}},standoff:4}},type:lx?"log":"linear",tickfont:{{size:9}}}}),
      yaxis:Object.assign({{}},GSTYLE,{{title:{{text:yl,font:{{size:10,color:"#0A2463"}},standoff:4}},type:ly?"log":"linear",tickfont:{{size:9}}}}),
      hoverlabel:{{bgcolor:"#0A2463",bordercolor:"#D4AF37",font:{{family:"IBM Plex Mono",size:9,color:"white"}}}},
    }};
  }}

  /* ── Axis range helpers ────────────────────────────────────────────────── */
  function toPlotlyRange(forced,logScale,allVals){{
    if(forced!==null){{if(logScale)return[Math.log10(forced[0]),Math.log10(forced[1])];return forced;}}
    if(!allVals.length) return null;
    var mn=Math.min.apply(null,allVals),mx=Math.max.apply(null,allVals);
    if(logScale){{var lMn=Math.log10(mn),lMx=Math.log10(mx),pad=Math.max((lMx-lMn)*0.05,0.2);return[lMn-pad,lMx+pad];}}
    var pad=(mx-mn)*0.05||Math.abs(mx)*0.05||0.01;return[mn-pad,mx+pad];
  }}
  var _allX=[],_allY=[];
  DATA.forEach(function(r){{
    if(r.x!=null&&!isNaN(r.x)&&(!logX||r.x>0))_allX.push(+r.x);
    if(r.y!=null&&!isNaN(r.y)&&(!logY||r.y>0))_allY.push(+r.y);
  }});
  var xRange=toPlotlyRange({x_range_js},logX,_allX);
  var yRange=toPlotlyRange({y_range_js},logY,_allY);

  /* ── Build main scatter traces ─────────────────────────────────────────── */
  function buildMainTraces(focusIdx){{
    var focusSet=null;
    if(focusIdx!==null){{
      focusSet={{}};
      if(Array.isArray(focusIdx))focusIdx.forEach(function(i){{focusSet[i]=true;}});
      else focusSet[focusIdx]=true;
    }}

    var xs=[],ys=[],colors=[],sizes=[],cdata=[],texts=[];
    var gxs=[],gys=[];

    DATA.forEach(function(r,ri){{
      if(r.x==null||r.y==null) return;
      var passF=(filteredIndices===null||filteredIndices.has(ri));
      var isFoc=(focusSet===null||focusSet[ri]===true);

      var htxt="<b>"+r._id+"</b>";
      {hover_js};
      htxt+="<br>{_h.escape(self.x_label)}: "+r.x+"<br>{_h.escape(self.y_label)}: "+r.y;

      if(isFoc&&passF){{
        xs.push(r.x);ys.push(r.y);
        colors.push(getColor(r));
        sizes.push(focusSet!==null?11:8);
        cdata.push(ri);
        texts.push(htxt);
      }}else{{
        gxs.push(r.x);gys.push(r.y);
      }}
    }});

    var traces=[];
    if(gxs.length) traces.push({{
      type:"scatter",mode:"markers",x:gxs,y:gys,
      marker:{{color:"rgba(0,0,0,0)",size:1,opacity:0}},
      hoverinfo:"skip",showlegend:false,
    }});
    traces.push({{
      type:"scatter",mode:"markers",x:xs,y:ys,
      marker:{{color:colors,size:sizes,opacity:0.9,
        line:{{width:focusSet!==null?1.2:0.5,color:focusSet!==null?"#1a1a2e":"rgba(0,0,0,.15)"}}}},
      text:texts,hovertemplate:"%{{text}}<extra></extra>",
      customdata:cdata,showlegend:false,
    }});
    return traces;
  }}

  /* ── Legend (catégoriel) ───────────────────────────────────────────────── */
  if(COLOR_CFG.type==="categorical"&&COLOR_CFG.cats&&COLOR_CFG.cats.length){{
    var lgd=document.createElement("div");
    lgd.style.cssText="display:flex;flex-wrap:wrap;gap:8px;padding:4px 0 8px 16px;font-family:IBM Plex Mono,monospace;font-size:10px;color:#4A5580;";
    COLOR_CFG.cats.forEach(function(c,i){{
      var item=document.createElement("span");
      item.style.cssText="display:flex;align-items:center;gap:4px;cursor:pointer;";
      var chip=document.createElement("span");
      chip.style.cssText="width:10px;height:10px;border-radius:50%;background:"+PAL[i%PAL.length]+";display:inline-block;";
      item.appendChild(chip);
      item.appendChild(document.createTextNode(c));
      lgd.appendChild(item);
    }});
    document.getElementById(sid+"_main_col").appendChild(lgd);
  }}

  /* ── Initial plot ──────────────────────────────────────────────────────── */
  Plotly.newPlot(sid+"_scatter",buildMainTraces(null),{{
    paper_bgcolor:"rgba(0,0,0,0)",plot_bgcolor:"#F8F9FD",
    font:{{family:"IBM Plex Mono,monospace",color:"#4A5580",size:11}},
    margin:{{t:10,r:16,b:48,l:64}},
    xaxis:Object.assign({{}},GSTYLE,{{
      title:{{text:"{_h.escape(self.x_label)}",font:{{size:13,color:"#0A2463"}},standoff:8}},
      type:logX?"log":"linear",tickfont:{{size:11}},range:xRange,
      showspikes:true,spikecolor:"rgba(10,36,99,.3)",spikemode:"across",spikethickness:1,spikedash:"dot",
    }}),
    yaxis:Object.assign({{}},GSTYLE,{{
      title:{{text:"{_h.escape(self.y_label)}",font:{{size:13,color:"#0A2463"}},standoff:8}},
      type:logY?"log":"linear",tickfont:{{size:11}},range:yRange,
      showspikes:true,spikecolor:"rgba(10,36,99,.3)",spikemode:"across",spikethickness:1,spikedash:"dot",
    }}),
    clickmode:"event+select",dragmode:false,hovermode:"closest",
    hoverlabel:{{bgcolor:"#0A2463",bordercolor:"#D4AF37",font:{{family:"IBM Plex Mono",size:10,color:"white"}}}},
    showlegend:false,
  }},PLYCFG);

  /* ── Panel open/close ─────────────────────────────────────────────────── */
  function openDetail(){{
    document.getElementById(sid+"_detail").classList.add("open");
    setTimeout(function(){{Plotly.Plots.resize(sid+"_scatter");}},400);
  }}
  function closeDetailPanel(){{
    document.getElementById(sid+"_detail").classList.remove("open");
    setTimeout(function(){{Plotly.Plots.resize(sid+"_scatter");}},400);
  }}

  /* ── Render detail panel ──────────────────────────────────────────────── */
  function renderDetail(riList){{
    var isSingle=riList.length===1;
    var kpiEl=document.getElementById(sid+"_det_kpi");
    if(isSingle){{
      var r=DATA[riList[0]];
      var kpis=[];
      {"; ".join([f'if(r["{c.replace(chr(34), chr(39))}"]!=null)kpis.push("<b>{_h.escape(c)}</b>: "+r["{c.replace(chr(34), chr(39))}"])' for c in self.hover_cols[:8]])};
      if(kpis.length){{kpiEl.innerHTML=kpis.join(" &nbsp;·&nbsp; ");kpiEl.style.display="flex";}}
      else kpiEl.style.display="none";
    }}else kpiEl.style.display="none";

    /* curves */
    CURVES_CFG.forEach(function(cv,i){{
      var elId=sid+"_crv"+i;
      var traces=[];
      riList.forEach(function(ri,ci){{
        var r=DATA[ri],cd=r.crv[i];
        if(!cd||!cd.x||!cd.y||!cd.x.length) return;
        var col=MULTI_COLORS[ci%MULTI_COLORS.length];
        traces.push({{
          x:cd.x,y:cd.y,type:"scatter",mode:"lines+markers",
          marker:{{size:3,color:col}},line:{{color:col,width:isSingle?1.5:1}},
          name:r._id,hoverinfo:"x+y",
        }});
      }});
      if(traces.length)
        Plotly.newPlot(elId,traces,subLayout(cv.x_label,cv.y_label,cv.log_x,cv.log_y),PLYCFG);
      else
        document.getElementById(elId).innerHTML='<div class="no-data-msg">Pas de données</div>';
    }});

    /* spectre */
    if(hasSpec){{
      var spEl=sid+"_spec";
      var spTraces=[];
      riList.forEach(function(ri,ci){{
        var r=DATA[ri];
        if(!r.sp||!r.sp.length||!r.wl) return;
        var col=MULTI_COLORS[ci%MULTI_COLORS.length];
        spTraces.push({{
          x:r.wl,y:r.sp,type:"scatter",mode:"lines",
          line:{{color:col,width:1.5}},
          fill:isSingle?"tozeroy":"none",fillcolor:"rgba(139,92,246,.1)",
          name:r._id,
        }});
      }});
      if(spTraces.length)
        Plotly.newPlot(spEl,spTraces,subLayout("λ (nm)","Intensité",false,false),PLYCFG);
      else
        document.getElementById(spEl).innerHTML='<div class="no-data-msg">Pas de spectre</div>';
    }}
  }}

  /* ── Mode / sélection ─────────────────────────────────────────────────── */
  window[sid+"_setMode"]=function(m){{
    mode=m;
    ["click","lasso","box"].forEach(function(x){{
      document.getElementById(sid+"_btn_"+x).classList.toggle("active",x===m);
    }});
    Plotly.relayout(sid+"_scatter",{{dragmode:m==="lasso"?"lasso":m==="box"?"select":false}});
  }};

  window[sid+"_clearSel"]=function(){{
    selIdx=[];
    document.getElementById(sid+"_selcount").textContent="Aucune sélection";
    document.getElementById(sid+"_selcount").classList.remove("has-sel");
    closeDetailPanel();
    var layout=document.getElementById(sid+"_scatter").layout;
    Plotly.react(sid+"_scatter",buildMainTraces(null),layout,PLYCFG);
  }};
  window[sid+"_closeDetail"]=function(){{closeDetailPanel();}};

  /* ── Click ─────────────────────────────────────────────────────────────── */
  document.getElementById(sid+"_scatter").on("plotly_click",function(evt){{
    if(mode!=="click") return;
    var pt=evt.points[0];
    if(!pt||pt.customdata==null) return;
    var ri=pt.customdata;
    selIdx=[ri];
    var r=DATA[ri];
    document.getElementById(sid+"_selcount").textContent="LED · "+r._id;
    document.getElementById(sid+"_selcount").classList.add("has-sel");
    document.getElementById(sid+"_detlabel").innerHTML="<span>▸</span>"+r._id;
    openDetail();
    var savedLayout=document.getElementById(sid+"_scatter").layout;
    Plotly.react(sid+"_scatter",buildMainTraces(ri),savedLayout,PLYCFG);
    renderDetail([ri]);
  }});

  /* ── Lasso / box ──────────────────────────────────────────────────────── */
  document.getElementById(sid+"_scatter").on("plotly_selected",function(evt){{
    if(!evt||!evt.points||!evt.points.length) return;
    var seen={{}};
    evt.points.forEach(function(p){{if(p.customdata!=null)seen[p.customdata]=true;}});
    selIdx=Object.keys(seen).map(Number);
    if(!selIdx.length) return;
    var cnt=selIdx.length;
    document.getElementById(sid+"_selcount").textContent=cnt+" LED"+(cnt>1?"s":"");
    document.getElementById(sid+"_selcount").classList.add("has-sel");
    document.getElementById(sid+"_detlabel").innerHTML="<span>▸</span>"+cnt+" LEDs";
    openDetail();
    var savedLayout=document.getElementById(sid+"_scatter").layout;
    Plotly.react(sid+"_scatter",buildMainTraces(selIdx),savedLayout,PLYCFG);
    renderDetail(selIdx.slice(0,12));
  }});

  document.getElementById(sid+"_scatter").on("plotly_deselect",function(){{window[sid+"_clearSel"]();}});
  document.getElementById(sid+"_scatter").addEventListener("dblclick",function(){{window[sid+"_clearSel"]();}});

  /* ── Resize ─────────────────────────────────────────────────────────────── */
  window.addEventListener("resize",function(){{
    Plotly.Plots.resize(sid+"_scatter");
    CURVES_CFG.forEach(function(_,i){{
      var el=document.getElementById(sid+"_crv"+i);if(el&&el.data)Plotly.Plots.resize(sid+"_crv"+i);
    }});
    if(hasSpec){{var el=document.getElementById(sid+"_spec");if(el&&el.data)Plotly.Plots.resize(sid+"_spec");}}
  }});

  /* ── Filtres ────────────────────────────────────────────────────────────── */
  function evalNumFilter(val,op,thr){{
    if(!op||thr===""||isNaN(+thr))return true;
    var v=+val,t=+thr;if(isNaN(v))return false;
    switch(op){{case"gt":return v>t;case"gte":return v>=t;case"lt":return v<t;case"lte":return v<=t;case"eq":return Math.abs(v-t)<1e-9;case"neq":return Math.abs(v-t)>=1e-9;default:return true;}}
  }}
  function evalStrFilter(val,values){{return(!values||!values.length)||values.indexOf(String(val))>=0;}}

  function computeFilteredSet(){{
    var rows=document.querySelectorAll("#"+sid+"_filterrows .sled-frow");
    if(!rows.length)return null;
    var hasActive=false;
    rows.forEach(function(row){{
      var col=row.querySelector(".sled-fcol").value;if(!col)return;
      var meta=FMETA[col];if(!meta)return;
      if(meta.type==="numeric"){{var op=row.querySelector(".sled-fop").value,val=row.querySelector(".sled-fval-num").value;if(op&&val!=="")hasActive=true;}}
      else{{if(row.querySelectorAll(".sled-fchk:checked").length)hasActive=true;}}
    }});
    if(!hasActive)return null;
    var result=new Set();
    FDATA.forEach(function(fd,ri){{
      var pass=true;
      rows.forEach(function(row){{
        if(!pass)return;
        var col=row.querySelector(".sled-fcol").value;if(!col)return;
        var meta=FMETA[col];if(!meta)return;
        var val=fd[col];if(val==null)return;
        if(meta.type==="numeric"){{
          if(!evalNumFilter(val,row.querySelector(".sled-fop").value,row.querySelector(".sled-fval-num").value))pass=false;
        }}else{{
          var checked=[];row.querySelectorAll(".sled-fchk:checked").forEach(function(c){{checked.push(c.value);}});
          if(!evalStrFilter(val,checked))pass=false;
        }}
      }});
      if(pass)result.add(ri);
    }});
    return result;
  }}

  window[sid+"_addFilter"]=function(){{
    var cols=Object.keys(FMETA);if(!cols.length)return;
    filterRowCount++;
    var rowId=sid+"_frow"+filterRowCount;
    var container=document.getElementById(sid+"_filterrows");
    var row=document.createElement("div");row.className="sled-frow";row.id=rowId;
    var sel=document.createElement("select");sel.className="sled-fcol spt-filter-op";sel.style.minWidth="160px";
    var opt0=document.createElement("option");opt0.value="";opt0.textContent="— colonne —";sel.appendChild(opt0);
    cols.forEach(function(c){{var o=document.createElement("option");o.value=c;o.textContent=c;sel.appendChild(o);}});
    var ctrl=document.createElement("div");ctrl.className="sled-fctrl";
    var del=document.createElement("button");del.className="slt-btn";del.textContent="✕";
    del.onclick=function(){{row.remove();window[sid+"_applyFilters"]();}};
    sel.onchange=function(){{
      ctrl.innerHTML="";var col=sel.value;if(!col)return;
      var meta=FMETA[col];if(!meta)return;
      if(meta.type==="numeric"){{
        var opSel=document.createElement("select");opSel.className="sled-fop spt-filter-op";
        [["","—"],["gt","&gt;"],["gte","&ge;"],["lt","&lt;"],["lte","&le;"],["eq","=="],["neq","!="]].forEach(function(p){{
          var o=document.createElement("option");o.value=p[0];o.innerHTML=p[1];opSel.appendChild(o);
        }});
        var numIn=document.createElement("input");numIn.type="number";numIn.className="sled-fval-num spt-filter-val";numIn.placeholder="valeur";
        numIn.addEventListener("keydown",function(e){{if(e.key==="Enter")window[sid+"_applyFilters"]();}});
        ctrl.appendChild(opSel);ctrl.appendChild(numIn);
      }}else{{
        var wrap=document.createElement("div");wrap.className="sled-fchk-wrap";
        meta.values.forEach(function(v){{
          var lbl=document.createElement("label");lbl.className="sled-fchk-label";
          var chk=document.createElement("input");chk.type="checkbox";chk.className="sled-fchk";chk.value=v;
          var span=document.createElement("span");span.textContent=v;
          lbl.appendChild(chk);lbl.appendChild(span);wrap.appendChild(lbl);
        }});
        ctrl.appendChild(wrap);
      }}
    }};
    row.appendChild(sel);row.appendChild(ctrl);row.appendChild(del);container.appendChild(row);
  }};

  window[sid+"_applyFilters"]=function(){{
    filteredIndices=computeFilteredSet();
    var total=DATA.length,cnt=filteredIndices?filteredIndices.size:total;
    var el=document.getElementById(sid+"_filtcount");
    if(filteredIndices){{el.textContent=cnt+" / "+total;el.className="spt-filt-count "+(cnt<total?"spt-filt-active":"spt-filt-ok");}}
    else el.textContent="";
    selIdx=[];
    document.getElementById(sid+"_selcount").textContent="Aucune sélection";
    document.getElementById(sid+"_selcount").classList.remove("has-sel");
    closeDetailPanel();
    var layout=document.getElementById(sid+"_scatter").layout;
    Plotly.react(sid+"_scatter",buildMainTraces(null),layout,PLYCFG);
  }};

  window[sid+"_resetFilters"]=function(){{
    filteredIndices=null;
    document.getElementById(sid+"_filterrows").innerHTML="";
    document.getElementById(sid+"_filtcount").textContent="";
    filterRowCount=0;selIdx=[];
    document.getElementById(sid+"_selcount").textContent="Aucune sélection";
    document.getElementById(sid+"_selcount").classList.remove("has-sel");
    closeDetailPanel();
    var layout=document.getElementById(sid+"_scatter").layout;
    Plotly.react(sid+"_scatter",buildMainTraces(null),layout,PLYCFG);
  }};

}})();
</script>
"""
