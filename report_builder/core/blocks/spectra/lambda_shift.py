from __future__ import annotations
import json
import html as _h
import numpy as np
import pandas as pd
from ..._helpers import Block, _safe_json, _is_vector_col
from ..data.data_mixin import DataMixin, DataArg


class LambdaShiftBlock(DataMixin, Block):
    """
    Lambda Peak vs J — décalage spectral interactif.

    Layout (panneau droit ouvert par défaut) :
      ┌─────────────────┬──────────────┬──────────────┬──────────┐
      │                 │  courbe Y    │   spectre    │  wafer   │
      │  scatter        │  (dropdown)  │   @ clic     │  mini    │
      │  principal      │  val. dessus │  val. dessus │          │
      └─────────────────┴──────────────┴──────────────┴──────────┘

    Paramètres
    ──────────
    j_col, lambda_col, spectra_col, wavelength_col  : colonnes vectorielles
    x_col, y_col  : colonnes scalaires position sur wafer (défaut "X", "Y")
    wafer_col     : colonne scalaire nom du wafer (pour filtrer les LEDs du même wafer)
    detail_cols   : dict label→colonne_df (vectorielles alignées sur J). None = auto.
    color_col, id_col, hover_cols, filter_cols
    log_x, lambda_min, lambda_max, x_range, y_range, height
    """

    needs_plotly = True

    def __init__(
        self,
        data: DataArg,
        j_col: str = "J",
        lambda_col: str = "Lambda_Peak",
        spectra_col: str = "Spectra",
        wavelength_col: str = "Wavelength",
        x_col: str = "X",
        y_col: str = "Y",
        wafer_col: str = "wafername",
        detail_cols: dict[str, str] | None = None,
        color_col: str = "srgb",
        id_col: str = "Led_Name",
        hover_cols: list[str] | None = None,
        filter_cols: list[str] | None = None,
        log_x: bool = True,
        lambda_min: float = 420.0,
        lambda_max: float = 750.0,
        x_range: tuple | None = None,
        y_range: tuple | None = None,
        height: int = 500,
        title: str = "Lambda Peak vs J",
        subtitle: str = "",
        num: str = "01",
    ):
        self._init_data(data)
        self.j_col = j_col
        self.lambda_col = lambda_col
        self.spectra_col = spectra_col
        self.wavelength_col = wavelength_col
        self.x_col = x_col
        self.y_col = y_col
        self.wafer_col = wafer_col
        self.detail_cols = detail_cols
        self.color_col = color_col
        self.id_col = id_col
        self.hover_cols = hover_cols or []
        self.filter_cols = filter_cols or []
        self.log_x = log_x
        self.lambda_min = lambda_min
        self.lambda_max = lambda_max
        self.x_range = x_range
        self.y_range = y_range
        self.height = height
        self.title = title
        self.subtitle = subtitle
        self.num = num
        self._id = f"lsb_{id(self)}"

    def _safe_list(self, v, target: int = 120) -> list:
        if not isinstance(v, (list, np.ndarray)):
            return []
        arr = np.asarray(v, dtype=float)
        if len(arr) > target:
            arr = arr[::max(1, len(arr) // target)]
        return [None if np.isnan(x) else float(x) for x in arr]

    def _resolve_detail_cols(self, df: pd.DataFrame) -> dict[str, str]:
        if self.detail_cols is not None:
            return {k: v for k, v in self.detail_cols.items() if v in df.columns}
        exclude = {self.j_col, self.spectra_col, self.wavelength_col,
                   "srgb", "CIEx", "CIEy", "I", "V", "L", "EQE"}
        result = {}
        for col in df.columns:
            if col in exclude:
                continue
            if _is_vector_col(df[col]):
                result[col] = col
        return result

    def _build_js_data(self, df: pd.DataFrame, detail_map: dict[str, str]) -> str:
        records = []
        for _, row in df.iterrows():
            rec: dict = {}
            rec["_id"] = str(row[self.id_col]) if self.id_col in row.index else str(len(records))

            # Position wafer (scalaires)
            rec["wx"] = float(row[self.x_col])   if self.x_col   in row.index and pd.notna(row[self.x_col])   else None
            rec["wy"] = float(row[self.y_col])   if self.y_col   in row.index and pd.notna(row[self.y_col])   else None
            rec["wn"] = str(row[self.wafer_col]) if self.wafer_col in row.index and pd.notna(row[self.wafer_col]) else ""

            # X/Y principal avec filtrage NaN + seuil physique
            j_raw  = np.array(row[self.j_col],      dtype=float) if self.j_col      in row.index else np.array([])
            lp_raw = np.array(row[self.lambda_col],  dtype=float) if self.lambda_col in row.index else np.array([])
            n = min(len(j_raw), len(lp_raw))
            if n > 0:
                mask = (
                    ~np.isnan(j_raw[:n])  &
                    ~np.isnan(lp_raw[:n]) &
                    (j_raw[:n]  > 0)      &
                    (lp_raw[:n] > self.lambda_min) &
                    (lp_raw[:n] < self.lambda_max)
                )
                orig_idx = np.where(mask)[0]
                rec["x"]        = j_raw[:n][mask].tolist()
                rec["y"]        = lp_raw[:n][mask].tolist()
                rec["orig_idx"] = orig_idx.tolist()
            else:
                rec["x"] = []; rec["y"] = []; rec["orig_idx"] = []

            # Colonnes détail alignées sur orig_idx
            rec["detail"] = {}
            for label, col in detail_map.items():
                if col not in row.index:
                    continue
                raw = row[col]
                if not isinstance(raw, (list, np.ndarray)) or len(raw) == 0:
                    rec["detail"][label] = []
                    continue
                raw_arr = np.array(raw, dtype=float)
                if len(raw_arr) >= n and n > 0:
                    vals = [None if np.isnan(raw_arr[i]) else float(raw_arr[i]) for i in rec["orig_idx"]]
                else:
                    vals = [None if np.isnan(v) else float(v) for v in raw_arr]
                rec["detail"][label] = vals

            # Couleur
            if self.color_col in row.index:
                cv = row[self.color_col]
                if isinstance(cv, (list, np.ndarray)):
                    cv_list = list(cv)
                    rec["color"] = cv_list
                    rec["color_scalar"] = cv_list[len(cv_list)//2] if cv_list else "#D4AF37"
                else:
                    rec["color"] = _safe_json(cv)
                    rec["color_scalar"] = _safe_json(cv)
            else:
                rec["color"] = "#D4AF37"; rec["color_scalar"] = "#D4AF37"

            # Spectres
            if self.spectra_col in row.index:
                sp = row[self.spectra_col]
                if isinstance(sp, (list, np.ndarray)) and len(sp) > 0:
                    rec["spectra"] = [self._safe_list(sp[i]) for i in rec["orig_idx"] if i < len(sp)]
            if self.wavelength_col in row.index:
                rec["wl"] = self._safe_list(row[self.wavelength_col])

            for c in self.hover_cols:
                if c in row.index:
                    v = row[c]
                    if not isinstance(v, (list, np.ndarray)):
                        rec[c] = _safe_json(v)

            records.append(rec)
        return json.dumps(records)

    def _build_filter_meta(self, df: pd.DataFrame) -> str:
        meta = {}
        for col in self.filter_cols:
            if col not in df.columns:
                continue
            series = df[col].dropna()
            if series.empty:
                continue
            try:
                numeric = pd.to_numeric(series)
                vals = sorted(numeric.tolist())
                meta[col] = {"type": "numeric", "min": vals[0], "max": vals[-1]}
            except (ValueError, TypeError):
                meta[col] = {"type": "string", "values": sorted(series.astype(str).unique().tolist())}
        return json.dumps(meta)

    def _build_filter_data(self, df: pd.DataFrame) -> str:
        records = []
        for _, row in df.iterrows():
            rec = {}
            for col in self.filter_cols:
                if col in row.index:
                    v = row[col]
                    if not isinstance(v, (list, np.ndarray)):
                        rec[col] = _safe_json(v)
            records.append(rec)
        return json.dumps(records)

    def _hover_js(self) -> str:
        lines = []
        for c in self.hover_cols:
            safe = c.replace('"', '\\"')
            lines.append(f'if(r["{safe}"]!=null) htxt+="<br>{safe}: "+r["{safe}"]')
        return (";\n          ".join(lines) + ";") if lines else ""

    def render(self, store=None) -> str:
        df = self.resolve_df(store)
        sid = self._id

        detail_map       = self._resolve_detail_cols(df)
        data_json        = self._build_js_data(df, detail_map)
        filter_meta_json = self._build_filter_meta(df)
        filter_data_json = self._build_filter_data(df)

        detail_labels_json = json.dumps(list(detail_map.keys()))
        default_label = next((k for k, v in detail_map.items() if v == self.lambda_col),
                             list(detail_map.keys())[0] if detail_map else "")
        default_label_js = json.dumps(default_label)

        log_x_js   = "true" if self.log_x else "false"
        has_filt   = "true" if self.filter_cols else "false"
        h          = self.height
        title_h    = _h.escape(self.title)
        sub_h      = _h.escape(self.subtitle)
        num_h      = _h.escape(self.num)
        x_range_js = f"[{self.x_range[0]},{self.x_range[1]}]" if self.x_range else "null"
        y_range_js = f"[{self.y_range[0]},{self.y_range[1]}]" if self.y_range else "null"
        hover_js   = self._hover_js()
        sub_graph_h = max(160, h // 2 - 50)

        return f"""
<style>
#{sid}_row {{
  display:flex; flex-direction:row; align-items:stretch; gap:0;
}}
#{sid}_scatter_col {{
  flex:1 1 0; min-width:0;
}}
#{sid}_right_panel {{
  flex:0 0 680px; width:680px;
  display:flex; flex-direction:column;
  border-left:2px solid #E4E8F4;
  background:#F8F9FD;
  position:relative;
  overflow:hidden;
  transition:flex-basis .38s cubic-bezier(.4,0,.2,1), width .38s cubic-bezier(.4,0,.2,1);
}}
#{sid}_right_panel::before {{
  content:''; position:absolute; top:0; left:0; bottom:0; width:2px;
  background:linear-gradient(180deg,#D4AF37,rgba(212,175,55,.2) 50%,transparent 80%);
}}
#{sid}_right_panel.closed {{
  flex-basis:0 !important; width:0 !important;
}}
#{sid}_right_inner {{
  display:flex; flex-direction:column; height:100%;
  padding:8px 10px 8px 14px; gap:0; min-width:660px;
}}
#{sid}_panels_row {{
  display:flex; flex-direction:row; gap:8px; flex:1; min-height:0; align-items:stretch;
}}
#{sid}_curve_col, #{sid}_spec_col {{
  flex:1 1 0; min-width:0; display:flex; flex-direction:column;
}}
#{sid}_wafer_row {{
  display:flex; flex-direction:row; gap:8px; flex-shrink:0; margin-top:8px;
}}
#{sid}_wafer_map_col {{
  flex:0 0 160px; max-width:160px; display:flex; flex-direction:column;
}}
#{sid}_wafer_info_col {{
  flex:1 1 0; min-width:0; display:flex; flex-direction:column; justify-content:center;
}}
.lsb-val-badge {{
  font-family:'IBM Plex Mono',monospace;
  font-size:10px; color:#0A2463;
  background:rgba(212,175,55,.12);
  border:1px solid rgba(212,175,55,.4);
  border-radius:3px; padding:2px 7px;
  display:inline-block; margin:2px 0 4px;
  letter-spacing:.03em;
}}
.lsb-val-badge.empty {{ background:transparent; border-color:transparent; color:#aaa; }}
.lsb-sub-hdr {{
  display:flex; align-items:center; gap:6px;
  font-family:'IBM Plex Mono',monospace; font-size:9px;
  color:#0A2463; letter-spacing:.05em; text-transform:uppercase;
  margin-bottom:2px; flex-shrink:0;
}}
.lsb-sub-hdr select {{
  font-size:9px; padding:1px 4px; border-radius:3px;
  border:1px solid #D4AF37; background:#fff; color:#0A2463;
  cursor:pointer; flex:1; min-width:0;
}}
</style>

<div class="led-block" id="{sid}_wrap">
  <div class="led-block-header">
    <span class="led-block-num">{num_h}</span>
    <span class="led-block-title">{title_h}</span>
    <span class="led-block-sub">{sub_h}</span>
  </div>
  <div class="led-block-rule"></div>

  <!-- toolbar -->
  <div class="scatter-led-toolbar">
    <button class="slt-btn active" id="{sid}_btn_click" onclick="{sid}_setMode('click')">✦ CLIC</button>
    <button class="slt-btn" id="{sid}_btn_lasso" onclick="{sid}_setMode('lasso')">⬡ LASSO</button>
    <button class="slt-btn" id="{sid}_btn_box"   onclick="{sid}_setMode('box')">▣ ZONE</button>
    <div class="slt-sep"></div>
    <button class="slt-btn" onclick="{sid}_clearSel()">✕ EFFACER</button>
    <span class="slt-count" id="{sid}_selcount">Aucune sélection</span>
    <div style="margin-left:auto;">
      <button class="slt-btn" id="{sid}_btn_toggle" onclick="{sid}_togglePanel()" title="Afficher/masquer le panneau">⊞ PANNEAU</button>
    </div>
  </div>

  <!-- filtres -->
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
  <div id="{sid}_row">

    <!-- scatter -->
    <div id="{sid}_scatter_col">
      <div id="{sid}_scatter" style="height:{h}px;"></div>
    </div>

    <!-- panneau droit -->
    <div id="{sid}_right_panel">
      <div id="{sid}_right_inner">

        <!-- header -->
        <div style="display:flex;align-items:center;gap:8px;flex-shrink:0;margin-bottom:6px;">
          <span class="led-block-num" style="font-size:9px;">↳</span>
          <span class="led-detail-label" id="{sid}_detlabel" style="flex:1;font-size:10px;color:#0A2463;font-family:'IBM Plex Mono',monospace;">
            <span style="color:#D4AF37;">—</span> sélectionner une LED
          </span>
        </div>

        <!-- 2 colonnes : courbe | spectre -->
        <div id="{sid}_panels_row">

          <!-- courbe -->
          <div id="{sid}_curve_col">
            <div class="lsb-sub-hdr">
              <span>Courbe vs J</span>
              <select id="{sid}_ycol_sel" onchange="{sid}_onYChange(this.value)"></select>
            </div>
            <div class="lsb-val-badge empty" id="{sid}_curve_val">—</div>
            <div id="{sid}_det_curve" style="height:{sub_graph_h}px;flex-shrink:0;"></div>
          </div>

          <!-- spectre -->
          <div id="{sid}_spec_col">
            <div class="lsb-sub-hdr"><span>Spectre</span></div>
            <div class="lsb-val-badge empty" id="{sid}_spec_val">—</div>
            <div id="{sid}_det_spec" style="height:{sub_graph_h}px;flex-shrink:0;"></div>
          </div>

        </div><!-- panels_row -->

        <!-- wafer row : carte + info LED -->
        <div id="{sid}_wafer_row">

          <!-- mini wafer cliquable -->
          <div id="{sid}_wafer_map_col">
            <div class="lsb-sub-hdr"><span>Position wafer</span></div>
            <div class="lsb-val-badge empty" id="{sid}_wafer_val">—</div>
            <div id="{sid}_det_wafer" style="height:150px;flex-shrink:0;cursor:crosshair;"
                 title="Clic = naviguer vers cette LED"></div>
          </div>

          <!-- info LED sélectionnée -->
          <div id="{sid}_wafer_info_col">
            <div class="lsb-sub-hdr"><span>LED active</span></div>
            <div id="{sid}_led_info" style="
              font-family:'IBM Plex Mono',monospace; font-size:10px; color:#4A5580;
              padding:6px 8px; background:#fff; border:1px solid #E4E8F4;
              border-radius:4px; line-height:1.8; margin-top:2px;
            ">— sélectionner une LED sur le scatter ou sur le wafer</div>
          </div>

        </div><!-- wafer_row -->
      </div><!-- right_inner -->
    </div><!-- right_panel -->

  </div><!-- row -->
</div>

<script>
(function(){{
  var DATA   = {data_json};
  var FDATA  = {filter_data_json};
  var FMETA  = {filter_meta_json};
  var DETAIL_LABELS = {detail_labels_json};
  var sid    = "{sid}";
  var logX   = {log_x_js};
  var hasFlt = {has_filt};
  var mode   = "click";
  var selIdx = [];
  var filteredIndices = null;
  var filterRowCount  = 0;
  var currentYLabel   = {default_label_js};
  var lastLedIndices  = null;
  var lastClickedPt   = null;
  var panelOpen       = true;

  var MULTI  = ["#D4AF37","#3B82F6","#EF4444","#8B5CF6","#10B981","#F59E0B","#EC4899","#06B6D4","#84CC16","#F97316"];
  var PLYCFG = {{responsive:true,displaylogo:false,modeBarButtonsToRemove:["autoScale2d","toggleSpikelines","sendDataToCloud"]}};
  var GSTYLE = {{gridcolor:"#E4E8F4",linecolor:"#E4E8F4",zerolinecolor:"#E4E8F4"}};

  if(hasFlt) document.getElementById(sid+"_filterbar").style.display="block";

  /* ── Dropdown Y ── */
  var selEl=document.getElementById(sid+"_ycol_sel");
  DETAIL_LABELS.forEach(function(lbl){{
    var o=document.createElement("option");o.value=lbl;o.textContent=lbl;
    if(lbl===currentYLabel) o.selected=true;
    selEl.appendChild(o);
  }});
  window[sid+"_onYChange"]=function(lbl){{
    currentYLabel=lbl;
    if(lastLedIndices) renderDetail(lastLedIndices,lastClickedPt);
  }};

  /* ── Toggle panneau ── */
  window[sid+"_togglePanel"]=function(){{
    panelOpen=!panelOpen;
    var panel=document.getElementById(sid+"_right_panel");
    if(panelOpen) panel.classList.remove("closed");
    else panel.classList.add("closed");
    setTimeout(function(){{Plotly.Plots.resize(sid+"_scatter");}},420);
  }};

  /* ── Couleurs ── */
  var _catMap={{}},_catIdx=0;
  function resolveColor(raw){{
    if(!raw) return "#D4AF37";
    if(typeof raw==="string"&&raw.startsWith("#")) return raw;
    if(!_catMap[raw]) _catMap[raw]=MULTI[_catIdx++%MULTI.length];
    return _catMap[raw];
  }}

  /* ── Sous-layout ── */
  function subLayout(xl,yl,lx,ly,extra){{
    var lay={{paper_bgcolor:"rgba(0,0,0,0)",plot_bgcolor:"#F8F9FD",
      font:{{family:"IBM Plex Mono,monospace",color:"#4A5580",size:9}},
      margin:{{t:4,r:6,b:30,l:40}},showlegend:false,
      xaxis:Object.assign({{}},GSTYLE,{{title:{{text:xl,font:{{size:8,color:"#0A2463"}},standoff:2}},type:lx?"log":"linear",tickfont:{{size:7}}}}),
      yaxis:Object.assign({{}},GSTYLE,{{title:{{text:yl,font:{{size:8,color:"#0A2463"}},standoff:2}},type:ly?"log":"linear",tickfont:{{size:7}}}}),
      hoverlabel:{{bgcolor:"#0A2463",bordercolor:"#D4AF37",font:{{family:"IBM Plex Mono",size:8,color:"white"}}}}}};
    if(extra) Object.assign(lay,extra);
    return lay;
  }}

  /* ── Badge valeur ── */
  function setBadge(id,text){{
    var el=document.getElementById(id);
    if(!el) return;
    if(text){{el.textContent=text;el.classList.remove("empty");}}
    else{{el.textContent="—";el.classList.add("empty");}}
  }}

  /* ── Filtres ── */
  function evalNumFilter(val,op,thr){{
    if(!op||thr===""||isNaN(+thr)) return true;
    var v=+val,t=+thr;if(isNaN(v)) return false;
    switch(op){{case"gt":return v>t;case"gte":return v>=t;case"lt":return v<t;case"lte":return v<=t;case"eq":return Math.abs(v-t)<1e-9;case"neq":return Math.abs(v-t)>=1e-9;default:return true;}}
  }}
  function computeFilteredSet(){{
    var rows=document.querySelectorAll("#"+sid+"_filterrows .sled-frow");
    if(!rows.length) return null;
    var hasActive=false;
    rows.forEach(function(row){{var col=row.querySelector(".sled-fcol").value;if(!col||!FMETA[col]) return;
      if(FMETA[col].type==="numeric"){{var op=row.querySelector(".sled-fop").value,val=row.querySelector(".sled-fval-num").value;if(op&&val!=="")hasActive=true;}}
      else{{if(row.querySelectorAll(".sled-fchk:checked").length)hasActive=true;}}}});
    if(!hasActive) return null;
    var result=new Set();
    FDATA.forEach(function(fd,ri){{var pass=true;
      rows.forEach(function(row){{if(!pass) return;var col=row.querySelector(".sled-fcol").value;if(!col||!FMETA[col]) return;
        var val=fd[col];if(val==null) return;
        if(FMETA[col].type==="numeric"){{if(!evalNumFilter(val,row.querySelector(".sled-fop").value,row.querySelector(".sled-fval-num").value))pass=false;}}
        else{{var checked=[];row.querySelectorAll(".sled-fchk:checked").forEach(function(c){{checked.push(c.value);}});if(checked.length&&checked.indexOf(String(val))<0)pass=false;}}}});
      if(pass) result.add(ri);}});
    return result;
  }}
  window[sid+"_addFilter"]=function(){{
    var cols=Object.keys(FMETA);if(!cols.length) return;filterRowCount++;
    var container=document.getElementById(sid+"_filterrows");
    var row=document.createElement("div");row.className="sled-frow";
    var sel=document.createElement("select");sel.className="sled-fcol spt-filter-op";sel.style.minWidth="130px";
    var opt0=document.createElement("option");opt0.value="";opt0.textContent="— colonne —";sel.appendChild(opt0);
    cols.forEach(function(c){{var o=document.createElement("option");o.value=c;o.textContent=c;sel.appendChild(o);}});
    var ctrl=document.createElement("div");ctrl.className="sled-fctrl";
    var del=document.createElement("button");del.className="slt-btn";del.textContent="✕";
    del.onclick=function(){{row.remove();window[sid+"_applyFilters"]();}};
    sel.onchange=function(){{ctrl.innerHTML="";var col=sel.value;if(!col||!FMETA[col]) return;
      if(FMETA[col].type==="numeric"){{
        var opSel=document.createElement("select");opSel.className="sled-fop spt-filter-op";
        [["","—"],["gt","&gt;"],["gte","&ge;"],["lt","&lt;"],["lte","&le;"],["eq","=="],["neq","!="]].forEach(function(p){{var o=document.createElement("option");o.value=p[0];o.innerHTML=p[1];opSel.appendChild(o);}});
        var ni=document.createElement("input");ni.type="number";ni.className="sled-fval-num spt-filter-val";ni.placeholder="valeur";
        ni.addEventListener("keydown",function(e){{if(e.key==="Enter")window[sid+"_applyFilters"]();}});
        ctrl.appendChild(opSel);ctrl.appendChild(ni);
      }}else{{var wrap=document.createElement("div");wrap.className="sled-fchk-wrap";
        FMETA[col].values.forEach(function(v){{var lbl=document.createElement("label");lbl.className="sled-fchk-label";
          var chk=document.createElement("input");chk.type="checkbox";chk.className="sled-fchk";chk.value=v;
          var span=document.createElement("span");span.textContent=v;lbl.appendChild(chk);lbl.appendChild(span);wrap.appendChild(lbl);}});
        ctrl.appendChild(wrap);}}}};
    row.appendChild(sel);row.appendChild(ctrl);row.appendChild(del);container.appendChild(row);
  }};
  window[sid+"_applyFilters"]=function(){{
    filteredIndices=computeFilteredSet();
    var total=DATA.length,cnt=filteredIndices?filteredIndices.size:total;
    var el=document.getElementById(sid+"_filtcount");
    if(filteredIndices){{el.textContent=cnt+" / "+total;el.className="spt-filt-count "+(cnt<total?"spt-filt-active":"spt-filt-ok");}}else el.textContent="";
    selIdx=[];document.getElementById(sid+"_selcount").textContent="Aucune sélection";document.getElementById(sid+"_selcount").classList.remove("has-sel");
    Plotly.react(sid+"_scatter",buildTraces(null),document.getElementById(sid+"_scatter").layout,PLYCFG);
  }};
  window[sid+"_resetFilters"]=function(){{
    filteredIndices=null;document.getElementById(sid+"_filterrows").innerHTML="";document.getElementById(sid+"_filtcount").textContent="";
    filterRowCount=0;selIdx=[];document.getElementById(sid+"_selcount").textContent="Aucune sélection";document.getElementById(sid+"_selcount").classList.remove("has-sel");
    Plotly.react(sid+"_scatter",buildTraces(null),document.getElementById(sid+"_scatter").layout,PLYCFG);
  }};

  /* ── Auto-range ── */
  function computeAutoRange(forced,isLog,allVals){{
    if(forced!==null) return isLog?[Math.log10(forced[0]),Math.log10(forced[1])]:forced;
    if(!allVals.length) return null;
    var mn=Math.min.apply(null,allVals),mx=Math.max.apply(null,allVals);
    if(isLog){{var lm=Math.log10(mn),lM=Math.log10(mx),p=Math.max((lM-lm)*0.06,0.3);return[lm-p,lM+p];}}
    var p=(mx-mn)*0.06||Math.abs(mx)*0.06||1;return[mn-p,mx+p];
  }}
  var _allX=[],_allY=[];
  DATA.forEach(function(r){{(r.x||[]).forEach(function(v){{if(v!=null&&v>0)_allX.push(v);}});(r.y||[]).forEach(function(v){{if(v!=null&&!isNaN(v))_allY.push(v);}});}});
  var xRange=computeAutoRange({x_range_js},logX,_allX);
  var yRange=computeAutoRange({y_range_js},false,_allY);

  /* ── Build scatter principal ── */
  function buildTraces(focusRi){{
    var focusSet=null;
    if(focusRi!==null){{focusSet={{}};if(Array.isArray(focusRi))focusRi.forEach(function(i){{focusSet[i]=true;}});else focusSet[focusRi]=true;}}
    var activeTraces=[],ghostXs=[],ghostYs=[];
    DATA.forEach(function(r,ri){{
      var pass=(filteredIndices===null||filteredIndices.has(ri));
      var focused=(focusSet===null||focusSet[ri]===true);
      var xArr=r.x||[],yArr=r.y||[];
      if(!pass||!focused){{for(var pi=0;pi<Math.min(xArr.length,yArr.length);pi++){{ghostXs.push(xArr[pi]);ghostYs.push(yArr[pi]);}}return;}}
      var lineCol=Array.isArray(r.color)?resolveColor(r.color_scalar||r.color[0]):resolveColor(r.color_scalar||r.color);
      var isSF=(focusSet!==null&&Object.keys(focusSet).length===1&&focusSet[ri]);
      var texts=xArr.map(function(xv,pi){{
        var htxt="<b>"+r._id+"</b>";
        {hover_js}
        htxt+="<br>J: "+xv.toExponential(2)+" A/cm²<br>λ Peak: "+(yArr[pi]!=null?yArr[pi].toFixed(1):"—")+" nm";
        return htxt;
      }});
      activeTraces.push({{type:"scatter",mode:"lines+markers",x:xArr,y:yArr,
        line:{{color:lineCol,width:isSF?2:1.2}},
        marker:{{color:lineCol,size:isSF?5:3,line:{{width:isSF?1:0,color:"#1a1a2e"}}}},
        text:texts,hovertemplate:"%{{text}}<extra></extra>",
        customdata:xArr.map(function(_,pi){{return[ri,pi];}}),name:r._id,showlegend:false}});
    }});
    var traces=[];
    if(ghostXs.length) traces.push({{type:"scatter",mode:"markers",x:ghostXs,y:ghostYs,marker:{{color:"rgba(0,0,0,0)",size:1}},hoverinfo:"skip",showlegend:false}});
    return traces.concat(activeTraces);
  }}

  var mainLayout={{paper_bgcolor:"rgba(0,0,0,0)",plot_bgcolor:"#F8F9FD",
    font:{{family:"IBM Plex Mono,monospace",color:"#4A5580",size:11}},
    margin:{{t:10,r:20,b:52,l:64}},showlegend:false,
    xaxis:Object.assign({{}},GSTYLE,{{title:{{text:"J (A/cm²)",font:{{size:13,color:"#0A2463"}},standoff:8}},
      type:logX?"log":"linear",tickfont:{{size:11}},range:xRange,
      showspikes:true,spikecolor:"rgba(10,36,99,.3)",spikemode:"across",spikethickness:1,spikedash:"dot"}}),
    yaxis:Object.assign({{}},GSTYLE,{{title:{{text:"λ Peak (nm)",font:{{size:13,color:"#0A2463"}},standoff:8}},
      type:"linear",tickfont:{{size:11}},range:yRange,
      showspikes:true,spikecolor:"rgba(10,36,99,.3)",spikemode:"across",spikethickness:1,spikedash:"dot"}}),
    clickmode:"event+select",dragmode:false,hovermode:"closest",
    hoverlabel:{{bgcolor:"#0A2463",bordercolor:"#D4AF37",font:{{family:"IBM Plex Mono",size:10,color:"white"}}}}}};

  Plotly.newPlot(sid+"_scatter",buildTraces(null),mainLayout,PLYCFG);

  /* ── Wafer coords globaux ── */
  var _waferCoords=[];
  DATA.forEach(function(r){{if(r.wx!=null)_waferCoords.push(Math.abs(r.wx),Math.abs(r.wy));}});
  var _waferMaxR=_waferCoords.length?Math.max.apply(null,_waferCoords)*1.15:1;
  var _waferCircX=[],_waferCircY=[];
  for(var _a=0;_a<=360;_a+=3){{_waferCircX.push(Math.cos(_a*Math.PI/180)*_waferMaxR);_waferCircY.push(Math.sin(_a*Math.PI/180)*_waferMaxR);}}

  /* ── Build traces wafer ── */
  function buildWaferTraces(selRi){{
    var selR=DATA[selRi];
    var waferName=selR?selR.wn:"";
    /* LEDs du même wafer */
    var bgXs=[],bgYs=[],bgCols=[],bgTexts=[],bgCustom=[];
    DATA.forEach(function(r,ri){{
      if(r.wx==null||r.wy==null) return;
      if(waferName&&r.wn!==waferName) return;
      bgXs.push(r.wx);bgYs.push(r.wy);
      bgCustom.push(ri);
      bgTexts.push("<b>"+r._id+"</b><br>X="+r.wx+" Y="+r.wy);
      bgCols.push(ri===selRi?"#EF4444":(r.x&&r.x.length>0?"#94A3B8":"#E2E8F0"));
    }});
    var traces=[];
    /* cercle */
    traces.push({{type:"scatter",mode:"lines",
      x:_waferCircX,y:_waferCircY,
      line:{{color:"#CBD5E1",width:1.5}},hoverinfo:"skip",showlegend:false}});
    /* tous les dies */
    if(bgXs.length) traces.push({{
      type:"scatter",mode:"markers",x:bgXs,y:bgYs,
      marker:{{
        color:bgCols,
        size:bgCols.map(function(c){{return c==="#EF4444"?11:6;}}),
        opacity:bgCols.map(function(c){{return c==="#EF4444"?1:0.7;}}),
        line:{{width:bgCols.map(function(c){{return c==="#EF4444"?2:0;}}),color:"white"}}
      }},
      text:bgTexts,hovertemplate:"%{{text}}<extra></extra>",
      customdata:bgCustom,showlegend:false
    }});
    return traces;
  }}

  /* ── Layout wafer ── */
  var _waferLayout={{
    paper_bgcolor:"rgba(0,0,0,0)",plot_bgcolor:"#F8F9FD",
    margin:{{t:2,r:2,b:2,l:2}},showlegend:false,
    xaxis:{{visible:false,scaleanchor:"y",range:[-_waferMaxR*1.05,_waferMaxR*1.05]}},
    yaxis:{{visible:false,range:[-_waferMaxR*1.05,_waferMaxR*1.05]}},
    clickmode:"event",hovermode:"closest",
    hoverlabel:{{bgcolor:"#0A2463",bordercolor:"#D4AF37",font:{{family:"IBM Plex Mono",size:8,color:"white"}}}},
  }};

  function renderWafer(selRi){{
    var r=DATA[selRi];
    if(r&&r.wx!=null) setBadge(sid+"_wafer_val","X="+r.wx+" · Y="+r.wy+(r.wn?" · "+r.wn:""));
    else setBadge(sid+"_wafer_val",null);
    Plotly.newPlot(sid+"_det_wafer",buildWaferTraces(selRi),_waferLayout,PLYCFG);
    /* Clic sur un die → naviguer vers cette LED */
    document.getElementById(sid+"_det_wafer").on("plotly_click",function(evt){{
      var pt=evt.points[0];
      if(pt==null||pt.customdata==null) return;
      var ri=pt.customdata;
      var r=DATA[ri];
      if(!r||!r.x||!r.x.length) return;  /* LED sans données valides */
      /* Mettre à jour la sélection */
      selIdx=[ri];
      document.getElementById(sid+"_selcount").textContent="LED · "+r._id;
      document.getElementById(sid+"_selcount").classList.add("has-sel");
      /* Highlight sur le scatter principal */
      Plotly.react(sid+"_scatter",buildTraces(ri),document.getElementById(sid+"_scatter").layout,PLYCFG);
      /* Render le panneau avec le dernier point cliqué = point médian */
      var midPt=Math.floor(r.x.length/2);
      renderDetail([ri],midPt);
    }});
  }}

  /* ── Render panneau droit complet ── */
  function renderDetail(ledIndices,clickedPt){{
    lastLedIndices=ledIndices;lastClickedPt=clickedPt;
    var isSingle=ledIndices.length===1;

    /* Header */
    var r0=DATA[ledIndices[0]];
    document.getElementById(sid+"_detlabel").innerHTML=
      "<span style='color:#D4AF37;'>▸</span> "+
      (isSingle?r0._id:ledIndices.length+" LEDs")+
      (isSingle&&clickedPt!=null?" · pt "+(clickedPt+1):"");

    /* ── Courbe Y ── */
    var curveTraces=[];
    ledIndices.forEach(function(ri,ci){{
      var r=DATA[ri],col=MULTI[ci%MULTI.length];
      var xs=r.x||[];
      var ys=(r.detail&&r.detail[currentYLabel])||[];
      if(!xs.length||!ys.length) return;
      var fx=[],fy=[],mC=[],mS=[];
      xs.forEach(function(xv,pi){{
        if(ys[pi]!=null){{fx.push(xv);fy.push(ys[pi]);
          mC.push(isSingle&&pi===clickedPt?"#EF4444":col);
          mS.push(isSingle&&pi===clickedPt?10:3);}}}});
      if(!fx.length) return;
      curveTraces.push({{type:"scatter",mode:"lines+markers",x:fx,y:fy,
        line:{{color:col,width:isSingle?1.8:1.2}},
        marker:{{color:mC,size:mS,line:{{width:isSingle?0.8:0,color:"#1a1a2e"}}}},
        name:r._id,hovertemplate:"J: %{{x:.2e}}<br>"+currentYLabel+": %{{y:.2f}}<extra>"+r._id+"</extra>",
        showlegend:!isSingle}});
    }});
    /* Badge valeur au point cliqué */
    if(isSingle&&clickedPt!=null){{
      var rr=DATA[ledIndices[0]];
      var ys=(rr.detail&&rr.detail[currentYLabel])||[];
      var val=ys[clickedPt];
      setBadge(sid+"_curve_val",val!=null?currentYLabel+": "+val.toFixed(3):null);
    }}else setBadge(sid+"_curve_val",null);

    if(curveTraces.length)
      Plotly.newPlot(sid+"_det_curve",curveTraces,subLayout("J (A/cm²)",currentYLabel,logX,false),PLYCFG);
    else
      document.getElementById(sid+"_det_curve").innerHTML='<div class="no-data-msg">Pas de données pour "'+currentYLabel+'"</div>';

    /* ── Spectre ── */
    var specTraces=[];
    ledIndices.forEach(function(ri,ci){{
      var r=DATA[ri],col=MULTI[ci%MULTI.length];
      if(!r.spectra||!r.wl||!r.spectra.length) return;
      var specIdx=isSingle&&clickedPt!=null
        ?Math.min(clickedPt,r.spectra.length-1)
        :Math.min(Math.round(r.spectra.length/2),r.spectra.length-1);
      var sp=r.spectra[specIdx];if(!sp||!sp.length) return;
      var jVal=r.x&&r.x[specIdx]!=null?r.x[specIdx].toExponential(2):"?";
      var lpVal=r.y&&r.y[specIdx]!=null?r.y[specIdx].toFixed(1):"?";
      var maxI=0,maxV=-Infinity;sp.forEach(function(v,i){{if(v!=null&&v>maxV){{maxV=v;maxI=i;}}}});
      var fwArr=(r.detail&&r.detail["FWHM"])||[];
      var fwVal=fwArr[specIdx]!=null?fwArr[specIdx].toFixed(1)+"nm":"—";
      specTraces.push({{x:r.wl,y:sp,type:"scatter",mode:"lines",
        line:{{color:col,width:1.8}},fill:isSingle?"tozeroy":"none",
        fillcolor:"rgba(212,175,55,.07)",name:r._id,showlegend:!isSingle}});
      if(isSingle){{
        specTraces.push({{type:"scatter",mode:"markers",x:[r.wl[maxI]],y:[maxV],
          marker:{{size:9,color:"#EF4444",symbol:"circle",line:{{width:2,color:"white"}}}},
          hovertemplate:"λ peak = %{{x:.1f}} nm<extra></extra>",showlegend:false}});
        setBadge(sid+"_spec_val","J="+jVal+" · λ="+lpVal+"nm · FWHM="+fwVal);
      }}
    }});
    if(!isSingle) setBadge(sid+"_spec_val",null);
    if(specTraces.length){{
      Plotly.newPlot(sid+"_det_spec",specTraces,subLayout("λ (nm)","Intensité",false,false),PLYCFG);
    }}else{{
      document.getElementById(sid+"_det_spec").innerHTML='<div class="no-data-msg">Pas de spectre</div>';
    }}

    /* ── Mini wafer ── */
    if(isSingle){{
      renderWafer(ledIndices[0]);
      /* Info LED dans la zone texte */
      var ri0=ledIndices[0],rr=DATA[ri0];
      var lpVal=rr.y&&rr.y[clickedPt!=null?clickedPt:0]!=null?rr.y[clickedPt!=null?clickedPt:0].toFixed(1):"—";
      var jVal=rr.x&&rr.x[clickedPt!=null?clickedPt:0]!=null?rr.x[clickedPt!=null?clickedPt:0].toExponential(2):"—";
      var fwArr=(rr.detail&&rr.detail["FWHM"])||[];
      var fwVal=fwArr[clickedPt!=null?clickedPt:0]!=null?fwArr[clickedPt!=null?clickedPt:0].toFixed(1)+"nm":"—";
      document.getElementById(sid+"_led_info").innerHTML=
        "<b style='color:#0A2463;'>"+rr._id+"</b><br>"+
        "Wafer : "+(rr.wn||"—")+"<br>"+
        "Position : X="+(rr.wx!=null?rr.wx:"—")+" · Y="+(rr.wy!=null?rr.wy:"—")+"<br>"+
        "@ pt "+(clickedPt!=null?clickedPt+1:"—")+" : J="+jVal+" A/cm²<br>"+
        "λ Peak = "+lpVal+" nm · FWHM = "+fwVal;
    }}else{{
      setBadge(sid+"_wafer_val",null);
      /* En lasso, afficher tous les dies sélectionnés sur le wafer */
      var waferName=DATA[ledIndices[0]]?DATA[ledIndices[0]].wn:"";
      var selSet=new Set(ledIndices);
      var bgXs=[],bgYs=[],bgCols=[],bgTexts=[],bgCustom=[];
      DATA.forEach(function(r,ri){{
        if(r.wx==null||r.wy==null) return;
        if(waferName&&r.wn!==waferName) return;
        bgXs.push(r.wx);bgYs.push(r.wy);bgCustom.push(ri);
        bgTexts.push("<b>"+r._id+"</b><br>X="+r.wx+" Y="+r.wy);
        bgCols.push(selSet.has(ri)?"#D4AF37":(r.x&&r.x.length>0?"#94A3B8":"#E2E8F0"));
      }});
      var traces=[{{type:"scatter",mode:"lines",x:_waferCircX,y:_waferCircY,line:{{color:"#CBD5E1",width:1.5}},hoverinfo:"skip",showlegend:false}}];
      if(bgXs.length) traces.push({{type:"scatter",mode:"markers",x:bgXs,y:bgYs,
        marker:{{color:bgCols,size:bgCols.map(function(c){{return c==="#D4AF37"?9:6;}}),
          opacity:bgCols.map(function(c){{return c==="#D4AF37"?1:0.5;}}),
          line:{{width:bgCols.map(function(c){{return c==="#D4AF37"?1:0;}}),color:"#1a1a2e"}}}},
        text:bgTexts,hovertemplate:"%{{text}}<extra></extra>",
        customdata:bgCustom,showlegend:false}});
      Plotly.newPlot(sid+"_det_wafer",traces,_waferLayout,PLYCFG);
      /* Clic depuis le lasso-wafer aussi */
      document.getElementById(sid+"_det_wafer").on("plotly_click",function(evt){{
        var pt=evt.points[0];if(pt==null||pt.customdata==null) return;
        var ri=pt.customdata,r=DATA[ri];if(!r||!r.x||!r.x.length) return;
        selIdx=[ri];
        document.getElementById(sid+"_selcount").textContent="LED · "+r._id;
        document.getElementById(sid+"_selcount").classList.add("has-sel");
        Plotly.react(sid+"_scatter",buildTraces(ri),document.getElementById(sid+"_scatter").layout,PLYCFG);
        renderDetail([ri],Math.floor(r.x.length/2));
      }});
      document.getElementById(sid+"_led_info").innerHTML=
        "<b style='color:#0A2463;'>"+ledIndices.length+" LEDs sélectionnées</b><br>"+
        "<span style='color:#D4AF37;'>●</span> = sélectionnées · clic = naviguer vers une LED";
    }}

    /* Resize après rendu */
    setTimeout(function(){{
      [sid+"_det_curve",sid+"_det_spec",sid+"_det_wafer"].forEach(function(eid){{
        var el=document.getElementById(eid);if(el&&el.data)Plotly.Plots.resize(eid);
      }});
    }},60);
  }}

  /* ── Mode ── */
  window[sid+"_setMode"]=function(m){{
    mode=m;["click","lasso","box"].forEach(function(x){{document.getElementById(sid+"_btn_"+x).classList.toggle("active",x===m);}});
    Plotly.relayout(sid+"_scatter",{{dragmode:m==="lasso"?"lasso":m==="box"?"select":false}});
  }};
  window[sid+"_clearSel"]=function(){{
    selIdx=[];
    document.getElementById(sid+"_selcount").textContent="Aucune sélection";
    document.getElementById(sid+"_selcount").classList.remove("has-sel");
    lastLedIndices=null;lastClickedPt=null;
    setBadge(sid+"_curve_val",null);setBadge(sid+"_spec_val",null);setBadge(sid+"_wafer_val",null);
    document.getElementById(sid+"_detlabel").innerHTML="<span style='color:#D4AF37;'>—</span> sélectionner une LED";
    document.getElementById(sid+"_det_wafer").innerHTML="";
    document.getElementById(sid+"_led_info").textContent="— sélectionner une LED sur le scatter ou sur le wafer";
    Plotly.react(sid+"_scatter",buildTraces(null),document.getElementById(sid+"_scatter").layout,PLYCFG);
  }};

  /* ── Événements ── */
  document.getElementById(sid+"_scatter").on("plotly_click",function(evt){{
    if(mode!=="click") return;var pt=evt.points[0],cd=pt.customdata;if(!cd||cd.length<2) return;
    var ri=cd[0],pi=cd[1],r=DATA[ri];selIdx=[ri];
    document.getElementById(sid+"_selcount").textContent="LED · "+r._id;
    document.getElementById(sid+"_selcount").classList.add("has-sel");
    Plotly.react(sid+"_scatter",buildTraces(ri),document.getElementById(sid+"_scatter").layout,PLYCFG);
    renderDetail([ri],pi);
  }});
  document.getElementById(sid+"_scatter").on("plotly_selected",function(evt){{
    if(!evt||!evt.points||!evt.points.length) return;var seen={{}};
    evt.points.forEach(function(p){{if(p.customdata&&p.customdata.length>=2)seen[p.customdata[0]]=true;}});
    selIdx=Object.keys(seen).map(Number);if(!selIdx.length) return;var cnt=selIdx.length;
    document.getElementById(sid+"_selcount").textContent=cnt+" LED"+(cnt>1?"s":"")+" · lasso";
    document.getElementById(sid+"_selcount").classList.add("has-sel");
    Plotly.react(sid+"_scatter",buildTraces(selIdx),document.getElementById(sid+"_scatter").layout,PLYCFG);
    renderDetail(selIdx.slice(0,10),null);
  }});
  document.getElementById(sid+"_scatter").on("plotly_deselect",function(){{window[sid+"_clearSel"]();}});
  document.getElementById(sid+"_scatter").addEventListener("dblclick",function(){{window[sid+"_clearSel"]();}});

  window.addEventListener("resize",function(){{
    Plotly.Plots.resize(sid+"_scatter");
    [sid+"_det_curve",sid+"_det_spec",sid+"_det_wafer"].forEach(function(eid){{
      var el=document.getElementById(eid);if(el&&el.data)Plotly.Plots.resize(eid);
    }});
  }});

}})();
</script>
"""