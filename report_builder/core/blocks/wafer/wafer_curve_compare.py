from __future__ import annotations
import json
import html as _h
import numpy as np
import pandas as pd
from ..._helpers import Block, _safe_json, _col_analysis, _is_vector_col
from ..data.data_mixin import DataArg, _normalize_data


class WaferCurveCompareBlock(Block):
    """
    Comparateur de courbes entre wafers et/ou positions — inspiré de DesignMatrixBlock.

    Une wafermap cliquable (carrousel entre wafers, comme WaferMaps). Clic simple =
    aperçu d'une position. Ctrl+clic (ou Cmd+clic) = ajoute/retire la position à une
    liste de comparaison cumulative, superposée sur 4 panneaux : JV (J vs V), EQE vs J,
    L vs W, Spectre (avec slider pour choisir le point de mesure). La sélection
    persiste quand on change de wafer via le carrousel — on peut donc comparer une
    position du wafer A avec une position du wafer B. Aucune limite sur le nombre
    de positions comparées (au-delà de 10, les couleurs de la palette recyclent).

    Filtre : même système que WaferMaps — dropdown Colormap (+ style de colorscale)
    pour la couleur des positions sur la wafermap, et dropdown Filtre (colonne + valeur)
    pour ne montrer/pouvoir sélectionner que le sous-ensemble de positions filtré.

    Params
    ------
    data            : DataFrame ou clé DataStore.
    x_col / y_col   : colonnes position (défaut "X", "Y").
    wafer_col       : colonne wafer (défaut "wafername").
    id_col          : colonne identifiant (défaut "" → index).
    v_col, j_col, i_col : colonnes vectorielles pour JV / J-EQE (défaut "V","J","I").
    l_col, w_col, eqe_col : colonnes vectorielles L(W), EQE (défaut "L","W","EQE").
    spectra_col, wavelength_col : colonnes vectorielles spectre.
    color_col       : colonne scalaire par défaut pour le dropdown Colormap.
    colormap_cols   : colonnes scalaires proposées dans le dropdown Colormap
                       (défaut : auto-détectées, colonnes numériques).
    filter_cols     : colonnes proposées dans le dropdown Filtre
                       (défaut : auto-détectées, colonnes catégorielles).
    colorscale      : colorscale Plotly par défaut.
    map_height      : hauteur de la wafermap en px.
    panel_height    : hauteur totale de la grille des 4 panneaux de courbes en px
                       (indépendante de map_height, défaut plus grand pour la lisibilité).
    num / title / subtitle : métadonnées du header.
    """

    needs_plotly = True

    _COLORS = ["#6366f1", "#f59e0b", "#10b981", "#ef4444", "#3b82f6",
               "#ec4899", "#84cc16", "#f97316", "#14b8a6", "#a855f7"]

    def __init__(
        self,
        data: DataArg,
        x_col: str = "X",
        y_col: str = "Y",
        wafer_col: str = "wafername",
        id_col: str = "",
        v_col: str = "V",
        i_col: str = "I",
        j_col: str = "J",
        l_col: str = "L",
        w_col: str = "W",
        eqe_col: str = "EQE",
        spectra_col: str = "Spectra",
        wavelength_col: str = "Wavelength",
        color_col: str = "",
        colormap_cols: list[str] | None = None,
        filter_cols: list[str] | None = None,
        colorscale: str = "Viridis",
        map_height: int = 460,
        panel_height: int = 620,
        num: str = "01",
        title: str = "Comparateur de courbes",
        subtitle: str = "clic = aperçu · mode comparaison = superpose les positions cliquées",
    ):
        self._data_arg = _normalize_data(data)
        self.x_col = x_col
        self.y_col = y_col
        self.wafer_col = wafer_col
        self.id_col = id_col
        self.v_col = v_col
        self.i_col = i_col
        self.j_col = j_col
        self.l_col = l_col
        self.w_col = w_col
        self.eqe_col = eqe_col
        self.spectra_col = spectra_col
        self.wavelength_col = wavelength_col
        self.color_col = color_col
        self._colormap_cols_arg = colormap_cols
        self._filter_cols_arg = filter_cols
        self.colorscale = colorscale
        self.map_height = map_height
        self.panel_height = panel_height
        self.num = num
        self.title = title
        self.subtitle = subtitle
        self._id = f"wcc_{id(self)}"

    def _resolve_col_lists(self, df: pd.DataFrame) -> None:
        cols = _col_analysis(df)
        self.colormap_cols = self._colormap_cols_arg or cols["scalar_num"][:8]
        self.filter_cols = self._filter_cols_arg or cols["scalar_cat"][:6]

    def resolve_df(self, store=None) -> pd.DataFrame:
        data = self._data_arg
        if isinstance(data, pd.DataFrame):
            return data
        if store is None:
            raise RuntimeError(
                f"WaferCurveCompareBlock references data key {data!r} but no DataStore was provided."
            )
        return store.resolve(data)

    # ── Sérialisation ─────────────────────────────────────────────────────

    @staticmethod
    def _ds(arr, target=200):
        if not isinstance(arr, (list, np.ndarray)):
            return []
        if len(arr) <= target:
            return [_safe_json(v) for v in arr]
        step = max(1, len(arr) // target)
        return [_safe_json(arr[i]) for i in range(0, len(arr), step)]

    def _build_wafer_json(self, df: pd.DataFrame) -> str:
        if not hasattr(self, "colormap_cols"):
            self._resolve_col_lists(df)
        curve_cols = [c for c in [self.v_col, self.i_col, self.j_col,
                                   self.l_col, self.w_col, self.eqe_col] if c and c in df.columns]
        scalar_extra = list(dict.fromkeys(
            c for c in (self.colormap_cols + self.filter_cols + ([self.color_col] if self.color_col else []))
            if c and c in df.columns and not _is_vector_col(df[c])
        ))
        out: dict = {}
        for wafer, grp in df.groupby(self.wafer_col):
            leds = []
            for _, row in grp.iterrows():
                rec = {
                    "x": _safe_json(row[self.x_col]) if self.x_col in row.index else 0,
                    "y": _safe_json(row[self.y_col]) if self.y_col in row.index else 0,
                    "_id": str(row[self.id_col]) if self.id_col and self.id_col in row.index else str(len(leds)),
                }
                for c in scalar_extra:
                    try:
                        rec[c] = _safe_json(row[c])
                    except Exception:
                        pass
                for c in curve_cols:
                    v = row[c]
                    if isinstance(v, (list, np.ndarray)):
                        rec[c] = self._ds(v)
                if self.spectra_col and self.spectra_col in row.index:
                    sp = row[self.spectra_col]
                    if isinstance(sp, (list, np.ndarray)) and len(sp) > 0:
                        rec["_sp"] = [self._ds(sp[i]) for i in range(len(sp)) if isinstance(sp[i], (list, np.ndarray))]
                if self.wavelength_col and self.wavelength_col in row.index:
                    wl = row[self.wavelength_col]
                    if isinstance(wl, (list, np.ndarray)):
                        rec["_wl"] = self._ds(wl)
                leds.append(rec)
            out[str(wafer)] = leds
        return json.dumps(out)

    # ── Render ────────────────────────────────────────────────────────────

    def render(self, store=None) -> str:
        wid = self._id
        df = self.resolve_df(store)
        self._resolve_col_lists(df)
        wafer_json = self._build_wafer_json(df)
        colors_json = json.dumps(self._COLORS)
        cs_js = json.dumps(self.colorscale)
        colormap_json = json.dumps(self.colormap_cols)
        filter_json = json.dumps(self.filter_cols)
        default_cmap = json.dumps(self.color_col or (self.colormap_cols[0] if self.colormap_cols else ""))
        map_h = self.map_height
        panel_h = self.panel_height
        x_esc = _h.escape(self.x_col)
        y_esc = _h.escape(self.y_col)
        cfg = {
            "vCol": self.v_col, "iCol": self.i_col, "jCol": self.j_col,
            "lCol": self.l_col, "wCol": self.w_col, "eCol": self.eqe_col,
        }
        cfg_json = json.dumps(cfg)

        return f"""
<div class="led-block" id="{wid}_wrap">
  <div class="led-block-header">
    <span class="led-block-num">{_h.escape(self.num)}</span>
    <span class="led-block-title">{_h.escape(self.title)}</span>
    <span class="led-block-sub">{_h.escape(self.subtitle)}</span>
  </div>
  <div class="led-block-rule"></div>

  <div style="padding:16px;">
    <div style="display:flex;align-items:center;gap:12px;margin-bottom:12px;">
      <button id="{wid}_prev" onclick="window['{wid}_carouselNav'](-1)"
        style="font-size:18px;line-height:1;background:rgba(10,36,99,.06);border:1px solid rgba(10,36,99,.18);border-radius:6px;padding:4px 12px;cursor:pointer;color:#0A2463;">&#8592;</button>
      <div style="flex:1;text-align:center;">
        <span id="{wid}_wafer_name" style="font-family:'Syne',sans-serif;font-weight:700;font-size:15px;color:#0A2463;"></span>
        <span id="{wid}_wafer_counter" style="font-family:'IBM Plex Mono',monospace;font-size:10px;color:#8896BB;margin-left:10px;"></span>
      </div>
      <button id="{wid}_next" onclick="window['{wid}_carouselNav'](+1)"
        style="font-size:18px;line-height:1;background:rgba(10,36,99,.06);border:1px solid rgba(10,36,99,.18);border-radius:6px;padding:4px 12px;cursor:pointer;color:#0A2463;">&#8594;</button>
      <button id="{wid}_mode_btn" onclick="window['{wid}_toggleCompareMode']()"
        style="font-size:10px;padding:5px 10px;border:0.5px solid rgba(10,36,99,.25);border-radius:6px;background:transparent;cursor:pointer;color:#4A5580;font-weight:600;">
        ⚏ Mode comparaison : OFF
      </button>
      <button id="{wid}_clearcmp" onclick="window['{wid}_clearCmp']()"
        style="font-size:10px;padding:5px 10px;border:0.5px solid rgba(10,36,99,.2);border-radius:6px;background:transparent;cursor:pointer;color:#888;">
        ✕ vider la comparaison
      </button>
    </div>

    <div style="display:grid;grid-template-columns:0.9fr 1.4fr;gap:14px;">

      <!-- Wafermap -->
      <div>
        <div class="wm-toolbar" style="display:flex;align-items:center;gap:6px;flex-wrap:wrap;margin-bottom:8px;">
          <span class="wm-tool-label">Colormap</span>
          <div class="wm-select-wrap">
            <select class="wm-select" id="{wid}_cmap_col" onchange="window['{wid}_updateCmapCol'](this.value)"></select>
          </div>
          <div class="wm-select-wrap">
            <select class="wm-select" id="{wid}_cs_style" onchange="window['{wid}_updateCsStyle'](this.value)" style="width:90px;">
              <option value="Viridis">Viridis</option>
              <option value="Jet">Jet</option>
              <option value="Plasma">Plasma</option>
              <option value="Inferno">Inferno</option>
              <option value="RdBu">RdBu</option>
              <option value="Turbo">Turbo</option>
            </select>
          </div>
          <div class="wm-sep"></div>
          <span class="wm-tool-label">Filtre</span>
          <div class="wm-select-wrap">
            <select class="wm-select" id="{wid}_fcol" style="width:90px" onchange="window['{wid}_updateFcol'](this.value)">
              <option value="">— aucun —</option>
            </select>
          </div>
          <div class="wm-select-wrap" id="{wid}_fvalwrap" style="display:none;">
            <select class="wm-select" id="{wid}_fval" onchange="window['{wid}_applyFilter'](this.value)">
              <option value="">Tous</option>
            </select>
          </div>
          <span id="{wid}_map_cnt" style="margin-left:auto;font-size:9px;color:#8896BB;font-family:'IBM Plex Mono',monospace;"></span>
        </div>
        <div style="border:0.5px solid rgba(10,36,99,.2);border-radius:8px;overflow:hidden;background:#F8F9FD;">
          <div id="{wid}_map" style="height:{map_h}px;"></div>
          <div id="{wid}_foot" style="padding:6px 10px;font-family:'IBM Plex Mono',monospace;font-size:10px;color:#4A5580;border-top:0.5px solid rgba(10,36,99,.1);">
            Cliquer = aperçu · ctrl+clic = comparer
          </div>
        </div>
        <div id="{wid}_tags" style="display:flex;gap:6px;flex-wrap:wrap;margin-top:10px;"></div>
      </div>

      <!-- Panneaux courbes -->
      <div style="display:grid;grid-template-columns:1fr 1fr;grid-template-rows:1fr 1fr;gap:10px;height:{panel_h}px;">
        <div style="border:0.5px solid rgba(10,36,99,.2);border-radius:8px;background:#fff;display:flex;flex-direction:column;min-height:0;">
          <div style="padding:3px 8px;font-family:'IBM Plex Mono',monospace;font-size:8px;font-weight:700;color:#0A2463;text-transform:uppercase;letter-spacing:.06em;border-bottom:0.5px solid rgba(10,36,99,.08);display:flex;align-items:center;gap:6px;">
            <span>JV</span>
            <button id="{wid}_jv_log_btn" onclick="window['{wid}_toggleJvLog']()"
              style="margin-left:auto;font-family:'IBM Plex Mono',monospace;font-size:7px;font-weight:500;border:1px solid rgba(10,36,99,.25);border-radius:3px;padding:1px 6px;cursor:pointer;background:#fff;color:#4A5580;text-transform:none;letter-spacing:0;">J:Lin</button>
          </div>
          <div id="{wid}_c_jv" style="flex:1;min-height:0;"></div>
        </div>
        <div style="border:0.5px solid rgba(10,36,99,.2);border-radius:8px;background:#fff;display:flex;flex-direction:column;min-height:0;">
          <div style="padding:3px 8px;font-family:'IBM Plex Mono',monospace;font-size:8px;font-weight:700;color:#0A2463;text-transform:uppercase;letter-spacing:.06em;border-bottom:0.5px solid rgba(10,36,99,.08);">EQE vs J</div>
          <div id="{wid}_c_eqe" style="flex:1;min-height:0;"></div>
        </div>
        <div style="border:0.5px solid rgba(10,36,99,.2);border-radius:8px;background:#fff;display:flex;flex-direction:column;min-height:0;">
          <div style="padding:3px 8px;font-family:'IBM Plex Mono',monospace;font-size:8px;font-weight:700;color:#0A2463;text-transform:uppercase;letter-spacing:.06em;border-bottom:0.5px solid rgba(10,36,99,.08);">L vs W</div>
          <div id="{wid}_c_lw" style="flex:1;min-height:0;"></div>
        </div>
        <div style="border:0.5px solid rgba(10,36,99,.2);border-radius:8px;background:#fff;display:flex;flex-direction:column;min-height:0;">
          <div style="padding:3px 8px;font-family:'IBM Plex Mono',monospace;font-size:8px;font-weight:700;color:#0A2463;text-transform:uppercase;letter-spacing:.06em;border-bottom:0.5px solid rgba(10,36,99,.08);display:flex;align-items:center;gap:6px;">
            <span>Spectre</span>
            <input type="range" id="{wid}_sp_slider" min="0" max="0" value="0" style="flex:1;height:10px;" oninput="window['{wid}_onSpSlider'](this.value)">
          </div>
          <div id="{wid}_c_sp" style="flex:1;min-height:0;"></div>
        </div>
      </div>
    </div>
  </div>
</div>

<script>
(function(){{
  var WDATA = {wafer_json};
  var CFG = {cfg_json};
  var COLORS = {colors_json};
  var CMAP_COLS = {colormap_json};
  var FILTER_COLS = {filter_json};
  var DEFAULT_CMAP = {default_cmap};
  var wid = "{wid}";
  var CS = {cs_js};
  var X_ESC = "{x_esc}";
  var Y_ESC = "{y_esc}";

  var PLYCFG = {{responsive:true,displaylogo:false,modeBarButtonsToRemove:["autoScale2d","toggleSpikelines","sendDataToCloud"]}};
  var GSTYLE = {{gridcolor:"#E4E8F4",linecolor:"#E4E8F4",zerolinecolor:"#E4E8F4"}};

  var waferNames = Object.keys(WDATA).sort();
  var carouselIdx = 0;
  var focus = null;          // {{wafer, led}} — aperçu simple (mode comparaison OFF)
  var cmp = [];               // [{{wafer, led}}, ...] — comparaison cumulative (mode comparaison ON), pas de limite

  var st = {{
    cmapCol: DEFAULT_CMAP || (CMAP_COLS[0]||""),
    csStyle: CS,
    filterCol: FILTER_COLS[0]||"",
    filterVal: "",
    jvLogY: false,     // échelle log sur l'axe J du panneau JV
    compareMode: false, // toggle : OFF = clic remplace la sélection, ON = clic ajoute/retire (superpose)
  }};

  function currentLeds(){{ return WDATA[waferNames[carouselIdx]]||[]; }}

  /* ── Filtre (colonne + valeur), identique à WaferMaps ── */
  function filteredLeds(){{
    var leds = currentLeds();
    if(!st.filterCol||st.filterVal==="") return leds;
    return leds.filter(function(l){{
      var v=l[st.filterCol];
      if(v==null) return false;
      var parts=st.filterVal.match(/^(>=|<=|>|<|=)[ ]*(.+)/);
      var op=parts?parts[1]:"=";
      var raw=parts?parts[2].trim():st.filterVal.trim();
      var val2=Number(raw);
      var isNum=raw!==""&&!isNaN(val2)&&isFinite(val2);
      if(isNum){{
        var vn=Number(v);
        if(isNaN(vn)) return false;
        if(op===">=") return vn>=val2;
        if(op==="<=") return vn<=val2;
        if(op===">")  return vn>val2;
        if(op==="<")  return vn<val2;
        return vn===val2;
      }}
      var vs=String(v).toLowerCase();
      var rs=raw.toLowerCase();
      if(op===">="||op==="") return vs>=rs;
      if(op==="<=") return vs<=rs;
      if(op===">")  return vs>rs;
      if(op==="<")  return vs<rs;
      return vs===rs;
    }});
  }}

  function filterValues(col){{
    var seen={{}};
    currentLeds().forEach(function(l){{ if(l[col]!=null) seen[l[col]]=true; }});
    return Object.keys(seen).sort();
  }}

  (function initToolbar(){{
    var cmSel = document.getElementById(wid+"_cmap_col");
    CMAP_COLS.forEach(function(c){{
      var o=document.createElement("option");
      o.value=c; o.textContent=c;
      if(c===st.cmapCol) o.selected=true;
      cmSel.appendChild(o);
    }});
    var csSel = document.getElementById(wid+"_cs_style");
    for(var i=0;i<csSel.options.length;i++){{
      if(csSel.options[i].value===st.csStyle) csSel.selectedIndex=i;
    }}
    var fcSel = document.getElementById(wid+"_fcol");
    FILTER_COLS.forEach(function(c){{
      var o=document.createElement("option");
      o.value=c; o.textContent=c;
      fcSel.appendChild(o);
    }});
  }})();

  window[wid+"_updateCmapCol"] = function(col){{ st.cmapCol=col; renderMap(); }};
  window[wid+"_updateCsStyle"] = function(cs){{ st.csStyle=cs; renderMap(); }};
  window[wid+"_updateFcol"] = function(col){{
    st.filterCol=col; st.filterVal="";
    var wrap=document.getElementById(wid+"_fvalwrap");
    if(!col){{ wrap.style.display="none"; renderMap(); return; }}
    wrap.style.display="";
    var vals=filterValues(col);
    var sel=document.getElementById(wid+"_fval");
    sel.innerHTML='<option value="">Tous</option>'+vals.map(function(v){{return '<option value="'+v+'">'+v+'</option>';}}).join('');
    renderMap();
  }};
  window[wid+"_applyFilter"] = function(val){{ st.filterVal=val; renderMap(); }};
  function ledByKey(k){{
    var parts = k.split("::"), w = parts[0], id_ = parts.slice(1).join("::");
    var arr = WDATA[w]||[];
    for(var i=0;i<arr.length;i++) if(arr[i]._id===id_) return arr[i];
    return null;
  }}
  function keyOf(w, led){{ return w+"::"+led._id; }}

  function zip2(a,b){{
    var o=[]; var n=Math.min((a||[]).length,(b||[]).length);
    for(var i=0;i<n;i++){{ if(a[i]!=null&&b[i]!=null&&!isNaN(a[i])&&!isNaN(b[i])) o.push([a[i],b[i]]); }}
    return o;
  }}
  function normalize(arr){{
    var mx=Math.max.apply(null,(arr||[]).filter(function(v){{return v!=null&&!isNaN(v);}}));
    if(!mx||mx===0) return arr||[];
    return (arr||[]).map(function(v){{return v!=null?v/mx:v;}});
  }}

  function miniLayout(xt,yt,logx,logy){{
    return {{
      paper_bgcolor:"rgba(0,0,0,0)",plot_bgcolor:"#F8F9FD",
      font:{{family:"IBM Plex Mono,monospace",color:"#4A5580",size:8}},
      margin:{{t:4,r:6,b:26,l:34}},
      showlegend:false,
      xaxis:Object.assign({{}},GSTYLE,{{title:{{text:xt,font:{{size:8,color:"#0A2463"}},standoff:2}},type:logx?"log":"linear",tickfont:{{size:7}}}}),
      yaxis:Object.assign({{}},GSTYLE,{{title:{{text:yt,font:{{size:8,color:"#0A2463"}},standoff:2}},type:logy?"log":"linear",tickfont:{{size:7}}}}),
    }};
  }}

  function goToWafer(idx){{
    carouselIdx = Math.max(0, Math.min(idx, waferNames.length-1));
    document.getElementById(wid+"_wafer_name").textContent = waferNames[carouselIdx]||"—";
    document.getElementById(wid+"_wafer_counter").textContent = waferNames.length?((carouselIdx+1)+" / "+waferNames.length):"";
    document.getElementById(wid+"_prev").disabled = carouselIdx===0;
    document.getElementById(wid+"_next").disabled = carouselIdx===waferNames.length-1;
    document.getElementById(wid+"_foot").textContent = "Cliquer = aperçu · ctrl+clic = comparer";
    if(st.filterCol){{
      var vals=filterValues(st.filterCol);
      var sel=document.getElementById(wid+"_fval");
      sel.innerHTML='<option value="">Tous</option>'+vals.map(function(v){{return '<option value="'+v+'">'+v+'</option>';}}).join('');
      sel.value = vals.indexOf(st.filterVal)>=0 ? st.filterVal : "";
      st.filterVal = sel.value;
    }}
    renderMap();
    renderPanels();
  }}
  window[wid+"_carouselNav"] = function(dir){{ goToWafer(carouselIdx+dir); }};

  function renderMap(){{
    var leds = filteredLeds();
    var mapEl = document.getElementById(wid+"_map");
    document.getElementById(wid+"_map_cnt").textContent = leds.length+" / "+currentLeds().length+" positions";
    if(!leds.length){{
      Plotly.react(mapEl, [], {{
        paper_bgcolor:"rgba(0,0,0,0)", plot_bgcolor:"rgba(248,249,253,1)",
        annotations:[{{text:"Aucune donnée",xref:"paper",yref:"paper",x:.5,y:.5,showarrow:false,font:{{size:12,color:"#8896BB"}}}}]
      }}, PLYCFG);
      return;
    }}
    var xs = leds.map(function(l){{return l.x;}});
    var ys = leds.map(function(l){{return l.y;}});
    var w = waferNames[carouselIdx];
    var hasColor = !!st.cmapCol;

    function minStep(arr){{
      var uniq = arr.filter(function(v,i,a){{return a.indexOf(v)===i;}}).sort(function(a,b){{return a-b;}});
      var step = Infinity;
      for(var i=1;i<uniq.length;i++) step = Math.min(step, uniq[i]-uniq[i-1]);
      return isFinite(step) ? step : 1;
    }}
    var xStep = minStep(xs), yStep = minStep(ys);
    var pitch = Math.min(xStep, yStep);
    var xmin = Math.min.apply(null,xs), xmax = Math.max.apply(null,xs);
    var ymin = Math.min.apply(null,ys), ymax = Math.max.apply(null,ys);

    var cmpColorOf = {{}};
    cmp.forEach(function(c,ci){{ cmpColorOf[c.k] = COLORS[ci%COLORS.length]; }});
    /* couleur de mise en évidence (cmp prioritaire, sinon focus en or) par clé */
    function highlightColorOf(k){{
      if(cmpColorOf[k]) return cmpColorOf[k];
      if(focus && focus.k===k) return "#D4AF37";
      return null;
    }}

    var customdata = leds.map(function(l,i){{ return [i, l._id]; }});
    var tpl = "<b>%{{customdata[1]}}</b><br>X: %{{x}} · Y: %{{y}}<br><extra></extra>";
    var flip = (st.csStyle==="Jet");

    /* Une seule trace, toujours : un 2e trace overlay pour la sélection rendait
       le clic peu fiable (hit-testing ambigu entre 2 traces superposées) et
       masquait parfois les points. La sélection/comparaison est représentée
       par le contour + la taille du marker (arrays par-point). */
    var lineWidths = leds.map(function(l){{ return highlightColorOf(keyOf(w,l)) ? 2.5 : 0; }});
    var baseSize = 8;
    var sizes = leds.map(function(l){{ return highlightColorOf(keyOf(w,l)) ? baseSize+2.5 : baseSize; }});

    var markerCfg;
    if(hasColor){{
      markerCfg = {{
        symbol:"square", size:sizes,
        color: leds.map(function(l){{ var v=l[st.cmapCol]; return v!=null?v:null; }}),
        colorscale: st.csStyle, reversescale: flip, showscale: true,
        colorbar:{{thickness:12,len:0.85,tickfont:{{family:"IBM Plex Mono,monospace",size:8,color:"#4A5580"}},title:{{text:st.cmapCol,font:{{size:8,color:"#0A2463"}},side:"right"}},outlinewidth:0}},
        line:{{width:lineWidths, color: leds.map(function(l){{ return highlightColorOf(keyOf(w,l)) || "rgba(0,0,0,0)"; }})}},
      }};
    }} else {{
      markerCfg = {{
        symbol:"square", size:sizes,
        color: leds.map(function(l){{ return highlightColorOf(keyOf(w,l)) || "rgba(10,36,99,.15)"; }}),
        line:{{width:lineWidths, color:"#fff"}},
      }};
    }}

    var trace = {{
      type:"scatter", mode:"markers", x:xs, y:ys,
      marker: markerCfg,
      customdata: customdata,
      hovertemplate: tpl,
    }};

    var layout = {{
      paper_bgcolor:"rgba(0,0,0,0)", plot_bgcolor:"rgba(248,249,253,1)",
      font:{{family:"IBM Plex Mono,monospace",color:"#4A5580",size:10}},
      margin:{{t:8,r:hasColor?70:10,b:36,l:44}},
      xaxis:Object.assign({{}},GSTYLE,{{title:{{text:X_ESC,font:{{size:10,color:"#0A2463"}}}},range:[xmin-pitch,xmax+pitch],dtick:1,tickfont:{{size:9}},showgrid:true,zeroline:false,fixedrange:true}}),
      yaxis:Object.assign({{}},GSTYLE,{{title:{{text:Y_ESC,font:{{size:10,color:"#0A2463"}}}},range:[ymin-pitch,ymax+pitch],dtick:1,tickfont:{{size:9}},showgrid:true,zeroline:false,fixedrange:true}}),
      shapes:[{{type:"circle",xref:"paper",yref:"paper",x0:0.02,y0:0.02,x1:0.98,y1:0.98,line:{{color:"rgba(10,36,99,0.35)",width:1.8}},fillcolor:"rgba(0,0,0,0)",layer:"above"}}],
      clickmode:"event+select",
      dragmode:false,
      hoverlabel:{{bgcolor:"#0A2463",bordercolor:"#D4AF37",font:{{family:"IBM Plex Mono",size:9,color:"white"}}}},
    }};

    Plotly.react(mapEl, [trace], layout, PLYCFG).then(function(){{
      function calcSize(el){{
        var mL=44,mR=hasColor?70:10,mT=8,mB=36;
        var plotW = el.offsetWidth-mL-mR, plotH = el.offsetHeight-mT-mB;
        if(plotW<=0||plotH<=0) return 8;
        var xRange=(xmax-xmin)+2*pitch, yRange=(ymax-ymin)+2*pitch;
        var szX=plotW/xRange*pitch, szY=plotH/yRange*pitch;
        return Math.max(4, Math.min(szX,szY)*0.92);
      }}
      function applySizes(el){{
        var s = calcSize(el);
        var newSizes = leds.map(function(l){{ return highlightColorOf(keyOf(w,l)) ? s+2.5 : s; }});
        Plotly.restyle(el, {{"marker.size": [newSizes]}}, [0]);
      }}
      applySizes(mapEl);
      if(window[wid+"_resizeObs"]) window[wid+"_resizeObs"].disconnect();
      window[wid+"_resizeObs"] = new ResizeObserver(function(){{
        var el = document.getElementById(wid+"_map");
        if(el) applySizes(el);
      }});
      window[wid+"_resizeObs"].observe(mapEl);
    }});

    /* Le handler n'est lié qu'UNE SEULE fois (sinon Plotly accumule les listeners
       à chaque re-render, faisant se déclencher plusieurs fois le même clic — les
       toggles ctrl+clic s'annulent alors deux à deux et une 2e position du même
       wafer semble "ne pas s'ajouter"). onMapClick relit toujours filteredLeds()
       à la volée plutôt que de capturer un tableau figé dans la closure. */
    if(!mapEl.__wccClickBound){{
      mapEl.on("plotly_click", onMapClick);
      mapEl.__wccClickBound = true;
    }}
  }}

  function onMapClick(evt){{
    if(!evt.points || !evt.points.length) return;
    var pt = evt.points[0];
    var leds = filteredLeds();
    var led = leds[pt.customdata[0]];
    if(!led) return;
    var w = waferNames[carouselIdx];
    var k = keyOf(w, led);
    if(st.compareMode){{
      var i = cmp.findIndex(function(c){{return c.k===k;}});
      if(i>=0) cmp.splice(i,1);
      else cmp.push({{k:k, w:w, led:led}});
      focus = null;
      document.getElementById(wid+"_foot").textContent = cmp.length+" position(s) en comparaison";
    }} else {{
      focus = {{k:k, w:w, led:led}};
      cmp = [];
      document.getElementById(wid+"_foot").innerHTML =
        '<span style="color:#D4AF37">&#9656;</span> '+w+' — '+led._id+' — X='+led.x+' Y='+led.y;
    }}
    renderMap();
    renderPanels();
    renderTags();
  }}

  window[wid+"_toggleCompareMode"] = function(){{
    st.compareMode = !st.compareMode;
    if(st.compareMode && focus){{ cmp = [focus]; focus = null; }}
    if(!st.compareMode){{ cmp = []; focus = null; }}
    var btn = document.getElementById(wid+"_mode_btn");
    btn.textContent = "⚏ Mode comparaison : "+(st.compareMode?"ON":"OFF");
    btn.style.background = st.compareMode ? "rgba(10,36,99,.12)" : "transparent";
    btn.style.color = st.compareMode ? "#0A2463" : "#4A5580";
    btn.style.borderColor = st.compareMode ? "#0A2463" : "rgba(10,36,99,.25)";
    document.getElementById(wid+"_foot").textContent = st.compareMode
      ? "Mode comparaison : cliquer des positions pour les superposer"
      : "Cliquer = aperçu d'une position";
    renderMap(); renderPanels(); renderTags();
  }};

  window[wid+"_clearCmp"] = function(){{
    cmp = []; focus = null;
    document.getElementById(wid+"_foot").textContent = st.compareMode
      ? "Mode comparaison : cliquer des positions pour les superposer"
      : "Cliquer = aperçu d'une position";
    renderMap(); renderPanels(); renderTags();
  }};

  function renderTags(){{
    var tz = document.getElementById(wid+"_tags");
    tz.innerHTML = "";
    cmp.forEach(function(c,ci){{
      var col = COLORS[ci%COLORS.length];
      var t = document.createElement("div");
      t.style.cssText = "background:rgba(10,36,99,.05);border:1px solid "+col+";border-radius:12px;padding:2px 9px;font-size:10px;color:#0A2463;cursor:pointer;font-family:'IBM Plex Mono',monospace;";
      t.innerHTML = '<span style="color:'+col+'">&#9632;</span> '+c.w+' · '+c.led._id+' <b style="margin-left:4px">&times;</b>';
      t.onclick = (function(k){{
        return function(){{
          var i = cmp.findIndex(function(x){{return x.k===k;}});
          if(i>=0) cmp.splice(i,1);
          renderMap(); renderPanels(); renderTags();
        }};
      }})(c.k);
      tz.appendChild(t);
    }});
  }}

  /* ── Panneaux courbes (aperçu seul si pas de comparaison, sinon overlay cmp) ── */
  function activeSet(){{
    if(cmp.length) return cmp;
    if(focus) return [focus];
    return [];
  }}

  function renderPanels(){{
    var set = activeSet();
    var jvT=[], eqeT=[], lwT=[];
    var maxSteps = 0;

    set.forEach(function(c,ci){{
      var col = COLORS[ci%COLORS.length];
      var r = c.led;
      var name = c.w+" · "+r._id;

      var V = r[CFG.vCol]||[], J = r[CFG.jCol]||[], I = r[CFG.iCol]||[];
      var L = r[CFG.lCol]||[], W = r[CFG.wCol]||[], EQE = r[CFG.eCol]||[];

      var pjv = zip2(V, J.length?J:I);
      if(pjv.length) jvT.push({{x:pjv.map(function(p){{return p[0];}}),y:pjv.map(function(p){{return p[1];}}),name:name,type:"scatter",mode:"lines",line:{{color:col,width:1.6}}}});

      var pje = zip2(J,EQE).filter(function(p){{return p[0]>0;}});
      if(pje.length) eqeT.push({{x:pje.map(function(p){{return p[0];}}),y:pje.map(function(p){{return p[1];}}),name:name,type:"scatter",mode:"lines",line:{{color:col,width:1.6}}}});

      var pwl = zip2(W,L).filter(function(p){{return p[0]>0&&p[1]>0;}});
      if(pwl.length) lwT.push({{x:pwl.map(function(p){{return p[0];}}),y:pwl.map(function(p){{return p[1];}}),name:name,type:"scatter",mode:"lines",line:{{color:col,width:1.6}}}});

      if((r._sp||[]).length>maxSteps) maxSteps = r._sp.length;
    }});

    var showLegend = set.length>1;
    Plotly.react(wid+"_c_jv", jvT, Object.assign(miniLayout("V","J / I",false,st.jvLogY),{{showlegend:showLegend,legend:{{font:{{size:7}}}}}}), PLYCFG);
    Plotly.react(wid+"_c_eqe", eqeT, Object.assign(miniLayout("J (A/cm²)","EQE (%)",true,false),{{showlegend:showLegend,legend:{{font:{{size:7}}}}}}), PLYCFG);
    Plotly.react(wid+"_c_lw", lwT, Object.assign(miniLayout("W","L",true,true),{{showlegend:showLegend,legend:{{font:{{size:7}}}}}}), PLYCFG);

    var slider = document.getElementById(wid+"_sp_slider");
    slider.max = Math.max(0, maxSteps-1);
    if(parseInt(slider.value) > maxSteps-1) slider.value = Math.max(0, maxSteps-1);
    renderSpectra(set, showLegend);
  }}

  function renderSpectra(set, showLegend){{
    var idx = parseInt(document.getElementById(wid+"_sp_slider").value)||0;
    var spT = [];
    set.forEach(function(c,ci){{
      var col = COLORS[ci%COLORS.length];
      var r = c.led;
      var sp = normalize((r._sp||[])[idx]||[]);
      var wl = r._wl||[];
      if(!sp.length || !wl.length) return;
      spT.push({{x:wl,y:sp,name:c.w+" · "+c.led._id,type:"scatter",mode:"lines",line:{{color:col,width:1.6}}}});
    }});
    Plotly.react(wid+"_c_sp", spT, Object.assign(miniLayout("λ (nm)","Intensité norm.",false,false),{{showlegend:showLegend,legend:{{font:{{size:7}}}},yaxis:{{range:[0,1.05]}}}}), PLYCFG);
  }}
  window[wid+"_onSpSlider"] = function(){{ renderSpectra(activeSet(), activeSet().length>1); }};

  window[wid+"_toggleJvLog"] = function(){{
    st.jvLogY = !st.jvLogY;
    var btn = document.getElementById(wid+"_jv_log_btn");
    btn.textContent = "J:"+(st.jvLogY?"Log":"Lin");
    btn.style.background = st.jvLogY ? "rgba(10,36,99,.1)" : "#fff";
    btn.style.color = st.jvLogY ? "#0A2463" : "#4A5580";
    btn.style.borderColor = st.jvLogY ? "rgba(10,36,99,.4)" : "rgba(10,36,99,.25)";
    Plotly.relayout(wid+"_c_jv", {{"yaxis.type": st.jvLogY?"log":"linear"}});
  }};

  document.addEventListener("keydown", function(e){{
    if(e.key==="ArrowLeft"||e.key==="ArrowRight"){{
      var wrap = document.getElementById(wid+"_wrap");
      if(!wrap || !wrap.matches(":hover")) return;
      e.preventDefault();
      goToWafer(carouselIdx+(e.key==="ArrowRight"?1:-1));
    }}
  }});

  goToWafer(0);
}})();
</script>
"""
