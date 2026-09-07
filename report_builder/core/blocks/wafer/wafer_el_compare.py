from __future__ import annotations
import json
import html as _h
import numpy as np
import pandas as pd
from ..._helpers import Block, _safe_json, _col_analysis, _is_vector_col
from ..data.data_mixin import DataArg, _normalize_data


class WaferELCompareBlock(Block):
    """
    Wafermap cliquable ↔ EL pattern ↔ spectre.

    Clic sur une position (X, Y) de la wafermap : affiche l'image EL pattern
    associée à cette position (carrousel si plusieurs images) et le spectre
    associé (slider si plusieurs mesures J). Ctrl+clic (ou Cmd+clic) ajoute/
    retire une position à une sélection de comparaison cumulative : les EL
    patterns sélectionnés s'affichent côte à côte et les spectres se
    superposent sur un même graphe (couleur par position, légende). La
    sélection persiste en changeant de wafer via le carrousel.

    Deux sources distinctes, jointes par (wafer, X, Y) au clic :
      - data     : dataset "spectres" (Spectra, Wavelength, colonnes scalaires)
      - el_data  : dataset "images EL pattern" (full_path, image_number, type)

    Les deux df sont toujours résolus localement (jamais via le DataStore),
    car ce sont typiquement des DataFrames construits à la volée à partir
    de dossiers d'images (voir found_folder_EL_pattern / get_all_image_from_folder).

    Filtres
    -------
    - filter_cols : colonnes du dataset "spectres" utilisables en filtre sur la
      wafermap (ex. Optical_Sensor, Test_Date, max_EQE_reached), même mécanique
      que le toolbar "Filtre" de WaferMaps.
    - Type d'image EL (boutons, comme dans Imageviewer) + filtre LED (boutons)
      + verrouillage du numéro d'image (image_number) : une fois choisis, ils
      restent actifs en changeant de position/wafer.
    """

    needs_plotly = True

    _COLORS = ["#6366f1", "#f59e0b", "#10b981", "#ef4444", "#3b82f6",
               "#ec4899", "#84cc16", "#f97316", "#14b8a6", "#a855f7"]

    def __init__(
        self,
        data: DataArg,
        el_data: DataArg,
        x_col: str = "X",
        y_col: str = "Y",
        wafer_col: str = "wafername",
        id_col: str = "",
        spectra_col: str = "Spectra",
        wavelength_col: str = "Wavelength",
        filter_cols: list[str] | None = None,
        el_x_col: str = "",
        el_y_col: str = "",
        el_wafer_col: str = "",
        el_led_col: str = "led_name",
        image_col: str = "full_path",
        imgnum_col: str = "image_number",
        type_col: str = "type",
        color_col: str = "",
        colorscale: str = "Viridis",
        map_height: int = 300,
        content_height: int = 560,
        num: str = "01",
        title: str = "EL Pattern ↔ Spectre",
        subtitle: str = "clic = aperçu · mode comparaison = superpose les positions cliquées",
    ):
        self._data_arg = _normalize_data(data)
        self._el_data_arg = _normalize_data(el_data)
        self.x_col = x_col
        self.y_col = y_col
        self.wafer_col = wafer_col
        self.id_col = id_col
        self.spectra_col = spectra_col
        self.wavelength_col = wavelength_col
        self._filter_cols_arg = filter_cols
        self.el_x_col = el_x_col or x_col
        self.el_y_col = el_y_col or y_col
        self.el_wafer_col = el_wafer_col or wafer_col
        self.el_led_col = el_led_col
        self.image_col = image_col
        self.imgnum_col = imgnum_col
        self.type_col = type_col
        self.color_col = color_col
        self.colorscale = colorscale
        self.map_height = map_height
        self.content_height = content_height
        self.num = num
        self.title = title
        self.subtitle = subtitle
        self._id = f"welc_{id(self)}"

    # ── Résolution données (deux sources, toujours locales) ─────────────────

    def resolve_df(self, store=None) -> pd.DataFrame:
        return self._resolve(self._data_arg, store)

    def resolve_el_df(self, store=None) -> pd.DataFrame:
        return self._resolve(self._el_data_arg, store)

    @staticmethod
    def _resolve(data, store):
        if isinstance(data, pd.DataFrame):
            return data
        if store is None:
            raise RuntimeError(
                f"WaferELCompareBlock references data key {data!r} but no DataStore was provided."
            )
        return store.resolve(data)

    def _resolve_filter_cols(self, df: pd.DataFrame) -> None:
        if self._filter_cols_arg is not None:
            self.filter_cols = self._filter_cols_arg
            return
        cols = _col_analysis(df)
        self.filter_cols = cols["scalar_cat"][:6]

    # ── Sérialisation ─────────────────────────────────────────────────────

    @staticmethod
    def _pos_key(x, y) -> str:
        def _n(v):
            try:
                f = float(v)
                return str(int(f)) if f.is_integer() else str(f)
            except (TypeError, ValueError):
                return str(v)
        return f"{_n(x)},{_n(y)}"

    def _build_wafer_json(self, df: pd.DataFrame) -> str:
        """WDATA[wafer] = [{x, y, _id, _pos, color, <filter_cols>, _spectra:[[...]], _wl:[...]}]"""
        if not hasattr(self, "filter_cols"):
            self._resolve_filter_cols(df)
        scalar_filter_cols = [c for c in self.filter_cols if c in df.columns and not _is_vector_col(df[c])]

        out: dict = {}
        for wafer, grp in df.groupby(self.wafer_col):
            leds = []
            for _, row in grp.iterrows():
                x = row[self.x_col] if self.x_col in row.index else 0
                y = row[self.y_col] if self.y_col in row.index else 0
                rec = {
                    "x": _safe_json(x),
                    "y": _safe_json(y),
                    "_pos": self._pos_key(x, y),
                    "_id": str(row[self.id_col]) if self.id_col and self.id_col in row.index else str(len(leds)),
                }
                if self.color_col and self.color_col in row.index:
                    try:
                        rec["color"] = _safe_json(row[self.color_col])
                    except Exception:
                        pass

                for c in scalar_filter_cols:
                    try:
                        rec[c] = _safe_json(row[c])
                    except Exception:
                        pass

                if self.spectra_col and self.spectra_col in row.index:
                    sp = row[self.spectra_col]
                    if isinstance(sp, (list, np.ndarray)) and len(sp) > 0:
                        def _ds(s, target=150):
                            if not isinstance(s, (list, np.ndarray)) or len(s) <= target:
                                return [_safe_json(v) for v in s]
                            step = max(1, len(s) // target)
                            return [_safe_json(s[i]) for i in range(0, len(s), step)]
                        rec["_spectra"] = [_ds(sp[i]) for i in range(len(sp)) if isinstance(sp[i], (list, np.ndarray))]

                if self.wavelength_col and self.wavelength_col in row.index:
                    wl = row[self.wavelength_col]
                    if isinstance(wl, (list, np.ndarray)):
                        step = max(1, len(wl) // 150)
                        rec["_wl"] = [_safe_json(wl[i]) for i in range(0, len(wl), step)]

                leds.append(rec)
            out[str(wafer)] = leds
        return json.dumps(out)

    def _build_el_json(self, df: pd.DataFrame) -> str:
        """ELDATA[wafer][pos_key] = [{src, label, led, imgnum, type}]"""
        out: dict = {}
        for wafer, grp in df.groupby(self.el_wafer_col):
            positions: dict = {}
            for _, row in grp.iterrows():
                if self.el_x_col not in row.index or self.el_y_col not in row.index:
                    continue
                pos = self._pos_key(row[self.el_x_col], row[self.el_y_col])
                img_path = row.get(self.image_col, "")
                src = str(img_path).replace("\\", "/") if img_path else ""
                if not src:
                    continue
                led = str(row.get(self.el_led_col, "")) if self.el_led_col else ""
                imgnum = row.get(self.imgnum_col, None)
                typ = str(row.get(self.type_col, "")) if self.type_col else ""
                positions.setdefault(pos, []).append({
                    "src": src,
                    "label": led or src.split("/")[-1],
                    "led": led,
                    "imgnum": str(imgnum) if imgnum is not None else "",
                    "type": typ,
                })
            out[str(wafer)] = positions
        return json.dumps(out)

    def _all_el_types(self, df: pd.DataFrame) -> list[str]:
        if not self.type_col or self.type_col not in df.columns:
            return []
        return sorted(df[self.type_col].dropna().astype(str).unique().tolist())

    # ── Render ────────────────────────────────────────────────────────────

    def render(self, store=None) -> str:
        wid = self._id
        df = self.resolve_df(store)
        el_df = self.resolve_el_df(store)

        self._resolve_filter_cols(df)
        wafer_json = self._build_wafer_json(df)
        el_json = self._build_el_json(el_df)
        el_types_json = json.dumps(self._all_el_types(el_df))
        filter_cols_json = json.dumps(self.filter_cols)
        colors_json = json.dumps(self._COLORS)
        has_color = "true" if self.color_col else "false"
        map_h = self.map_height
        content_h = self.content_height
        el_h = round(content_h * 0.55)
        x_esc = _h.escape(self.x_col)
        y_esc = _h.escape(self.y_col)

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
      <button id="{wid}_clearcmp" onclick="window['{wid}_clearSel']()"
        style="font-size:10px;padding:5px 10px;border:0.5px solid rgba(10,36,99,.2);border-radius:6px;background:transparent;cursor:pointer;color:#888;">
        ✕ vider la comparaison
      </button>
    </div>

    <!-- Filtre spectre (positions affichées sur la wafermap) -->
    <div id="{wid}_map_toolbar" style="display:flex;align-items:center;gap:6px;flex-wrap:wrap;margin-bottom:8px;">
      <span style="font-family:'IBM Plex Mono',monospace;font-size:9px;color:rgba(10,36,99,.5);">Filtres</span>
      <div id="{wid}_filters" style="display:flex;align-items:center;gap:6px;flex-wrap:wrap;"></div>
      <button id="{wid}_fclear" onclick="window['{wid}_clearFilters']()"
        style="font-size:9px;padding:3px 7px;border:0.5px solid rgba(10,36,99,.2);border-radius:4px;background:transparent;cursor:pointer;color:#888;">
        ✕ effacer
      </button>
      <span id="{wid}_map_cnt" style="margin-left:auto;font-size:9px;color:#8896BB;font-family:'IBM Plex Mono',monospace;"></span>
    </div>

    <div style="display:grid;grid-template-columns:0.55fr 1.65fr;gap:14px;">

      <!-- Wafermap (réduite) -->
      <div>
        <div style="border:0.5px solid rgba(10,36,99,.2);border-radius:8px;overflow:hidden;background:#F8F9FD;">
          <div id="{wid}_map" style="height:{map_h}px;"></div>
          <div id="{wid}_foot" style="padding:6px 10px;font-family:'IBM Plex Mono',monospace;font-size:10px;color:#4A5580;border-top:0.5px solid rgba(10,36,99,.1);">
            Cliquer sur une position
          </div>
        </div>
        <div id="{wid}_tags" style="display:flex;gap:6px;flex-wrap:wrap;margin-top:8px;"></div>
      </div>

      <!-- EL pattern + spectre (agrandis) -->
      <div style="display:flex;flex-direction:column;gap:10px;min-height:0;height:{content_h}px;">

        <div style="display:flex;flex-direction:column;border:0.5px solid rgba(10,36,99,.2);border-radius:8px;overflow:hidden;background:#fff;height:{el_h}px;">
          <div style="padding:4px 10px;border-bottom:0.5px solid rgba(10,36,99,.1);display:flex;align-items:center;gap:8px;flex-wrap:wrap;flex-shrink:0;">
            <span style="font-family:var(--fd,'Syne',sans-serif);font-weight:700;font-size:9px;color:#0A2463;text-transform:uppercase;letter-spacing:.06em;">EL Pattern</span>
            <div id="{wid}_el_type_btns" style="display:flex;border:0.5px solid rgba(10,36,99,.2);border-radius:4px;overflow:hidden;"></div>
            <span id="{wid}_el_label" style="font-family:'IBM Plex Mono',monospace;font-size:9px;color:#8896BB;flex:1;min-width:60px;"></span>
            <div id="{wid}_el_nav" style="display:none;align-items:center;gap:4px;">
              <button onclick="window['{wid}_elNav'](-1)" style="width:20px;height:20px;border:0.5px solid rgba(10,36,99,.2);border-radius:3px;background:transparent;cursor:pointer;font-size:11px;color:#0A2463;">&#8249;</button>
              <span id="{wid}_el_cnt" style="font-size:9px;color:#4A5580;font-family:'IBM Plex Mono',monospace;"></span>
              <button onclick="window['{wid}_elNav'](1)" style="width:20px;height:20px;border:0.5px solid rgba(10,36,99,.2);border-radius:3px;background:transparent;cursor:pointer;font-size:11px;color:#0A2463;">&#8250;</button>
            </div>
          </div>
          <div id="{wid}_el_led_row" style="display:none;padding:3px 10px;align-items:center;gap:6px;border-bottom:0.5px solid rgba(10,36,99,.08);flex-shrink:0;">
            <span style="font-family:'IBM Plex Mono',monospace;font-size:8px;color:rgba(10,36,99,.5);white-space:nowrap;">LED</span>
            <div id="{wid}_el_led_btns" style="display:flex;gap:3px;flex-wrap:wrap;"></div>
          </div>
          <div id="{wid}_el_imgnum_btns" style="display:none;padding:3px 10px;gap:3px;flex-wrap:wrap;border-bottom:0.5px solid rgba(10,36,99,.08);background:rgba(10,36,99,.02);flex-shrink:0;"></div>

          <!-- Vue simple (0 ou 1 position sélectionnée) -->
          <div id="{wid}_el_single" style="flex:1;position:relative;display:flex;align-items:center;justify-content:center;background:#0A0E1A;min-height:0;">
            <img id="{wid}_el_img" src="" alt="" style="display:none;max-width:96%;max-height:96%;object-fit:contain;border-radius:4px;">
            <span id="{wid}_el_ph" style="font-family:'IBM Plex Mono',monospace;font-size:11px;color:rgba(255,255,255,.35);">Aucune image EL à cette position</span>
          </div>

          <!-- Vue comparaison (2+ positions, côte à côte) -->
          <div id="{wid}_el_compare_grid" style="display:none;flex:1;min-height:0;overflow:auto;gap:6px;padding:8px;grid-template-columns:repeat(auto-fit,minmax(160px,1fr));background:#0A0E1A;"></div>
        </div>

        <div style="display:flex;flex-direction:column;border:0.5px solid rgba(10,36,99,.2);border-radius:8px;overflow:hidden;background:#fff;flex:1;min-height:0;">
          <div style="padding:4px 10px;border-bottom:0.5px solid rgba(10,36,99,.1);display:flex;align-items:center;gap:8px;flex-shrink:0;">
            <span style="font-family:var(--fd,'Syne',sans-serif);font-weight:700;font-size:9px;color:#0A2463;text-transform:uppercase;letter-spacing:.06em;">Spectre</span>
            <span id="{wid}_spec_label" style="font-family:'IBM Plex Mono',monospace;font-size:9px;color:#D4AF37;flex:1;"></span>
          </div>
          <div style="padding:4px 10px;flex-shrink:0;border-bottom:0.5px solid rgba(10,36,99,.08);display:flex;align-items:center;gap:8px;">
            <span style="font-family:'IBM Plex Mono',monospace;font-size:8px;color:#8896BB;">J</span>
            <input type="range" id="{wid}_spec_slider" min="0" max="0" value="0" style="flex:1;" oninput="window['{wid}_onSpecSlider'](this.value)">
          </div>
          <div id="{wid}_det_spec" style="flex:1;min-height:0;"></div>
        </div>

      </div>
    </div>
  </div>
</div>

<script>
(function(){{
  var WDATA = {wafer_json};
  var ELDATA = {el_json};
  var EL_TYPES = {el_types_json};
  var FILTER_COLS = {filter_cols_json};
  var COLORS = {colors_json};
  var wid = "{wid}";
  var HAS_COLOR = {has_color};
  var X_ESC = "{x_esc}";
  var Y_ESC = "{y_esc}";

  var PLYCFG = {{responsive:true,displaylogo:false,modeBarButtonsToRemove:["autoScale2d","toggleSpikelines","sendDataToCloud"]}};
  var GSTYLE = {{gridcolor:"#E4E8F4",linecolor:"#E4E8F4",zerolinecolor:"#E4E8F4"}};

  var waferNames = Object.keys(WDATA).sort();
  var carouselIdx = 0;
  var sel = [];   // [{{k, w, led}}, ...] — sélection (1 = aperçu simple, 2+ = comparaison)
  var curElIdx = 0;   // index image courant, vue simple uniquement

  var st = {{
    filters: {{}},         // cumulés : {{col: val, ...}} — combinés en ET
    elType: "all",       // type EL verrouillé — persiste d'une position à l'autre
    elLed: "all",        // filtre LED (comme Imageviewer) — recalculé à chaque wafer
    elImgNum: "",         // numéro d'image verrouillé — persiste d'une position à l'autre
    compareMode: false,  // toggle : OFF = clic remplace la sélection, ON = clic ajoute/retire (superpose)
  }};

  function currentLeds(){{ return WDATA[waferNames[carouselIdx]]||[]; }}
  function currentEl(){{ return ELDATA[waferNames[carouselIdx]]||{{}}; }}
  function keyOf(w, led){{ return w+"::"+led._id; }}
  function elImagesFor(c){{ var els = ELDATA[c.w]||{{}}; return els[c.led._pos] || []; }}

  function matchFilter(v, filterVal){{
    if(v==null) return false;
    var parts = filterVal.match(/^(>=|<=|>|<|=)[ ]*(.+)/);
    var op = parts?parts[1]:"=";
    var raw = parts?parts[2].trim():filterVal.trim();
    var val2 = Number(raw);
    var isNum = raw!==""&&!isNaN(val2)&&isFinite(val2);
    if(isNum){{
      var vn = Number(v);
      if(isNaN(vn)) return false;
      if(op===">=") return vn>=val2;
      if(op==="<=") return vn<=val2;
      if(op===">")  return vn>val2;
      if(op==="<")  return vn<val2;
      return vn===val2;
    }}
    var vs = String(v).toLowerCase(), rs = raw.toLowerCase();
    if(op===">="||op==="") return vs>=rs;
    if(op==="<=") return vs<=rs;
    if(op===">")  return vs>rs;
    if(op==="<")  return vs<rs;
    return vs===rs;
  }}

  /* ── Filtres spectre cumulés (colonnes scalaires, comme WaferMaps) ── */
  function filteredLeds(){{
    var leds = currentLeds();
    var activeCols = Object.keys(st.filters).filter(function(c){{ return st.filters[c]!==""; }});
    if(!activeCols.length) return leds;
    return leds.filter(function(l){{
      return activeCols.every(function(c){{ return matchFilter(l[c], st.filters[c]); }});
    }});
  }}

  /* valeurs dispo pour une colonne, en tenant compte des AUTRES filtres déjà actifs (cascade) */
  function filterValues(col){{
    var others = Object.keys(st.filters).filter(function(c){{ return c!==col && st.filters[c]!==""; }});
    var base = currentLeds().filter(function(l){{
      return others.every(function(c){{ return matchFilter(l[c], st.filters[c]); }});
    }});
    var seen = {{}};
    base.forEach(function(l){{ if(l[col]!=null) seen[l[col]]=true; }});
    return Object.keys(seen).sort();
  }}

  function buildFilterToolbar(){{
    var container = document.getElementById(wid+"_filters");
    container.innerHTML = "";
    FILTER_COLS.forEach(function(col){{
      var wrap = document.createElement("div");
      wrap.style.cssText = "display:flex;align-items:center;gap:3px;";
      var lbl = document.createElement("span");
      lbl.textContent = col;
      lbl.style.cssText = "font-family:'IBM Plex Mono',monospace;font-size:8px;color:rgba(10,36,99,.45);white-space:nowrap;";
      var sel_ = document.createElement("select");
      sel_.dataset.col = col;
      sel_.style.cssText = "font-size:10px;padding:3px 6px;border:0.5px solid "+
        (st.filters[col]?"#0A2463":"rgba(10,36,99,.2)")+";border-radius:4px;background:#fff;color:#0A2463;max-width:130px;";
      var opts = ['<option value="">Tous</option>'].concat(
        filterValues(col).map(function(v){{
          var s = (st.filters[col]===String(v)) ? " selected" : "";
          return '<option value="'+v+'"'+s+'>'+v+'</option>';
        }})
      );
      sel_.innerHTML = opts.join('');
      sel_.addEventListener("change", function(){{
        if(this.value) st.filters[col] = this.value;
        else delete st.filters[col];
        buildFilterToolbar();
        renderMap();
      }});
      wrap.appendChild(lbl);
      wrap.appendChild(sel_);
      container.appendChild(wrap);
    }});
  }}

  window[wid+"_clearFilters"] = function(){{
    st.filters = {{}};
    buildFilterToolbar();
    renderMap();
  }};

  /* ── Filtre type EL (verrouillé entre positions) ── */
  function buildElTypeButtons(){{
    var container = document.getElementById(wid+"_el_type_btns");
    container.innerHTML = "";
    var types = ["all"].concat(EL_TYPES);
    types.forEach(function(t,i){{
      var btn = document.createElement("button");
      btn.textContent = t==="all" ? "Tous" : t;
      btn.dataset.type = t;
      btn.style.cssText =
        "height:20px;padding:0 7px;border:none;cursor:pointer;"+
        "font-family:'IBM Plex Mono',monospace;font-size:9px;"+
        (i>0?"border-left:0.5px solid rgba(10,36,99,.15);":"")+
        (t===st.elType
          ? "background:rgba(10,36,99,0.1);color:#0A2463;font-weight:600;"
          : "background:transparent;color:#888;");
      btn.addEventListener("click", function(){{
        st.elType = t;
        refreshElTypeButtons();
        refreshView();
      }});
      container.appendChild(btn);
    }});
  }}
  function refreshElTypeButtons(){{
    document.getElementById(wid+"_el_type_btns").querySelectorAll("button").forEach(function(btn){{
      var active = btn.dataset.type===st.elType;
      btn.style.background = active ? "rgba(10,36,99,0.1)" : "transparent";
      btn.style.color = active ? "#0A2463" : "#888";
      btn.style.fontWeight = active ? "600" : "normal";
    }});
  }}
  buildElTypeButtons();

  /* ── Filtre LED (boutons, comme Imageviewer) — recalculé par wafer ── */
  function currentElLeds(){{
    var els = currentEl();
    var seen = {{}};
    Object.keys(els).forEach(function(pos){{
      els[pos].forEach(function(img){{ if(img.led) seen[img.led]=true; }});
    }});
    return Object.keys(seen).sort();
  }}

  function buildElLedButtons(){{
    var row = document.getElementById(wid+"_el_led_row");
    var container = document.getElementById(wid+"_el_led_btns");
    var leds = currentElLeds();
    container.innerHTML = "";
    if(!leds.length){{ row.style.display = "none"; return; }}
    row.style.display = "flex";
    if(!leds.includes(st.elLed)) st.elLed = "all";
    ["all"].concat(leds).forEach(function(led){{
      var btn = document.createElement("button");
      btn.textContent = led==="all" ? "Tous" : led;
      btn.dataset.led = led;
      var active = led===st.elLed;
      btn.style.cssText =
        "height:18px;padding:0 7px;border-radius:3px;cursor:pointer;"+
        "font-family:'IBM Plex Mono',monospace;font-size:8px;"+
        "border:0.5px solid "+(active?"#0A2463":"rgba(10,36,99,.25)")+";"+
        "background:"+(active?"#0A2463":"transparent")+";"+
        "color:"+(active?"#fff":"rgba(10,36,99,.6)")+";";
      btn.addEventListener("click", function(){{
        st.elLed = led;
        buildElLedButtons();
        refreshView();
      }});
      container.appendChild(btn);
    }});
  }}

  function filterElImages(images){{
    var out = images;
    if(st.elType!=="all") out = out.filter(function(img){{ return img.type===st.elType; }});
    if(st.elLed!=="all") out = out.filter(function(img){{ return img.led===st.elLed; }});
    return out;
  }}

  /* Choisit, pour une entrée sélectionnée, l'image respectant le type/LED
     filtrés et si possible le numéro d'image verrouillé. */
  function pickElImages(c){{
    return filterElImages(elImagesFor(c));
  }}

  function buildElImgNumButtons(unionImages){{
    var container = document.getElementById(wid+"_el_imgnum_btns");
    container.innerHTML = "";
    var seen = {{}};
    unionImages.forEach(function(img,i){{
      var num = img.imgnum || String(i+1);
      if(!seen[num]) seen[num]=true;
    }});
    var nums = Object.keys(seen);
    if(nums.length<=1){{ container.style.display="none"; return; }}
    container.style.display = "flex";
    nums.forEach(function(num){{
      var btn = document.createElement("button");
      btn.textContent = num;
      btn.dataset.imgnum = num;
      var active = num===st.elImgNum;
      btn.style.cssText =
        "height:18px;min-width:18px;padding:0 5px;border-radius:3px;cursor:pointer;"+
        "font-family:'IBM Plex Mono',monospace;font-size:8px;"+
        "border:0.5px solid "+(active?"#0A2463":"rgba(10,36,99,.25)")+";"+
        "background:"+(active?"#0A2463":"transparent")+";"+
        "color:"+(active?"#fff":"rgba(10,36,99,.6)")+";";
      btn.addEventListener("click", function(){{
        st.elImgNum = num;
        curElIdx = 0;
        refreshView();
      }});
      container.appendChild(btn);
    }});
  }}

  function miniLayout(xt,yt){{
    return {{
      paper_bgcolor:"rgba(0,0,0,0)",plot_bgcolor:"#F8F9FD",
      font:{{family:"IBM Plex Mono,monospace",color:"#4A5580",size:9}},
      margin:{{t:4,r:10,b:28,l:38}},
      showlegend:false,
      xaxis:Object.assign({{}},GSTYLE,{{title:{{text:xt,font:{{size:9,color:"#0A2463"}},standoff:3}},tickfont:{{size:8}}}}),
      yaxis:Object.assign({{}},GSTYLE,{{title:{{text:yt,font:{{size:9,color:"#0A2463"}},standoff:3}},tickfont:{{size:8}}}}),
    }};
  }}

  function goToWafer(idx){{
    carouselIdx = Math.max(0, Math.min(idx, waferNames.length-1));
    document.getElementById(wid+"_wafer_name").textContent = waferNames[carouselIdx]||"—";
    document.getElementById(wid+"_wafer_counter").textContent = waferNames.length?((carouselIdx+1)+" / "+waferNames.length):"";
    document.getElementById(wid+"_prev").disabled = carouselIdx===0;
    document.getElementById(wid+"_next").disabled = carouselIdx===waferNames.length-1;
    buildFilterToolbar();
    buildElLedButtons();
    renderMap();
    /* la sélection (sel) persiste au changement de wafer — pas de clearSelection() ici */
  }}
  window[wid+"_carouselNav"] = function(dir){{ goToWafer(carouselIdx+dir); }};

  /* Plotly conserve son état (_fullLayout, etc) directement sur le noeud DOM.
     Un innerHTML="" brut sur un div qu'il gère laisse cet état orphelin et fait
     planter le Plotly.react suivant (spectre qui "disparaît" en changeant de wafer).
     On purge proprement avant de vider/réutiliser un tel div. */
  function purgeEl(id){{
    var el = document.getElementById(id);
    if(el && el.data) {{ try {{ Plotly.purge(el); }} catch(e){{}} }}
    return el;
  }}

  window[wid+"_clearSel"] = function(){{
    sel = []; curElIdx = 0;
    refreshView();
  }};

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
    var els = currentEl();
    var w = waferNames[carouselIdx];

    var selColorOf = {{}};
    sel.forEach(function(c,ci){{ selColorOf[c.k] = COLORS[ci%COLORS.length]; }});

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

    var customdata = leds.map(function(l,i){{ return [i, l._id, els[l._pos]?els[l._pos].length:0]; }});
    var tpl = "<b>%{{customdata[1]}}</b><br>X: %{{x}} · Y: %{{y}}<br>%{{customdata[2]}} image(s) EL<br><extra></extra>";

    /* Une seule trace, toujours : un 2e trace overlay pour la sélection rendait
       le clic peu fiable (hit-testing ambigu entre les deux traces) et masquait
       parfois les points. La sélection est représentée par le contour + la
       taille du marker (arrays par-point), jamais par une trace séparée. */
    var lineWidths = leds.map(function(l){{ return selColorOf[keyOf(w,l)] ? 2.5 : 0; }});
    var lineColors = leds.map(function(l){{ return selColorOf[keyOf(w,l)] || "rgba(0,0,0,0)"; }});
    var baseSize = 8;
    var sizes = leds.map(function(l){{ return selColorOf[keyOf(w,l)] ? baseSize+2.5 : baseSize; }});

    var markerCfg;
    if(HAS_COLOR){{
      /* colormap continu : la couleur de remplissage vient de la colorscale,
         la sélection est visible via le contour + la taille */
      markerCfg = {{
        symbol:"square", size:sizes,
        color: leds.map(function(l){{ return l.color!=null?l.color:null; }}),
        colorscale:"Viridis", showscale:true,
        line:{{width:lineWidths, color:lineColors}},
      }};
    }} else {{
      /* pas de colormap : couleur discrète (a une image EL ou non), la
         sélection peut alors aussi teinter le remplissage directement */
      markerCfg = {{
        symbol:"square", size:sizes,
        color: leds.map(function(l){{
          var k=keyOf(w,l);
          if(selColorOf[k]) return selColorOf[k];
          return els[l._pos] ? "#0A2463" : "rgba(10,36,99,.12)";
        }}),
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
      margin:{{t:8,r:HAS_COLOR?60:8,b:36,l:40}},
      xaxis:Object.assign({{}},GSTYLE,{{title:{{text:X_ESC,font:{{size:10,color:"#0A2463"}}}},range:[xmin-pitch,xmax+pitch],dtick:1,tickfont:{{size:9}},showgrid:true,zeroline:false,fixedrange:true}}),
      yaxis:Object.assign({{}},GSTYLE,{{title:{{text:Y_ESC,font:{{size:10,color:"#0A2463"}}}},range:[ymin-pitch,ymax+pitch],dtick:1,tickfont:{{size:9}},showgrid:true,zeroline:false,fixedrange:true}}),
      shapes:[{{type:"circle",xref:"paper",yref:"paper",x0:0.02,y0:0.02,x1:0.98,y1:0.98,line:{{color:"rgba(10,36,99,0.35)",width:1.8}},fillcolor:"rgba(0,0,0,0)",layer:"above"}}],
      clickmode:"event+select",
      dragmode:false,
      hoverlabel:{{bgcolor:"#0A2463",bordercolor:"#D4AF37",font:{{family:"IBM Plex Mono",size:9,color:"white"}}}},
    }};

    Plotly.react(mapEl, [trace], layout, PLYCFG).then(function(){{
      function calcSize(el){{
        var mL=40,mR=HAS_COLOR?60:8,mT=8,mB=36;
        var plotW = el.offsetWidth-mL-mR, plotH = el.offsetHeight-mT-mB;
        if(plotW<=0||plotH<=0) return 7;
        var xRange=(xmax-xmin)+2*pitch, yRange=(ymax-ymin)+2*pitch;
        var szX=plotW/xRange*pitch, szY=plotH/yRange*pitch;
        return Math.max(3, Math.min(szX,szY)*0.92);
      }}
      function applySizes(el){{
        var s = calcSize(el);
        var newSizes = leds.map(function(l){{ return selColorOf[keyOf(w,l)] ? s+2.5 : s; }});
        Plotly.restyle(el, {{"marker.size":[newSizes]}}, [0]);
      }}
      applySizes(mapEl);
      if(window[wid+"_resizeObs"]) window[wid+"_resizeObs"].disconnect();
      window[wid+"_resizeObs"] = new ResizeObserver(function(){{
        var el = document.getElementById(wid+"_map");
        if(el) applySizes(el);
      }});
      window[wid+"_resizeObs"].observe(mapEl);
    }});

    /* Le handler n'est lié qu'UNE SEULE fois : re-binder à chaque render fait
       accumuler les listeners (les toggles ctrl+clic s'annulent alors deux à
       deux). onMapClick relit toujours filteredLeds() à la volée. */
    if(!mapEl.__welcClickBound){{
      mapEl.on("plotly_click", onMapClick);
      mapEl.__welcClickBound = true;
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
      var i = sel.findIndex(function(c){{return c.k===k;}});
      if(i>=0) sel.splice(i,1);
      else sel.push({{k:k, w:w, led:led}});
    }} else {{
      sel = [{{k:k, w:w, led:led}}];
    }}
    curElIdx = 0;
    renderMap();
    refreshView();
  }}

  window[wid+"_toggleCompareMode"] = function(){{
    st.compareMode = !st.compareMode;
    if(st.compareMode && sel.length>1) sel = sel.slice(0,1);
    if(!st.compareMode) sel = [];
    var btn = document.getElementById(wid+"_mode_btn");
    btn.textContent = "⚏ Mode comparaison : "+(st.compareMode?"ON":"OFF");
    btn.style.background = st.compareMode ? "rgba(10,36,99,.12)" : "transparent";
    btn.style.color = st.compareMode ? "#0A2463" : "#4A5580";
    btn.style.borderColor = st.compareMode ? "#0A2463" : "rgba(10,36,99,.25)";
    curElIdx = 0;
    renderMap();
    refreshView();
  }};

  function footText(){{
    if(!sel.length) return "Cliquer sur une position";
    if(sel.length===1){{
      var c = sel[0];
      return '<span style="color:#D4AF37">&#9656;</span> '+c.w+' — '+c.led._id+' — X='+c.led.x+' Y='+c.led.y;
    }}
    return sel.length+" position(s) en comparaison";
  }}

  function renderTags(){{
    var tz = document.getElementById(wid+"_tags");
    tz.innerHTML = "";
    if(sel.length<2) return;
    sel.forEach(function(c,ci){{
      var col = COLORS[ci%COLORS.length];
      var t = document.createElement("div");
      t.style.cssText = "background:rgba(10,36,99,.05);border:1px solid "+col+";border-radius:12px;padding:2px 9px;font-size:10px;color:#0A2463;cursor:pointer;font-family:'IBM Plex Mono',monospace;";
      t.innerHTML = '<span style="color:'+col+'">&#9632;</span> '+c.w+' · '+c.led._id+' <b style="margin-left:4px">&times;</b>';
      t.onclick = (function(k){{
        return function(){{
          var i = sel.findIndex(function(x){{return x.k===k;}});
          if(i>=0) sel.splice(i,1);
          renderMap(); refreshView();
        }};
      }})(c.k);
      tz.appendChild(t);
    }});
  }}

  /* ── Rendu unifié EL pattern + spectre selon la taille de la sélection ── */
  function refreshView(){{
    document.getElementById(wid+"_foot").innerHTML = footText();
    renderElPanel();
    renderSpectrumSet();
    renderTags();
  }}

  function renderElPanel(){{
    var singleWrap = document.getElementById(wid+"_el_single");
    var gridWrap = document.getElementById(wid+"_el_compare_grid");

    if(sel.length>1){{
      singleWrap.style.display = "none";
      gridWrap.style.display = "grid";
      document.getElementById(wid+"_el_nav").style.display = "none";
      document.getElementById(wid+"_el_label").textContent = sel.length+" positions";
      renderElGrid();
    }} else {{
      gridWrap.style.display = "none";
      singleWrap.style.display = "flex";
      renderElSingle();
    }}

    var unionImgs = [];
    (sel.length?sel:[]).forEach(function(c){{ unionImgs = unionImgs.concat(pickElImages(c)); }});
    buildElImgNumButtons(unionImgs);
  }}

  function renderElSingle(){{
    var img = document.getElementById(wid+"_el_img");
    var ph = document.getElementById(wid+"_el_ph");
    var lbl = document.getElementById(wid+"_el_label");
    var nav = document.getElementById(wid+"_el_nav");

    if(!sel.length){{
      img.style.display = "none"; ph.style.display = "block";
      lbl.textContent = ""; nav.style.display = "none";
      return;
    }}
    var images = pickElImages(sel[0]);
    if(!images.length){{
      img.style.display = "none"; ph.style.display = "block";
      lbl.textContent = ""; nav.style.display = "none";
      return;
    }}
    var idx = 0;
    if(st.elImgNum!==""){{
      var f = images.findIndex(function(im){{return im.imgnum===st.elImgNum;}});
      if(f>=0) idx=f;
    }}
    if(curElIdx>=images.length) curElIdx=0;
    else idx = curElIdx || idx;

    var entry = images[idx];
    curElIdx = idx;
    ph.style.display = "none";
    img.style.display = "block";
    img.src = entry.src;
    lbl.textContent = entry.label + (entry.type ? " · "+entry.type : "") + (entry.imgnum ? " · #"+entry.imgnum : "");
    nav.style.display = images.length>1 ? "flex" : "none";
    document.getElementById(wid+"_el_cnt").textContent = (idx+1)+"/"+images.length;
  }}

  window[wid+"_elNav"] = function(dir){{
    if(!sel.length) return;
    var images = pickElImages(sel[0]);
    if(!images.length) return;
    curElIdx = (curElIdx + dir + images.length) % images.length;
    st.elImgNum = images[curElIdx].imgnum;
    renderElSingle();
    buildElImgNumButtons(images);
  }};

  function renderElGrid(){{
    var grid = document.getElementById(wid+"_el_compare_grid");
    grid.innerHTML = "";
    sel.forEach(function(c,ci){{
      var col = COLORS[ci%COLORS.length];
      var images = pickElImages(c);
      var entry = null;
      if(images.length){{
        var idx = 0;
        if(st.elImgNum!==""){{
          var f = images.findIndex(function(im){{return im.imgnum===st.elImgNum;}});
          if(f>=0) idx=f;
        }}
        entry = images[idx];
      }}
      var cell = document.createElement("div");
      cell.style.cssText = "display:flex;flex-direction:column;min-width:0;min-height:120px;border:1.5px solid "+col+";border-radius:6px;overflow:hidden;";
      var hdr = document.createElement("div");
      hdr.style.cssText = "padding:3px 8px;font-family:'IBM Plex Mono',monospace;font-size:8px;color:#fff;background:"+col+";white-space:nowrap;overflow:hidden;text-overflow:ellipsis;flex-shrink:0;";
      hdr.textContent = c.w+" · "+c.led._id;
      cell.appendChild(hdr);
      var body = document.createElement("div");
      body.style.cssText = "flex:1;display:flex;align-items:center;justify-content:center;background:#0A0E1A;min-height:0;";
      if(entry){{
        var im = document.createElement("img");
        im.src = entry.src;
        im.style.cssText = "max-width:100%;max-height:100%;object-fit:contain;";
        im.title = entry.label + (entry.type?" · "+entry.type:"") + (entry.imgnum?" · #"+entry.imgnum:"");
        body.appendChild(im);
      }} else {{
        var ph2 = document.createElement("span");
        ph2.style.cssText = "font-family:'IBM Plex Mono',monospace;font-size:9px;color:rgba(255,255,255,.35);text-align:center;padding:8px;";
        ph2.textContent = "Aucune image EL";
        body.appendChild(ph2);
      }}
      cell.appendChild(body);
      grid.appendChild(cell);
    }});
  }}

  function renderSpectrumSet(){{
    var slider = document.getElementById(wid+"_spec_slider");
    var lbl = document.getElementById(wid+"_spec_label");
    var el = document.getElementById(wid+"_det_spec");

    if(!sel.length){{
      purgeEl(wid+"_det_spec").innerHTML = '<div class="no-data-msg">Cliquer une position</div>';
      lbl.textContent = ""; slider.max=0; slider.value=0;
      return;
    }}
    var maxSteps = 0;
    sel.forEach(function(c){{ if((c.led._spectra||[]).length>maxSteps) maxSteps=c.led._spectra.length; }});
    if(!maxSteps){{
      purgeEl(wid+"_det_spec").innerHTML = '<div class="no-data-msg">Aucun spectre à cette position</div>';
      lbl.textContent = ""; slider.max=0; slider.value=0;
      return;
    }}
    slider.max = maxSteps-1;
    if(parseInt(slider.value) > maxSteps-1) slider.value = maxSteps-1;

    window[wid+"_onSpecSlider"] = function(val){{
      var i = parseInt(val);
      var traces = [];
      var multi = sel.length>1;
      sel.forEach(function(c,ci){{
        var specs = c.led._spectra||[], wl = c.led._wl||[];
        if(!specs[i] || !wl.length) return;
        var col = multi ? COLORS[ci%COLORS.length] : "#8B5CF6";
        var trace = {{
          x:wl, y:specs[i], type:"scatter", mode:"lines",
          line:{{color:col,width:1.8}},
          name: c.w+" · "+c.led._id,
          showlegend: multi,
        }};
        if(!multi){{ trace.fill="tozeroy"; trace.fillcolor="rgba(139,92,246,.1)"; }}
        traces.push(trace);
      }});
      lbl.textContent = "pt "+(i+1)+" / "+maxSteps;
      Plotly.react(el, traces, Object.assign(miniLayout("λ (nm)","Intensité"),{{showlegend:multi,legend:{{font:{{size:7}}}}}}), PLYCFG);
    }};
    window[wid+"_onSpecSlider"](parseInt(slider.value));
  }}

  document.addEventListener("keydown", function(e){{
    if(e.key==="ArrowLeft"||e.key==="ArrowRight"){{
      var wrap = document.getElementById(wid+"_wrap");
      if(!wrap || !wrap.matches(":hover")) return;
      e.preventDefault();
      goToWafer(carouselIdx+(e.key==="ArrowRight"?1:-1));
    }}
  }});

  goToWafer(0);
  refreshView();
}})();
</script>
"""
