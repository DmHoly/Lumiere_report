from __future__ import annotations
import json
import html as _h
import numpy as np
import pandas as pd
from ..._helpers import Block, _safe_json, _is_vector_col, _col_analysis
from ..data.data_mixin import DataMixin, DataArg


class WaferMaps(DataMixin, Block):
    """
    Cartes de wafer interactives — v3 (Carousel + Scatter carrés).

    Nouveautés v3 :
      - Carousel : navigation entre wafers avec flèches ← → (plus d'empilement vertical)
      - Scatter carrés (symbol="square") à la place de la heatmap
      - Colorscale dropdown : Viridis, Jet, Plasma, Inferno, RdBu, Turbo
      - Toggle log/lin sur les axes X et Y de chaque courbe
    """
    needs_plotly = True

    def __init__(
        self,
        data: DataArg,
        x_col: str = "X",
        y_col: str = "Y",
        wafer_col: str = "wafername",
        color_col: str = "",
        colormap_cols: list[str] | None = None,
        filter_col: str = "",
        filter_cols: list[str] | None = None,
        id_col: str = "",
        kpi_cols: list[str] | None = None,
        curve_cols: dict | None = None,
        spectra_col: str = "",
        wavelength_col: str = "",
        colorscale: str = "Viridis",
        map_height: int = 340,
        map_ratio: str = "1fr 2fr",
        num: str = "03",
        title: str = "Wafer Maps",
        subtitle: str = "Position (X, Y)",
    ):
        self._init_data(data)
        self.x_col = x_col
        self.y_col = y_col
        self.wafer_col = wafer_col
        self.color_col = color_col
        self._colormap_cols_arg = colormap_cols
        self._filter_cols_arg = filter_cols
        self._kpi_cols_arg = kpi_cols
        self.curve_cols = curve_cols or {}
        self.spectra_col = spectra_col
        self.wavelength_col = wavelength_col
        self.id_col = id_col
        self.filter_col = filter_col
        self.colorscale = colorscale
        self.map_height = map_height
        self.num = num
        self.title = title
        self.subtitle = subtitle
        self._id = f"wm_{id(self)}"
        self.map_ratio = map_ratio
        if self.has_local_data:
            self._resolve_col_lists(self.resolve_df())

    def _resolve_col_lists(self, df: pd.DataFrame) -> None:
        cols = _col_analysis(df)
        self.colormap_cols = self._colormap_cols_arg or cols["scalar_num"][:8]
        self.filter_cols = self._filter_cols_arg or cols["scalar_cat"][:6]
        self.kpi_cols = self._kpi_cols_arg or cols["scalar_num"][:6]

    def _build_wafer_json(self, df: pd.DataFrame) -> str:
        if not hasattr(self, "colormap_cols"):
            self._resolve_col_lists(df)

        all_extra = list(dict.fromkeys(
            c for c in (self.colormap_cols + self.kpi_cols + self.filter_cols)
            if c and c in df.columns
        ))
        scalar_extra = [c for c in all_extra if not _is_vector_col(df[c])]

        out = {}
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

                for lbl, cfg in self.curve_cols.items():
                    xc, yc = cfg.get("x", ""), cfg.get("y", "")
                    if xc in row.index and yc in row.index:
                        xv, yv = row[xc], row[yc]
                        rec[f"_cx_{lbl}"] = [_safe_json(z) for z in xv] if isinstance(xv, (list, np.ndarray)) else []
                        rec[f"_cy_{lbl}"] = [_safe_json(z) for z in yv] if isinstance(yv, (list, np.ndarray)) else []

                if self.spectra_col and self.spectra_col in row.index:
                    sp = row[self.spectra_col]
                    if isinstance(sp, (list, np.ndarray)) and len(sp) > 0:
                        def _ds(s, target=120):
                            if not isinstance(s, (list, np.ndarray)) or len(s) <= target:
                                return [_safe_json(v) for v in s]
                            step = max(1, len(s) // target)
                            return [_safe_json(s[i]) for i in range(0, len(s), step)]

                        rec["_spectra"] = [_ds(sp[i]) for i in range(len(sp)) if isinstance(sp[i], (list, np.ndarray))]

                if self.wavelength_col and self.wavelength_col in row.index:
                    wl = row[self.wavelength_col]
                    if isinstance(wl, (list, np.ndarray)):
                        step = max(1, len(wl) // 120)
                        rec["_wl"] = [_safe_json(wl[i]) for i in range(0, len(wl), step)]

                for lbl, cfg in self.curve_cols.items():
                    if cfg.get("x", "") in ["J", "j"] or "J" in cfg.get("xlabel", ""):
                        xc = cfg.get("x", "")
                        if xc in row.index:
                            xv = row[xc]
                            if isinstance(xv, (list, np.ndarray)):
                                rec["_J_vals"] = [_safe_json(z) for z in xv]
                        break

                leds.append(rec)
            out[str(wafer)] = leds

        return json.dumps(out)

    def render(self, store=None) -> str:
        wid = self._id
        map_ratio = self.map_ratio

        if self.has_local_data:
            # Df local : groupby Python, sérialisation inline
            df = self.resolve_df()
            if not hasattr(self, "colormap_cols"):
                self._resolve_col_lists(df)
            wafer_init_js = f"var WDATA={self._build_wafer_json(df)};"
        else:
            # Clé store : groupby JS, zéro copie
            key = self._data_arg
            if store is None:
                raise RuntimeError(
                    f"WaferMaps references store key {key!r} but no DataStore was provided."
                )
            df = store.resolve(key)
            if not hasattr(self, "colormap_cols"):
                self._resolve_col_lists(df)
            # Colonnes scalaires à inclure dans chaque LED record
            all_extra = list(dict.fromkeys(
                c for c in (self.colormap_cols + self.kpi_cols + self.filter_cols)
                if c and c in df.columns
            ))
            scalar_extra = [c for c in all_extra if not _is_vector_col(df[c])]
            curve_defs = [
                {"lbl": lbl, "xk": cfg.get("x",""), "yk": cfg.get("y","")}
                for lbl, cfg in self.curve_cols.items()
            ]
            wm_cfg = {
                "key":        key,
                "waferCol":   self.wafer_col,
                "xCol":       self.x_col,
                "yCol":       self.y_col,
                "idCol":      self.id_col or None,
                "scalarExtra": scalar_extra,
                "curveDefs":  curve_defs,
                "spectraCol": self.spectra_col or None,
                "wlCol":      self.wavelength_col or None,
            }
            wm_cfg_json = json.dumps(wm_cfg)
            wafer_init_js = (
                f"var _wc={wm_cfg_json},"
                f"_wr=(window.__DATA_STORE__||{{}})[_wc.key]||[],"
                f"WDATA={{}};"
                f"_wr.forEach(function(r,i){{"
                f"  var w=String(r[_wc.waferCol]||'?');"
                f"  if(!WDATA[w])WDATA[w]=[];"
                f"  var led={{x:r[_wc.xCol]!=null?r[_wc.xCol]:0,"
                f"y:r[_wc.yCol]!=null?r[_wc.yCol]:0,"
                f"_id:(_wc.idCol&&r[_wc.idCol]!=null)?String(r[_wc.idCol]):String(i)}};"
                f"  (_wc.scalarExtra||[]).forEach(function(c){{if(r[c]!=null&&!Array.isArray(r[c]))led[c]=r[c];}});"
                f"  (_wc.curveDefs||[]).forEach(function(d){{"
                f"    if(r[d.xk]!=null)led['_cx_'+d.lbl]=r[d.xk];"
                f"    if(r[d.yk]!=null)led['_cy_'+d.lbl]=r[d.yk];}});"
                f"  if(_wc.spectraCol&&r[_wc.spectraCol]!=null)led['_spectra']=r[_wc.spectraCol];"
                f"  if(_wc.wlCol&&r[_wc.wlCol]!=null)led['_wl']=r[_wc.wlCol];"
                f"  WDATA[w].push(led);}});"
            )
        curves_json = json.dumps({
            lbl: {
                "log_y": cfg.get("log_y", False),
                "xlabel": cfg.get("x", ""),
                "ylabel": cfg.get("y", ""),
            }
            for lbl, cfg in self.curve_cols.items()
        })
        colormap_json = json.dumps(self.colormap_cols)
        filter_json = json.dumps(self.filter_cols)
        kpi_json = json.dumps(self.kpi_cols)
        has_spec_js = "true" if self.spectra_col else "false"
        default_cmap = json.dumps(self.color_col or (self.colormap_cols[0] if self.colormap_cols else ""))
        n_curves = len(self.curve_cols)
        x_esc = _h.escape(self.x_col)
        y_esc = _h.escape(self.y_col)
        cs_js = json.dumps(self.colorscale)
        map_h = self.map_height

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
        style="font-size:18px;line-height:1;background:rgba(10,36,99,.06);border:1px solid rgba(10,36,99,.18);border-radius:6px;padding:4px 12px;cursor:pointer;color:#0A2463;transition:background .15s;"
        onmouseover="this.style.background='rgba(10,36,99,.14)'"
        onmouseout="this.style.background='rgba(10,36,99,.06)'">&#8592;</button>

      <div style="flex:1;text-align:center;">
        <span id="{wid}_wafer_name" style="font-family:'Syne',sans-serif;font-weight:700;font-size:15px;color:#0A2463;"></span>
        <span id="{wid}_wafer_counter" style="font-family:'IBM Plex Mono',monospace;font-size:10px;color:#8896BB;margin-left:10px;"></span>
      </div>

      <button id="{wid}_next" onclick="window['{wid}_carouselNav'](+1)"
        style="font-size:18px;line-height:1;background:rgba(10,36,99,.06);border:1px solid rgba(10,36,99,.18);border-radius:6px;padding:4px 12px;cursor:pointer;color:#0A2463;transition:background .15s;"
        onmouseover="this.style.background='rgba(10,36,99,.14)'"
        onmouseout="this.style.background='rgba(10,36,99,.06)'">&#8594;</button>
    </div>

    <div id="{wid}_dots" style="display:flex;justify-content:center;gap:5px;margin-bottom:14px;flex-wrap:wrap;"></div>

    <div class="wm-toolbar" id="{wid}_toolbar" style="display:flex;align-items:center;gap:6px;flex-wrap:wrap;margin-bottom:10px;">
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

      <div class="wm-sep"></div>
      <button class="wm-btn active" id="{wid}_bclick" onclick="window['{wid}_setDrag']('click')">✦ CLIC</button>
      <button class="wm-btn" id="{wid}_blasso" onclick="window['{wid}_setDrag']('lasso')">⬡ LASSO</button>
      <button class="wm-btn" id="{wid}_bbox" onclick="window['{wid}_setDrag']('select')">▣ ZONE</button>
      <div class="wm-sep"></div>
      <button class="wm-btn" onclick="window['{wid}_clearSel']()">✕</button>
      <span class="wm-sel-count" id="{wid}_selcnt">—</span>
      <span class="wm-val-badge" id="{wid}_cnt" style="margin-left:auto;font-size:9px;color:#8896BB;"></span>
    </div>

    <div class="wafer-card-body" id="{wid}_body" style="grid-template-columns:{map_ratio};gap:10px">
      <div class="wafer-card-map">
        <div id="{wid}_map" style="height:{map_h}px;"></div>
      </div>
      <div class="wafer-card-curves" id="{wid}_curves" style="grid-template-rows:repeat({max(n_curves + (1 if self.spectra_col else 0), 1)},1fr)">
        {self._curve_divs(wid, n_curves)}
      </div>
    </div>

    <div class="wm-detail-panel" id="{wid}_det">
      <div class="wm-detail-inner">
        <div class="wm-detail-grid" id="{wid}_detgrid">
          <div class="wm-led-list" id="{wid}_ledlist">
            <div class="wm-led-list-header">LEDs en ce point</div>
          </div>

          <div style="display:flex;flex-direction:column;gap:0;min-height:0;background:var(--surface);border:1px solid var(--border);">
            <div style="padding:4px 10px;font-family:var(--fd);font-weight:700;font-size:9px;color:var(--navy);text-transform:uppercase;letter-spacing:.08em;border-bottom:1px solid var(--border);flex-shrink:0;display:flex;justify-content:space-between;align-items:center;">
              <span id="{wid}_det_curves_title">—</span>
              <span style="display:flex;gap:4px;">
                <button id="{wid}_det_logx" onclick="window['{wid}_toggleDetAxis']('x')" style="font-family:'IBM Plex Mono',monospace;font-size:8px;border:1px solid rgba(10,36,99,.25);border-radius:4px;padding:1px 6px;cursor:pointer;background:#fff;color:#0A2463;" title="Basculer axe X log/lin">X:Lin</button>
                <button id="{wid}_det_logy" onclick="window['{wid}_toggleDetAxis']('y')" style="font-family:'IBM Plex Mono',monospace;font-size:8px;border:1px solid rgba(10,36,99,.25);border-radius:4px;padding:1px 6px;cursor:pointer;background:#fff;color:#0A2463;" title="Basculer axe Y log/lin">Y:Lin</button>
              </span>
            </div>
            <div id="{wid}_det_curves" style="flex:1;min-height:0;"></div>
          </div>

          <div style="display:flex;flex-direction:column;gap:0;min-height:0;background:var(--surface);border:1px solid var(--border);">
            <div style="padding:4px 10px;font-family:var(--fd);font-weight:700;font-size:9px;color:var(--navy);text-transform:uppercase;letter-spacing:.08em;border-bottom:1px solid var(--border);flex-shrink:0;display:flex;justify-content:space-between;align-items:center;">
              <span>Spectre</span>
              <span style="display:flex;align-items:center;gap:6px;">
                <span id="{wid}_spec_label" style="font-family:var(--fm);font-size:8px;color:var(--gold);font-weight:400;"></span>
                <button id="{wid}_det_spec_lx" onclick="window['{wid}_toggleDetSpecAxis']('x')" style="font-family:'IBM Plex Mono',monospace;font-size:7px;font-weight:500;border:1px solid rgba(10,36,99,.2);border-radius:3px;padding:1px 5px;cursor:pointer;background:#fff;color:#4A5580;transition:all .15s;">X:Lin</button>
                <button id="{wid}_det_spec_ly" onclick="window['{wid}_toggleDetSpecAxis']('y')" style="font-family:'IBM Plex Mono',monospace;font-size:7px;font-weight:500;border:1px solid rgba(10,36,99,.2);border-radius:3px;padding:1px 5px;cursor:pointer;background:#fff;color:#4A5580;transition:all .15s;">Y:Lin</button>
              </span>
            </div>
            <div style="padding:4px 10px;flex-shrink:0;border-bottom:1px solid var(--border);display:flex;align-items:center;gap:8px;">
              <span style="font-family:var(--fm);font-size:8px;color:var(--slate-400);">J</span>
              <input type="range" id="{wid}_spec_slider" min="0" max="0" value="0" style="flex:1;" oninput="window['{wid}_onSpecSlider'](this.value)">
            </div>
            <div id="{wid}_det_spec" style="flex:1;min-height:0;"></div>
          </div>
        </div>

        <div id="{wid}_agg_kpis" style="display:none">
          <div style="font-family:var(--fm);font-size:9px;color:var(--muted);letter-spacing:.06em;text-transform:uppercase;margin-bottom:4px;" id="{wid}_agg_title">KPIs agrégés</div>
          <div class="wm-kpi-agg-grid" id="{wid}_agg_grid"></div>
        </div>
      </div>
    </div>

    <div class="wafer-card-foot" id="{wid}_foot">Cliquer ou sélectionner des points</div>
  </div>
</div>

<script>
(function(){{
  {wafer_init_js}
  var CURVES       = {curves_json};
  var CMAP_COLS    = {colormap_json};
  var FILTER_COLS  = {filter_json};
  var KPI_COLS     = {kpi_json};
  var hasSpec      = {has_spec_js};
  var wid          = "{wid}";
  var nCurves      = {n_curves};
  var DEFAULT_CMAP = {default_cmap};
  var DEFAULT_CS   = {cs_js};
  var X_ESC        = "{x_esc}";
  var Y_ESC        = "{y_esc}";

  var PLYCFG = {{responsive:true,displaylogo:false,modeBarButtonsToRemove:["autoScale2d","toggleSpikelines","sendDataToCloud"]}};
  var GSTYLE = {{gridcolor:"#E4E8F4",linecolor:"#E4E8F4",zerolinecolor:"#E4E8F4"}};
  var MULTI  = ["#D4AF37","#3B82F6","#EF4444","#8B5CF6","#10B981","#F59E0B","#EC4899","#06B6D4"];

  var waferNames  = Object.keys(WDATA).sort();
  var carouselIdx = 0;

  var st = {{
    cmapCol: DEFAULT_CMAP || (CMAP_COLS[0]||""),
    csStyle: DEFAULT_CS,
    filterCol: FILTER_COLS[0]||"",
    filterVal: "",
    dragMode: "click",
    selIndices: [],
    detLogX: false,
    detLogY: false,
    detSpecLogX: false,
    detSpecLogY: false,
    miniLogX: [],
    miniLogY: [],
    _lastSelLeds: null,
    _lastShowLegend: false,
  }};

  var _miniCount = nCurves + (hasSpec ? 1 : 0);
  for(var _i=0; _i<_miniCount; _i++){{ st.miniLogX.push(false); st.miniLogY.push(false); }}

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
      if(csSel.options[i].value===DEFAULT_CS) csSel.selectedIndex=i;
    }}

    var fcSel = document.getElementById(wid+"_fcol");
    FILTER_COLS.forEach(function(c){{
      var o=document.createElement("option");
      o.value=c; o.textContent=c;
      fcSel.appendChild(o);
    }});
  }})();

  (function buildDots(){{
    var cont = document.getElementById(wid+"_dots");
    waferNames.forEach(function(n,i){{
      var d=document.createElement("div");
      d.id=wid+"_dot_"+i;
      d.style.cssText="width:7px;height:7px;border-radius:50%;cursor:pointer;transition:background .2s;";
      d.style.background = i===0?"#0A2463":"rgba(10,36,99,.2)";
      d.onclick=(function(idx){{return function(){{goToWafer(idx);}};}})(i);
      d.title=n;
      cont.appendChild(d);
    }});
  }})();

  function goToWafer(idx){{
    carouselIdx = Math.max(0, Math.min(idx, waferNames.length-1));
    waferNames.forEach(function(_,i){{
      var d=document.getElementById(wid+"_dot_"+i);
      if(d) d.style.background = i===carouselIdx?"#0A2463":"rgba(10,36,99,.2)";
    }});
    document.getElementById(wid+"_wafer_name").textContent = waferNames[carouselIdx];
    document.getElementById(wid+"_wafer_counter").textContent = (carouselIdx+1)+" / "+waferNames.length;
    document.getElementById(wid+"_prev").disabled = carouselIdx===0;
    document.getElementById(wid+"_next").disabled = carouselIdx===waferNames.length-1;
    st.selIndices=[];
    document.getElementById(wid+"_selcnt").textContent="—";
    document.getElementById(wid+"_det").classList.remove("open");
    document.getElementById(wid+"_det").style.display="none";
    renderMap();
  }}

  window[wid+"_carouselNav"] = function(dir){{ goToWafer(carouselIdx+dir); }};

  function currentLeds(){{ return WDATA[waferNames[carouselIdx]]||[]; }}

