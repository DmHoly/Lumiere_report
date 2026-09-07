from __future__ import annotations
import json
import html as _h
import numpy as np
import pandas as pd
from ..._helpers import Block, _safe_json, _is_vector_col, _col_analysis
from ..data.data_mixin import DataMixin, DataArg


class WaferComparator(DataMixin, Block):
    """
    Comparateur de wafers côte à côte — LUMIÈRE block v2.

    Nouveautés v2 :
    ─────────────────
    • ⊞ TOUT SÉLECTIONNER : bouton par carte (toggle tout / rien)
    • ↔ SYNC/DÉSYNCHRO : quand désactivé, W1 et W2 ont des sélections
        totalement indépendantes (pas de miroir automatique)
    • 🎨 COLOR PICKERS : palette de swatches par carte pour choisir la
        couleur des tracés dans les courbes comparatives

    Fonctionnalités de base :
    ─────────────────────────
    • Deux heatmaps Plotly côte à côte (colormap + colorscale partagés)
    • Clic / Lasso / Zone sur chaque carte
    • Panel courbes comparatives (EQE, Spectre, …)
    • Panel KPI scatter W1 vs W2 avec R², pente, Δ% médian, régression

    Params
    ──────
    data            : clé DataStore str ou pd.DataFrame
    x_col / y_col   : colonnes coordonnées (défaut "X", "Y")
    wafer_col       : colonne nom du wafer (défaut "wafername")
    color_col       : colonne colormap par défaut
    colormap_cols   : liste de colonnes scalaires pour le dropdown colormap
    kpi_cols        : colonnes scalaires pour le scatter KPI
    curve_cols      : dict {"label": {"x": col, "y": col, "log_y": bool}}
    spectra_col     : colonne contenant les spectres
    wavelength_col  : colonne longueurs d'onde
    id_col          : colonne identifiant la LED
    colorscale      : colorscale Plotly par défaut
    color_w1        : couleur hex des tracés W1 (défaut "#0A2463")
    color_w2        : couleur hex des tracés W2 (défaut "#3B82F6")
    map_height      : hauteur des heatmaps en px
    synced          : synchronisation W1↔W2 par défaut (True)
    num / title / subtitle : métadonnées du header
    """

    needs_plotly = True

    _COLOR_PALETTE = [
        ("#0A2463", "Navy"),
        ("#3B82F6", "Bleu"),
        ("#10B981", "Vert"),
        ("#EF4444", "Rouge"),
        ("#8B5CF6", "Violet"),
        ("#F59E0B", "Ambre"),
        ("#EC4899", "Rose"),
        ("#06B6D4", "Cyan"),
        ("#64748B", "Ardoise"),
        ("#D4AF37", "Or"),
    ]

    def __init__(
        self,
        data: DataArg,
        x_col: str = "X",
        y_col: str = "Y",
        wafer_col: str = "wafername",
        color_col: str = "",
        colormap_cols: list[str] | None = None,
        kpi_cols: list[str] | None = None,
        curve_cols: dict | None = None,
        spectra_col: str = "",
        wavelength_col: str = "",
        id_col: str = "",
        colorscale: str = "Viridis",
        color_w1: str = "#0A2463",
        color_w2: str = "#3B82F6",
        map_height: int = 300,
        synced: bool = True,
        num: str = "04",
        title: str = "Wafer Comparator",
        subtitle: str = "Comparaison position × position",
    ):
        self._init_data(data)
        self.x_col = x_col
        self.y_col = y_col
        self.wafer_col = wafer_col
        self.color_col = color_col
        self._colormap_cols_arg = colormap_cols
        self._kpi_cols_arg = kpi_cols
        self.curve_cols = curve_cols or {}
        self.spectra_col = spectra_col
        self.wavelength_col = wavelength_col
        self.id_col = id_col
        self.colorscale = colorscale
        self.color_w1 = color_w1
        self.color_w2 = color_w2
        self.map_height = map_height
        self.synced = synced
        self.num = num
        self.title = title
        self.subtitle = subtitle
        self._id = f"wc_{id(self)}"
        if self.has_local_data:
            self._resolve_col_lists(self.resolve_df())

    def _resolve_col_lists(self, df: pd.DataFrame) -> None:
        cols = _col_analysis(df)
        self.colormap_cols = self._colormap_cols_arg or cols["scalar_num"][:10]
        self.kpi_cols = self._kpi_cols_arg or cols["scalar_num"][:8]

    def _build_wafer_json(self, df: pd.DataFrame) -> str:
        if not hasattr(self, "colormap_cols"):
            self._resolve_col_lists(df)
        all_scalar = list(dict.fromkeys(
            c for c in (self.colormap_cols + self.kpi_cols)
            if c and c in df.columns and not _is_vector_col(df[c])
        ))
        out = {}
        for wafer, grp in df.groupby(self.wafer_col):
            leds = []
            for _, row in grp.iterrows():
                rec = {
                    "x":   _safe_json(row[self.x_col])  if self.x_col  in row.index else 0,
                    "y":   _safe_json(row[self.y_col])  if self.y_col  in row.index else 0,
                    "_id": str(row[self.id_col]) if self.id_col and self.id_col in row.index else str(len(leds)),
                }
                for c in all_scalar:
                    try: rec[c] = _safe_json(row[c])
                    except Exception: pass
                for lbl, cfg in self.curve_cols.items():
                    xc, yc = cfg.get("x", ""), cfg.get("y", "")
                    if xc in row.index and yc in row.index:
                        xv, yv = row[xc], row[yc]
                        rec[f"_cx_{lbl}"] = [_safe_json(z) for z in xv] if isinstance(xv, (list, np.ndarray)) else []
                        rec[f"_cy_{lbl}"] = [_safe_json(z) for z in yv] if isinstance(yv, (list, np.ndarray)) else []
                if self.spectra_col and self.spectra_col in row.index:
                    sp = row[self.spectra_col]
                    if isinstance(sp, (list, np.ndarray)) and len(sp) > 0:
                        def _ds(s, target=80):
                            if not isinstance(s, (list, np.ndarray)) or len(s) <= target:
                                return [_safe_json(v) for v in s]
                            step = max(1, len(s) // target)
                            return [_safe_json(s[i]) for i in range(0, len(s), step)]
                        rec["_spectra"] = [_ds(sp[i]) for i in range(len(sp)) if isinstance(sp[i], (list, np.ndarray))]
                if self.wavelength_col and self.wavelength_col in row.index:
                    wl = row[self.wavelength_col]
                    if isinstance(wl, (list, np.ndarray)):
                        step = max(1, len(wl) // 80)
                        rec["_wl"] = [_safe_json(wl[i]) for i in range(0, len(wl), step)]
                leds.append(rec)
            out[str(wafer)] = leds
        return json.dumps(out)

    def _color_picker_html(self, wid: str, slot: int, default_color: str) -> str:
        swatches = []
        for hex_c, name in self._COLOR_PALETTE:
            border = "2.5px solid #111" if hex_c.lower() == default_color.lower() else "2px solid transparent"
            swatches.append(
                f'<span title="{name}" '
                f'onclick="window[\'{wid}_setColor{slot}\'](this,\'{hex_c}\')" '
                f'style="display:inline-block;width:14px;height:14px;border-radius:50%;'
                f'background:{hex_c};cursor:pointer;border:{border};'
                f'transition:border .1s;flex-shrink:0;" '
                f'id="{wid}_sw{slot}_{hex_c.replace("#","")}">'
                f'</span>'
            )
        return (
            '<div style="display:flex;align-items:center;gap:3px;flex-wrap:wrap;">'
            + "".join(swatches)
            + '</div>'
        )

    def render(self, store=None) -> str:
        df = self.resolve_df(store)
        if not hasattr(self, "colormap_cols"):
            self._resolve_col_lists(df)

        wid           = self._id
        wafer_json    = self._build_wafer_json(df)
        curves_json   = json.dumps({
            lbl: {"log_y": cfg.get("log_y", False), "log_x": cfg.get("log_x", False),
                  "xlabel": cfg.get("x", ""), "ylabel": cfg.get("y", "")}
            for lbl, cfg in self.curve_cols.items()
        })
        colormap_json = json.dumps(self.colormap_cols)
        kpi_json      = json.dumps(self.kpi_cols)
        has_spec_js   = "true" if self.spectra_col else "false"
        default_cmap  = json.dumps(self.color_col or (self.colormap_cols[0] if self.colormap_cols else ""))
        default_kpi   = json.dumps(self.kpi_cols[0] if self.kpi_cols else "")
        cs_js         = json.dumps(self.colorscale)
        map_h         = self.map_height
        x_esc         = _h.escape(self.x_col)
        y_esc         = _h.escape(self.y_col)
        c1_js         = json.dumps(self.color_w1)
        c2_js         = json.dumps(self.color_w2)
        synced_js     = "true" if self.synced else "false"
        picker1       = self._color_picker_html(wid, 1, self.color_w1)
        picker2       = self._color_picker_html(wid, 2, self.color_w2)
        w1_bg         = self.color_w1
        w2_bg         = self.color_w2

        return f"""
<!-- WaferComparator {wid} -->
<style>
#{wid}_wrap .wc-panel{{background:var(--surface,#fff);border:1px solid var(--border,#E4E8F4);border-radius:6px;overflow:hidden;}}
#{wid}_wrap .wc-btn{{font-family:'IBM Plex Mono',monospace;font-size:9px;letter-spacing:.05em;border:1px solid rgba(10,36,99,.2);border-radius:4px;padding:3px 9px;cursor:pointer;background:#fff;color:#0A2463;transition:all .15s;white-space:nowrap;}}
#{wid}_wrap .wc-btn:hover{{background:rgba(10,36,99,.06);}}
#{wid}_wrap .wc-btn.active{{background:#0A2463;color:#D4AF37;border-color:#0A2463;}}
#{wid}_wrap .wc-btn.sync-on{{background:#10B981;color:#fff;border-color:#10B981;}}
#{wid}_wrap .wc-select{{font-family:'IBM Plex Mono',monospace;font-size:9px;color:#0A2463;border:1px solid rgba(10,36,99,.2);border-radius:4px;padding:3px 6px;background:#fff;cursor:pointer;}}
#{wid}_wrap .wc-map-label{{font-family:'IBM Plex Mono',monospace;font-weight:700;font-size:9px;text-transform:uppercase;letter-spacing:.08em;padding:5px 10px;border-bottom:1px solid var(--border,#E4E8F4);display:flex;align-items:center;gap:8px;}}
#{wid}_wrap .wc-map-sub{{padding:5px 10px;border-bottom:1px solid var(--border,#E4E8F4);display:flex;align-items:center;gap:6px;background:var(--slate-50,#F8F9FD);flex-wrap:wrap;}}
#{wid}_wrap .wc-stat-grid{{display:grid;grid-template-columns:repeat(4,1fr);gap:6px;padding:8px 12px;}}
#{wid}_wrap .wc-stat-card{{background:var(--slate-50,#F8F9FD);border:1px solid var(--border,#E4E8F4);border-radius:5px;padding:6px 8px;text-align:center;}}
#{wid}_wrap .wc-stat-val{{font-family:'IBM Plex Mono',monospace;font-weight:700;font-size:13px;color:#0A2463;}}
#{wid}_wrap .wc-stat-lbl{{font-family:'IBM Plex Mono',monospace;font-size:8px;color:#8896BB;text-transform:uppercase;letter-spacing:.06em;margin-top:2px;}}
#{wid}_wrap .wc-stat-val.neg{{color:#b91c1c;}}
#{wid}_wrap .wc-stat-val.pos{{color:#065f46;}}
</style>

<div class="led-block" id="{wid}_wrap">
  <div class="led-block-header">
    <span class="led-block-num">{_h.escape(self.num)}</span>
    <span class="led-block-title">{_h.escape(self.title)}</span>
    <span class="led-block-sub">{_h.escape(self.subtitle)}</span>
  </div>
  <div class="led-block-rule"></div>

  <div style="padding:14px;">

    <!-- TOOLBAR GLOBAL -->
    <div style="display:flex;align-items:center;gap:8px;flex-wrap:wrap;margin-bottom:12px;">
      <span style="font-family:'IBM Plex Mono',monospace;font-size:9px;font-weight:700;color:#0A2463;">W1</span>
      <select class="wc-select" id="{wid}_w1sel" style="min-width:120px;" onchange="window['{wid}_onW1Change'](this.value)"></select>
      <span style="color:#D4AF37;font-size:14px;font-weight:700;">⇔</span>
      <span style="font-family:'IBM Plex Mono',monospace;font-size:9px;font-weight:700;color:#3B82F6;">W2</span>
      <select class="wc-select" id="{wid}_w2sel" style="min-width:120px;" onchange="window['{wid}_onW2Change'](this.value)"></select>
      <div style="width:1px;height:18px;background:rgba(10,36,99,.15);margin:0 2px;"></div>
      <span style="font-family:'IBM Plex Mono',monospace;font-size:9px;color:#8896BB;">Colormap</span>
      <select class="wc-select" id="{wid}_cmapsel" onchange="window['{wid}_onCmapChange'](this.value)"></select>
      <select class="wc-select" id="{wid}_csssel" onchange="window['{wid}_onCssChange'](this.value)" style="width:80px;">
        <option value="Viridis">Viridis</option><option value="Jet">Jet</option>
        <option value="Plasma">Plasma</option><option value="Inferno">Inferno</option>
        <option value="RdBu">RdBu</option><option value="Turbo">Turbo</option>
      </select>
      <div style="width:1px;height:18px;background:rgba(10,36,99,.15);margin:0 2px;"></div>
      <button class="wc-btn active" id="{wid}_bclick" onclick="window['{wid}_setDrag']('click')">✦ CLIC</button>
      <button class="wc-btn" id="{wid}_blasso" onclick="window['{wid}_setDrag']('lasso')">⬡ LASSO</button>
      <button class="wc-btn" id="{wid}_bbox" onclick="window['{wid}_setDrag']('select')">▣ ZONE</button>
      <button class="wc-btn sync-on" id="{wid}_bsync" onclick="window['{wid}_toggleSync']()" title="Synchronisation sélection W1↔W2">↔ Sync</button>
      <button class="wc-btn" onclick="window['{wid}_clearAll']()" style="margin-left:2px;">✕ RESET</button>
      <span id="{wid}_selinfo" style="font-family:'IBM Plex Mono',monospace;font-size:9px;color:#8896BB;margin-left:4px;">Cliquer ou sélectionner</span>
    </div>

    <!-- CARTES CÔTE À CÔTE -->
    <div style="display:grid;grid-template-columns:1fr 1fr;gap:10px;margin-bottom:10px;">

      <!-- W1 -->
      <div class="wc-panel" style="display:flex;flex-direction:column;">
        <div class="wc-map-label">
          <span style="width:10px;height:10px;border-radius:50%;background:{w1_bg};border:1px solid rgba(0,0,0,.15);flex-shrink:0;" id="{wid}_w1dot"></span>
          <span style="background:{w1_bg};color:#fff;padding:1px 7px;border-radius:3px;font-size:8px;" id="{wid}_w1badge">W1</span>
          <span id="{wid}_w1name" style="flex:1;"></span>
          <span id="{wid}_w1cnt" style="font-size:8px;color:#8896BB;"></span>
        </div>
        <div class="wc-map-sub">
          <button class="wc-btn" style="font-size:8px;padding:2px 7px;" onclick="window['{wid}_selectAll'](1)" title="Tout sélectionner / désélectionner W1">⊞ Tout</button>
          <div style="width:1px;height:14px;background:rgba(10,36,99,.12);"></div>
          <span style="font-family:'IBM Plex Mono',monospace;font-size:8px;color:#8896BB;white-space:nowrap;">Couleur :</span>
          {picker1}
        </div>
        <div id="{wid}_map1" style="height:{map_h}px;"></div>
      </div>

      <!-- W2 -->
      <div class="wc-panel" style="display:flex;flex-direction:column;">
        <div class="wc-map-label">
          <span style="width:10px;height:10px;border-radius:50%;background:{w2_bg};border:1px solid rgba(0,0,0,.15);flex-shrink:0;" id="{wid}_w2dot"></span>
          <span style="background:{w2_bg};color:#fff;padding:1px 7px;border-radius:3px;font-size:8px;" id="{wid}_w2badge">W2</span>
          <span id="{wid}_w2name" style="flex:1;"></span>
          <span id="{wid}_w2cnt" style="font-size:8px;color:#8896BB;"></span>
        </div>
        <div class="wc-map-sub">
          <button class="wc-btn" style="font-size:8px;padding:2px 7px;" onclick="window['{wid}_selectAll'](2)" title="Tout sélectionner / désélectionner W2">⊞ Tout</button>
          <div style="width:1px;height:14px;background:rgba(10,36,99,.12);"></div>
          <span style="font-family:'IBM Plex Mono',monospace;font-size:8px;color:#8896BB;white-space:nowrap;">Couleur :</span>
          {picker2}
        </div>
        <div id="{wid}_map2" style="height:{map_h}px;"></div>
      </div>
    </div>

    <!-- PANEL COURBES -->
    <div class="wc-panel" id="{wid}_curve_panel" style="margin-bottom:10px;display:none;">
      <div style="padding:6px 12px;border-bottom:1px solid var(--border,#E4E8F4);display:flex;align-items:center;gap:8px;flex-wrap:wrap;">
        <span style="font-family:'IBM Plex Mono',monospace;font-weight:700;font-size:9px;color:#0A2463;text-transform:uppercase;letter-spacing:.08em;flex:1;">Comparaison des courbes</span>
        <div id="{wid}_curve_tabs" style="display:flex;gap:4px;"></div>
        <button id="{wid}_clogx" onclick="window['{wid}_toggleCurveLog']('x')" class="wc-btn" style="font-size:8px;">X:Lin</button>
        <button id="{wid}_clogy" onclick="window['{wid}_toggleCurveLog']('y')" class="wc-btn" style="font-size:8px;">Y:Lin</button>
      </div>
      <div id="{wid}_curve_plot" style="height:220px;"></div>
    </div>

    <!-- PANEL KPI -->
    <div class="wc-panel" id="{wid}_kpi_panel" style="display:none;">
      <div style="padding:6px 12px;border-bottom:1px solid var(--border,#E4E8F4);display:flex;align-items:center;gap:8px;flex-wrap:wrap;">
        <span style="font-family:'IBM Plex Mono',monospace;font-weight:700;font-size:9px;color:#0A2463;text-transform:uppercase;letter-spacing:.08em;">Analyse KPI position × position</span>
        <span style="font-family:'IBM Plex Mono',monospace;font-size:9px;color:#0A2463;font-weight:700;">W1 →</span>
        <select class="wc-select" id="{wid}_kx_sel" style="min-width:100px;" onchange="window['{wid}_refreshKpi']()"></select>
        <span style="font-family:'IBM Plex Mono',monospace;font-size:9px;color:#3B82F6;font-weight:700;">W2 ↑</span>
        <select class="wc-select" id="{wid}_ky_sel" style="min-width:100px;" onchange="window['{wid}_refreshKpi']()"></select>
        <div style="width:1px;height:18px;background:rgba(10,36,99,.15);margin:0 2px;"></div>
        <label style="display:flex;align-items:center;gap:4px;cursor:pointer;"><input type="checkbox" id="{wid}_show_identity" checked onchange="window['{wid}_refreshKpi']()"><span style="font-family:'IBM Plex Mono',monospace;font-size:9px;color:#8896BB;">y=x</span></label>
        <label style="display:flex;align-items:center;gap:4px;cursor:pointer;"><input type="checkbox" id="{wid}_show_regr" checked onchange="window['{wid}_refreshKpi']()"><span style="font-family:'IBM Plex Mono',monospace;font-size:9px;color:#8896BB;">Régression</span></label>
        <label style="display:flex;align-items:center;gap:4px;cursor:pointer;"><input type="checkbox" id="{wid}_color_delta" onchange="window['{wid}_refreshKpi']()"><span style="font-family:'IBM Plex Mono',monospace;font-size:9px;color:#8896BB;">Color Δ%</span></label>
      </div>
      <div class="wc-stat-grid">
        <div class="wc-stat-card"><div class="wc-stat-val" id="{wid}_stat_r2">—</div><div class="wc-stat-lbl">R²</div></div>
        <div class="wc-stat-card"><div class="wc-stat-val" id="{wid}_stat_slope">—</div><div class="wc-stat-lbl">Pente</div></div>
        <div class="wc-stat-card"><div class="wc-stat-val" id="{wid}_stat_offset">—</div><div class="wc-stat-lbl">Offset</div></div>
        <div class="wc-stat-card"><div class="wc-stat-val" id="{wid}_stat_delta">—</div><div class="wc-stat-lbl">Δ% médian</div></div>
      </div>
      <div id="{wid}_kpi_plot" style="height:280px;"></div>
    </div>

  </div>
</div>

<script>
(function(){{
  var WDATA={wafer_json};
  var CURVES={curves_json};
  var CMAP_COLS={colormap_json};
  var KPI_COLS={kpi_json};
  var hasSpec={has_spec_js};
  var wid="{wid}";
  var DEFAULT_CMAP={default_cmap};
  var DEFAULT_KPI={default_kpi};
  var DEFAULT_CS={cs_js};
  var X_COL="{x_esc}";
  var Y_COL="{y_esc}";

  var PLYCFG={{responsive:true,displaylogo:false,modeBarButtonsToRemove:["autoScale2d","toggleSpikelines","sendDataToCloud"]}};
  var GSTYLE={{gridcolor:"#E4E8F4",linecolor:"#E4E8F4",zerolinecolor:"#E4E8F4"}};
  var CG="#D4AF37";

  var waferNames=Object.keys(WDATA).sort();
  var st={{
    w1:waferNames[0]||"", w2:waferNames[1]||waferNames[0]||"",
    cmapCol:DEFAULT_CMAP||(CMAP_COLS[0]||""),
    csStyle:DEFAULT_CS,
    dragMode:"click",
    sel1:[], sel2:[],
    synced:{synced_js},
    c1:{c1_js},
    c2:{c2_js},
    curveTab:Object.keys(CURVES)[0]||(hasSpec?"__spec__":""),
    curveLogX:false, curveLogY:false,
    kpiX:DEFAULT_KPI||(KPI_COLS[0]||""),
    kpiY:DEFAULT_KPI||(KPI_COLS[0]||""),
  }};

  /* ── INIT ── */
  function initSelects(){{
    ["_w1sel","_w2sel"].forEach(function(sfx,i){{
      var sel=document.getElementById(wid+sfx); if(!sel) return;
      waferNames.forEach(function(n){{
        var o=document.createElement("option"); o.value=n; o.textContent=n;
        if((i===0&&n===st.w1)||(i===1&&n===st.w2)) o.selected=true;
        sel.appendChild(o);
      }});
    }});
    var cmSel=document.getElementById(wid+"_cmapsel");
    CMAP_COLS.forEach(function(c){{
      var o=document.createElement("option"); o.value=c; o.textContent=c;
      if(c===st.cmapCol) o.selected=true;
      cmSel.appendChild(o);
    }});
    var csSel=document.getElementById(wid+"_csssel");
    for(var i=0;i<csSel.options.length;i++){{if(csSel.options[i].value===DEFAULT_CS) csSel.selectedIndex=i;}}
    ["_kx_sel","_ky_sel"].forEach(function(sfx){{
      var sel=document.getElementById(wid+sfx); if(!sel) return;
      KPI_COLS.forEach(function(c){{
        var o=document.createElement("option"); o.value=c; o.textContent=c; sel.appendChild(o);
      }});
      sel.value=st.kpiX;
    }});
    var tabs=document.getElementById(wid+"_curve_tabs");
    var allCurves=Object.keys(CURVES); if(hasSpec) allCurves.push("__spec__");
    allCurves.forEach(function(lbl){{
      var b=document.createElement("button");
      b.className="wc-btn"+(lbl===st.curveTab?" active":"");
      b.textContent=lbl==="__spec__"?"Spectre":lbl;
      b.onclick=function(){{
        st.curveTab=lbl;
        tabs.querySelectorAll("button").forEach(function(x){{x.classList.remove("active");}});
        b.classList.add("active"); refreshCurvePlot();
      }};
      tabs.appendChild(b);
    }});
    updateSyncBtn();
  }}

  /* ── MAPS ── */
  function buildTrace(leds,cmapCol,csStyle,selIdx){{
    if(!leds||!leds.length) return [];
    var xs=[],ys=[],zs=[],texts=[];
    leds.forEach(function(l,i){{
      xs.push(l.x); ys.push(l.y);
      var v=(cmapCol&&l[cmapCol]!=null)?l[cmapCol]:null; zs.push(v);
      texts.push("<b>"+l._id+"</b><br>"+X_COL+":"+l.x+" "+Y_COL+":"+l.y+(cmapCol&&v!=null?"<br>"+cmapCol+":"+fmtNum(v):""));
    }});
    var validZ=zs.filter(function(v){{return v!=null;}});
    var zmin=validZ.length?Math.min.apply(null,validZ):0, zmax=validZ.length?Math.max.apply(null,validZ):1;
    var selX=[],selY=[],selT=[];
    selIdx.forEach(function(i){{selX.push(leds[i].x);selY.push(leds[i].y);selT.push(texts[i]);}});
    var base={{type:"scatter",mode:"markers",x:xs,y:ys,text:texts,hoverinfo:"text",
      marker:{{size:16,color:zs,colorscale:csStyle,cmin:zmin,cmax:zmax,
        colorbar:{{thickness:10,len:0.7,tickfont:{{size:8,family:"IBM Plex Mono,monospace"}}}},
        line:{{width:selIdx.length?leds.map(function(_,i){{return selIdx.indexOf(i)>=0?2.5:0;}}):0,color:CG}}}}}};
    var sel={{type:"scatter",mode:"markers",x:selX,y:selY,text:selT,hoverinfo:"text",
      marker:{{size:22,color:"rgba(0,0,0,0)",line:{{width:2.5,color:CG}}}},showlegend:false}};
    return selX.length?[base,sel]:[base];
  }}

  function mapLayout(dragMode){{
    return {{paper_bgcolor:"rgba(0,0,0,0)",plot_bgcolor:"#F8F9FD",
      font:{{family:"IBM Plex Mono,monospace",color:"#4A5580",size:9}},
      margin:{{t:8,r:14,b:28,l:36}},showlegend:false,
      dragmode:dragMode==="click"?"zoom":dragMode,
      xaxis:Object.assign({{}},GSTYLE,{{title:{{text:X_COL,font:{{size:9}},standoff:2}},tickfont:{{size:8}}}}),
      yaxis:Object.assign({{}},GSTYLE,{{title:{{text:Y_COL,font:{{size:9}},standoff:2}},tickfont:{{size:8}},scaleanchor:"x"}}),
    }};
  }}

  function renderMap(slot){{
    var wname=slot===1?st.w1:st.w2, divId=wid+(slot===1?"_map1":"_map2");
    var leds=WDATA[wname]||[], selIdx=slot===1?st.sel1:st.sel2;
    var traces=buildTrace(leds,st.cmapCol,st.csStyle,selIdx);
    var nameEl=document.getElementById(wid+(slot===1?"_w1name":"_w2name"));
    var cntEl=document.getElementById(wid+(slot===1?"_w1cnt":"_w2cnt"));
    if(nameEl) nameEl.textContent=wname;
    if(cntEl)  cntEl.textContent=leds.length+" pts";
    var layout=mapLayout(st.dragMode);
    if(!document.getElementById(divId)._pi){{
      Plotly.newPlot(divId,traces,layout,PLYCFG);
      document.getElementById(divId)._pi=true;
      document.getElementById(divId).on("plotly_click",function(data){{
        if(st.dragMode!=="click") return;
        var pt=data.points[0];
        var idx=pt.pointIndex!==undefined?pt.pointIndex:pt.pointNumber;
        if(idx==null) return;
        var arr=slot===1?st.sel1:st.sel2;
        var pos=arr.indexOf(idx);
        if(pos>=0) arr.splice(pos,1); else arr.push(idx);
        afterSelection(slot);
      }});
      document.getElementById(divId).on("plotly_selected",function(data){{
        if(!data||!data.points) return;
        var arr=slot===1?st.sel1:st.sel2; arr.length=0;
        data.points.forEach(function(p){{
          var idx=p.pointIndex!==undefined?p.pointIndex:p.pointNumber;
          if(idx!=null) arr.push(idx);
        }});
        afterSelection(slot);
      }});
    }} else Plotly.react(divId,traces,layout,PLYCFG);
  }}

  function renderBothMaps(){{renderMap(1);renderMap(2);}}

  /* ★ TOUT SÉLECTIONNER */
  window[wid+"_selectAll"]=function(slot){{
    var wname=slot===1?st.w1:st.w2;
    var leds=WDATA[wname]||[], arr=slot===1?st.sel1:st.sel2;
    if(arr.length===leds.length){{arr.length=0;}}
    else{{arr.length=0; leds.forEach(function(_,i){{arr.push(i);}});}}
    afterSelection(slot);
  }};

  /* ★ SYNC TOGGLE */
  window[wid+"_toggleSync"]=function(){{
    st.synced=!st.synced; updateSyncBtn();
    /* re-display sync state in selinfo */
    updateSelInfo();
  }};
  function updateSyncBtn(){{
    var btn=document.getElementById(wid+"_bsync"); if(!btn) return;
    if(st.synced){{btn.textContent="↔ Sync";btn.className="wc-btn sync-on";btn.title="Synchronisé — cliquer pour désynchroniser";}}
    else{{btn.textContent="↔ Désynchro";btn.className="wc-btn";btn.title="Désynchro — cliquer pour resynchroniser";}}
  }}

  /* ★ COLOR PICKERS */
  window[wid+"_setColor1"]=function(el,hex){{
    st.c1=hex;
    document.querySelectorAll('[id^="'+wid+'_sw1_"]').forEach(function(s){{
      s.style.border=s.id===wid+"_sw1_"+hex.replace("#","")?"2.5px solid #111":"2px solid transparent";
    }});
    var badge=document.getElementById(wid+"_w1badge"), dot=document.getElementById(wid+"_w1dot");
    if(badge) badge.style.background=hex;
    if(dot) dot.style.background=hex;
    if(document.getElementById(wid+"_curve_panel").style.display!=="none") refreshCurvePlot();
  }};
  window[wid+"_setColor2"]=function(el,hex){{
    st.c2=hex;
    document.querySelectorAll('[id^="'+wid+'_sw2_"]').forEach(function(s){{
      s.style.border=s.id===wid+"_sw2_"+hex.replace("#","")?"2.5px solid #111":"2px solid transparent";
    }});
    var badge=document.getElementById(wid+"_w2badge"), dot=document.getElementById(wid+"_w2dot");
    if(badge) badge.style.background=hex;
    if(dot) dot.style.background=hex;
    if(document.getElementById(wid+"_curve_panel").style.display!=="none") refreshCurvePlot();
  }};

  /* ── AFTER SELECTION ── */
  function afterSelection(slot){{
    /* Mirror only if synced AND a specific slot triggered */
    if(st.synced&&slot!=null) mirrorSelection(slot);
    renderBothMaps(); updateSelInfo();
    var hasSel=st.sel1.length||st.sel2.length;
    document.getElementById(wid+"_curve_panel").style.display=hasSel?"":"none";
    document.getElementById(wid+"_kpi_panel").style.display=hasSel?"":"none";
    if(hasSel){{refreshCurvePlot();refreshKpi();}}
  }}

  function mirrorSelection(slot){{
    function posKey(l){{return l.x+","+l.y;}}
    var leds1=WDATA[st.w1]||[], leds2=WDATA[st.w2]||[];
    if(slot===1){{
      var keys1=st.sel1.map(function(i){{return posKey(leds1[i]);}});
      st.sel2.length=0;
      leds2.forEach(function(l,i){{if(keys1.indexOf(posKey(l))>=0) st.sel2.push(i);}});
    }} else {{
      var keys2=st.sel2.map(function(i){{return posKey(leds2[i]);}});
      st.sel1.length=0;
      leds1.forEach(function(l,i){{if(keys2.indexOf(posKey(l))>=0) st.sel1.push(i);}});
    }}
  }}

  /* ── CURVES ── */
  function getSelectedLeds(slot){{
    var wname=slot===1?st.w1:st.w2, leds=WDATA[wname]||[];
    var selIdx=slot===1?st.sel1:st.sel2;
    return selIdx.length?selIdx.map(function(i){{return leds[i];}}):leds;
  }}

  function refreshCurvePlot(){{
    var tab=st.curveTab, divId=wid+"_curve_plot";
    var leds1=getSelectedLeds(1), leds2=getSelectedLeds(2);
    var traces=[], isSpec=tab==="__spec__", cfg=isSpec?null:CURVES[tab];

    function addTraces(leds,wname,color,dash){{
      if(isSpec){{
        var allSpec=[],wl=null;
        leds.forEach(function(l){{
          if(l._spectra&&l._spectra.length){{
            var sp=l._spectra[l._spectra.length-1];
            if(sp&&sp.length) allSpec.push(sp);
            if(!wl&&l._wl) wl=l._wl;
          }}
        }});
        if(!allSpec.length) return;
        var len=allSpec[0].length, avg=new Array(len).fill(0);
        allSpec.forEach(function(s){{s.forEach(function(v,i){{avg[i]+=(v||0)/allSpec.length;}});}});
        traces.push({{type:"scatter",mode:"lines",x:wl||avg.map(function(_,i){{return i;}}),y:avg,
          name:wname+" (moy. n="+allSpec.length+")",line:{{color:color,width:2,dash:dash||"solid"}}}});
      }} else {{
        var plotted=0;
        leds.forEach(function(l){{
          var cx=l["_cx_"+tab], cy=l["_cy_"+tab];
          if(!cx||!cy||!cx.length) return;
          traces.push({{type:"scatter",mode:"lines",x:cx,y:cy,name:wname+" — "+l._id,
            line:{{color:color,width:1.5,dash:dash||"solid"}},opacity:0.75,
            showlegend:plotted===0,legendgroup:wname}});
          plotted++;
        }});
        if(plotted>1){{
          var lens=[]; leds.forEach(function(l){{var cy=l["_cy_"+tab];if(cy)lens.push(cy.length);}});
          var maxLen=Math.max.apply(null,lens);
          if(maxLen>0){{
            var sum=new Array(maxLen).fill(0), cnt=new Array(maxLen).fill(0);
            leds.forEach(function(l){{var cy=l["_cy_"+tab]; if(!cy) return;
              cy.forEach(function(v,i){{if(v!=null){{sum[i]+=v;cnt[i]++;}}}});}});
            var refCx=(leds.find(function(l){{return l["_cx_"+tab]&&l["_cx_"+tab].length;}})||leds[0])["_cx_"+tab]||[];
            traces.push({{type:"scatter",mode:"lines",x:refCx,
              y:sum.map(function(s,i){{return cnt[i]?s/cnt[i]:null;}}),
              name:wname+" MOY",line:{{color:color,width:2.5,dash:"solid"}},legendgroup:wname}});
          }}
        }}
      }}
    }}

    addTraces(leds1,st.w1,st.c1,"solid");
    addTraces(leds2,st.w2,st.c2,"dash");

    var xlabel=isSpec?"λ (nm)":(cfg?cfg.xlabel||"X":"X");
    var ylabel=isSpec?"Intensité (u.a.)":(cfg?cfg.ylabel||"Y":"Y");
    var layout={{paper_bgcolor:"rgba(0,0,0,0)",plot_bgcolor:"#F8F9FD",
      font:{{family:"IBM Plex Mono,monospace",color:"#4A5580",size:9}},
      margin:{{t:8,r:14,b:34,l:46}},showlegend:true,
      legend:{{font:{{size:8}},bgcolor:"rgba(255,255,255,.7)"}},
      xaxis:Object.assign({{}},GSTYLE,{{title:{{text:xlabel,font:{{size:9}},standoff:2}},type:st.curveLogX?"log":"linear",tickfont:{{size:8}}}}),
      yaxis:Object.assign({{}},GSTYLE,{{title:{{text:ylabel,font:{{size:9}},standoff:2}},type:st.curveLogY?"log":"linear",tickfont:{{size:8}}}}),
    }};
    if(!document.getElementById(divId)._cp){{Plotly.newPlot(divId,traces,layout,PLYCFG);document.getElementById(divId)._cp=true;}}
    else Plotly.react(divId,traces,layout,PLYCFG);
  }}

  /* ── KPI ── */
  window[wid+"_refreshKpi"]=function(){{
    st.kpiX=document.getElementById(wid+"_kx_sel").value;
    st.kpiY=document.getElementById(wid+"_ky_sel").value;
    refreshKpi();
  }};

  function refreshKpi(){{
    var divId=wid+"_kpi_plot";
    var leds1=WDATA[st.w1]||[], leds2=WDATA[st.w2]||[];
    var kx=st.kpiX, ky=st.kpiY;
    var showId=document.getElementById(wid+"_show_identity").checked;
    var showReg=document.getElementById(wid+"_show_regr").checked;
    var colorDelta=document.getElementById(wid+"_color_delta").checked;
    function posKey(l){{return l.x+","+l.y;}}
    var map2={{}}; leds2.forEach(function(l){{map2[posKey(l)]=l;}});
    var xs=[],ys=[],texts=[],deltas=[];
    var selKeys1=new Set(st.sel1.map(function(i){{return posKey(leds1[i]);}}));
    var selKeys2=new Set(st.sel2.map(function(i){{return posKey(leds2[i]);}}));
    var useSel=st.sel1.length||st.sel2.length;
    leds1.forEach(function(l1){{
      var key=posKey(l1), l2=map2[key]; if(!l2) return;
      if(useSel&&!selKeys1.has(key)&&!selKeys2.has(key)) return;
      var vx=l1[kx], vy=l2[ky];
      if(vx==null||vy==null||isNaN(vx)||isNaN(vy)) return;
      xs.push(parseFloat(vx)); ys.push(parseFloat(vy));
      var d=vx!==0?(vy-vx)/Math.abs(vx)*100:null; deltas.push(d);
      texts.push("<b>("+l1.x+","+l1.y+")</b><br>"+st.w1+" "+kx+": "+fmtNum(vx)+"<br>"+
                 st.w2+" "+ky+": "+fmtNum(vy)+(d!=null?"<br>Δ%: "+(d>0?"+":"")+fmtNum(d)+"%":""));
    }});
    var slope=null,intercept=null,r2=null;
    if(xs.length>1){{
      var n=xs.length, mx=xs.reduce(function(a,b){{return a+b;}},0)/n, my=ys.reduce(function(a,b){{return a+b;}},0)/n;
      var sxy=0,sxx=0,syy=0;
      for(var i=0;i<n;i++){{sxy+=(xs[i]-mx)*(ys[i]-my);sxx+=(xs[i]-mx)*(xs[i]-mx);syy+=(ys[i]-my)*(ys[i]-my);}}
      slope=sxx>0?sxy/sxx:null; intercept=slope!=null?my-slope*mx:null;
      r2=(sxx>0&&syy>0)?(sxy*sxy)/(sxx*syy):null;
    }}
    var medDelta=null;
    var validD=deltas.filter(function(d){{return d!=null&&!isNaN(d);}});
    if(validD.length){{
      validD.sort(function(a,b){{return a-b;}}); var mid=Math.floor(validD.length/2);
      medDelta=validD.length%2?validD[mid]:(validD[mid-1]+validD[mid])/2;
    }}
    setText(wid+"_stat_r2",r2!=null?fmtNum(r2,3):"—");
    setText(wid+"_stat_slope",slope!=null?fmtNum(slope,3):"—");
    setText(wid+"_stat_offset",intercept!=null?fmtNum(intercept,3):"—");
    var deltaEl=document.getElementById(wid+"_stat_delta");
    if(deltaEl){{
      deltaEl.textContent=medDelta!=null?(medDelta>0?"+":"")+fmtNum(medDelta,1)+"%":"—";
      deltaEl.className="wc-stat-val"+(medDelta==null?"":medDelta>0?" pos":" neg");
    }}
    var colors;
    if(colorDelta&&deltas.length){{
      var absMax=Math.max.apply(null,deltas.filter(function(d){{return d!=null;}}).map(Math.abs));
      colors=deltas.map(function(d){{
        if(d==null) return "#ccc"; var t=absMax>0?d/absMax:0;
        return t>0?lerpColor("#E4E8F4","#10B981",t):lerpColor("#E4E8F4","#EF4444",-t);
      }});
    }} else colors=xs.map(function(){{return st.c1;}});
    var traces=[{{type:"scatter",mode:"markers",x:xs,y:ys,text:texts,hoverinfo:"text",
      marker:{{size:8,color:colors,line:{{width:1,color:"rgba(10,36,99,.3)"}}}},name:"Positions"}}];
    var allVals=xs.concat(ys);
    var vmin=allVals.length?Math.min.apply(null,allVals):0, vmax=allVals.length?Math.max.apply(null,allVals):1;
    var pad=(vmax-vmin)*0.07;
    if(showId&&allVals.length) traces.push({{type:"scatter",mode:"lines",x:[vmin-pad,vmax+pad],y:[vmin-pad,vmax+pad],line:{{color:"#8896BB",width:1,dash:"dot"}},name:"y = x"}});
    if(showReg&&slope!=null) traces.push({{type:"scatter",mode:"lines",x:[vmin-pad,vmax+pad],y:[slope*(vmin-pad)+intercept,slope*(vmax+pad)+intercept],line:{{color:"#D4AF37",width:1.5,dash:"solid"}},name:"Régr. (pente="+fmtNum(slope,2)+")"}});
    var layout={{paper_bgcolor:"rgba(0,0,0,0)",plot_bgcolor:"#F8F9FD",font:{{family:"IBM Plex Mono,monospace",color:"#4A5580",size:9}},
      margin:{{t:8,r:14,b:42,l:52}},showlegend:true,legend:{{font:{{size:8}},bgcolor:"rgba(255,255,255,.7)"}},
      xaxis:Object.assign({{}},GSTYLE,{{title:{{text:st.w1+" — "+kx,font:{{size:9}},standoff:2}},tickfont:{{size:8}}}}),
      yaxis:Object.assign({{}},GSTYLE,{{title:{{text:st.w2+" — "+ky,font:{{size:9}},standoff:2}},tickfont:{{size:8}}}}),
    }};
    if(!document.getElementById(divId)._kp){{Plotly.newPlot(divId,traces,layout,PLYCFG);document.getElementById(divId)._kp=true;}}
    else Plotly.react(divId,traces,layout,PLYCFG);
  }}

  /* ── PUBLIC API ── */
  window[wid+"_onW1Change"]=function(v){{st.w1=v;st.sel1=[];if(st.synced)st.sel2=[];renderBothMaps();afterSelection(null);}};
  window[wid+"_onW2Change"]=function(v){{st.w2=v;st.sel2=[];if(st.synced)st.sel1=[];renderBothMaps();afterSelection(null);}};
  window[wid+"_onCmapChange"]=function(v){{st.cmapCol=v;renderBothMaps();}};
  window[wid+"_onCssChange"]=function(v){{st.csStyle=v;renderBothMaps();}};
  window[wid+"_setDrag"]=function(mode){{
    st.dragMode=mode;
    var btnMap={{click:wid+"_bclick",lasso:wid+"_blasso",select:wid+"_bbox"}};
    Object.values(btnMap).forEach(function(id){{document.getElementById(id).classList.remove("active");}});
    document.getElementById(btnMap[mode]).classList.add("active");
    var dm=mode==="click"?"zoom":mode;
    Plotly.relayout(wid+"_map1",{{dragmode:dm}}).catch(function(){{}});
    Plotly.relayout(wid+"_map2",{{dragmode:dm}}).catch(function(){{}});
  }};
  window[wid+"_clearAll"]=function(){{
    st.sel1=[];st.sel2=[];renderBothMaps();updateSelInfo();
    document.getElementById(wid+"_curve_panel").style.display="none";
    document.getElementById(wid+"_kpi_panel").style.display="none";
  }};
  window[wid+"_toggleCurveLog"]=function(axis){{
    if(axis==="x"){{st.curveLogX=!st.curveLogX;document.getElementById(wid+"_clogx").textContent="X:"+(st.curveLogX?"Log":"Lin");document.getElementById(wid+"_clogx").classList.toggle("active",st.curveLogX);}}
    else{{st.curveLogY=!st.curveLogY;document.getElementById(wid+"_clogy").textContent="Y:"+(st.curveLogY?"Log":"Lin");document.getElementById(wid+"_clogy").classList.toggle("active",st.curveLogY);}}
    refreshCurvePlot();
  }};

  /* ── UTILS ── */
  function updateSelInfo(){{
    var el=document.getElementById(wid+"_selinfo"); if(!el) return;
    var n1=st.sel1.length, n2=st.sel2.length;
    if(!n1&&!n2){{el.textContent="Cliquer ou sélectionner"; return;}}
    var msg="W1: "+n1+" pts  |  W2: "+n2+" pts";
    if(!st.synced) msg+="  ↔ désynchro";
    el.textContent=msg;
  }}
  function fmtNum(v,d){{if(v==null||isNaN(v))return "—";d=d==null?2:d;return parseFloat(v.toFixed(d)).toString();}}
  function setText(id,txt){{var el=document.getElementById(id);if(el)el.textContent=txt;}}
  function lerpColor(a,b,t){{
    function h(s){{return parseInt(s.slice(1),16);}}
    var ca=h(a),cb=h(b);
    var r=Math.round(((ca>>16)&0xff)*(1-t)+((cb>>16)&0xff)*t);
    var g=Math.round(((ca>>8)&0xff)*(1-t)+((cb>>8)&0xff)*t);
    var bl=Math.round((ca&0xff)*(1-t)+(cb&0xff)*t);
    return "rgb("+r+","+g+","+bl+")";
  }}

  /* ── BOOT ── */
  initSelects();
  var ky=document.getElementById(wid+"_ky_sel");
  if(ky&&KPI_COLS.length>0){{ky.value=KPI_COLS[0];st.kpiY=KPI_COLS[0];}}
  (function waitPlotly(){{
    if(typeof Plotly!=="undefined"){{
      renderBothMaps();
      document.getElementById(wid+"_kpi_panel").style.display="";
      refreshKpi();
    }} else setTimeout(waitPlotly,80);
  }})();

}})();
</script>
"""