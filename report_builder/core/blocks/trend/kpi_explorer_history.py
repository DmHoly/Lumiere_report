from __future__ import annotations

import html as _h
import json

import pandas as pd

from ..._helpers import Block, _safe_json
from ..data.data_mixin import DataMixin
from ..types import DataArg


class KPIExplorer(DataMixin, Block):
    """
    Combined KPI history explorer for boxplot and scatter views.

    Features:
      - wafer autocomplete
      - POINTS toggle for boxplots
      - RECORDS toggle with inline help
      - TARGET toggle with inline help, visible in scatter mode too
      - axis-aware wavelength target zones on X and/or Y
      - optical and epi-run filters (in slide-in drawer)
      - time range selector with density histogram (compact)
    """

    needs_plotly = True

    def __init__(
        self,
        data: DataArg,
        kpi_cols: list[str] | None = None,
        x_col: str = "id",
        color_col: str = "Lot",
        wafer_col: str = "wafername",
        date_col: str = "Test_Date",
        optical_col: str = "Optical_Sensor",
        epi_col: str = "epi_run_type",
        height: int = 860,
        num: str = "01",
        title: str = "KPI Explorer",
        subtitle: str = "",
        default_mode: str = "box",
        log_x_default: bool = False,
        log_y_default: bool = False,
    ):
        self._init_data(data)
        self.kpi_cols = kpi_cols or [
            "max_EQE",
            "EQE_25A_cm2",
            "J_at_MaxEQE",
            "V at Max EQE",
            "V_25A_cm2",
            "Lambda_Dom_at_MaxEQE",
            "Lambda_Dom_25A_cm2",
            "Lambda_Peak_at_MaxEQE",
        ]
        self.x_col = x_col
        self.color_col = color_col
        self.wafer_col = wafer_col
        self.date_col = date_col
        self.optical_col = optical_col
        self.height = height
        self.num = num
        self.title = title
        self.subtitle = subtitle
        self.default_mode = default_mode
        self.log_x_default = log_x_default
        self.log_y_default = log_y_default
        self.epi_col = epi_col
        self._id = f"kpi_explorer_{id(self)}"

    def _build_js_data(self, df: pd.DataFrame) -> str:
        cols = list(
            dict.fromkeys(
                self.kpi_cols
                + [
                    self.x_col,
                    self.color_col,
                    self.wafer_col,
                    self.date_col,
                    self.optical_col,
                    self.epi_col,
                    "last_update",
                    "Led_Name",
                    "X",
                    "Y",
                ]
            )
        )
        cols = [column for column in cols if column in df.columns]
        return json.dumps(
            [{column: _safe_json(row[column]) for column in cols} for _, row in df[cols].iterrows()]
        )

    def _build_filter_presets(self) -> str:
        return json.dumps(
    {
                "Aucun filtre": [],
                "max_EQE > 0%":   [{"col": "max_EQE", "op": ">", "value": 0}],
                "max_EQE > 0.1%": [{"col": "max_EQE", "op": ">", "value": 0.1}],
                "Bleu - dom 25A/cm² entre 420 et 500 nm": [
                    {"col": "Lambda_Dom_25A_cm2", "op": "between", "min": 420, "max": 500},
                ],
                "Vert - dom 25A/cm² entre 480 et 580 nm": [
                    {"col": "Lambda_Dom_25A_cm2", "op": "between", "min": 480, "max": 580},
                ],
                "Rouge - dom max EQE > 605 nm": [
                    {"col": "Lambda_Dom_at_MaxEQE", "op": ">", "value": 605},
                ],
                "Rouge - dom 25A/cm² > 605 nm": [
                    {"col": "Lambda_Dom_25A_cm2", "op": ">", "value": 605},
                ],
                "Rouge - dom 25A/cm² > 580 nm ET max_EQE > 0.001%": [
                    {"col": "Lambda_Dom_at_MaxEQE", "op": ">", "value": 580},
                    {"col": "Lambda_Dom_25A_cm2",   "op": ">", "value": 605},
                    {"col": "max_EQE",              "op": ">", "value": 0.001},
                ],
                "Rouge - peak max EQE > 580 nm": [
                    {"col": "Lambda_Peak_at_MaxEQE", "op": ">", "value": 580},
                ],
                "Bleu - dom 25A/cm² entre 420 et 500 nm ET max_EQE > 0.1%": [
                    {"col": "Lambda_Dom_25A_cm2", "op": "between", "min": 420, "max": 500},
                    {"col": "max_EQE",            "op": ">", "value": 0.1},
                ],
                "Vert - dom 25A/cm² entre 480 et 580 nm ET max_EQE > 0.1%": [
                    {"col": "Lambda_Dom_25A_cm2", "op": "between", "min": 480, "max": 580},
                    {"col": "max_EQE",            "op": ">", "value": 0.1},
                ],
            }
        )

    def _build_target_zones(self) -> str:
        return json.dumps(
            {
                "Lambda_Dom_at_MaxEQE": [
                    {
                        "label": "Blue target",
                        "min": 450,
                        "max": 470,
                        "color": "rgba(59,130,246,0.12)",
                    },
                    {
                        "label": "Green target",
                        "min": 520,
                        "max": 540,
                        "color": "rgba(34,197,94,0.12)",
                    },
                    {
                        "label": "Red target",
                        "min": 605,
                        "max": 640,
                        "color": "rgba(239,68,68,0.12)",
                    },
                ],
                "Lambda_Dom_25A_cm2": [
                    {
                        "label": "Blue target",
                        "min": 450,
                        "max": 470,
                        "color": "rgba(59,130,246,0.12)",
                    },
                    {
                        "label": "Green target",
                        "min": 520,
                        "max": 540,
                        "color": "rgba(34,197,94,0.12)",
                    },
                    {
                        "label": "Red target",
                        "min": 605,
                        "max": 640,
                        "color": "rgba(239,68,68,0.12)",
                    },
                ],
            }
        )

    def _render_toggle_button(self, toggle_id: str, label: str, info_text: str, *, checked: bool) -> str:
        label_h = _h.escape(label)
        info_h = _h.escape(info_text, quote=True)
        pressed = "true" if checked else "false"
        background = "#0F766E" if checked else "#CBD5E1"
        knob_left = "18px" if checked else "2px"
        return f"""
    <span style="display:inline-flex;align-items:center;gap:7px;padding:5px 10px;border:1px solid #CBD5E1;border-radius:999px;background:#FFFFFF;">
      <span class="spt-filter-label" style="margin:0;">{label_h}</span>
      <span title="{info_h}" style="display:inline-flex;align-items:center;justify-content:center;width:15px;height:15px;border-radius:999px;border:1px solid #94A3B8;color:#64748B;font-size:10px;font-weight:700;cursor:help;user-select:none;">i</span>
      <button type="button" id="{toggle_id}" aria-pressed="{pressed}" style="position:relative;width:38px;height:22px;border:none;border-radius:999px;background:{background};cursor:pointer;padding:0;transition:background .18s ease, opacity .18s ease;">
        <span style="position:absolute;top:2px;left:{knob_left};width:18px;height:18px;border-radius:999px;background:#FFFFFF;box-shadow:0 1px 3px rgba(15,23,42,0.18);transition:left .18s ease;"></span>
      </button>
    </span>
"""

    def render(self, store=None) -> str:
        df = self.resolve_df(store)

        sid = self._id
        if self.has_local_data:
            data_init = f"var DATA = {self._build_js_data(df)};"
        else:
            data_init = f"var DATA = {self.store_js_expr(self._data_arg)};"
        filters_json = self._build_filter_presets()
        targets_json = self._build_target_zones()

        kpi_cols = [column for column in self.kpi_cols if column in df.columns]
        kpi_json = json.dumps(kpi_cols)

        optical_values = (
            sorted(df[self.optical_col].dropna().astype(str).unique().tolist())
            if self.optical_col in df.columns
            else []
        )
        wafer_values = (
            sorted(df[self.wafer_col].dropna().astype(str).unique().tolist())
            if self.wafer_col in df.columns
            else []
        )
        epi_values = (
            sorted(df[self.epi_col].dropna().astype(str).unique().tolist()) if self.epi_col in df.columns else []
        )

        optical_json = json.dumps(optical_values)
        wafer_json = json.dumps(wafer_values)
        epi_json = json.dumps(epi_values)
        lot_values = (
            sorted(df[self.color_col].dropna().astype(str).unique().tolist())
            if self.color_col in df.columns
            else []
        )
        lot_json = json.dumps(lot_values)

        title_h = _h.escape(self.title)
        subtitle_h = _h.escape(self.subtitle)
        x_col = _h.escape(self.x_col)
        color_col = _h.escape(self.color_col)
        wafer_col = _h.escape(self.wafer_col)
        date_col = _h.escape(self.date_col)
        optical_col = _h.escape(self.optical_col)
        epi_col = _h.escape(self.epi_col)

        default_mode_js = json.dumps(self.default_mode)
        logx_checked = "checked" if self.log_x_default else ""
        logy_checked = "checked" if self.log_y_default else ""
        box_display = "flex" if self.default_mode == "box" else "none"
        scatter_display = "flex" if self.default_mode == "scatter" else "none"
        box_active = "active" if self.default_mode == "box" else ""
        scatter_active = "active" if self.default_mode == "scatter" else ""
        default_x = kpi_cols[0] if kpi_cols else ""
        default_y = kpi_cols[1] if len(kpi_cols) > 1 else default_x
        target_toggle = self._render_toggle_button(
            f"{sid}_toggle_target",
            "TARGET",
            "Show or hide wavelength target bands on the relevant axis.",
            checked=True,
        )
        record_toggle = self._render_toggle_button(
            f"{sid}_toggle_record",
            "RECORDS",
            "Keep only wafers that progressively beat the selected KPI record. Available in box mode.",
            checked=False,
        )

        return f"""
<div class="led-block" id="{sid}_wrap">

  <div class="led-block-header">
    <span class="led-block-num">{_h.escape(self.num)}</span>
    <span class="led-block-title">{title_h}</span>
    <span class="led-block-sub">{subtitle_h}</span>
  </div>
  <div class="led-block-rule"></div>

  <!-- ── Compact single toolbar row ── -->
  <div style="display:flex;gap:8px;align-items:center;flex-wrap:wrap;margin-bottom:8px;">

    <!-- Mode tabs -->
    <button class="slt-btn {box_active}" id="{sid}_btn_box">BOXPLOT</button>
    <button class="slt-btn {scatter_active}" id="{sid}_btn_scatter">SCATTER</button>

    <div style="width:1px;height:20px;background:#E2E8F0;flex-shrink:0;"></div>

    <!-- Global filters (always visible) -->
    <span class="spt-filter-label">FILTRE</span>
    <select class="spt-filter-op" id="{sid}_filter"></select>

    <span class="spt-filter-label">LOT</span>
    <div style="position:relative;">
      <button id="{sid}_lot_btn" class="spt-filter-op"
              style="min-width:110px;text-align:left;display:inline-flex;align-items:center;justify-content:space-between;gap:6px;cursor:pointer;user-select:none;padding:3px 8px;">
        <span id="{sid}_lot_label">Tous les lots</span>
        <span style="color:#94A3B8;font-size:9px;">&#9662;</span>
      </button>
      <div id="{sid}_lot_dd"
           style="display:none;position:absolute;top:calc(100% + 2px);left:0;min-width:200px;
                  background:#FFFFFF;border:1px solid #CBD5E1;border-radius:8px;
                  box-shadow:0 4px 16px rgba(0,0,0,.14);z-index:999;">
        <div style="padding:6px 8px;border-bottom:1px solid #F1F5F9;">
          <input id="{sid}_lot_search" type="text" placeholder="Rechercher un lot…"
                 autocomplete="off" spellcheck="false"
                 style="width:100%;border:1px solid #CBD5E1;border-radius:4px;padding:3px 6px;
                        font-size:11px;font-family:'IBM Plex Mono',monospace;box-sizing:border-box;outline:none;">
        </div>
        <div id="{sid}_lot_list"
             style="max-height:200px;overflow-y:auto;padding:4px 0;
                    font-size:11px;font-family:'IBM Plex Mono',monospace;"></div>
        <div style="padding:5px 8px;border-top:1px solid #F1F5F9;">
          <span id="{sid}_lot_clr"
                style="cursor:pointer;color:#64748B;font-size:10px;text-decoration:underline;display:none;">Tout effacer</span>
        </div>
      </div>
    </div>

    <span class="spt-filter-label">WAFER</span>
    <div style="position:relative;">
      <button id="{sid}_wafer_btn" class="spt-filter-op"
              style="min-width:140px;text-align:left;display:inline-flex;align-items:center;justify-content:space-between;gap:6px;cursor:pointer;user-select:none;padding:3px 8px;">
        <span id="{sid}_wafer_label">Tous les wafers</span>
        <span style="color:#94A3B8;font-size:9px;">&#9662;</span>
      </button>
      <div id="{sid}_wafer_dd"
           style="display:none;position:absolute;top:calc(100% + 2px);left:0;min-width:220px;
                  background:#FFFFFF;border:1px solid #CBD5E1;border-radius:8px;
                  box-shadow:0 4px 16px rgba(0,0,0,.14);z-index:999;">
        <div style="padding:6px 8px;border-bottom:1px solid #F1F5F9;">
          <input id="{sid}_wafer_search" type="text" placeholder="Rechercher un wafer…"
                 autocomplete="off" spellcheck="false"
                 style="width:100%;border:1px solid #CBD5E1;border-radius:4px;padding:3px 6px;
                        font-size:11px;font-family:'IBM Plex Mono',monospace;box-sizing:border-box;outline:none;">
        </div>
        <div id="{sid}_wafer_list"
             style="max-height:200px;overflow-y:auto;padding:4px 0;
                    font-size:11px;font-family:'IBM Plex Mono',monospace;"></div>
        <div style="padding:5px 8px;border-top:1px solid #F1F5F9;">
          <span id="{sid}_wafer_clr"
                style="cursor:pointer;color:#64748B;font-size:10px;text-decoration:underline;display:none;">Tout effacer</span>
        </div>
      </div>
    </div>

    <!-- Box mode controls -->
    <div id="{sid}_ctrl_box"
         style="display:{box_display};gap:8px;align-items:center;">
      <div style="width:1px;height:20px;background:#E2E8F0;flex-shrink:0;"></div>
      <span class="spt-filter-label">KPI</span>
      <select class="spt-filter-op" id="{sid}_kpi"></select>
      <button class="slt-btn active" id="{sid}_btn_pts"
              title="Afficher / masquer les points individuels">POINTS</button>
    </div>

    <!-- Scatter mode controls -->
    <div id="{sid}_ctrl_scatter"
         style="display:{scatter_display};gap:8px;align-items:center;">
      <div style="width:1px;height:20px;background:#E2E8F0;flex-shrink:0;"></div>
      <span class="spt-filter-label">X</span>
      <select class="spt-filter-op" id="{sid}_x"></select>
      <span class="spt-filter-label">Y</span>
      <select class="spt-filter-op" id="{sid}_y"></select>
      <label class="slt-count" style="cursor:pointer;display:inline-flex;align-items:center;gap:5px;">
        <input type="checkbox" id="{sid}_logx" {logx_checked}> log X
      </label>
      <label class="slt-count" style="cursor:pointer;display:inline-flex;align-items:center;gap:5px;">
        <input type="checkbox" id="{sid}_logy" {logy_checked}> log Y
      </label>
    </div>

    <div style="flex:1;min-width:8px;"></div>

    <!-- Filtres drawer button with active-filter badge -->
    <button id="{sid}_btn_filters" class="slt-btn"
            style="display:inline-flex;align-items:center;gap:6px;padding:4px 14px;white-space:nowrap;">
      ⚙ Filtres
      <span id="{sid}_filter_badge"
            style="display:none;background:#DC2626;color:#FFFFFF;border-radius:999px;
                   font-size:10px;font-weight:800;padding:1px 6px;line-height:1.5;
                   min-width:16px;text-align:center;"></span>
    </button>
  </div>

  <!-- ── Compact time-range slider ── -->
  <div style="margin:0 0 8px;padding:6px 10px 4px;border:1px solid #E5E7EB;
              border-radius:10px;background:#FFFFFF;user-select:none;">
    <div style="display:flex;align-items:center;gap:8px;margin-bottom:4px;">
      <span class="spt-filter-label" style="flex-shrink:0;">FENETRE</span>
      <span id="{sid}_tr_label"
            style="font-size:11px;font-weight:700;color:#0F172A;
                   font-family:'IBM Plex Mono',monospace;flex:1;text-align:center;"></span>
      <button class="slt-btn" id="{sid}_all_time"
              style="flex-shrink:0;padding:2px 8px;font-size:10px;">TOUT</button>
    </div>
    <div id="{sid}_tr_track"
         style="position:relative;height:28px;border-radius:4px;
                background:repeating-linear-gradient(-45deg,
                  #C6CBD8 0px,#C6CBD8 2px,#E8EBF2 2px,#E8EBF2 9px);
                border:1px solid #BCC1CF;overflow:visible;cursor:default;">
      <canvas id="{sid}_tr_canvas"
              style="position:absolute;top:0;left:0;width:100%;height:100%;
                     z-index:0;pointer-events:none;border-radius:3px;"></canvas>
      <div id="{sid}_tr_fill"
           style="position:absolute;top:0;bottom:0;
                  background:rgba(134,239,172,0.48);
                  border-left:2px solid #22C55E;border-right:2px solid #22C55E;
                  cursor:grab;z-index:1;"></div>
      <div id="{sid}_tr_lh"
           style="position:absolute;top:50%;transform:translate(-50%,-50%);
                  width:11px;height:22px;background:#FFFFFF;
                  border:1.5px solid #64748B;border-radius:3px;
                  cursor:ew-resize;z-index:3;box-shadow:0 1px 5px rgba(0,0,0,.22);
                  display:flex;align-items:center;justify-content:center;gap:2px;">
        <div style="width:1.5px;height:10px;background:#94A3B8;border-radius:1px;"></div>
        <div style="width:1.5px;height:10px;background:#94A3B8;border-radius:1px;"></div>
      </div>
      <div id="{sid}_tr_rh"
           style="position:absolute;top:50%;transform:translate(-50%,-50%);
                  width:11px;height:22px;background:#FFFFFF;
                  border:1.5px solid #64748B;border-radius:3px;
                  cursor:ew-resize;z-index:3;box-shadow:0 1px 5px rgba(0,0,0,.22);
                  display:flex;align-items:center;justify-content:center;gap:2px;">
        <div style="width:1.5px;height:10px;background:#94A3B8;border-radius:1px;"></div>
        <div style="width:1.5px;height:10px;background:#94A3B8;border-radius:1px;"></div>
      </div>
    </div>
    <div id="{sid}_tr_ticks"
         style="position:relative;height:18px;margin-top:0;font-size:10px;
                color:#94A3B8;font-family:'IBM Plex Mono',monospace;overflow:visible;"></div>
  </div>

  <!-- ── Main plot area ── -->
  <div style="display:grid;grid-template-columns:minmax(0,1fr) 410px;
              gap:18px;align-items:start;width:100%;overflow:visible;">
    <div class="sled-main" style="min-width:0;overflow:visible;">
      <div id="{sid}_plot" style="height:{self.height}px;width:100%;"></div>
      <div id="{sid}_legend" style="display:flex;flex-wrap:wrap;gap:6px 12px;padding:8px 0 0;margin-top:4px;font-family:'IBM Plex Mono',monospace;font-size:11px;"></div>
    </div>
    <div class="led-detail-inner" id="{sid}_card"
         style="padding:18px;min-height:{self.height - 40}px;max-height:none;
                overflow:visible;box-sizing:border-box;"></div>
  </div>
</div>

<!-- ── Filter Drawer overlay ── -->
<div id="{sid}_drawer_overlay"
     style="position:fixed;inset:0;background:rgba(15,23,42,0.30);z-index:1000;
            display:none;backdrop-filter:blur(1px);transition:opacity .2s;">
</div>

<!-- ── Filter Drawer panel ── -->
<div id="{sid}_drawer"
     style="position:fixed;right:0;top:0;height:100vh;width:340px;
            background:#FFFFFF;z-index:1001;
            transform:translateX(100%);
            transition:transform .25s cubic-bezier(.4,0,.2,1);
            overflow-y:auto;box-shadow:-4px 0 32px rgba(15,23,42,0.18);
            font-family:'IBM Plex Mono',monospace;">
  <div style="padding:20px 20px 40px;">

    <!-- Drawer header -->
    <div style="display:flex;justify-content:space-between;align-items:center;
                margin-bottom:20px;padding-bottom:12px;border-bottom:2px solid #E5E7EB;">
      <span style="font-weight:800;font-size:13px;color:#0F172A;letter-spacing:.06em;">
        ⚙ FILTRES AVANCÉS
      </span>
      <button id="{sid}_drawer_close"
              style="background:none;border:1px solid #E2E8F0;border-radius:6px;
                     padding:4px 10px;cursor:pointer;font-size:13px;color:#64748B;
                     font-family:'IBM Plex Mono',monospace;transition:background .15s;">✕</button>
    </div>

    <!-- TARGET + RECORDS toggles -->
    <div style="display:flex;flex-direction:column;gap:10px;margin-bottom:20px;
                padding-bottom:16px;border-bottom:1px solid #F1F5F9;">
      <div style="display:flex;align-items:center;">
        {target_toggle}
      </div>
      <div style="display:flex;align-items:center;">
        {record_toggle}
      </div>
    </div>

    <!-- Optical sensor checkboxes -->
    <div style="margin-bottom:20px;">
      <div style="font-size:10px;font-weight:800;color:#94A3B8;letter-spacing:.10em;
                  text-transform:uppercase;margin-bottom:10px;">OPTICAL SENSOR</div>
      <div id="{sid}_optical_checks" style="display:flex;flex-wrap:wrap;gap:6px;"></div>
    </div>

    <!-- EPI RUN TYPE checkboxes -->
    <div>
      <div style="font-size:10px;font-weight:800;color:#94A3B8;letter-spacing:.10em;
                  text-transform:uppercase;margin-bottom:10px;">EPI RUN TYPE</div>
      <div id="{sid}_epi_checks" style="display:flex;flex-wrap:wrap;gap:6px;"></div>
    </div>

  </div>
</div>

<script>
(function() {{
  {data_init}
  var KPI_LIST = {kpi_json};
  var FILTERS = {filters_json};
  var TARGET_ZONES = {targets_json};
  var OPTICAL_VALUES = {optical_json};
  var EPI_VALUES = {epi_json};
  var WAFER_VALUES = {wafer_json};
  var LOT_VALUES = {lot_json};

  var sid = "{sid}";
  var xCol = "{x_col}";
  var colorCol = "{color_col}";
  var waferCol = "{wafer_col}";
  var dateCol = "{date_col}";
  var opticalCol = "{optical_col}";
  var epiCol = "{epi_col}";

  var MONTHS = ["Jan","Fev","Mar","Avr","Mai","Juin","Juil","Aou","Sep","Oct","Nov","Dec"];
  var currentMode = {default_mode_js};
  var champMode = false;
  var showTargets = true;
  var waferSelected = [];
  var lotSelected = [];

  var btnBox = document.getElementById(sid + "_btn_box");
  var btnScatter = document.getElementById(sid + "_btn_scatter");
  var ctrlBox = document.getElementById(sid + "_ctrl_box");
  var ctrlScatter = document.getElementById(sid + "_ctrl_scatter");
  var kpiSelect = document.getElementById(sid + "_kpi");
  var xSelect = document.getElementById(sid + "_x");
  var ySelect = document.getElementById(sid + "_y");
  var logXCheck = document.getElementById(sid + "_logx");
  var logYCheck = document.getElementById(sid + "_logy");
  var filterSelect = document.getElementById(sid + "_filter");
  var opticalChecks = document.getElementById(sid + "_optical_checks");
  var epiChecks = document.getElementById(sid + "_epi_checks");
  var plotDiv = document.getElementById(sid + "_plot");
  var cardDiv = document.getElementById(sid + "_card");
  var allTimeBtn = document.getElementById(sid + "_all_time");
  var btnPts = document.getElementById(sid + "_btn_pts");
  var targetToggle = document.getElementById(sid + "_toggle_target");
  var recordToggle = document.getElementById(sid + "_toggle_record");

  var lotBtn = document.getElementById(sid + "_lot_btn");
  var lotDd = document.getElementById(sid + "_lot_dd");
  var lotSearch = document.getElementById(sid + "_lot_search");
  var lotList = document.getElementById(sid + "_lot_list");
  var lotLabel = document.getElementById(sid + "_lot_label");
  var lotClr = document.getElementById(sid + "_lot_clr");
  var waferBtn = document.getElementById(sid + "_wafer_btn");
  var waferDd = document.getElementById(sid + "_wafer_dd");
  var waferSearch = document.getElementById(sid + "_wafer_search");
  var waferList = document.getElementById(sid + "_wafer_list");
  var waferLabel = document.getElementById(sid + "_wafer_label");
  var waferClr = document.getElementById(sid + "_wafer_clr");

  var trTrack = document.getElementById(sid + "_tr_track");
  var trFill = document.getElementById(sid + "_tr_fill");
  var trLH = document.getElementById(sid + "_tr_lh");
  var trRH = document.getElementById(sid + "_tr_rh");
  var trLabel = document.getElementById(sid + "_tr_label");
  var trTicks = document.getElementById(sid + "_tr_ticks");
  var trCanvas = document.getElementById(sid + "_tr_canvas");
  var legendDiv = document.getElementById(sid + "_legend");

  // ── Drawer elements ──
  var drawerOverlay = document.getElementById(sid + "_drawer_overlay");
  var drawer = document.getElementById(sid + "_drawer");
  var btnFilters = document.getElementById(sid + "_btn_filters");
  var drawerClose = document.getElementById(sid + "_drawer_close");
  var filterBadge = document.getElementById(sid + "_filter_badge");

  var PLYCFG = {{ responsive:true, displaylogo:false, modeBarButtonsToRemove:["sendDataToCloud"] }};

  KPI_LIST.forEach(function(kpi) {{
    [kpiSelect, xSelect, ySelect].forEach(function(sel) {{
      var option = document.createElement("option");
      option.value = kpi;
      option.textContent = kpi;
      sel.appendChild(option);
    }});
  }});
  xSelect.value = "{_h.escape(default_x)}";
  ySelect.value = "{_h.escape(default_y)}";

  Object.keys(FILTERS).forEach(function(name) {{
    var option = document.createElement("option");
    option.value = name;
    option.textContent = name;
    filterSelect.appendChild(option);
  }});

  // ── Build optical sensor checkboxes (inside drawer) ──
  OPTICAL_VALUES.forEach(function(value) {{
    var label = document.createElement("label");
    label.style.cssText =
      "display:inline-flex;align-items:center;gap:5px;padding:5px 9px;" +
      "border:1px solid #CBD5E1;border-radius:999px;background:#F8FAFC;" +
      "font-size:12px;cursor:pointer;color:#0F172A;";
    var checkbox = document.createElement("input");
    checkbox.type = "checkbox";
    checkbox.className = sid + "_optical_cb";
    checkbox.value = value;
    checkbox.checked = true;
    checkbox.addEventListener("change", function() {{
      updateFilterBadge();
      updatePlot();
    }});
    var span = document.createElement("span");
    span.textContent = value;
    label.appendChild(checkbox);
    label.appendChild(span);
    opticalChecks.appendChild(label);
  }});

  // ── Build epi run type checkboxes (inside drawer) ──
  EPI_VALUES.forEach(function(value) {{
    var label = document.createElement("label");
    label.style.cssText =
      "display:inline-flex;align-items:center;gap:5px;padding:5px 9px;" +
      "border:1px solid #CBD5E1;border-radius:999px;background:#F8FAFC;" +
      "font-size:12px;cursor:pointer;color:#0F172A;";
    var checkbox = document.createElement("input");
    checkbox.type = "checkbox";
    checkbox.className = sid + "_epi_cb";
    checkbox.value = value;
    checkbox.checked = true;
    checkbox.addEventListener("change", function() {{
      updateFilterBadge();
      updatePlot();
    }});
    var span = document.createElement("span");
    span.textContent = value;
    label.appendChild(checkbox);
    label.appendChild(span);
    epiChecks.appendChild(label);
  }});

  // ── Drawer open / close ──
  function openDrawer() {{
    drawerOverlay.style.display = "block";
    // Force reflow then transition
    requestAnimationFrame(function() {{
      drawer.style.transform = "translateX(0)";
    }});
  }}
  function closeDrawer() {{
    drawer.style.transform = "translateX(100%)";
    drawerOverlay.style.display = "none";
  }}
  btnFilters.addEventListener("click", openDrawer);
  drawerOverlay.addEventListener("click", closeDrawer);
  drawerClose.addEventListener("click", closeDrawer);

  // Close drawer on Escape
  document.addEventListener("keydown", function(event) {{
    if (event.key === "Escape") closeDrawer();
  }});

  // ── Badge: count active filter deviations from default ──
  function updateFilterBadge() {{
    var count = 0;
    // Unchecked optical sensors
    document.querySelectorAll("." + sid + "_optical_cb").forEach(function(cb) {{
      if (!cb.checked) count++;
    }});
    // Unchecked epi types
    document.querySelectorAll("." + sid + "_epi_cb").forEach(function(cb) {{
      if (!cb.checked) count++;
    }});
    // TARGET off = deviation
    if (!showTargets) count++;
    // RECORDS on = active filter
    if (champMode) count++;
    if (waferSelected.length) count++;
    if (lotSelected.length) count++;
    if (count > 0) {{
      filterBadge.style.display = "inline-block";
      filterBadge.textContent = count;
    }} else {{
      filterBadge.style.display = "none";
    }}
  }}

  function updateToggleButton(button, enabled, disabled) {{
    if (!button) return;
    var knob = button.querySelector("span");
    button.setAttribute("aria-pressed", enabled ? "true" : "false");
    button.disabled = !!disabled;
    button.style.background = disabled ? "#CBD5E1" : (enabled ? "#0F766E" : "#CBD5E1");
    button.style.opacity = disabled ? "0.55" : "1";
    button.style.cursor = disabled ? "not-allowed" : "pointer";
    if (knob) knob.style.left = enabled ? "18px" : "2px";
  }}

  function syncToggleButtons() {{
    updateToggleButton(targetToggle, showTargets, false);
    updateToggleButton(recordToggle, champMode, currentMode !== "box");
    updateFilterBadge();
  }}

  function setMode(mode) {{
    currentMode = mode;
    ctrlBox.style.display = mode === "box" ? "flex" : "none";
    ctrlScatter.style.display = mode === "scatter" ? "flex" : "none";
    btnBox.classList.toggle("active", mode === "box");
    btnScatter.classList.toggle("active", mode === "scatter");
    syncToggleButtons();
    updatePlot();
  }}
  btnBox.addEventListener("click", function() {{ setMode("box"); }});
  btnScatter.addEventListener("click", function() {{ setMode("scatter"); }});

  var ptsStates = ["all", "outliers", false];
  var ptsLabels = ["POINTS", "OUTLIERS", "NO PTS"];
  var ptsIndex = 0;
  btnPts.addEventListener("click", function() {{
    ptsIndex = (ptsIndex + 1) % ptsStates.length;
    btnPts.textContent = ptsLabels[ptsIndex];
    btnPts.classList.toggle("active", ptsIndex === 0);
    updatePlot();
  }});

  targetToggle.addEventListener("click", function() {{
    showTargets = !showTargets;
    syncToggleButtons();
    updatePlot();
  }});
  recordToggle.addEventListener("click", function() {{
    if (currentMode !== "box") return;
    champMode = !champMode;
    syncToggleButtons();
    updatePlot();
  }});

  // ── Generic multi-select dropdown ─────────────────────────
  function buildMultiSelect(values, selected, listEl, query, onUpdate) {{
    var lower = (query || "").toLowerCase();
    var hits = lower
      ? values.filter(function(v) {{ return v.toLowerCase().indexOf(lower) >= 0; }})
      : values;
    listEl.innerHTML = "";
    hits.slice(0, 100).forEach(function(value) {{
      var item = document.createElement("label");
      item.style.cssText = "display:flex;align-items:center;gap:8px;padding:5px 10px;cursor:pointer;color:#0F172A;white-space:nowrap;";
      var cb = document.createElement("input");
      cb.type = "checkbox";
      cb.checked = selected.indexOf(value) >= 0;
      cb.style.flexShrink = "0";
      item.appendChild(cb);
      item.appendChild(document.createTextNode(value));
      item.addEventListener("mouseover", function() {{ item.style.background = "#F1F5F9"; }});
      item.addEventListener("mouseout", function() {{ item.style.background = ""; }});
      cb.addEventListener("change", function(e) {{
        e.stopPropagation();
        if (cb.checked) {{ if (selected.indexOf(value) < 0) selected.push(value); }}
        else {{ var i = selected.indexOf(value); if (i >= 0) selected.splice(i, 1); }}
        if (onUpdate) onUpdate();
        updatePlot();
      }});
      listEl.appendChild(item);
    }});
  }}

  function updateMultiLabel(selected, labelEl, clrEl, pluralText) {{
    if (selected.length === 0) {{
      labelEl.textContent = "Tous les " + pluralText;
      clrEl.style.display = "none";
    }} else if (selected.length === 1) {{
      labelEl.textContent = selected[0];
      clrEl.style.display = "inline";
    }} else {{
      labelEl.textContent = selected.length + " " + pluralText;
      clrEl.style.display = "inline";
    }}
  }}

  function setupMultiDropdown(btnEl, ddEl, searchEl, listEl, labelEl, clrEl, values, selected, pluralText) {{
    var onUpdate = function() {{
      updateMultiLabel(selected, labelEl, clrEl, pluralText);
      updateFilterBadge();
    }};
    btnEl.addEventListener("click", function(e) {{
      e.stopPropagation();
      var isOpen = ddEl.style.display !== "none";
      [lotDd, waferDd].forEach(function(dd) {{ dd.style.display = "none"; }});
      if (!isOpen) {{
        searchEl.value = "";
        buildMultiSelect(values, selected, listEl, "", onUpdate);
        updateMultiLabel(selected, labelEl, clrEl, pluralText);
        ddEl.style.display = "block";
        setTimeout(function() {{ searchEl.focus(); }}, 30);
      }}
    }});
    btnEl.addEventListener("keydown", function(e) {{
      if (e.key === "Enter" || e.key === " ") {{ btnEl.click(); e.preventDefault(); }}
      if (e.key === "Escape") {{ ddEl.style.display = "none"; }}
    }});
    searchEl.addEventListener("input", function() {{
      buildMultiSelect(values, selected, listEl, searchEl.value, onUpdate);
    }});
    searchEl.addEventListener("keydown", function(e) {{
      if (e.key === "Escape") {{ ddEl.style.display = "none"; btnEl.focus(); }}
    }});
    ddEl.addEventListener("click", function(e) {{ e.stopPropagation(); }});
    clrEl.addEventListener("click", function(e) {{
      e.stopPropagation();
      selected.splice(0, selected.length);
      buildMultiSelect(values, selected, listEl, "", onUpdate);
      onUpdate();
      updatePlot();
    }});
  }}

  document.addEventListener("click", function() {{
    [lotDd, waferDd].forEach(function(dd) {{ dd.style.display = "none"; }});
  }});

  setupMultiDropdown(lotBtn, lotDd, lotSearch, lotList, lotLabel, lotClr, LOT_VALUES, lotSelected, "lots");
  setupMultiDropdown(waferBtn, waferDd, waferSearch, waferList, waferLabel, waferClr, WAFER_VALUES, waferSelected, "wafers");

  function isNum(value) {{
    return value !== null && value !== undefined && value !== "" && !isNaN(Number(value));
  }}
  function fmt(value) {{
    if (value === null || value === undefined || isNaN(value)) return "-";
    return Number(value).toPrecision(4);
  }}
  function escapeHtml(value) {{
    return String(value)
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;")
      .replaceAll("'", "&#039;");
  }}
  function fmtDate(date) {{
    if (!date) return "?";
    return date.getDate() + " " + MONTHS[date.getMonth()] + " " + date.getFullYear();
  }}
  function parseDate(row) {{
    var raw = row[dateCol] || row["last_update"];
    if (!raw) return null;
    var date = new Date(raw);
    return isNaN(date.getTime()) ? null : date;
  }}
  function median(values) {{
    var numbers = values.filter(isNum).map(Number).sort(function(left, right) {{ return left - right; }});
    if (!numbers.length) return null;
    var mid = Math.floor(numbers.length / 2);
    return numbers.length % 2 ? numbers[mid] : (numbers[mid - 1] + numbers[mid]) / 2;
  }}
  function mean(values) {{
    var numbers = values.filter(isNum).map(Number);
    if (!numbers.length) return null;
    return numbers.reduce(function(sum, value) {{ return sum + value; }}, 0) / numbers.length;
  }}
  function std(values) {{
    var numbers = values.filter(isNum).map(Number);
    if (numbers.length < 2) return null;
    var avg = mean(numbers);
    return Math.sqrt(numbers.reduce(function(sum, value) {{ return sum + Math.pow(value - avg, 2); }}, 0) / (numbers.length - 1));
  }}
  function groupBy(data, column) {{
    var out = {{}};
    data.forEach(function(row) {{
      var key = row[column] || "Unknown";
      if (!out[key]) out[key] = [];
      out[key].push(row);
    }});
    return out;
  }}
  function selectedOpticalSensors() {{
    var selected = [];
    document.querySelectorAll("." + sid + "_optical_cb:checked").forEach(function(checkbox) {{
      selected.push(checkbox.value);
    }});
    return selected;
  }}
  function selectedEpiTypes() {{
    var selected = [];
    document.querySelectorAll("." + sid + "_epi_cb:checked").forEach(function(checkbox) {{
      selected.push(checkbox.value);
    }});
    return selected;
  }}

  function rgbaFromHex(hex, alpha) {{
    var normalized = String(hex || "#64748B").replace("#", "");
    if (normalized.length === 3) {{
      normalized = normalized.split("").map(function(ch) {{ return ch + ch; }}).join("");
    }}
    var red = parseInt(normalized.slice(0, 2), 16);
    var green = parseInt(normalized.slice(2, 4), 16);
    var blue = parseInt(normalized.slice(4, 6), 16);
    return "rgba(" + red + "," + green + "," + blue + "," + alpha + ")";
  }}

  function buildLotColorMap(data) {{
    var palette = [
      "#0F766E", "#DC2626", "#2563EB", "#D97706", "#7C3AED", "#059669",
      "#DB2777", "#0891B2", "#65A30D", "#4F46E5", "#C2410C", "#334155"
    ];
    var map = {{}};
    var lots = Array.from(new Set(data.map(function(row) {{
      return String(row[colorCol] || "Unknown");
    }}))).sort();
    lots.forEach(function(lot, index) {{
      map[lot] = palette[index % palette.length];
    }});
    return map;
  }}

  var LOT_COLOR_MAP = buildLotColorMap(DATA);

  var TR = {{ dataMin:null, dataMax:null, p0:0, p1:1 }};
  var trDrag = {{ on:false, type:null, x0:0, p0:0, p1:0 }};

  function trInit() {{
    var dates = DATA.map(parseDate).filter(Boolean);
    if (!dates.length) {{ trLabel.textContent = "Pas de dates"; return; }}
    var timestamps = dates.map(function(date) {{ return date.getTime(); }});
    TR.dataMin = new Date(Math.min.apply(null, timestamps));
    TR.dataMax = new Date(Math.max.apply(null, timestamps));
    TR.p0 = 0;
    TR.p1 = 1;
    trBuildTicks();
    setTimeout(trDrawHistogram, 20);
    trRedraw();
  }}
  function trToDate(position) {{
    var span = TR.dataMax.getTime() - TR.dataMin.getTime();
    return new Date(TR.dataMin.getTime() + position * span);
  }}
  function trFmtLabel(date) {{
    if (!TR.dataMin || !TR.dataMax) return "";
    var span = TR.dataMax.getTime() - TR.dataMin.getTime();
    var days = span / 864e5;
    var hours = String(date.getHours()).padStart(2, "0");
    var minutes = String(date.getMinutes()).padStart(2, "0");
    if (days <= 2) return date.getDate() + " " + MONTHS[date.getMonth()] + " " + hours + ":" + minutes;
    if (days <= 60) return date.getDate() + " " + MONTHS[date.getMonth()] + " " + date.getFullYear();
    return MONTHS[date.getMonth()] + " " + date.getFullYear();
  }}
  function trRedraw() {{
    var left = TR.p0 * 100;
    var right = TR.p1 * 100;
    trFill.style.left = left + "%";
    trFill.style.width = (right - left) + "%";
    trLH.style.left = left + "%";
    trRH.style.left = right + "%";
    trLabel.textContent = trFmtLabel(trToDate(TR.p0)) + "  -  " + trFmtLabel(trToDate(TR.p1));
    allTimeBtn.classList.toggle("active", TR.p0 <= 0.001 && TR.p1 >= 0.999);
  }}
  function trBuildTicks() {{
    trTicks.innerHTML = "";
    if (!TR.dataMin || !TR.dataMax) return;
    var span = TR.dataMax.getTime() - TR.dataMin.getTime();
    if (span <= 0) return;
    var DAY = 864e5;
    var WEEK = 7 * DAY;
    var HOUR = 36e5;
    var days = span / DAY;

    function addTick(position, isMinor, label) {{
      var element = document.createElement("div");
      element.style.cssText =
        "position:absolute;left:" + position + "%;top:0;transform:translateX(-50%);" +
        "display:flex;flex-direction:column;align-items:center;pointer-events:none;" +
        (isMinor ? "" : "z-index:2;");
      var line = document.createElement("div");
      line.style.cssText =
        "width:1px;flex-shrink:0;background:" + (isMinor ? "#C2C8D6" : "#4E5A72") + ";" +
        "height:" + (isMinor ? "4" : "8") + "px;";
      element.appendChild(line);
      if (!isMinor && label) {{
        var span = document.createElement("span");
        span.style.cssText = "white-space:nowrap;font-size:10px;color:#3D4A62;font-weight:600;margin-top:1px;";
        span.textContent = label;
        element.appendChild(span);
      }}
      trTicks.appendChild(element);
    }}

    if (days > 30) {{
      var majorTicks = [];
      var cursor = new Date(TR.dataMin.getFullYear(), TR.dataMin.getMonth(), 1, 0, 0, 0, 0);
      if (cursor.getTime() < TR.dataMin.getTime()) cursor.setMonth(cursor.getMonth() + 1);
      while (cursor.getTime() <= TR.dataMax.getTime()) {{
        majorTicks.push(cursor.getTime());
        var next = new Date(cursor);
        next.setMonth(next.getMonth() + 1);
        cursor = next;
      }}
      var dayCursor = new Date(TR.dataMin.getFullYear(), TR.dataMin.getMonth(), TR.dataMin.getDate(), 0, 0, 0, 0);
      dayCursor.setDate(dayCursor.getDate() + (1 - dayCursor.getDay() + 7) % 7);
      while (dayCursor.getTime() <= TR.dataMax.getTime()) {{
        var timestamp = dayCursor.getTime();
        var tooClose = false;
        for (var index = 0; index < majorTicks.length; index++) {{
          if (Math.abs(timestamp - majorTicks[index]) < 3 * DAY) {{ tooClose = true; break; }}
        }}
        if (!tooClose) {{
          var position = (timestamp - TR.dataMin.getTime()) / span * 100;
          if (position >= 0 && position <= 100) addTick(position, true, null);
        }}
        dayCursor = new Date(dayCursor.getTime() + WEEK);
      }}
      majorTicks.forEach(function(timestamp) {{
        var position = (timestamp - TR.dataMin.getTime()) / span * 100;
        if (position >= 0 && position <= 100) {{
          var date = new Date(timestamp);
          addTick(position, false, MONTHS[date.getMonth()] + " " + String(date.getFullYear()).slice(2));
        }}
      }});
    }} else if (days > 7) {{
      var day = new Date(TR.dataMin.getFullYear(), TR.dataMin.getMonth(), TR.dataMin.getDate(), 0, 0, 0, 0);
      if (day.getTime() < TR.dataMin.getTime()) day = new Date(day.getTime() + DAY);
      while (day.getTime() <= TR.dataMax.getTime()) {{
        var position = (day.getTime() - TR.dataMin.getTime()) / span * 100;
        if (position >= 0 && position <= 100) addTick(position, false, day.getDate() + " " + MONTHS[day.getMonth()]);
        day = new Date(day.getTime() + DAY);
      }}
    }} else if (days > 1) {{
      var HALF_DAY = 12 * HOUR;
      var cursorDay = new Date(TR.dataMin.getFullYear(), TR.dataMin.getMonth(), TR.dataMin.getDate(), 0, 0, 0, 0);
      if (cursorDay.getTime() < TR.dataMin.getTime()) cursorDay = new Date(cursorDay.getTime() + DAY);
      while (cursorDay.getTime() <= TR.dataMax.getTime()) {{
        var dayPos = (cursorDay.getTime() - TR.dataMin.getTime()) / span * 100;
        if (dayPos >= 0 && dayPos <= 100) addTick(dayPos, false, cursorDay.getDate() + " " + MONTHS[cursorDay.getMonth()]);
        var noon = new Date(cursorDay.getTime() + HALF_DAY);
        if (noon.getTime() <= TR.dataMax.getTime()) {{
          var noonPos = (noon.getTime() - TR.dataMin.getTime()) / span * 100;
          if (noonPos >= 0 && noonPos <= 100) addTick(noonPos, true, null);
        }}
        cursorDay = new Date(cursorDay.getTime() + DAY);
      }}
    }} else {{
      var targetSpan = span / 6;
      var interval = targetSpan < 2 * HOUR ? HOUR : targetSpan < 3 * HOUR ? 2 * HOUR : targetSpan < 6 * HOUR ? 3 * HOUR : 6 * HOUR;
      var start = Math.ceil(TR.dataMin.getTime() / interval) * interval;
      for (var time = start; time <= TR.dataMax.getTime(); time += interval) {{
        var position = (time - TR.dataMin.getTime()) / span * 100;
        if (position >= 0 && position <= 100) {{
          var tickDate = new Date(time);
          addTick(position, false, String(tickDate.getHours()).padStart(2, "0") + ":00");
        }}
      }}
    }}
  }}
  function trDrawHistogram() {{
    if (!trCanvas || !TR.dataMin || !TR.dataMax) return;
    var rect = trTrack.getBoundingClientRect();
    var width = Math.round(rect.width);
    var height = Math.round(rect.height);
    if (width <= 0 || height <= 0) return;
    trCanvas.width = width;
    trCanvas.height = height;
    var ctx = trCanvas.getContext("2d");
    ctx.clearRect(0, 0, width, height);
    var span = TR.dataMax.getTime() - TR.dataMin.getTime();
    if (span <= 0) return;
    var DAY = 864e5;
    var bucketMs = Math.max(DAY, span / 52);
    var bucketCount = Math.ceil(span / bucketMs);
    if (bucketCount < 1) return;
    var counts = new Array(bucketCount).fill(0);
    DATA.forEach(function(row) {{
      var date = parseDate(row);
      if (!date) return;
      var bucketIndex = Math.floor((date.getTime() - TR.dataMin.getTime()) / bucketMs);
      bucketIndex = Math.max(0, Math.min(bucketCount - 1, bucketIndex));
      counts[bucketIndex]++;
    }});
    var maxCount = Math.max.apply(null, counts);
    if (maxCount === 0) return;
    var maxBarHeight = height * 0.80;
    var barWidth = width / bucketCount;
    ctx.fillStyle = "rgba(51,65,85,0.30)";
    for (var bucket = 0; bucket < bucketCount; bucket++) {{
      if (counts[bucket] === 0) continue;
      var barHeight = Math.max(2, (counts[bucket] / maxCount) * maxBarHeight);
      ctx.fillRect(bucket * barWidth + 0.5, height - barHeight, barWidth - 1, barHeight);
    }}
  }}

  function trPointerDown(event, dragType) {{
    trDrag.on = true;
    trDrag.type = dragType;
    trDrag.x0 = event.clientX;
    trDrag.p0 = TR.p0;
    trDrag.p1 = TR.p1;
    event.preventDefault();
    event.stopPropagation();
  }}
  document.addEventListener("mousemove", function(event) {{
    if (!trDrag.on) return;
    var rect = trTrack.getBoundingClientRect();
    var dx = (event.clientX - trDrag.x0) / rect.width;
    if (trDrag.type === "L") {{
      TR.p0 = Math.max(0, Math.min(trDrag.p1 - 0.01, trDrag.p0 + dx));
    }} else if (trDrag.type === "R") {{
      TR.p1 = Math.max(trDrag.p0 + 0.01, Math.min(1, trDrag.p1 + dx));
    }} else {{
      var width = trDrag.p1 - trDrag.p0;
      var newLeft = Math.max(0, Math.min(1 - width, trDrag.p0 + dx));
      TR.p0 = newLeft;
      TR.p1 = newLeft + width;
    }}
    trRedraw();
    updatePlot();
  }});
  document.addEventListener("mouseup", function() {{ trDrag.on = false; }});
  trLH.addEventListener("mousedown", function(event) {{ trPointerDown(event, "L"); }});
  trRH.addEventListener("mousedown", function(event) {{ trPointerDown(event, "R"); }});
  trFill.addEventListener("mousedown", function(event) {{ trPointerDown(event, "F"); }});
  trTrack.addEventListener("mousedown", function(event) {{
    if (event.target !== trTrack) return;
    var rect = trTrack.getBoundingClientRect();
    var position = (event.clientX - rect.left) / rect.width;
    if (Math.abs(position - TR.p0) < Math.abs(position - TR.p1)) {{
      TR.p0 = Math.max(0, Math.min(TR.p1 - 0.01, position));
    }} else {{
      TR.p1 = Math.max(TR.p0 + 0.01, Math.min(1, position));
    }}
    trRedraw();
    updatePlot();
  }});
  allTimeBtn.addEventListener("click", function() {{
    TR.p0 = 0;
    TR.p1 = 1;
    trRedraw();
    updatePlot();
  }});

  function applyTimeFilter(data) {{
    if (!TR.dataMin || !TR.dataMax) return data;
    if (TR.p0 <= 0.001 && TR.p1 >= 0.999) return data;
    var span = TR.dataMax.getTime() - TR.dataMin.getTime();
    var minDate = new Date(TR.dataMin.getTime() + TR.p0 * span);
    var maxDate = new Date(TR.dataMin.getTime() + TR.p1 * span);
    return data.filter(function(row) {{
      var date = parseDate(row);
      return date && date >= minDate && date <= maxDate;
    }});
  }}
  function applyPresetFilters(data, name) {{
    var rules = FILTERS[name] || [];
    return data.filter(function(row) {{
      for (var index = 0; index < rules.length; index++) {{
        var rule = rules[index];
        var value = Number(row[rule.col]);
        if (!isNum(value)) return false;
        if (rule.op === ">" && !(value > rule.value)) return false;
        if (rule.op === ">=" && !(value >= rule.value)) return false;
        if (rule.op === "<" && !(value < rule.value)) return false;
        if (rule.op === "<=" && !(value <= rule.value)) return false;
        if (rule.op === "between" && !(value >= rule.min && value <= rule.max)) return false;
      }}
      return true;
    }});
  }}
  function applyLotFilter(data) {{
    if (!lotSelected.length) return data;
    return data.filter(function(row) {{ return lotSelected.indexOf(String(row[colorCol])) >= 0; }});
  }}
  function applyWaferFilter(data) {{
    if (!waferSelected.length) return data;
    return data.filter(function(row) {{ return waferSelected.indexOf(String(row[waferCol])) >= 0; }});
  }}
  function applyOpticalFilter(data) {{
    var selected = selectedOpticalSensors();
    if (!OPTICAL_VALUES.length) return data;
    if (!selected.length) return [];
    return data.filter(function(row) {{ return selected.indexOf(String(row[opticalCol])) >= 0; }});
  }}
  function applyEpiFilter(data) {{
    var selected = selectedEpiTypes();
    if (!EPI_VALUES.length) return data;
    if (!selected.length) return [];
    return data.filter(function(row) {{ return selected.indexOf(String(row[epiCol])) >= 0; }});
  }}
  function applyAllFilters(data) {{
    var filtered = applyTimeFilter(data);
    filtered = applyPresetFilters(filtered, filterSelect.value);
    filtered = applyLotFilter(filtered);
    filtered = applyWaferFilter(filtered);
    filtered = applyOpticalFilter(filtered);
    return applyEpiFilter(filtered);
  }}

  function filterDescription() {{
    var parts = [];
    if (currentMode === "box") {{
      parts.push("KPI : " + kpiSelect.value + ".");
    }} else {{
      parts.push(ySelect.value.replaceAll("_", " ") + " vs " + xSelect.value.replaceAll("_", " ") + ".");
    }}
    var rules = FILTERS[filterSelect.value] || [];
    parts.push(rules.length ? "Preset : " + filterSelect.value + "." : "Aucun preset.");
    parts.push(lotSelected.length ? "Lots : " + lotSelected.join(", ") + "." : "Tous les lots.");
    parts.push(waferSelected.length ? "Wafers : " + waferSelected.join(", ") + "." : "Tous les wafers.");
    var sensors = selectedOpticalSensors();
    parts.push(sensors.length ? "Sensors : " + sensors.join(", ") + "." : "Aucun sensor.");
    var epiTypes = selectedEpiTypes();
    parts.push(epiTypes.length ? "Epi types : " + epiTypes.join(", ") + "." : "Aucun epi type.");
    parts.push(showTargets ? "Targets : actives." : "Targets : masquees.");
    if (currentMode === "box") parts.push(champMode ? "Suivi d'amélioration : actifs." : "Suivi d'amélioration : desactives.");
    if (TR.dataMin && TR.dataMax && !(TR.p0 <= 0.001 && TR.p1 >= 0.999)) {{
      parts.push("Periode : " + trFmtLabel(trToDate(TR.p0)) + " - " + trFmtLabel(trToDate(TR.p1)) + ".");
    }} else {{
      parts.push("Periode : tout l'historique.");
    }}
    return parts.join(" ");
  }}

  function computeChampionWafers(data, eqeCol) {{
    var eqeColumn = eqeCol || "max_EQE";
    var groups = groupBy(data, waferCol);
    var stats = [];
    Object.keys(groups).forEach(function(wafer) {{
      var rows = groups[wafer];
      var eqeValues = rows.map(function(row) {{ return row[eqeColumn]; }});
      var med = median(eqeValues);
      if (med === null) return;
      var dates = rows.map(parseDate).filter(Boolean);
      if (!dates.length) return;
      var maxDate = new Date(Math.max.apply(null, dates.map(function(date) {{ return date.getTime(); }})));
      stats.push({{ wafer:wafer, value:med, date:maxDate }});
    }});
    stats.sort(function(left, right) {{ return left.date - right.date; }});
    var champions = [];
    var runningMax = -Infinity;
    stats.forEach(function(stat) {{
      if (stat.value > runningMax) {{
        runningMax = stat.value;
        champions.push({{ wafer:stat.wafer, value:stat.value, date:stat.date }});
      }}
    }});
    return champions;
  }}

  function buildChampHtml(champData, kpiName) {{
    if (!champData || !champData.length) return "";
    kpiName = kpiName || "max_EQE";
    var html =
      '<div style="margin-bottom:14px;padding:12px 14px;border-radius:14px;' +
      'background:linear-gradient(135deg,#F0FDF4,#ECFDF5);border:1px solid #86EFAC;">' +
      '<div style="font-size:11px;color:#166534;font-weight:800;text-transform:uppercase;' +
      'letter-spacing:.08em;margin-bottom:8px;">RECORDS - ' + escapeHtml(kpiName) + '</div>';
    champData.forEach(function(champion, index) {{
      var gain = index > 0 && champData[index - 1].value > 0
        ? ' &nbsp;up&nbsp;+' + ((champion.value - champData[index - 1].value) / champData[index - 1].value * 100).toFixed(0) + '%'
        : '';
      html +=
        '<div style="display:flex;justify-content:space-between;align-items:baseline;' +
        'padding:3px 0;border-bottom:1px solid #D1FAE5;">' +
        '<span style="font-size:10px;color:#064E3B;">' +
          escapeHtml(fmtDate(champion.date)) + '&nbsp;&nbsp;<b>' + escapeHtml(champion.wafer) + '</b>' +
        '</span>' +
        '<span style="font-size:11px;font-weight:800;color:#065F46;white-space:nowrap;">' +
          escapeHtml(fmt(champion.value)) + gain +
        '</span>' +
        '</div>';
    }});
    if (champData.length > 1) {{
      var spanMs = champData[champData.length - 1].date.getTime() - champData[0].date.getTime();
      var days = Math.round(spanMs / 864e5);
      html +=
        '<div style="margin-top:6px;font-size:10px;color:#166534;">' +
        champData.length + ' records sur ' + days + ' j - gain total : x' +
        (champData[0].value > 0 ? (champData[champData.length - 1].value / champData[0].value).toFixed(2) : '-') +
        '</div>';
    }}
    html += '</div>';
    return html;
  }}

  function renderLegend(traces) {{
    var seen = {{}};
    var html = "";
    traces.forEach(function(trace) {{
      if (trace.name === "Fit lineaire") return;
      if (seen[trace.name]) return;
      seen[trace.name] = true;
      var nameParts = String(trace.name).split(" \u00b7 ");
      var epiLabel = nameParts.length > 1 ? nameParts[1] : "";
      var isMbe = epiLabel === "MBE";
      var color = (trace.type === "box")
        ? (trace.line && trace.line.color ? trace.line.color : "#64748B")
        : (trace.marker && typeof trace.marker.color === "string" ? trace.marker.color : "#64748B");
      var swatch = isMbe
        ? "<span style='display:inline-block;width:11px;height:11px;border-radius:2px;border:2px solid " + color + ";background:transparent;flex-shrink:0;'></span>"
        : "<span style='display:inline-block;width:11px;height:11px;border-radius:2px;background:" + color + ";flex-shrink:0;'></span>";
      html += "<span data-tname='" + escapeHtml(trace.name) + "'"
            + " style='display:inline-flex;align-items:center;gap:5px;padding:3px 8px;border-radius:6px;border:1px solid #E2E8F0;background:#F8FAFC;cursor:pointer;transition:opacity .15s;'>"
            + swatch
            + "<span style='color:#334155;'>" + escapeHtml(trace.name) + "</span></span>";
    }});
    legendDiv.innerHTML = html || "<span style='color:#94A3B8;'>Aucune donn\u00e9e</span>";
  }}

  legendDiv.addEventListener("click", function(event) {{
    var el = event.target.closest("[data-tname]");
    if (!el) return;
    var name = el.dataset.tname;
    var data = plotDiv.data || [];
    var idx = [];
    data.forEach(function(trace, i) {{ if (trace.name === name) idx.push(i); }});
    if (!idx.length) return;
    var isVis = data[idx[0]].visible !== false && data[idx[0]].visible !== "legendonly";
    Plotly.restyle(plotDiv, {{ visible: isVis ? "legendonly" : true }}, idx);
    el.style.opacity = isVis ? "0.38" : "1";
  }});

  function makeDesignOrder(data) {{
    var groups = groupBy(data, xCol);
    return Object.keys(groups).sort(function(left, right) {{
      function maxTimestamp(group) {{
        var timestamps = group.map(parseDate).filter(Boolean).map(function(date) {{ return date.getTime(); }});
        return timestamps.length ? Math.max.apply(null, timestamps) : null;
      }}
      var leftDate = maxTimestamp(groups[left]);
      var rightDate = maxTimestamp(groups[right]);
      if (!leftDate && !rightDate) return String(left).localeCompare(String(right));
      if (!leftDate) return 1;
      if (!rightDate) return -1;
      return leftDate - rightDate;
    }});
  }}

  function makeBoxTraces(data, kpi) {{
    var pointMode = ptsStates[ptsIndex];
    var groups = groupBy(data, colorCol);
    var lotColorMap = LOT_COLOR_MAP;
    var traces = [];
    Object.keys(groups).forEach(function(lot) {{
      var lotRows = groups[lot].filter(function(row) {{ return isNum(row[kpi]); }});
      var epiGroups = groupBy(lotRows, epiCol);
      var lotColor = lotColorMap[String(lot)] || "#64748B";
      ["MOCVD", "MBE", "Unknown"].forEach(function(epiType) {{
        var rows = epiGroups[epiType] || [];
        if (!rows.length) return;
        var isMbe = epiType === "MBE";
        var isMocvd = epiType === "MOCVD";
        traces.push({{
          type:"box",
          name:lot + " · " + epiType,
          legendgroup:String(lot),
          x:rows.map(function(row) {{ return row[xCol]; }}),
          y:rows.map(function(row) {{ return Number(row[kpi]); }}),
          boxpoints:pointMode,
          jitter:0.35,
          pointpos:0,
          marker:{{
            size:4,
            opacity:isMbe ? 0.42 : 0.32,
            color:rgbaFromHex(lotColor, isMbe ? 0.14 : 0.52),
            line:{{ width:0.8, color:lotColor }}
          }},
          line:{{ width:1.8, color:lotColor }},
          fillcolor:isMbe ? "rgba(255,255,255,0)" : rgbaFromHex(lotColor, isMocvd ? 0.42 : 0.18),
          customdata:rows.map(function(row) {{ return [row[waferCol], row[opticalCol], row[epiCol], row[dateCol], row["Led_Name"]]; }}),
          hovertemplate:
            "ID: %{{x}}<br>Lot: " + lot +
            "<br>Wafer: %{{customdata[0]}}<br>Optical: %{{customdata[1]}}" +
            "<br>Epi: %{{customdata[2]}}<br>Date: %{{customdata[3]}}<br>" + kpi + ": %{{y}}<extra></extra>"
        }});
      }});
      Object.keys(epiGroups).forEach(function(epiType) {{
        if (["MOCVD", "MBE", "Unknown"].indexOf(epiType) >= 0) return;
        var rows = epiGroups[epiType] || [];
        if (!rows.length) return;
        traces.push({{
          type:"box",
          name:lot + " · " + epiType,
          legendgroup:String(lot),
          x:rows.map(function(row) {{ return row[xCol]; }}),
          y:rows.map(function(row) {{ return Number(row[kpi]); }}),
          boxpoints:pointMode,
          jitter:0.35,
          pointpos:0,
          marker:{{ size:4, opacity:0.32, color:rgbaFromHex(lotColor, 0.22), line:{{ width:0.8, color:lotColor }} }},
          line:{{ width:1.8, color:lotColor }},
          fillcolor:rgbaFromHex(lotColor, 0.18),
          customdata:rows.map(function(row) {{ return [row[waferCol], row[opticalCol], row[epiCol], row[dateCol], row["Led_Name"]]; }}),
          hovertemplate:
            "ID: %{{x}}<br>Lot: " + lot +
            "<br>Wafer: %{{customdata[0]}}<br>Optical: %{{customdata[1]}}" +
            "<br>Epi: %{{customdata[2]}}<br>Date: %{{customdata[3]}}<br>" + kpi + ": %{{y}}<extra></extra>"
        }});
      }});
    }});
    return traces;
  }}

  function computeBoxSummary(data, kpi) {{
    var clean = data.filter(function(row) {{ return isNum(row[kpi]); }});
    if (!clean.length) return null;
    var waferGroups = groupBy(clean, waferCol);
    var waferStats = Object.keys(waferGroups).map(function(wafer) {{
      var values = waferGroups[wafer].map(function(row) {{ return row[kpi]; }});
      return {{
        wafer:wafer,
        n:values.filter(isNum).length,
        median:median(values),
        mean:mean(values),
        std:std(values)
      }};
    }}).filter(function(stat) {{ return stat.n >= 1; }});
    return {{
      n:clean.length,
      nWafers:waferStats.length,
      median:median(clean.map(function(row) {{ return row[kpi]; }})),
      std:std(clean.map(function(row) {{ return row[kpi]; }})),
      bestMedian:waferStats.slice().sort(function(left, right) {{ return right.median - left.median; }})[0],
      mostStable:waferStats.filter(function(stat) {{ return stat.std !== null; }})
        .sort(function(left, right) {{ return left.std - right.std || right.median - left.median; }})[0] || null
    }};
  }}

  function renderBoxCard(data, kpi, champData) {{
    var summary = computeBoxSummary(data, kpi);
    var description = filterDescription();
    var champHtml = buildChampHtml(champData, kpi);
    if (!summary) {{
      cardDiv.innerHTML = champHtml + "<b>No data after filtering</b>" +
        "<div style='margin-top:12px;font-size:12px;color:#64748B;'>" + escapeHtml(description) + "</div>";
      return;
    }}
    cardDiv.innerHTML = champHtml + `
      <div style="font-size:12px;color:#64748B;text-transform:uppercase;letter-spacing:.08em;">KPI affiche</div>
      <div style="font-size:24px;font-weight:800;color:#0F172A;margin-bottom:10px;line-height:1.1;">${{kpi.replaceAll("_", " ")}}</div>
      <div style="font-size:12px;color:#64748B;margin-bottom:14px;line-height:1.5;">${{escapeHtml(description)}}</div>
      <div style="display:grid;grid-template-columns:1fr 1fr;gap:10px;">
        <div style="padding:12px;border-radius:14px;background:#F8FAFC;">
          <div style="font-size:11px;color:#64748B;">Median</div>
          <div style="font-size:20px;font-weight:800;">${{fmt(summary.median)}}</div>
        </div>
        <div style="padding:12px;border-radius:14px;background:#F8FAFC;">
          <div style="font-size:11px;color:#64748B;">Std</div>
          <div style="font-size:20px;font-weight:800;">${{fmt(summary.std)}}</div>
        </div>
      </div>
      <div style="margin-top:14px;padding:14px;border-radius:16px;background:#FFF7ED;border:1px solid #FED7AA;">
        <div style="font-size:12px;color:#9A3412;">Best wafer en mediane</div>
        <div style="font-size:21px;font-weight:900;color:#7C2D12;line-height:1.15;">${{summary.bestMedian.wafer}}</div>
        <div style="font-size:13px;color:#7C2D12;margin-top:6px;line-height:1.35;">
          median=<b>${{fmt(summary.bestMedian.median)}}</b> · mean=<b>${{fmt(summary.bestMedian.mean)}}</b><br>
          std=<b>${{fmt(summary.bestMedian.std)}}</b> · n=<b>${{summary.bestMedian.n}}</b>
        </div>
      </div>
      <div style="margin-top:14px;padding:14px;border-radius:16px;background:#F8FAFC;border:1px solid #E2E8F0;">
        <div style="font-size:12px;color:#64748B;">Wafer le plus stable</div>
        <div style="font-size:21px;font-weight:900;color:#0F172A;line-height:1.15;">${{summary.mostStable ? summary.mostStable.wafer : "-"}}</div>
        <div style="font-size:13px;color:#334155;margin-top:6px;line-height:1.35;">
          std=<b>${{summary.mostStable ? fmt(summary.mostStable.std) : "-"}}</b> · median=<b>${{summary.mostStable ? fmt(summary.mostStable.median) : "-"}}</b>
        </div>
      </div>
      <div style="margin-top:16px;font-size:12px;color:#64748B;"><b>${{summary.n}}</b> points · <b>${{summary.nWafers}}</b> wafers</div>
    `;
  }}

  function pearson(xs, ys) {{
    var pairs = [];
    for (var index = 0; index < xs.length; index++) if (isNum(xs[index]) && isNum(ys[index])) pairs.push([Number(xs[index]), Number(ys[index])]);
    if (pairs.length < 3) return null;
    var xValues = pairs.map(function(pair) {{ return pair[0]; }});
    var yValues = pairs.map(function(pair) {{ return pair[1]; }});
    var meanX = mean(xValues);
    var meanY = mean(yValues);
    var numerator = 0;
    var dx = 0;
    var dy = 0;
    for (var index = 0; index < pairs.length; index++) {{
      var offsetX = xValues[index] - meanX;
      var offsetY = yValues[index] - meanY;
      numerator += offsetX * offsetY;
      dx += offsetX * offsetX;
      dy += offsetY * offsetY;
    }}
    return (dx === 0 || dy === 0) ? null : numerator / Math.sqrt(dx * dy);
  }}
  function linearFit(xs, ys) {{
    var pairs = [];
    for (var index = 0; index < xs.length; index++) if (isNum(xs[index]) && isNum(ys[index])) pairs.push([Number(xs[index]), Number(ys[index])]);
    if (pairs.length < 2) return null;
    var xValues = pairs.map(function(pair) {{ return pair[0]; }});
    var yValues = pairs.map(function(pair) {{ return pair[1]; }});
    var meanX = mean(xValues);
    var meanY = mean(yValues);
    var numerator = 0;
    var denominator = 0;
    for (var index = 0; index < pairs.length; index++) {{
      numerator += (xValues[index] - meanX) * (yValues[index] - meanY);
      denominator += Math.pow(xValues[index] - meanX, 2);
    }}
    if (denominator === 0) return null;
    var slope = numerator / denominator;
    var intercept = meanY - slope * meanX;
    var minX = Math.min.apply(null, xValues);
    var maxX = Math.max.apply(null, xValues);
    return {{ x:[minX, maxX], y:[intercept + slope * minX, intercept + slope * maxX], slope:slope, intercept:intercept }};
  }}
  function makeScatterTraces(data, xKpi, yKpi) {{
    var traces = [];
    var groups = groupBy(data, colorCol);
    Object.keys(groups).forEach(function(lot) {{
      var lotRows = groups[lot].filter(function(row) {{ return isNum(row[xKpi]) && isNum(row[yKpi]); }});
      var epiGroups = groupBy(lotRows, epiCol);
      var lotColor = LOT_COLOR_MAP[String(lot)] || "#64748B";
      ["MOCVD", "MBE", "Unknown"].forEach(function(epiType) {{
        var rows = epiGroups[epiType] || [];
        if (!rows.length) return;
        var isMbe = epiType === "MBE";
        traces.push({{
          type:"scatter",
          mode:"markers",
          name:lot + " · " + epiType,
          legendgroup:String(lot),
          x:rows.map(function(row) {{ return Number(row[xKpi]); }}),
          y:rows.map(function(row) {{ return Number(row[yKpi]); }}),
          marker:{{
            size:7,
            symbol:isMbe ? "circle-open" : "circle",
            color:lotColor,
            opacity:isMbe ? 0.90 : 0.72,
            line:{{ width:isMbe ? 2 : 0.8, color:lotColor }}
          }},
          customdata:rows.map(function(row) {{ return [row[xCol], row[waferCol], row[opticalCol], row[epiCol], row[dateCol], row["Led_Name"]]; }}),
          hovertemplate:
            "ID: %{{customdata[0]}}<br>Wafer: %{{customdata[1]}}<br>Lot: " + lot +
            "<br>Optical: %{{customdata[2]}}<br>Epi: %{{customdata[3]}}<br>Date: %{{customdata[4]}}<br>" +
            xKpi + ": %{{x}}<br>" + yKpi + ": %{{y}}<extra></extra>"
        }});
      }});
      Object.keys(epiGroups).forEach(function(epiType) {{
        if (["MOCVD", "MBE", "Unknown"].indexOf(epiType) >= 0) return;
        var rows = epiGroups[epiType] || [];
        if (!rows.length) return;
        traces.push({{
          type:"scatter",
          mode:"markers",
          name:lot + " · " + epiType,
          legendgroup:String(lot),
          x:rows.map(function(row) {{ return Number(row[xKpi]); }}),
          y:rows.map(function(row) {{ return Number(row[yKpi]); }}),
          marker:{{ size:7, symbol:"circle", color:lotColor, opacity:0.72, line:{{ width:0.8, color:lotColor }} }},
          customdata:rows.map(function(row) {{ return [row[xCol], row[waferCol], row[opticalCol], row[epiCol], row[dateCol], row["Led_Name"]]; }}),
          hovertemplate:
            "ID: %{{customdata[0]}}<br>Wafer: %{{customdata[1]}}<br>Lot: " + lot +
            "<br>Optical: %{{customdata[2]}}<br>Epi: %{{customdata[3]}}<br>Date: %{{customdata[4]}}<br>" +
            xKpi + ": %{{x}}<br>" + yKpi + ": %{{y}}<extra></extra>"
        }});
      }});
    }});
    if (!logXCheck.checked && !logYCheck.checked) {{
      var fit = linearFit(data.map(function(row) {{ return row[xKpi]; }}), data.map(function(row) {{ return row[yKpi]; }}));
      if (fit) traces.push({{ type:"scatter", mode:"lines", name:"Fit lineaire", x:fit.x, y:fit.y, line:{{ width:2, dash:"dash", color:"#0A2463" }}, hoverinfo:"skip" }});
    }}
    return traces;
  }}
  function computeScatterSummary(data, xKpi, yKpi) {{
    var clean = data.filter(function(row) {{ return isNum(row[xKpi]) && isNum(row[yKpi]); }});
    if (!clean.length) return null;
    var xValues = clean.map(function(row) {{ return row[xKpi]; }});
    var yValues = clean.map(function(row) {{ return row[yKpi]; }});
    return {{
      n:clean.length,
      nWafers:new Set(clean.map(function(row) {{ return row[waferCol]; }})).size,
      xMedian:median(xValues),
      yMedian:median(yValues),
      xStd:std(xValues),
      yStd:std(yValues),
      corr:pearson(xValues, yValues),
      fit:linearFit(xValues, yValues)
    }};
  }}
  function renderScatterCard(data, xKpi, yKpi) {{
    var summary = computeScatterSummary(data, xKpi, yKpi);
    var description = filterDescription();
    if (!summary) {{
      cardDiv.innerHTML = "<b>No data after filtering</b><div style='margin-top:12px;font-size:12px;color:#64748B;'>" + escapeHtml(description) + "</div>";
      return;
    }}
    cardDiv.innerHTML = `
      <div style="font-size:12px;color:#64748B;text-transform:uppercase;letter-spacing:.08em;">Scatter affiche</div>
      <div style="font-size:22px;font-weight:800;color:#0F172A;margin-bottom:10px;line-height:1.15;">
        ${{yKpi.replaceAll("_", " ")}}<br>
        <span style="font-size:13px;color:#64748B;">vs</span> ${{xKpi.replaceAll("_", " ")}}
      </div>
      <div style="font-size:12px;color:#64748B;margin-bottom:14px;line-height:1.5;">${{escapeHtml(description)}}</div>
      <div style="display:grid;grid-template-columns:1fr 1fr;gap:10px;">
        <div style="padding:12px;border-radius:14px;background:#F8FAFC;">
          <div style="font-size:11px;color:#64748B;">Median X</div><div style="font-size:18px;font-weight:800;">${{fmt(summary.xMedian)}}</div>
        </div>
        <div style="padding:12px;border-radius:14px;background:#F8FAFC;">
          <div style="font-size:11px;color:#64748B;">Median Y</div><div style="font-size:18px;font-weight:800;">${{fmt(summary.yMedian)}}</div>
        </div>
        <div style="padding:12px;border-radius:14px;background:#F8FAFC;">
          <div style="font-size:11px;color:#64748B;">Std X</div><div style="font-size:18px;font-weight:800;">${{fmt(summary.xStd)}}</div>
        </div>
        <div style="padding:12px;border-radius:14px;background:#F8FAFC;">
          <div style="font-size:11px;color:#64748B;">Std Y</div><div style="font-size:18px;font-weight:800;">${{fmt(summary.yStd)}}</div>
        </div>
      </div>
      <div style="margin-top:14px;padding:14px;border-radius:16px;background:#FFF7ED;border:1px solid #FED7AA;">
        <div style="font-size:12px;color:#9A3412;">Correlation Pearson</div>
        <div style="font-size:24px;font-weight:900;color:#7C2D12;line-height:1.15;">${{fmt(summary.corr)}}</div>
        <div style="font-size:13px;color:#7C2D12;margin-top:6px;">n=<b>${{summary.n}}</b> · wafers=<b>${{summary.nWafers}}</b></div>
      </div>
      <div style="margin-top:14px;padding:14px;border-radius:16px;background:#F8FAFC;border:1px solid #E2E8F0;">
        <div style="font-size:12px;color:#64748B;">Fit lineaire</div>
        <div style="font-size:13px;color:#334155;margin-top:6px;line-height:1.35;">
          slope=<b>${{summary.fit ? fmt(summary.fit.slope) : "-"}}</b><br>intercept=<b>${{summary.fit ? fmt(summary.fit.intercept) : "-"}}</b>
        </div>
      </div>
    `;
  }}

  function buildAxisTargetShapes(kpi, axis) {{
    if (!showTargets) return [];
    var zones = TARGET_ZONES[kpi] || [];
    var shapes = [];
    zones.forEach(function(zone) {{
      if (axis === "x") {{
        shapes.push({{ type:"rect", xref:"x", x0:zone.min, x1:zone.max, yref:"paper", y0:0, y1:1, fillcolor:zone.color || "rgba(34,197,94,0.14)", line:{{ width:0 }}, layer:"below" }});
        shapes.push({{ type:"line", xref:"x", x0:zone.min, x1:zone.min, yref:"paper", y0:0, y1:1, line:{{ width:1, dash:"dot", color:"rgba(15,23,42,0.35)" }}, layer:"below" }});
        shapes.push({{ type:"line", xref:"x", x0:zone.max, x1:zone.max, yref:"paper", y0:0, y1:1, line:{{ width:1, dash:"dot", color:"rgba(15,23,42,0.35)" }}, layer:"below" }});
      }} else {{
        shapes.push({{ type:"rect", xref:"paper", x0:0, x1:1, yref:"y", y0:zone.min, y1:zone.max, fillcolor:zone.color || "rgba(34,197,94,0.14)", line:{{ width:0 }}, layer:"below" }});
        shapes.push({{ type:"line", xref:"paper", x0:0, x1:1, yref:"y", y0:zone.min, y1:zone.min, line:{{ width:1, dash:"dot", color:"rgba(15,23,42,0.35)" }}, layer:"below" }});
        shapes.push({{ type:"line", xref:"paper", x0:0, x1:1, yref:"y", y0:zone.max, y1:zone.max, line:{{ width:1, dash:"dot", color:"rgba(15,23,42,0.35)" }}, layer:"below" }});
      }}
    }});
    return shapes;
  }}
  function buildAxisTargetAnnotations(kpi, axis) {{
    if (!showTargets) return [];
    var zones = TARGET_ZONES[kpi] || [];
    return zones.map(function(zone) {{
      if (axis === "x") {{
        return {{
          xref:"x",
          x:(Number(zone.min) + Number(zone.max)) / 2,
          xanchor:"center",
          yref:"paper",
          y:1,
          yanchor:"bottom",
          yshift:6,
          text:zone.label || "Target",
          showarrow:false,
          bgcolor:"rgba(255,255,255,0.70)",
          bordercolor:"rgba(15,23,42,0.18)",
          borderwidth:1,
          borderpad:3,
          font:{{ family:"IBM Plex Mono, monospace", size:10, color:"#334155" }}
        }};
      }}
      return {{
        xref:"paper",
        x:1,
        xanchor:"right",
        yref:"y",
        y:(Number(zone.min) + Number(zone.max)) / 2,
        text:zone.label || "Target",
        showarrow:false,
        bgcolor:"rgba(255,255,255,0.70)",
        bordercolor:"rgba(15,23,42,0.18)",
        borderwidth:1,
        borderpad:3,
        font:{{ family:"IBM Plex Mono, monospace", size:10, color:"#334155" }}
      }};
    }});
  }}
  function buildTargetLayout(mode, xKpi, yKpi) {{
    if (!showTargets) return {{ shapes:[], annotations:[] }};
    if (mode === "box") {{
      return {{
        shapes:buildAxisTargetShapes(yKpi, "y"),
        annotations:buildAxisTargetAnnotations(yKpi, "y")
      }};
    }}
    return {{
      shapes:buildAxisTargetShapes(yKpi, "y").concat(buildAxisTargetShapes(xKpi, "x")),
      annotations:buildAxisTargetAnnotations(yKpi, "y").concat(buildAxisTargetAnnotations(xKpi, "x"))
    }};
  }}

  function updatePlot() {{
    var filtered = applyAllFilters(DATA);
    if (currentMode === "box") {{
      var kpi = kpiSelect.value;
      var filteredRows = filtered.filter(function(row) {{ return isNum(row[kpi]); }});
      var champData = null;
      if (champMode) {{
        champData = computeChampionWafers(filteredRows, kpi);
        var championNames = champData.map(function(champion) {{ return champion.wafer; }});
        filteredRows = filteredRows.filter(function(row) {{ return championNames.indexOf(String(row[waferCol])) >= 0; }});
      }}
      var order = makeDesignOrder(filteredRows);
      var targetLayout = buildTargetLayout("box", null, kpi);
      var boxTraces = makeBoxTraces(filteredRows, kpi);
      Plotly.react(plotDiv, boxTraces, {{
        template:"plotly_white",
        height:{self.height},
        shapes:targetLayout.shapes,
        annotations:targetLayout.annotations,
        margin:{{ l:80, r:30, t:30, b:300 }},
        plot_bgcolor:"#F8F9FD",
        paper_bgcolor:"rgba(0,0,0,0)",
        font:{{ family:"IBM Plex Mono, monospace", size:11, color:"#4A5580" }},
        xaxis:{{ title:"", tickangle:-90, showgrid:false, zeroline:false, tickfont:{{ size:17 }}, categoryorder:"array", categoryarray:order }},
        yaxis:{{ title:kpi.replaceAll("_", " "), showgrid:true, gridcolor:"#E4E8F4", zeroline:false, automargin:true }},
        showlegend:false,
        boxmode:"overlay",
        boxgap:0.18,
        boxgroupgap:0.08,
        hoverlabel:{{ bgcolor:"#0A2463", bordercolor:"#D4AF37", font:{{ family:"IBM Plex Mono", size:10, color:"white" }} }}
      }}, PLYCFG);
      renderLegend(boxTraces);
      renderBoxCard(filteredRows, kpi, champData);
    }} else {{
      var xKpi = xSelect.value;
      var yKpi = ySelect.value;
      var filteredRows = filtered.filter(function(row) {{ return isNum(row[xKpi]) && isNum(row[yKpi]); }});
      var targetLayout = buildTargetLayout("scatter", xKpi, yKpi);
      var scatterTraces = makeScatterTraces(filteredRows, xKpi, yKpi);
      Plotly.react(plotDiv, scatterTraces, {{
        template:"plotly_white",
        height:{self.height},
        shapes:targetLayout.shapes,
        annotations:targetLayout.annotations,
        margin:{{ l:80, r:30, t:50, b:80 }},
        plot_bgcolor:"#F8F9FD",
        paper_bgcolor:"rgba(0,0,0,0)",
        font:{{ family:"IBM Plex Mono, monospace", size:11, color:"#4A5580" }},
        xaxis:{{ title:xKpi.replaceAll("_", " "), type:logXCheck.checked ? "log" : "linear", showgrid:true, gridcolor:"#E4E8F4", zeroline:false, automargin:true }},
        yaxis:{{ title:yKpi.replaceAll("_", " "), type:logYCheck.checked ? "log" : "linear", showgrid:true, gridcolor:"#E4E8F4", zeroline:false, automargin:true }},
        showlegend:false,
        hoverlabel:{{ bgcolor:"#0A2463", bordercolor:"#D4AF37", font:{{ family:"IBM Plex Mono", size:10, color:"white" }} }}
      }}, PLYCFG);
      renderLegend(scatterTraces);
      renderScatterCard(filteredRows, xKpi, yKpi);
    }}
    setTimeout(function() {{ Plotly.Plots.resize(plotDiv); }}, 50);
  }}

  [kpiSelect, xSelect, ySelect, filterSelect].forEach(function(element) {{
    element.addEventListener("change", updatePlot);
  }});
  [logXCheck, logYCheck].forEach(function(element) {{
    element.addEventListener("change", updatePlot);
  }});
  window.addEventListener("resize", function() {{ Plotly.Plots.resize(plotDiv); trDrawHistogram(); }});

  syncToggleButtons();
  trInit();
  setMode(currentMode);
}})();
</script>
"""


class KPIBoxPlotHistory(KPIExplorer):
    def __init__(self, data, *, x_col: str = "id", **kwargs):
        kwargs.setdefault("default_mode", "box")
        super().__init__(data, x_col=x_col, **kwargs)


class KPIScatterHistory(KPIExplorer):
    def __init__(self, data, **kwargs):
        kwargs.setdefault("default_mode", "scatter")
        super().__init__(data, **kwargs)