function filteredLeds(){{
            var leds=currentLeds();
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
    currentLeds().forEach(function(l){{if(l[col]!=null)seen[l[col]]=true;}});
    return Object.keys(seen).sort();
  }}

  function miniLayout(xt,yt,xl,yl){{
    return {{
      paper_bgcolor:"rgba(0,0,0,0)",plot_bgcolor:"#F8F9FD",
      font:{{family:"IBM Plex Mono,monospace",color:"#4A5580",size:9}},
      margin:{{t:4,r:6,b:28,l:38}},
      showlegend:false,
      xaxis:Object.assign({{}},GSTYLE,{{title:{{text:xt,font:{{size:9,color:"#0A2463"}},standoff:3}},type:xl?"log":"linear",tickfont:{{size:8}}}}),
      yaxis:Object.assign({{}},GSTYLE,{{title:{{text:yt,font:{{size:9,color:"#0A2463"}},standoff:3}},type:yl?"log":"linear",tickfont:{{size:8}}}}),
    }};
  }}

  function renderMap(){{
    var leds = filteredLeds();
    document.getElementById(wid+"_cnt").textContent = leds.length+" / "+currentLeds().length+" LEDs";

    if(!leds.length){{
      Plotly.react(document.getElementById(wid+"_map"), [], {{
        paper_bgcolor:"rgba(0,0,0,0)", plot_bgcolor:"rgba(248,249,253,1)",
        annotations:[{{text:"Aucune LED",xref:"paper",yref:"paper",x:.5,y:.5,showarrow:false,font:{{size:12,color:"#8896BB"}}}}]
      }}, PLYCFG);
      return;
    }}

    var xs    = leds.map(function(l){{return l.x;}});
    var ys    = leds.map(function(l){{return l.y;}});
    var cvals = leds.map(function(l){{return l[st.cmapCol];}});
    var cnum = cvals.map(function(v){{var n=parseFloat(v);return isNaN(n)?null:n;}});
    var hasColor = cnum.some(function(v){{return v!==null;}});

    function minStep(arr) {{
      var uniq = arr.filter(function(v,i,a){{return a.indexOf(v)===i;}}).sort(function(a,b){{return a-b;}});
      var step = Infinity;
      for(var i=1;i<uniq.length;i++) step = Math.min(step, uniq[i]-uniq[i-1]);
      return isFinite(step) ? step : 1;
    }}

    var xStep = minStep(xs);
    var yStep = minStep(ys);
    var pitch = Math.min(xStep, yStep);
    var xmin = Math.min.apply(null,xs), xmax = Math.max.apply(null,xs);
    var ymin = Math.min.apply(null,ys), ymax = Math.max.apply(null,ys);

    var customdata = leds.map(function(l,i){{
      var cv = cnum[i];
      return [i, l._id, cv!=null?cv.toFixed(3):"—"];
    }});

    var tpl = "<b>%{{customdata[1]}}</b><br>";
    tpl += "X: %{{x}} · Y: %{{y}}<br>";
    if(hasColor) tpl += st.cmapCol+": %{{customdata[2]}}<br>";
    tpl += "<extra></extra>";

    var flip = (st.csStyle==="Jet");

    var trace = {{
      type: "scatter",
      mode: "markers",
      x: xs,
      y: ys,
      marker: {{
        symbol: "square",
        size: 8,
        color: cnum,
        colorscale: st.csStyle,
        reversescale: flip,
        showscale: hasColor,
        line: {{ width: 0 }},
        colorbar: {{
          thickness: 12,
          len: 0.85,
          tickfont: {{family:"IBM Plex Mono,monospace",size:8,color:"#4A5580"}},
          title: {{text:st.cmapCol,font:{{size:8,color:"#0A2463"}},side:"right"}},
          outlinewidth: 0,
        }},
      }},
      customdata: customdata,
      hovertemplate: tpl,
    }};

    var layout = {{
      paper_bgcolor: "rgba(0,0,0,0)",
      plot_bgcolor: "rgba(248,249,253,1)",
      font: {{family:"IBM Plex Mono,monospace",color:"#4A5580",size:10}},
      margin: {{t:8, r:hasColor?70:10, b:36, l:44}},
      xaxis: Object.assign({{}}, GSTYLE, {{
        title: {{text:X_ESC, font:{{size:10,color:"#0A2463"}}}},
        range: [xmin - pitch, xmax + pitch],
        dtick: 1,
        tickfont: {{size:9}},
        visible: true,
        showgrid: true,
        zeroline: false,
        fixedrange: true,
      }}),
      yaxis: Object.assign({{}}, GSTYLE, {{
        title: {{text:Y_ESC, font:{{size:10,color:"#0A2463"}}}},
        range: [ymin - pitch, ymax + pitch],
        dtick: 1,
        tickfont: {{size:9}},
        visible: true,
        showgrid: true,
        zeroline: false,
        fixedrange: true,
      }}),
      shapes: [{{
        type: "circle", xref: "paper", yref: "paper",
        x0: 0.02, y0: 0.02, x1: 0.98, y1: 0.98,
        line: {{color:"rgba(10,36,99,0.35)",width:1.8}},
        fillcolor: "rgba(0,0,0,0)",
        layer: "above",
      }}],
      clickmode: "event+select",
      dragmode: st.dragMode==="click" ? false : st.dragMode,
      hoverlabel: {{
        bgcolor: "#0A2463",
        bordercolor: "#D4AF37",
        font: {{family:"IBM Plex Mono",size:9,color:"white"}},
      }},
    }};

    var mapEl = document.getElementById(wid+"_map");
    Plotly.react(mapEl, [trace], layout, PLYCFG).then(function() {{
      function calcSize(el) {{
        var mL = 44, mR = hasColor ? 70 : 10, mT = 8, mB = 36;
        var plotW = el.offsetWidth  - mL - mR;
        var plotH = el.offsetHeight - mT - mB;
        if(plotW <= 0 || plotH <= 0) return 8;
        var xRange = (xmax - xmin) + 2 * pitch;
        var yRange = (ymax - ymin) + 2 * pitch;
        var szX = plotW / xRange * pitch;
        var szY = plotH / yRange * pitch;
        return Math.max(4, Math.min(szX, szY) * 0.92);
      }}
      Plotly.restyle(mapEl, {{"marker.size": calcSize(mapEl)}}, [0]);

      if(window[wid+"_resizeObs"]) window[wid+"_resizeObs"].disconnect();
      window[wid+"_resizeObs"] = new ResizeObserver(function(){{
        var el = document.getElementById(wid+"_map");
        if(el) Plotly.restyle(el, {{"marker.size": calcSize(el)}}, [0]);
      }});
      window[wid+"_resizeObs"].observe(mapEl);
    }});

    mapEl.removeAllListeners && mapEl.removeAllListeners("plotly_click");
    mapEl.removeAllListeners && mapEl.removeAllListeners("plotly_selected");
    mapEl.on("plotly_click", function(e){{ onMapClick(e, leds); }});
    mapEl.on("plotly_selected", function(e){{ onMapSelect(e, leds); }});
    mapEl.on("plotly_deselect", function(){{ clearSel(); }});
  }}

  window[wid+"_updateCmapCol"] = function(col){{ st.cmapCol=col; renderMap(); }};
  window[wid+"_updateCsStyle"] = function(cs){{ st.csStyle=cs; renderMap(); }};
  window[wid+"_updateFcol"] = function(col){{
    st.filterCol=col; st.filterVal="";
    var wrap=document.getElementById(wid+"_fvalwrap");
    if(!col){{wrap.style.display="none"; renderMap(); return;}}
    wrap.style.display="";
    var vals=filterValues(col);
    var sel=document.getElementById(wid+"_fval");
    sel.innerHTML='<option value="">Tous</option>'+vals.map(function(v){{return '<option value="'+v+'">'+v+'</option>';}}).join('');
    renderMap();
  }};
  window[wid+"_applyFilter"] = function(val){{ st.filterVal=val; renderMap(); }};
  window[wid+"_setDrag"] = function(m){{
    st.dragMode=m;
    ["click","lasso","box"].forEach(function(x){{
      document.getElementById(wid+"_b"+x).classList.toggle("active", x===m||(x==="box"&&m==="select"));
    }});
    Plotly.relayout(wid+"_map",{{dragmode:m==="click"?false:m}});
  }};

  function clearSel(){{
    st.selIndices=[];
    document.getElementById(wid+"_selcnt").textContent="—";
    document.getElementById(wid+"_selcnt").classList.remove("has-sel");
    var det=document.getElementById(wid+"_det");
    det.classList.remove("open");
    det.style.display="none";
    renderMap();
  }}
  window[wid+"_clearSel"]=clearSel;

  function onMapClick(evt, leds){{
    if(st.dragMode!=="click") return;
    if(!evt.points||!evt.points.length) return;
    var pt = evt.points[0];
    var ledIdx = pt.customdata[0];
    var clickedLed = leds[ledIdx];
    var stacked = leds.filter(function(l){{ return l.x===clickedLed.x && l.y===clickedLed.y; }});
    st.selIndices = [ledIdx];
    var selCnt = document.getElementById(wid+"_selcnt");
    selCnt.textContent = (stacked.length>1 ? stacked.length+" mesures" : "1 LED")+" — X="+clickedLed.x+" Y="+clickedLed.y;
    selCnt.classList.add("has-sel");
    document.getElementById(wid+"_foot").innerHTML = '<span style="color:#D4AF37">▸</span> '+clickedLed._id+' — X='+clickedLed.x+' Y='+clickedLed.y+(stacked.length>1?' · <b>'+stacked.length+' mesures superposées</b>':"");
    renderCurves(stacked, stacked.length>1);
    renderDetail(stacked, stacked.length>1);
  }}

  function onMapSelect(evt, leds){{
    if(!evt||!evt.points||!evt.points.length) return;
    var idxs = evt.points.map(function(p){{return p.customdata[0];}}).filter(function(i){{return i>=0;}});
    if(!idxs.length) return;
    st.selIndices = idxs;
    var selLeds = idxs.map(function(i){{return leds[i];}});
    var selCnt = document.getElementById(wid+"_selcnt");
    selCnt.textContent = selLeds.length+" LED"+(selLeds.length>1?"s":"")+" sélectionnée"+(selLeds.length>1?"s":"");
    selCnt.classList.add("has-sel");
    document.getElementById(wid+"_foot").innerHTML = '<span style="color:#D4AF37">▸</span> Sélection : '+selLeds.length+' LEDs · région';
    renderCurves(selLeds.slice(0,12), true);
    renderDetail(selLeds.slice(0,20), false);
  }}

  function renderCurves(selLeds, showLegend){{
    st._lastSelLeds = selLeds;
    st._lastShowLegend = showLegend;
    _doRenderCurves(selLeds, showLegend);
  }}

  function _doRenderCurves(selLeds, showLegend){{
    var curveLabels=Object.keys(CURVES);
    curveLabels.forEach(function(lbl,ci){{
      var cfg=CURVES[lbl];
      var traces=selLeds.map(function(r,ri){{
        var cx=r["_cx_"+lbl]||[], cy=r["_cy_"+lbl]||[];
        return {{x:cx,y:cy,type:"scatter",mode:"lines",line:{{color:MULTI[ri%MULTI.length],width:1.5}},name:r._id,showlegend:showLegend&&selLeds.length>1,hoverinfo:"x+y"}};
      }}).filter(function(t){{return t.x.length>0;}});
      var el=document.getElementById(wid+"_cv"+ci);
      if(!el) return;
      if(traces.length) Plotly.newPlot(el, traces, miniLayout(cfg.xlabel, cfg.ylabel, st.miniLogX[ci], st.miniLogY[ci]), PLYCFG);
      else el.innerHTML='<div class="no-data-msg">N/A</div>';
    }});

    if(hasSpec){{
      var spIdx = nCurves;
      var spEl=document.getElementById(wid+"_spec_side");
      if(!spEl) return;
      var spTraces=[];
      selLeds.forEach(function(r,ri){{
        var specs=r._spectra||[], wl=r._wl||[], jVals=r._J_vals||[];
        if(!specs.length||!wl.length) return;
        var nSp=specs.length;
        var baseColor=MULTI[ri%MULTI.length];
        specs.forEach(function(sp,i){{
          var t=nSp>1?i/(nSp-1):0.5;
          var lbl2=(selLeds.length>1?r._id+" ":"")+(jVals[i]!=null?"J="+Number(jVals[i]).toExponential(1):"pt "+(i+1));
          spTraces.push({{x:wl,y:sp,type:"scatter",mode:"lines",line:{{color:baseColor,width:1.0}},opacity:0.3+t*0.7,name:lbl2,hoverinfo:"x+y+name"}});
        }});
      }});
      if(spTraces.length) Plotly.newPlot(spEl, spTraces, miniLayout("λ (nm)", "Intensité", st.miniLogX[spIdx], st.miniLogY[spIdx]), PLYCFG);
      else spEl.innerHTML='<div class="no-data-msg">—</div>';
    }}
  }}

  function renderDetail(selLeds, isMultiPos){{
    var det=document.getElementById(wid+"_det");
    det.classList.add("open");
    det.style.display="block";

    var listEl=document.getElementById(wid+"_ledlist");
    listEl.innerHTML='<div class="wm-led-list-header">'+selLeds.length+' LED'+(selLeds.length>1?'s':'')+' sélectionnée'+(selLeds.length>1?'s':'')+'</div>';
    selLeds.forEach(function(r,ri){{
      var item=document.createElement("div");
      item.className="wm-led-item"+(ri===0?" active":"");
      var kpiVal=KPI_COLS.length?r[KPI_COLS[0]]:"";
      var dv=kpiVal!=null?(" · "+(typeof kpiVal==="number"?kpiVal.toFixed(2):kpiVal)):"";
      item.innerHTML='<div class="wm-led-item-dot" style="background:'+MULTI[ri%MULTI.length]+'"></div>'+'<span class="wm-led-item-name">'+r._id+'</span>'+'<span class="wm-led-item-val">'+(KPI_COLS[0]||"")+dv+'</span>';
      item.onclick=(function(led,idx){{return function(){{
        listEl.querySelectorAll(".wm-led-item").forEach(function(el){{el.classList.remove("active");}});
        item.classList.add("active");
        renderSingleLedDetail(led,idx);
      }};}})(r,ri);
      listEl.appendChild(item);
    }});

    var curveLabels2=Object.keys(CURVES);
    if(curveLabels2.length>0){{
      var lbl0=curveLabels2[0], cfg0=CURVES[lbl0];
      var allTraces=[];
      selLeds.forEach(function(r,ri){{
        var cx=r["_cx_"+lbl0]||[], cy=r["_cy_"+lbl0]||[];
        if(cx.length&&cy.length) allTraces.push({{x:cx,y:cy,type:"scatter",mode:"lines",line:{{color:MULTI[ri%MULTI.length],width:1.5}},name:r._id,hoverinfo:"x+y"}});
      }});
      document.getElementById(wid+"_det_curves_title").textContent = selLeds.length===1?selLeds[0]._id:selLeds.length+" LEDs";
      Plotly.newPlot(wid+"_det_curves", allTraces, miniLayout((cfg0||{{}}).xlabel||"X",(cfg0||{{}}).ylabel||"Y",st.detLogX,st.detLogY), PLYCFG);
    }} else {{
      document.getElementById(wid+"_det_curves").innerHTML='<div class="no-data-msg">Pas de courbes configurées</div>';
    }}

    renderSpectra(selLeds[0]);

    var aggEl=document.getElementById(wid+"_agg_kpis");
    var aggGrid=document.getElementById(wid+"_agg_grid");
    var aggTitle=document.getElementById(wid+"_agg_title");
    if(selLeds.length>1){{
      aggEl.style.display="block";
      aggTitle.textContent="KPIs agrégés · n="+selLeds.length;
      aggGrid.innerHTML="";
      KPI_COLS.forEach(function(col){{
        var vals=selLeds.map(function(r){{return parseFloat(r[col]);}}).filter(function(v){{return !isNaN(v);}});
        if(!vals.length) return;
        var mean=vals.reduce(function(a,b){{return a+b;}},0)/vals.length;
        var std=Math.sqrt(vals.reduce(function(a,v){{return a+(v-mean)*(v-mean);}},0)/vals.length);
        var card=document.createElement("div");
        card.className="wm-kpi-agg";
        card.innerHTML='<div class="wm-kpi-agg-label">'+col+'</div>'+'<div class="wm-kpi-agg-val">'+mean.toFixed(2)+'</div>'+'<div class="wm-kpi-agg-std">± '+std.toFixed(2)+'  (n='+vals.length+')</div>';
        aggGrid.appendChild(card);
      }});
    }} else {{
      aggEl.style.display="none";
    }}
  }}

  function renderSingleLedDetail(r,ri){{
    var curveLabels2=Object.keys(CURVES);
    if(!curveLabels2.length) return;
    var lbl0=curveLabels2[0], cfg0=CURVES[lbl0];
    var cx=r["_cx_"+lbl0]||[], cy=r["_cy_"+lbl0]||[];
    document.getElementById(wid+"_det_curves_title").textContent=r._id;
    Plotly.newPlot(wid+"_det_curves", [{{x:cx,y:cy,type:"scatter",mode:"lines+markers",line:{{color:MULTI[ri%MULTI.length],width:1.8}},marker:{{size:3}},name:r._id}}], miniLayout((cfg0||{{}}).xlabel||"X",(cfg0||{{}}).ylabel||"Y",st.detLogX,st.detLogY), PLYCFG);
    renderSpectra(r);
  }}

  function _setTogBtn(id, isLog){{
    var btn=document.getElementById(id);
    if(!btn) return;
    btn.classList && btn.classList.toggle && btn.classList.toggle("wm-tog-on", isLog);
    var prefix=btn.textContent.slice(0,2);
    btn.textContent=prefix+(isLog?"Log":"Lin");
    btn.style.background = isLog ? "rgba(10,36,99,.1)" : "#fff";
    btn.style.color = isLog ? "#0A2463" : "#4A5580";
    btn.style.borderColor = isLog ? "rgba(10,36,99,.4)" : "rgba(10,36,99,.2)";
    btn.style.fontWeight = isLog ? "600" : "500";
  }}

  window[wid+"_toggleDetAxis"]=function(axis){{
    if(axis==="x"){{
      st.detLogX=!st.detLogX;
      _setTogBtn(wid+"_det_logx", st.detLogX);
      Plotly.relayout(wid+"_det_curves", {{"xaxis.type": st.detLogX?"log":"linear"}});
    }}else{{
      st.detLogY=!st.detLogY;
      _setTogBtn(wid+"_det_logy", st.detLogY);
      Plotly.relayout(wid+"_det_curves", {{"yaxis.type": st.detLogY?"log":"linear"}});
    }}
  }};

  window[wid+"_toggleDetSpecAxis"]=function(axis){{
    if(axis==="x"){{
      st.detSpecLogX=!st.detSpecLogX;
      _setTogBtn(wid+"_det_spec_lx", st.detSpecLogX);
      Plotly.relayout(wid+"_det_spec", {{"xaxis.type": st.detSpecLogX?"log":"linear"}});
    }}else{{
      st.detSpecLogY=!st.detSpecLogY;
      _setTogBtn(wid+"_det_spec_ly", st.detSpecLogY);
      Plotly.relayout(wid+"_det_spec", {{"yaxis.type": st.detSpecLogY?"log":"linear"}});
    }}
  }};

  window[wid+"_toggleMiniAxis"]=function(ci, axis){{
    var isSpec=(ci==="spec");
    var idx = isSpec ? nCurves : ci;
    var elId = isSpec ? wid+"_spec_side" : wid+"_cv"+ci;
    var btnId = isSpec ? wid+"_spec_side_l"+axis : wid+"_cv"+ci+"_l"+axis;

    if(axis==="x"){{
      st.miniLogX[idx]=!st.miniLogX[idx];
      _setTogBtn(btnId, st.miniLogX[idx]);
      Plotly.relayout(elId, {{"xaxis.type": st.miniLogX[idx]?"log":"linear"}});
    }}else{{
      st.miniLogY[idx]=!st.miniLogY[idx];
      _setTogBtn(btnId, st.miniLogY[idx]);
      Plotly.relayout(elId, {{"yaxis.type": st.miniLogY[idx]?"log":"linear"}});
    }}
  }};

  function renderSpectra(r){{
    var specs=r._spectra||[], wl=r._wl||[], jVals=r._J_vals||[];
    var slider=document.getElementById(wid+"_spec_slider");
    var specLabel=document.getElementById(wid+"_spec_label");
    var specEl=document.getElementById(wid+"_det_spec");
    window[wid+"_onSpecSlider"]=function(val){{
      var i=parseInt(val);
      if(!specs[i]||!wl.length) return;
      var jLbl=jVals[i]!=null?"J = "+Number(jVals[i]).toExponential(2)+" A/cm²":"pt "+(i+1);
      specLabel.textContent=jLbl;
      Plotly.react(specEl, [{{x:wl,y:specs[i],type:"scatter",mode:"lines",line:{{color:"#8B5CF6",width:1.8}},fill:"tozeroy",fillcolor:"rgba(139,92,246,.1)",showlegend:false}}], miniLayout("λ (nm)","Intensité",st.detSpecLogX,st.detSpecLogY), PLYCFG);
    }};
    if(specs.length&&wl.length){{
      slider.max=specs.length-1;
      slider.value=specs.length-1;
      window[wid+"_onSpecSlider"](specs.length-1);
    }} else {{
      specEl.innerHTML='<div class="no-data-msg">—</div>';
      specLabel.textContent="";
    }}
  }}

  document.addEventListener("keydown",function(e){{
    if(e.key==="ArrowLeft"||e.key==="ArrowRight"){{
      var wrap=document.getElementById(wid+"_wrap");
      if(!wrap||!wrap.matches(":hover")) return;
      e.preventDefault();
      goToWafer(carouselIdx+(e.key==="ArrowRight"?1:-1));
    }}
  }});

  goToWafer(0);
}})();
</script>
"""

    def _curve_divs(self, wid: str, n_curves: int) -> str:
        """Génère les div pour les mini-courbes latérales avec toggles log/lin."""
        tog_style = (
            "font-family:'IBM Plex Mono',monospace;font-size:7px;font-weight:500;"
            "border:1px solid rgba(10,36,99,.2);border-radius:3px;"
            "padding:1px 5px;cursor:pointer;background:#fff;color:#4A5580;"
            "transition:all .15s;letter-spacing:.04em;line-height:1.4;"
        )
        bar_style = (
            "display:flex;align-items:center;gap:5px;padding:3px 8px;"
            "background:var(--slate-50);border-bottom:1px solid var(--border);"
            "flex-shrink:0;min-height:22px;"
        )
        label_style = (
            "font-family:'IBM Plex Mono',monospace;font-size:8px;font-weight:600;"
            "color:var(--navy);letter-spacing:.08em;text-transform:uppercase;"
        )

        curve_labels = list(self.curve_cols.keys())
        divs = ""
        for i in range(n_curves):
            lbl = curve_labels[i] if i < len(curve_labels) else f"Courbe {i}"
            divs += (
                f'<div style="display:flex;flex-direction:column;min-height:0;">'
                f'<div style="{bar_style}">'
                f'<span style="{label_style}">{lbl}</span>'
                f'<span style="display:flex;gap:3px;margin-left:auto;">'
                f'<button id="{wid}_cv{i}_lx" style="{tog_style}"'
                f' onclick="window[\'{wid}_toggleMiniAxis\']({i},\'x\')">X:Lin</button>'
                f'<button id="{wid}_cv{i}_ly" style="{tog_style}"'
                f' onclick="window[\'{wid}_toggleMiniAxis\']({i},\'y\')">Y:Lin</button>'
                f'</span></div>'
                f'<div id="{wid}_cv{i}" style="flex:1;min-height:0;"></div>'
                f'</div>'
            )

        if self.spectra_col:
            divs += (
                f'<div style="display:flex;flex-direction:column;min-height:0;">'
                f'<div style="{bar_style}">'
                f'<span style="{label_style}">Spectres PL</span>'
                f'<span style="display:flex;gap:3px;margin-left:auto;">'
                f'<button id="{wid}_spec_side_lx" style="{tog_style}"'
                f' onclick="window[\'{wid}_toggleMiniAxis\'](\'spec\',\'x\')">X:Lin</button>'
                f'<button id="{wid}_spec_side_ly" style="{tog_style}"'
                f' onclick="window[\'{wid}_toggleMiniAxis\'](\'spec\',\'y\')">Y:Lin</button>'
                f'</span></div>'
                f'<div id="{wid}_spec_side" style="flex:1;min-height:0;"></div>'
                f'</div>'
            )
        return divs
