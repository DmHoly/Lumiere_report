from __future__ import annotations
import json
import html as _h
import numpy as np
import pandas as pd
from ..._helpers import Block, _safe_json, _is_vector_col
from ..data.data_mixin import DataMixin, DataArg

class ScatterLED(DataMixin, Block):
    """
    Scatter principal : chaque ligne du df = une LED = une série de points.
    x_col / y_col : colonnes vectorielles (ex: I, EQE)
    color_col     : scalaire (une couleur par LED) ou vectoriel (une couleur par point)
    hover_cols    : colonnes scalaires à afficher dans le tooltip
    curve_x / curve_y : colonnes vectorielles pour mini courbe dans le détail (ex: V → J pour JV)
    spectra_col   : colonne vectorielle 2D (liste de spectres) ou None
    wavelength_col: colonne vectorielle longueurs d'onde
    filter_cols   : liste de colonnes scalaires proposées dans la barre de filtres.
                    Ex: ["Lambda_Dom_25A", "Lambda_Dom_max", "max_EQE", "runname"]
                    Si vide, la barre de filtres n'est pas affichée.
    """
    needs_plotly = True

    def __init__(
        self,
        data: DataArg,
        x_col: str,
        y_col: str,
        color_col: str = "",
        hover_cols: list[str] | None = None,
        log_x: bool = True,
        log_y: bool = False,
        height: int = 480,
        curve_x: str = "",
        curve_y: str = "",
        spectra_col: str = "",
        wavelength_col: str = "",
        id_col: str = "",
        filter_cols: list[str] | None = None,
        num: str = "01",
        title: str = "",
        subtitle: str = "",
        x_range: tuple | None = None,
        y_range: tuple | None = None,
        x_label: str = "",
        y_label: str = "",
    ):
        self._init_data(data)
        self.x_col = x_col; self.y_col = y_col
        self.color_col = color_col
        self.hover_cols = hover_cols or []
        self.log_x = log_x; self.log_y = log_y
        self.height = height
        self.curve_x = curve_x; self.curve_y = curve_y
        self.spectra_col = spectra_col; self.wavelength_col = wavelength_col
        self.id_col = id_col
        self.filter_cols = filter_cols or []
        self.num = num
        self.title = title or f"{y_col} vs {x_col}"
        self.subtitle = subtitle
        self.x_range = x_range
        self.y_range = y_range
        self.x_label = x_label or x_col
        self.y_label = y_label or y_col
        self._id = f"sled_{id(self)}"

    # ── helpers ──────────────────────────────────────────────────────────────

    def _build_filter_meta(self, df: pd.DataFrame) -> str:
        """
        Sérialise les métadonnées des colonnes filtrables :
        type ("numeric" | "string"), et pour les strings la liste des valeurs uniques.
        """
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
        """
        Sérialise les valeurs scalaires filtrables pour chaque LED (index = ligne du df).
        """
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

    def _build_js_data(self, df: pd.DataFrame) -> str:
        """Sérialise les données nécessaires au JS."""
        records = []
        for _, row in df.iterrows():
            rec = {
                "x":  _safe_json(row[self.x_col]) if self.x_col in row.index else [],
                "y":  _safe_json(row[self.y_col]) if self.y_col in row.index else [],
            }
            if self.color_col and self.color_col in row.index:
                v = row[self.color_col]
                rec["color"] = [_safe_json(x) for x in v] if isinstance(v, (list, np.ndarray)) else _safe_json(v)
            for c in self.hover_cols:
                if c in row.index:
                    rec[c] = _safe_json(row[c])
            for lam_col in ["Lambda_Dominant", "lambda", "Lambda"]:
                if lam_col in row.index and lam_col != self.color_col:
                    v = row[lam_col]
                    if isinstance(v, (list, np.ndarray)):
                        rec[lam_col] = [_safe_json(x) for x in v]
                    break
            if self.curve_x and self.curve_x in row.index:
                v = row[self.curve_x]
                rec["cx"] = [_safe_json(x) for x in v] if isinstance(v, (list, np.ndarray)) else []
            if self.curve_y and self.curve_y in row.index:
                v = row[self.curve_y]
                rec["cy"] = [_safe_json(x) for x in v] if isinstance(v, (list, np.ndarray)) else []
            if self.spectra_col and self.spectra_col in row.index:
                sp = row[self.spectra_col]
                if isinstance(sp, (list, np.ndarray)) and len(sp) > 0:
                    def _downsample_spec(s, target=120):
                        if not isinstance(s, (list, np.ndarray)) or len(s) <= target:
                            return [_safe_json(x) for x in s]
                        step = max(1, len(s) // target)
                        return [_safe_json(s[i]) for i in range(0, len(s), step)]
                    rec["spectra_all"] = [_downsample_spec(sp[i]) for i in range(len(sp))]
            if self.wavelength_col and self.wavelength_col in row.index:
                wl = row[self.wavelength_col]
                if isinstance(wl, (list, np.ndarray)):
                    if len(wl) > 120:
                        step = max(1, len(wl) // 120)
                        rec["wl"] = [_safe_json(wl[i]) for i in range(0, len(wl), step)]
                    else:
                        rec["wl"] = [_safe_json(x) for x in wl]
            if self.id_col and self.id_col in row.index:
                rec["_id"] = str(row[self.id_col])
            else:
                rec["_id"] = str(len(records))
            records.append(rec)
        return json.dumps(records)

    def _lambda_to_srgb(self, lam_nm: float) -> str:
        l = lam_nm
        if   l < 380: r,g,b = 0,0,0
        elif l < 440: r,g,b = -(l-440)/60, 0, 1
        elif l < 490: r,g,b = 0, (l-440)/50, 1
        elif l < 510: r,g,b = 0, 1, -(l-510)/20
        elif l < 580: r,g,b = (l-510)/70, 1, 0
        elif l < 645: r,g,b = 1, -(l-645)/65, 0
        elif l <= 700: r,g,b = 1,0,0
        else:          r,g,b = 0,0,0
        r,g,b = (max(0,min(1,x))**0.8 for x in (r,g,b))
        return "#{:02x}{:02x}{:02x}".format(int(r*255), int(g*255), int(b*255))

    def _build_lambda_colorscale(self) -> str:
        steps = list(range(400, 701, 5))
        scale = []
        for i, lam in enumerate(steps):
            t = i / (len(steps) - 1)
            scale.append([t, self._lambda_to_srgb(lam)])
        return json.dumps(scale)

    # ── render ────────────────────────────────────────────────────────────────

    def render(self, store=None) -> str:
        sid = self._id

        if self.has_local_data:
            # Df local : chemins Python inchangés
            df = self.resolve_df()
            data_json        = self._build_js_data(df)
            filter_meta_json = self._build_filter_meta(df)
            filter_data_json = self._build_filter_data(df)
            init_js = (f"var DATA={data_json};\n"
                       f"  var FDATA={filter_data_json};\n"
                       f"  var FMETA={filter_meta_json};")
        else:
            # Clé store : zéro copie — JS normalise les records depuis le store
            key = self._data_arg
            if store is None:
                raise RuntimeError(
                    f"ScatterLED references store key {key!r} but no DataStore was provided."
                )
            df = store.resolve(key)
            filter_meta = json.loads(self._build_filter_meta(df))
            curve_defs = (
                [{"lbl": "curve", "xk": self.curve_x, "yk": self.curve_y}]
                if self.curve_x and self.curve_y else []
            )
            cfg_dict = {
                "key":        key,
                "xCol":       self.x_col,
                "yCol":       self.y_col,
                "colorCol":   self.color_col or None,
                "curveX":     self.curve_x or None,
                "curveY":     self.curve_y or None,
                "spectraCol": self.spectra_col or None,
                "wlCol":      self.wavelength_col or None,
                "idCol":      self.id_col or None,
                "hoverCols":  self.hover_cols,
                "filterCols": self.filter_cols,
                "fmeta":      filter_meta,
            }
            cfg_json = json.dumps(cfg_dict)
            init_js = (
                f"var _CFG={cfg_json},"
                f"_raw=(window.__DATA_STORE__||{{}})[_CFG.key]||[],"
                f"DATA=_raw.map(function(r,i){{"
                f"  var rec={{x:_CFG.xCol?r[_CFG.xCol]:null,"
                f"y:_CFG.yCol?r[_CFG.yCol]:null,"
                f"color:_CFG.colorCol?r[_CFG.colorCol]:null,"
                f"cx:_CFG.curveX?r[_CFG.curveX]:null,"
                f"cy:_CFG.curveY?r[_CFG.curveY]:null,"
                f"wl:_CFG.wlCol?r[_CFG.wlCol]:null,"
                f"spectra_all:_CFG.spectraCol?r[_CFG.spectraCol]:null,"
                f"_id:(_CFG.idCol&&r[_CFG.idCol]!=null)?String(r[_CFG.idCol]):String(i)}};"
                f"  ['Lambda_Dominant','lambda','Lambda'].forEach(function(c){{if(r[c]!=null)rec[c]=r[c];}});"
                f"  (_CFG.hoverCols||[]).forEach(function(c){{if(r[c]!=null)rec[c]=r[c];}});"
                f"  return rec;}}),"
                f"FDATA=_raw.map(function(r){{var fd={{}};(_CFG.filterCols||[]).forEach(function(c){{if(r[c]!=null)fd[c]=r[c];}});return fd;}}),"
                f"FMETA=_CFG.fmeta||{{}};"
            )
        has_filters = "true" if self.filter_cols else "false"
        log_x_js  = "true" if self.log_x else "false"
        log_y_js  = "true" if self.log_y else "false"
        h         = self.height
        x_label   = _h.escape(self.x_label)
        y_label   = _h.escape(self.y_label)
        title_h   = _h.escape(self.title)
        sub_h     = _h.escape(self.subtitle)
        has_jv    = "true" if self.curve_x and self.curve_y else "false"
        has_spec  = "true" if self.spectra_col else "false"
        lambda_colorscale = self._build_lambda_colorscale()
        x_range_js = json.dumps(list(self.x_range)) if self.x_range else "null"
        y_range_js = json.dumps(list(self.y_range)) if self.y_range else "null"
        hover_js   = self._hover_fields_js()
        curve_x_esc = _h.escape(self.curve_x)
        curve_y_esc = _h.escape(self.curve_y)

        return f"""
<div class="led-block" id="{sid}_wrap">
  <div class="led-block-header">
    <span class="led-block-num">{_h.escape(self.num)}</span>
    <span class="led-block-title">{title_h}</span>
    <span class="led-block-sub">{sub_h}</span>
  </div>
  <div class="led-block-rule"></div>

  <!-- toolbar sélection -->
  <div class="scatter-led-toolbar">
    <button class="slt-btn active" id="{sid}_btn_click" onclick="{sid}_setMode('click')">✦ CLIC</button>
    <button class="slt-btn" id="{sid}_btn_lasso" onclick="{sid}_setMode('lasso')">⬡ LASSO</button>
    <button class="slt-btn" id="{sid}_btn_box"   onclick="{sid}_setMode('box')">▣ ZONE</button>
    <div class="slt-sep"></div>
    <button class="slt-btn" onclick="{sid}_clearSel()">✕ EFFACER</button>
    <span class="slt-count" id="{sid}_selcount">Aucune sélection</span>
  </div>

  <!-- toolbar filtres (visible seulement si filter_cols renseigné) -->
  <div class="sled-filter-bar" id="{sid}_filterbar" style="display:none">
    <div class="sled-filter-header">
      <span class="spt-filter-label">FILTRES</span>
      <button class="slt-btn slt-btn--gold" onclick="{sid}_addFilter()">+ AJOUTER</button>
      <button class="slt-btn" onclick="{sid}_applyFilters()">▶ APPLIQUER</button>
      <button class="slt-btn" onclick="{sid}_resetFilters()">↺ RESET</button>
      <span class="spt-filt-count" id="{sid}_filtcount"></span>
    </div>
    <!-- rangées de filtres ajoutées dynamiquement ici -->
    <div class="sled-filter-rows" id="{sid}_filterrows"></div>
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
          <div class="led-sub-wrap led-sub-wrap--eqe">
            <div class="led-sub-hdr">
              <span class="led-sub-title">{y_label} vs {x_label}</span>
              <span class="led-sub-axes">sélection</span>
            </div>
            <div class="led-sub-body"><div id="{sid}_det_main"></div></div>
          </div>
          <div class="led-sub-wrap led-sub-wrap--jv" id="{sid}_jv_wrap">
            <div class="led-sub-hdr">
              <span class="led-sub-title">{curve_y_esc} vs {curve_x_esc}</span>
              <span class="led-sub-axes">courbe</span>
            </div>
            <div class="led-sub-body"><div id="{sid}_det_jv"></div></div>
          </div>
          <div class="led-sub-wrap led-sub-wrap--spec" id="{sid}_spec_wrap">
            <div class="led-sub-hdr">
              <span class="led-sub-title">Spectre</span>
              <span class="led-sub-axes">@ pt cliqué</span>
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
  {init_js}
  var sid         = "{sid}";
  var logX        = {log_x_js}, logY = {log_y_js};
  var hasJV       = {has_jv};
  var hasSpec     = {has_spec};
  var hasFilters  = {has_filters};
  var mode        = "click";
  var selIdx      = [];
  var filteredIndices = null;   /* null = pas de filtre actif, sinon Set */
  var filterRowCount  = 0;

  var MULTI_COLORS = ["#D4AF37","#3B82F6","#EF4444","#8B5CF6","#10B981","#F59E0B","#EC4899","#06B6D4","#84CC16","#F97316"];
  var PLYCFG = {{responsive:true,displaylogo:false,modeBarButtonsToRemove:["autoScale2d","toggleSpikelines","sendDataToCloud"]}};
  var GSTYLE = {{gridcolor:"#E4E8F4",linecolor:"#E4E8F4",zerolinecolor:"#E4E8F4"}};

  /* ── Afficher la barre de filtres si configurée ── */
  if(hasFilters) document.getElementById(sid+"_filterbar").style.display="block";

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

  var LAMBDA_COLORSCALE = {lambda_colorscale};

  var _lambdaVals=[];
  DATA.forEach(function(r){{
    var lv=r["Lambda_Dominant"]||r["lambda"]||r["Lambda"];
    if(Array.isArray(lv)) lv.forEach(function(v){{if(v&&!isNaN(v)&&v>=400&&v<=700)_lambdaVals.push(+v);}});
  }});
  var hasLambdaColorbar=_lambdaVals.length>0;

  /* ── Filtres : évaluation ── */
  function evalNumFilter(val,op,thr){{
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

  function evalStrFilter(val,values){{
    /* values = tableau de strings sélectionnées ; vide = pas de filtre */
    if(!values||!values.length) return true;
    return values.indexOf(String(val))>=0;
  }}

  /* ── Collecte et application de tous les filtres actifs ── */
  function computeFilteredSet(){{
    var rows=document.querySelectorAll("#"+sid+"_filterrows .sled-frow");
    if(!rows.length) return null;

    /* vérifier si au moins un filtre est renseigné */
    var hasActive=false;
    rows.forEach(function(row){{
      var col=row.querySelector(".sled-fcol").value;
      if(!col) return;
      var meta=FMETA[col];
      if(!meta) return;
      if(meta.type==="numeric"){{
        var op=row.querySelector(".sled-fop").value;
        var val=row.querySelector(".sled-fval-num").value;
        if(op&&val!=="") hasActive=true;
      }}else{{
        var sel=row.querySelectorAll(".sled-fchk:checked");
        if(sel.length) hasActive=true;
      }}
    }});
    if(!hasActive) return null;

    var result=new Set();
    FDATA.forEach(function(fd,ri){{
      var pass=true;
      rows.forEach(function(row){{
        if(!pass) return;
        var col=row.querySelector(".sled-fcol").value;
        if(!col) return;
        var meta=FMETA[col];
        if(!meta) return;
        var val=fd[col];
        if(val==null) return; /* absent → ne pas exclure */
        if(meta.type==="numeric"){{
          var op=row.querySelector(".sled-fop").value;
          var thr=row.querySelector(".sled-fval-num").value;
          if(!evalNumFilter(val,op,thr)) pass=false;
        }}else{{
          var checked=[];
          row.querySelectorAll(".sled-fchk:checked").forEach(function(c){{checked.push(c.value);}});
          if(!evalStrFilter(val,checked)) pass=false;
        }}
      }});
      if(pass) result.add(ri);
    }});
    return result;
  }}

  /* ── Ajout d'une ligne de filtre ── */
  window[sid+"_addFilter"]=function(){{
    var cols=Object.keys(FMETA);
    if(!cols.length) return;
    filterRowCount++;
    var rowId=sid+"_frow"+filterRowCount;
    var container=document.getElementById(sid+"_filterrows");

    var row=document.createElement("div");
    row.className="sled-frow";
    row.id=rowId;

    /* select colonne */
    var sel=document.createElement("select");
    sel.className="sled-fcol spt-filter-op";
    sel.style.minWidth="160px";
    var opt0=document.createElement("option");
    opt0.value="";opt0.textContent="— colonne —";
    sel.appendChild(opt0);
    cols.forEach(function(c){{
      var o=document.createElement("option");
      o.value=c;o.textContent=c;
      sel.appendChild(o);
    }});

    /* zone de contrôle (opérateur+valeur ou checkboxes) */
    var ctrl=document.createElement("div");
    ctrl.className="sled-fctrl";

    /* bouton supprimer */
    var del=document.createElement("button");
    del.className="slt-btn";del.textContent="✕";
    del.onclick=function(){{row.remove();window[sid+"_applyFilters"]();}};

    sel.onchange=function(){{
      ctrl.innerHTML="";
      var col=sel.value;
      if(!col) return;
      var meta=FMETA[col];
      if(!meta) return;
      if(meta.type==="numeric"){{
        /* opérateur + input numérique */
        var opSel=document.createElement("select");
        opSel.className="sled-fop spt-filter-op";
        [["","—"],["gt","&gt;"],["gte","&ge;"],["lt","&lt;"],["lte","&le;"],["eq","=="],["neq","!="]].forEach(function(pair){{
          var o=document.createElement("option");
          o.value=pair[0];o.innerHTML=pair[1];
          opSel.appendChild(o);
        }});
        var numIn=document.createElement("input");
        numIn.type="number";numIn.className="sled-fval-num spt-filter-val";
        numIn.placeholder="valeur";
        numIn.addEventListener("keydown",function(e){{if(e.key==="Enter")window[sid+"_applyFilters"]();}});
        ctrl.appendChild(opSel);ctrl.appendChild(numIn);
      }}else{{
        /* checkboxes pour les valeurs uniques */
        var wrap=document.createElement("div");
        wrap.className="sled-fchk-wrap";
        meta.values.forEach(function(v){{
          var lbl=document.createElement("label");
          lbl.className="sled-fchk-label";
          var chk=document.createElement("input");
          chk.type="checkbox";chk.className="sled-fchk";chk.value=v;
          var span=document.createElement("span");span.textContent=v;
          lbl.appendChild(chk);lbl.appendChild(span);
          wrap.appendChild(lbl);
        }});
        ctrl.appendChild(wrap);
      }}
    }};

    row.appendChild(sel);
    row.appendChild(ctrl);
    row.appendChild(del);
    container.appendChild(row);
  }};

  /* ── Appliquer les filtres ── */
  window[sid+"_applyFilters"]=function(){{
    filteredIndices=computeFilteredSet();
    var total=DATA.length;
    var cnt=filteredIndices?filteredIndices.size:total;
    var el=document.getElementById(sid+"_filtcount");
    if(filteredIndices){{
      el.textContent=cnt+" / "+total;
      el.className="spt-filt-count "+(cnt<total?"spt-filt-active":"spt-filt-ok");
    }}else{{
      el.textContent="";
    }}
    selIdx=[];
    document.getElementById(sid+"_selcount").textContent="Aucune sélection";
    document.getElementById(sid+"_selcount").classList.remove("has-sel");
    closeDetailPanel();
    var layout=document.getElementById(sid+"_scatter").layout;
    Plotly.react(sid+"_scatter",buildScatterTraces(null),layout,PLYCFG);
    rescaleToVisible();
  }};

  /* ── Reset filtres ── */
  window[sid+"_resetFilters"]=function(){{
    filteredIndices=null;
    document.getElementById(sid+"_filterrows").innerHTML="";
    document.getElementById(sid+"_filtcount").textContent="";
    filterRowCount=0;
    selIdx=[];
    document.getElementById(sid+"_selcount").textContent="Aucune sélection";
    document.getElementById(sid+"_selcount").classList.remove("has-sel");
    closeDetailPanel();
    var layout=document.getElementById(sid+"_scatter").layout;
    Plotly.react(sid+"_scatter",buildScatterTraces(null),layout,PLYCFG);
    /* restaurer les plages initiales */
    var upd={{}};
    if({x_range_js}===null&&xRange) upd["xaxis.range"]=xRange;
    if({y_range_js}===null&&yRange) upd["yaxis.range"]=yRange;
    if(Object.keys(upd).length) Plotly.relayout(sid+"_scatter",upd);
  }};

  /* ── Rescale axes sur les données visibles (respecte les ranges forcés Python) ── */
  function rescaleToVisible(){{
    var vx=[],vy=[];
    DATA.forEach(function(r,ri){{
      if(filteredIndices!==null&&!filteredIndices.has(ri)) return;
      (Array.isArray(r.x)?r.x:[]).forEach(function(v){{if(v!=null&&!isNaN(v)&&isFinite(v)&&(!logX||v>1e-12))vx.push(v);}});
      (Array.isArray(r.y)?r.y:[]).forEach(function(v){{if(v!=null&&!isNaN(v)&&isFinite(v))vy.push(v);}});
    }});
    var upd={{}};
    if({x_range_js}===null&&vx.length){{
      var mn=Math.min.apply(null,vx),mx=Math.max.apply(null,vx);
      if(logX){{var lm=Math.log10(mn),lM=Math.log10(mx),p=Math.max((lM-lm)*0.04,0.2);upd["xaxis.range"]=[lm-p,lM+p];}}
      else{{var p=(mx-mn)*0.04||Math.abs(mx)*0.04||0.01;upd["xaxis.range"]=[mn-p,mx+p];}}
    }}
    if({y_range_js}===null&&vy.length){{
      var mn2=Math.min.apply(null,vy),mx2=Math.max.apply(null,vy);
      if(logY){{var lm2=Math.log10(mn2),lM2=Math.log10(mx2),p2=Math.max((lM2-lm2)*0.04,0.2);upd["yaxis.range"]=[lm2-p2,lM2+p2];}}
      else{{var p2=(mx2-mn2)*0.04||Math.abs(mx2)*0.04||0.01;upd["yaxis.range"]=[mn2-p2,mx2+p2];}}
    }}
    if(Object.keys(upd).length) Plotly.relayout(sid+"_scatter",upd);
  }}

  /* ── Build scatter traces ── */
  function buildScatterTraces(focusRi){{
    var focusSet=null;
    if(focusRi!==null){{
      focusSet={{}};
      if(Array.isArray(focusRi)) focusRi.forEach(function(i){{focusSet[i]=true;}});
      else focusSet[focusRi]=true;
    }}

    var xs=[],ys=[],colors=[],sizes=[],customdata=[],texts=[];
    var hxs=[],hys=[];

    DATA.forEach(function(r,ri){{
      var xArr=Array.isArray(r.x)?r.x:[];
      var yArr=Array.isArray(r.y)?r.y:[];
      var cArr=Array.isArray(r.color)?r.color:xArr.map(function(){{return r.color||"#D4AF37";}});
      var lArr=Array.isArray(r["Lambda_Dominant"])?r["Lambda_Dominant"]:
               Array.isArray(r["lambda"])?r["lambda"]:null;
      var nPts=Math.min(xArr.length,yArr.length);

      /* filtre actif : LED exclue → ghost */
      var passFilter=(filteredIndices===null||filteredIndices.has(ri));
      var isFocused=(focusSet===null||focusSet[ri]===true);

      if(isFocused&&passFilter){{
        for(var pi=0;pi<nPts;pi++){{
          xs.push(xArr[pi]);ys.push(yArr[pi]);
          colors.push(cArr[pi]||"#D4AF37");
          sizes.push(focusSet!==null?9:7);
          customdata.push([ri,pi]);
          var htxt="<b>"+r._id+"</b>";
          {hover_js};
          htxt+="<br>{x_label}: "+xArr[pi]+"<br>{y_label}: "+yArr[pi];
          if(lArr&&lArr[pi]) htxt+="<br>λ: "+lArr[pi].toFixed(1)+" nm";
          texts.push(htxt);
        }}
      }}else{{
        for(var pi=0;pi<nPts;pi++){{hxs.push(xArr[pi]);hys.push(yArr[pi]);}}
      }}
    }});

    var traces=[];
    if(hxs.length) traces.push({{
      type:"scatter",mode:"markers",x:hxs,y:hys,
      marker:{{color:"rgba(0,0,0,0)",size:1,opacity:0}},
      hoverinfo:"skip",showlegend:false,
    }});
    traces.push({{
      type:"scatter",mode:"markers",x:xs,y:ys,
      marker:{{color:colors,size:sizes,opacity:0.95,
        line:{{width:focusSet!==null?1.2:0.5,color:focusSet!==null?"#1a1a2e":"rgba(0,0,0,.15)"}}}},
      text:texts,hovertemplate:"%{{text}}<extra></extra>",
      customdata:customdata,showlegend:false,
    }});
    if(hasLambdaColorbar&&xs.length) traces.push({{
      type:"scatter",mode:"markers",x:[xs[0]],y:[ys[0]],
      marker:{{color:[500],colorscale:LAMBDA_COLORSCALE,showscale:true,
        cmin:400,cmax:700,opacity:0,size:0.1,
        colorbar:{{title:{{text:"λ (nm)",font:{{size:10,color:"#0A2463"}},side:"right"}},
          thickness:12,len:0.75,x:1.01,
          tickfont:{{size:9,family:"IBM Plex Mono"}},
          tickvals:[400,450,500,550,600,650,700]}}}},
      hoverinfo:"skip",showlegend:false,
    }});
    return traces;
  }}

  /* ── Axis ranges ── */
  var _allX=[],_allY=[];
  DATA.forEach(function(r){{
    (Array.isArray(r.x)?r.x:[]).forEach(function(v){{if(v!=null&&!isNaN(v)&&v>1e-12)_allX.push(v);}});
    (Array.isArray(r.y)?r.y:[]).forEach(function(v){{if(v!=null&&!isNaN(v))_allY.push(v);}});
  }});
  function toPlotlyRange(forced,logScale,allVals){{
    if(forced!==null){{if(logScale)return[Math.log10(forced[0]),Math.log10(forced[1])];return forced;}}
    if(!allVals.length) return null;
    var mn=Math.min.apply(null,allVals),mx=Math.max.apply(null,allVals);
    if(logScale){{var lMn=Math.log10(mn),lMx=Math.log10(mx),pad=Math.max((lMx-lMn)*0.04,0.2);return[lMn-pad,lMx+pad];}}
    var pad=(mx-mn)*0.04||Math.abs(mx)*0.04||0.01;return[mn-pad,mx+pad];
  }}
  var xRange=toPlotlyRange({x_range_js},logX,_allX);
  var yRange=toPlotlyRange({y_range_js},logY,_allY);

  /* ── Initial plot ── */
  Plotly.newPlot(sid+"_scatter",buildScatterTraces(null),{{
    paper_bgcolor:"rgba(0,0,0,0)",plot_bgcolor:"#F8F9FD",
    font:{{family:"IBM Plex Mono,monospace",color:"#4A5580",size:11}},
    margin:{{t:10,r:hasLambdaColorbar?60:16,b:48,l:64}},
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

  function openDetail(){{
    document.getElementById(sid+"_detail").classList.add("open");
    setTimeout(function(){{Plotly.Plots.resize(sid+"_scatter");}},400);
  }}
  function closeDetailPanel(){{
    document.getElementById(sid+"_detail").classList.remove("open");
    setTimeout(function(){{Plotly.Plots.resize(sid+"_scatter");}},400);
  }}

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
    Plotly.react(sid+"_scatter",buildScatterTraces(null),layout,PLYCFG);
  }};
  window[sid+"_closeDetail"]=function(){{closeDetailPanel();}};

  /* ── Render detail ── */
  function renderDetail(ledIndices,clickedPt){{
    var isSingle=ledIndices.length===1;
    var mainTraces=[];
    ledIndices.forEach(function(ri,ci){{
      var r=DATA[ri],col=MULTI_COLORS[ci%MULTI_COLORS.length];
      var xArr=Array.isArray(r.x)?r.x:[],yArr=Array.isArray(r.y)?r.y:[];
      var mSizes=xArr.map(function(_,pi){{return(isSingle&&pi===clickedPt)?10:3;}});
      var mColors=xArr.map(function(_,pi){{return(isSingle&&pi===clickedPt)?"#FF4444":col;}});
      mainTraces.push({{x:xArr,y:yArr,type:"scatter",mode:"lines+markers",
        marker:{{size:mSizes,color:mColors}},line:{{color:col,width:isSingle?1.5:1}},
        name:r._id,hoverinfo:"x+y"}});
    }});
    Plotly.newPlot(sid+"_det_main",mainTraces,subLayout("{x_label}","{y_label}",logX,logY),PLYCFG);

    if(hasJV){{
      var jvTraces=[];
      ledIndices.forEach(function(ri,ci){{
        var r=DATA[ri],col=MULTI_COLORS[ci%MULTI_COLORS.length];
        if(r.cx&&r.cy){{
          jvTraces.push({{x:r.cx,y:r.cy,type:"scatter",mode:"lines+markers",
            marker:{{size:3,color:col}},line:{{color:col,width:1.5}},
            name:r._id,hoverinfo:"x+y",showlegend:false}});
          if(isSingle&&clickedPt!=null&&r.cx[clickedPt]!=null&&r.cy[clickedPt]!=null){{
            jvTraces.push({{type:"scatter",mode:"markers",
              x:[r.cx[clickedPt]],y:[r.cy[clickedPt]],
              marker:{{size:10,color:"#EF4444",symbol:"circle",line:{{width:2,color:"white"}}}},
              hovertemplate:"<b>pt "+(clickedPt+1)+"</b><br>{curve_x_esc}: %{{x}}<br>{curve_y_esc}: %{{y}}<extra></extra>",
              showlegend:false}});
          }}
        }}
      }});
      if(jvTraces.length>0)
        Plotly.newPlot(sid+"_det_jv",jvTraces,subLayout("{curve_x_esc}","{curve_y_esc}",false,true),PLYCFG);
      else
        document.getElementById(sid+"_det_jv").innerHTML='<div class="no-data-msg">Pas de courbe JV</div>';
    }}

    if(hasSpec){{
      var specTraces=[];
      ledIndices.forEach(function(ri,ci){{
        var r=DATA[ri],col=MULTI_COLORS[ci%MULTI_COLORS.length];
        var allSpecs=r.spectra_all;
        if(!allSpecs||!allSpecs.length||!r.wl) return;
        var specIdx;
        if(isSingle&&clickedPt!=null){{
          specIdx=Math.min(clickedPt,allSpecs.length-1);
        }}else{{
          var yArr=Array.isArray(r.y)?r.y:[];
          var best=-Infinity,bestI=0;
          yArr.forEach(function(v,i){{if(v!=null&&!isNaN(v)&&v>best){{best=v;bestI=i;}}}});
          specIdx=Math.min(bestI,allSpecs.length-1);
        }}
        var sp=allSpecs[specIdx];
        if(sp&&sp.length) specTraces.push({{
          x:r.wl,y:sp,type:"scatter",mode:"lines",
          line:{{color:col,width:1.5}},
          fill:isSingle?"tozeroy":"none",fillcolor:"rgba(139,92,246,.1)",
          name:r._id+" (pt "+(specIdx+1)+")",
        }});
      }});
      if(specTraces.length>0)
        Plotly.newPlot(sid+"_det_spec",specTraces,subLayout("λ (nm)","Intensity",false,false),PLYCFG);
      else
        document.getElementById(sid+"_det_spec").innerHTML='<div class="no-data-msg">Pas de spectre</div>';
    }}
  }}

  /* ── Events ── */
  document.getElementById(sid+"_scatter").on("plotly_click",function(evt){{
    if(mode!=="click") return;
    var pt=evt.points[0],cd=pt.customdata;
    if(!cd||cd.length<2) return;
    var ri=cd[0],pi=cd[1];
    selIdx=[ri];
    var r=DATA[ri];
    document.getElementById(sid+"_selcount").textContent="LED · "+r._id;
    document.getElementById(sid+"_selcount").classList.add("has-sel");
    document.getElementById(sid+"_detlabel").innerHTML="<span>▸</span>"+r._id+" · pt "+(pi+1);
    openDetail();
    var savedLayout=document.getElementById(sid+"_scatter").layout;
    Plotly.react(sid+"_scatter",buildScatterTraces(ri),savedLayout,PLYCFG);
    renderDetail([ri],pi);
  }});

  document.getElementById(sid+"_scatter").on("plotly_selected",function(evt){{
    if(!evt||!evt.points||!evt.points.length) return;
    var seen={{}};
    evt.points.forEach(function(p){{if(p.customdata&&p.customdata.length>=2)seen[p.customdata[0]]=true;}});
    selIdx=Object.keys(seen).map(Number);
    if(!selIdx.length) return;
    var cnt=selIdx.length;
    document.getElementById(sid+"_selcount").textContent=cnt+" LED"+(cnt>1?"s":"")+" · lasso";
    document.getElementById(sid+"_selcount").classList.add("has-sel");
    document.getElementById(sid+"_detlabel").innerHTML="<span>▸</span>"+cnt+" LEDs · "+evt.points.length+" pts";
    openDetail();
    var savedLayout2=document.getElementById(sid+"_scatter").layout;
    Plotly.react(sid+"_scatter",buildScatterTraces(selIdx),savedLayout2,PLYCFG);
    renderDetail(selIdx.slice(0,12),null);
  }});

  document.getElementById(sid+"_scatter").on("plotly_deselect",function(){{window[sid+"_clearSel"]();}});
  document.getElementById(sid+"_scatter").addEventListener("dblclick",function(){{window[sid+"_clearSel"]();}});

  window.addEventListener("resize",function(){{
    Plotly.Plots.resize(sid+"_scatter");
    [sid+"_det_main",sid+"_det_jv",sid+"_det_spec"].forEach(function(eid){{
      var el=document.getElementById(eid);if(el&&el.data)Plotly.Plots.resize(eid);
    }});
  }});

  if(!hasJV)   document.getElementById(sid+"_jv_wrap").style.display="none";
  if(!hasSpec) document.getElementById(sid+"_spec_wrap").style.display="none";
  if(!hasJV&&!hasSpec) document.getElementById(sid+"_detplots").style.gridTemplateColumns="1fr";

}})();
</script>
"""

    def _hover_fields_js(self) -> str:
        lines = []
        for c in self.hover_cols:
            safe = c.replace('"', '\\"')
            lines.append(f'if(r["{safe}"]!=null) htxt+="<br>{safe}: "+r["{safe}"]')
        return ";\n        ".join(lines) if lines else ""