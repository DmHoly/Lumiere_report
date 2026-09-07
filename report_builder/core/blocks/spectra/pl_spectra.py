from __future__ import annotations
import json
import html as _h
import pandas as pd
from ..._helpers import Block, _safe_json
from ..data.data_mixin import DataMixin, DataArg


class PLSpectraBlock(DataMixin, Block):
    """
    Bloc interactif PL Spectra.

    Le df attendu est un df_merge qui contient à la fois les colonnes
    spectra (wavelength, Intensity_norm, kpi_id) et les colonnes KPI
    (sample, device, field, Laser power, lambda_dom, …).

    Une ligne = un point spectre (wavelength, Intensity_norm) lié à un kpi_id.

    Utilisation
    -----------
    # Passage direct
    report.add(PLSpectraBlock(df_merge, color_col="Laser power"))

    # Passage par store
    report.data.register("PDPL", df_merge)
    report.add(PLSpectraBlock("PDPL", color_col="Laser power"))

    Paramètres
    ----------
    data            : DataFrame ou clé store — df_merge avec cols spectra + KPI
    color_col       : colonne numérique utilisée pour l'échelle de couleur
    color_log       : True → échelle log pour la colormap
    kpi1_default    : KPI affiché par défaut dans le panel 1
    kpi2_default    : KPI affiché par défaut dans le panel 2
    offset_step     : décalage vertical entre spectres
    height          : hauteur totale du bloc en px
    kpi_cols        : liste des colonnes KPI proposées dans les dropdowns
                      (si None, on prend la liste par défaut)
    wavelength_col  : nom de la colonne wavelength dans df_merge
    intensity_col   : nom de la colonne intensity normalisée dans df_merge
    kpi_id_col      : nom de la colonne de clé spectre→kpi
    sample_col      : nom de la colonne sample
    device_col      : nom de la colonne device
    field_col       : nom de la colonne field
    title           : titre du bloc
    num             : numéro de bloc (optionnel)
    """

    needs_plotly = True

    DEFAULT_KPI_CANDIDATES = [
        "lambda_dom", "saturation", "FWHM", "Centroid",
        "Efficiency", "main_peak_area", "LER",
        "Max Height", "Mathematical Area",
        "LWHM", "RWHM", "laser OD",
    ]

    def __init__(
        self,
        data: DataArg,
        color_col: str = "Laser power",
        color_log: bool = True,
        kpi1_default: str = "lambda_dom",
        kpi2_default: str = "saturation",
        offset_step: float = 0.3,
        height: int = 580,
        kpi_cols: list[str] | None = None,
        wavelength_col: str = "wavelength",
        intensity_col: str = "Intensity_norm",
        kpi_id_col: str = "kpi_id",
        sample_col: str = "sample",
        device_col: str = "device",
        field_col: str = "field",
        title: str = "PL Spectra",
        num: str = "",
    ):
        self._init_data(data)
        self.color_col     = color_col
        self.color_log     = color_log
        self.kpi1_default  = kpi1_default
        self.kpi2_default  = kpi2_default
        self.offset_step   = offset_step
        self.height        = height
        self.kpi_cols      = kpi_cols
        self.wavelength_col = wavelength_col
        self.intensity_col  = intensity_col
        self.kpi_id_col    = kpi_id_col
        self.sample_col    = sample_col
        self.device_col    = device_col
        self.field_col     = field_col
        self.title         = title
        self.num           = num
        self._id           = f"plspectra_{id(self)}"

    # ─────────────────────────────────────────────────────────
    # Sérialisation
    # ─────────────────────────────────────────────────────────

    def _build_payload(self, df: pd.DataFrame) -> tuple[str, str, str, str, str]:
        """
        Retourne (groups_json, kpi_cols_json, samples_json, color_col_json, boxplot_json).
        """
        wl_col  = self.wavelength_col
        int_col = self.intensity_col
        kid_col = self.kpi_id_col
        s_col   = self.sample_col
        d_col   = self.device_col
        f_col   = self.field_col
        c_col   = self.color_col

        # Vérification colonnes requises
        for col in [wl_col, int_col, kid_col, s_col, d_col, f_col, c_col]:
            if col not in df.columns:
                raise ValueError(f"PLSpectraBlock : colonne manquante → '{col}'")

        # Colonnes KPI disponibles
        candidates = self.kpi_cols or self.DEFAULT_KPI_CANDIDATES
        available_kpi = [
            c for c in candidates
            if c in df.columns and c != c_col
        ]

        all_groups: dict[str, dict] = {}
        samples_order: list[str] = []

        for sample, df_s in df.groupby(s_col, sort=False):
            samples_order.append(str(sample))

            for (device, field), grp in df_s.groupby([d_col, f_col], sort=False):
                key = f"{sample}||{device}||{field}"

                # Métadonnées par kpi_id, triées par color_col
                kpi_meta_cols = [kid_col, c_col] + [
                    c for c in available_kpi if c in grp.columns
                ]
                kpi_meta = (
                    grp.drop_duplicates(kid_col)
                    .sort_values(c_col)[kpi_meta_cols]
                    .reset_index(drop=True)
                )

                # Spectres
                spectra: list[dict] = []
                for i, row in kpi_meta.iterrows():
                    kid  = row[kid_col]
                    cval = _safe_json(row[c_col])
                    sub  = grp[grp[kid_col] == kid].sort_values(wl_col)
                    spectra.append({
                        "kpi_id":    str(kid),
                        "cval":      cval,
                        "offset":    round(i * self.offset_step, 4),
                        "wl":        [_safe_json(v) for v in sub[wl_col].tolist()],
                        "intensity": [_safe_json(v) for v in sub[int_col].tolist()],
                    })

                # KPI rows (1 ligne par kpi_id)
                kpi_rows = [
                    {
                        c: _safe_json(row[c])
                        for c in kpi_meta_cols
                        if c in row.index
                    }
                    for _, row in kpi_meta.iterrows()
                ]

                all_groups[key] = {
                    "sample":   str(sample),
                    "device":   str(device),
                    "field":    str(field),
                    "spectra":  spectra,
                    "kpi_rows": kpi_rows,
                }

        # ── Données boxplot : tous samples × toutes puissances ──
        # On travaille sur df dédupliqué par kpi_id (1 ligne par mesure)
        df_kpi_unique = (
            df.drop_duplicates(kid_col)
            [[s_col, c_col] + [c for c in available_kpi if c in df.columns]]
            .copy()
        )
        # Structure : { sample: { color_val: { kpi_col: [values...] } } }
        # Pour le slider on a besoin de la liste des puissances uniques triées
        all_cvals_sorted = sorted(df_kpi_unique[c_col].dropna().unique().tolist())

        boxplot_by_sample: dict[str, list[dict]] = {}
        for sample, grp in df_kpi_unique.groupby(s_col, sort=False):
            rows = []
            for _, row in grp.iterrows():
                entry = {c_col: _safe_json(row[c_col])}
                for kc in available_kpi:
                    if kc in row.index:
                        entry[kc] = _safe_json(row[kc])
                rows.append(entry)
            boxplot_by_sample[str(sample)] = rows

        boxplot_data = {
            "by_sample":  boxplot_by_sample,
            "cvals":      [_safe_json(v) for v in all_cvals_sorted],
            "samples":    samples_order,
        }

        return (
            json.dumps(all_groups, default=_safe_json),
            json.dumps(available_kpi),
            json.dumps(samples_order),
            json.dumps(self.color_col),
            json.dumps(boxplot_data, default=_safe_json),
        )

    # ─────────────────────────────────────────────────────────
    # Render
    # ─────────────────────────────────────────────────────────

    def render(self, store=None) -> str:
        df = self.resolve_df(store)
        groups_json, kpi_cols_json, samples_json, color_col_json, boxplot_json = \
            self._build_payload(df)

        uid       = self._id
        kpi1_def  = json.dumps(self.kpi1_default)
        kpi2_def  = json.dumps(self.kpi2_default)
        color_log = json.dumps(self.color_log)
        h         = self.height
        title_h   = _h.escape(self.title)
        num_h     = _h.escape(self.num)
        sel_st    = self._sel_style()

        header_html = ""
        if num_h or title_h:
            header_html = (
                f'<div class="led-block-header">'
                f'<span class="led-block-num">{num_h}</span>'
                f'<span class="led-block-title">{title_h}</span>'
                f'</div><div class="led-block-rule"></div>'
            )

        return f"""
<!-- PLSpectraBlock {uid} -->
<div class="led-block" id="{uid}_wrap">
  {header_html}

  <div style="background:#fff;border-radius:10px;
              box-shadow:0 2px 14px rgba(0,0,0,.07);
              padding:16px 18px 14px;margin:8px 0;
              font-family:'IBM Plex Mono',monospace;
              font-size:12px;color:#222;">

    <!-- ── Toolbar ──────────────────────────────────────── -->
    <div style="display:flex;align-items:center;gap:12px;
                margin-bottom:14px;flex-wrap:wrap;">

      <label style="display:flex;align-items:center;gap:5px;">
        <span style="{self._lbl_style()}">Sample</span>
        <select id="{uid}_sample" style="{sel_st}"></select>
      </label>

      <label style="display:flex;align-items:center;gap:5px;">
        <span style="{self._lbl_style()}">Device / Field</span>
        <select id="{uid}_group" style="{sel_st}"></select>
      </label>

      <div style="width:1px;height:20px;background:#ddd;margin:0 2px;"></div>

      <label style="display:flex;align-items:center;gap:5px;">
        <span style="{self._lbl_style()}">Color</span>
        <select id="{uid}_ccol" style="{sel_st}">
          <option value="{_h.escape(self.color_col)}">{_h.escape(self.color_col)}</option>
        </select>
      </label>

      <label style="display:flex;align-items:center;gap:5px;">
        <span style="{self._lbl_style()}">KPI 1</span>
        <select id="{uid}_k1" style="{sel_st}"></select>
      </label>

      <label style="display:flex;align-items:center;gap:5px;">
        <span style="{self._lbl_style()}">KPI 2</span>
        <select id="{uid}_k2" style="{sel_st}"></select>
      </label>

      <span id="{uid}_hint"
            style="margin-left:auto;font-size:10px;opacity:.38;font-style:italic;">
        Clic sur KPI → highlight spectre
      </span>

    </div>

    <!-- ── Charts ────────────────────────────────────────── -->
    <div style="display:grid;grid-template-columns:2fr 1fr;gap:10px;height:{h}px;">

      <div style="background:#fafafa;border-radius:8px;
                  border:1px solid #eee;overflow:hidden;">
        <div id="{uid}_spectra" style="width:100%;height:100%;"></div>
      </div>

      <div style="display:grid;grid-template-rows:1fr 1fr;gap:10px;">
        <div style="background:#fafafa;border-radius:8px;
                    border:1px solid #eee;overflow:hidden;">
          <div id="{uid}_kpi1" style="width:100%;height:100%;"></div>
        </div>
        <div style="background:#fafafa;border-radius:8px;
                    border:1px solid #eee;overflow:hidden;">
          <div id="{uid}_kpi2" style="width:100%;height:100%;"></div>
        </div>
      </div>

    </div>
  </div><!-- fin carte spectre -->

  <!-- ── Carte Boxplot ──────────────────────────────────── -->
  <div style="background:#fff;border-radius:10px;
              box-shadow:0 2px 14px rgba(0,0,0,.07);
              padding:16px 18px 14px;margin:8px 0;
              font-family:'IBM Plex Mono',monospace;
              font-size:12px;color:#222;">

    <!-- Toolbar boxplot -->
    <div style="display:flex;align-items:center;gap:12px;margin-bottom:14px;flex-wrap:wrap;">

      <span style="font-weight:700;font-size:12px;letter-spacing:.04em;opacity:.7;">
        BOXPLOT — tous samples
      </span>

      <label style="display:flex;align-items:center;gap:5px;">
        <span style="{self._lbl_style()}">KPI</span>
        <select id="{uid}_bx_kpi" style="{sel_st}"></select>
      </label>

      <div style="width:1px;height:20px;background:#ddd;margin:0 2px;"></div>

      <div style="display:flex;align-items:flex-start;gap:8px;flex-wrap:wrap;flex:1;">
        <span style="{self._lbl_style()};white-space:nowrap;margin-top:3px;">
          {_h.escape(self.color_col)}
        </span>
        <!-- boutons tout/rien -->
        <button id="{uid}_btn_all"
                style="{self._pill_btn_style()}">Tout</button>
        <button id="{uid}_btn_none"
                style="{self._pill_btn_style()}">Aucun</button>
        <!-- pills checkboxes générées en JS -->
        <div id="{uid}_cb_wrap"
             style="display:flex;flex-wrap:wrap;gap:4px;align-items:center;">
        </div>
      </div>

      <span id="{uid}_bx_count"
            style="font-size:10px;opacity:.45;white-space:nowrap;margin-left:auto;"></span>

    </div>

    <!-- Boxplot chart -->
    <div style="background:#fafafa;border-radius:8px;border:1px solid #eee;overflow:hidden;">
      <div id="{uid}_boxplot" style="width:100%;height:320px;"></div>
    </div>

  </div><!-- fin carte boxplot -->

</div><!-- fin led-block -->

<script>(function(){{
  var GROUPS    = {groups_json};
  var KPI_COLS  = {kpi_cols_json};
  var SAMPLES   = {samples_json};
  var COLOR_COL = {color_col_json};
  var COLOR_LOG = {color_log};
  var BPDATA    = {boxplot_json};
  var uid = "{uid}";

  var elSample = document.getElementById(uid+"_sample");
  var elGroup  = document.getElementById(uid+"_group");
  var elK1     = document.getElementById(uid+"_k1");
  var elK2     = document.getElementById(uid+"_k2");
  var elHint   = document.getElementById(uid+"_hint");

  var _highlighted = null;
  var PLYCFG = {{responsive:true, displaylogo:false}};

  // ── KPI dropdowns (spectre) ──────────────────────────────
  KPI_COLS.forEach(function(c){{
    [elK1, elK2].forEach(function(el){{
      var o = document.createElement("option");
      o.value = c; o.textContent = c; el.appendChild(o);
    }});
  }});
  if({kpi1_def} && KPI_COLS.indexOf({kpi1_def}) >= 0) elK1.value = {kpi1_def};
  if({kpi2_def} && KPI_COLS.indexOf({kpi2_def}) >= 0) elK2.value = {kpi2_def};

  // ── Boxplot KPI dropdown ─────────────────────────────────
  var elBxKpi = document.getElementById(uid+"_bx_kpi");
  KPI_COLS.forEach(function(c){{
    var o = document.createElement("option");
    o.value = c; o.textContent = c; elBxKpi.appendChild(o);
  }});
  if({kpi1_def} && KPI_COLS.indexOf({kpi1_def}) >= 0) elBxKpi.value = {kpi1_def};

  // ── Checkboxes puissance ─────────────────────────────────
  var CVALS   = BPDATA.cvals;
  var elCbWrap = document.getElementById(uid+"_cb_wrap");
  var elBxCnt  = document.getElementById(uid+"_bx_count");
  var _cbState = {{}};   // {{ cval_str: true/false }}

  function fmtCval(v){{
    if(v == null) return "—";
    if(Math.abs(v) === 0) return "0";
    if(Math.abs(v) < 1e-2 || Math.abs(v) >= 1e4) return v.toExponential(1);
    return v.toPrecision(3);
  }}

  // Génère les pills checkbox
  CVALS.forEach(function(cv){{
    var key = String(cv);
    _cbState[key] = true;   // tout coché par défaut

    var pill = document.createElement("label");
    pill.style.cssText = "display:inline-flex;align-items:center;gap:3px;cursor:pointer;font-size:10px;padding:2px 7px;border-radius:20px;border:1px solid #ccc;background:#f5f5f5;color:#444;user-select:none;transition:all .12s;";
    pill.setAttribute("data-key", key);

    var cb = document.createElement("input");
    cb.type = "checkbox";
    cb.checked = true;
    cb.style.cssText = "width:10px;height:10px;cursor:pointer;accent-color:#4a90d9;";

    var lbl = document.createElement("span");
    lbl.textContent = fmtCval(cv);

    pill.appendChild(cb);
    pill.appendChild(lbl);

    cb.addEventListener("change", function(){{
      _cbState[key] = cb.checked;
      pill.style.background  = cb.checked ? "#ddeeff" : "#f5f5f5";
      pill.style.borderColor = cb.checked ? "#4a90d9" : "#ccc";
      pill.style.color       = cb.checked ? "#1a5fa8" : "#999";
      renderBoxplot();
    }});

    // Style initial (coché)
    pill.style.background  = "#ddeeff";
    pill.style.borderColor = "#4a90d9";
    pill.style.color       = "#1a5fa8";

    elCbWrap.appendChild(pill);
  }});

  // Tout / Aucun
  window[uid+"_cbAll"] = function(state){{
    elCbWrap.querySelectorAll("input[type=checkbox]").forEach(function(cb){{
      var key = cb.closest("label").getAttribute("data-key");
      cb.checked = state;
      _cbState[key] = state;
      var pill = cb.closest("label");
      pill.style.background  = state ? "#ddeeff" : "#f5f5f5";
      pill.style.borderColor = state ? "#4a90d9" : "#ccc";
      pill.style.color       = state ? "#1a5fa8" : "#999";
    }});
    renderBoxplot();
  }};

  document.getElementById(uid+"_btn_all").addEventListener("click", function(){{
    window[uid+"_cbAll"](true);
  }});
  document.getElementById(uid+"_btn_none").addEventListener("click", function(){{
    window[uid+"_cbAll"](false);
  }});

  function getSelectedCvals(){{
    return CVALS.filter(function(cv){{ return _cbState[String(cv)]; }});
  }}

  // ── Boxplot render ───────────────────────────────────────
  var BP_COLORS = [
    "#4477aa","#ee6677","#228833","#ccbb44",
    "#66ccee","#aa3377","#bbbbbb","#f5a623",
  ];

  function renderBoxplot(){{
    var kpi      = elBxKpi.value;
    var selected = getSelectedCvals();
    var selSet   = new Set(selected.map(String));

    var traces   = [];
    var totalPts = 0;

    BPDATA.samples.forEach(function(sample, si){{
      var rows = BPDATA.by_sample[sample];
      if(!rows) return;

      var ys = rows
        .filter(function(r){{
          return r[COLOR_COL] != null && selSet.has(String(r[COLOR_COL]));
        }})
        .map(function(r){{ return r[kpi]; }})
        .filter(function(v){{ return v != null && !isNaN(v); }});

      totalPts += ys.length;
      var col = BP_COLORS[si % BP_COLORS.length];

      traces.push({{
        type: "box",
        y: ys,
        name: sample,
        boxpoints: ys.length <= 60 ? "all" : "outliers",
        jitter: 0.35,
        pointpos: 0,
        marker: {{ color: col, size: 4, opacity: 0.65 }},
        line:   {{ color: col, width: 1.5 }},
        fillcolor: col + "26",   // ~15% opacity hex
        showlegend: true,
      }});
    }});

    var selN = selected.length;
    elBxCnt.textContent = totalPts + " pts · " + selN + " valeur" +
      (selN > 1 ? "s" : "") + " sélectionnée" + (selN > 1 ? "s" : "");

    Plotly.react(uid+"_boxplot", traces, {{
      margin: {{ t:20, r:20, b:60, l:60 }},
      yaxis: {{
        title: kpi,
        tickfont: {{ size:10 }},
        gridcolor: "#eee",
        zeroline: false,
      }},
      xaxis: {{
        tickfont: {{ size:10 }},
        gridcolor: "#eee",
      }},
      paper_bgcolor: "transparent",
      plot_bgcolor:  "transparent",
      legend: {{ font: {{ size:10 }}, orientation:"h", y:-0.18 }},
      boxmode: "group",
    }}, PLYCFG);
  }}

  elBxKpi.addEventListener("change", renderBoxplot);
  renderBoxplot();

  // ── Sample dropdown ──────────────────────────────────────
  SAMPLES.forEach(function(s){{
    var o = document.createElement("option");
    o.value = s; o.textContent = s; elSample.appendChild(o);
  }});

  // ── Group dropdown (filtré par sample) ───────────────────
  function fillGroups(){{
    elGroup.innerHTML = "";
    var sample = elSample.value;
    Object.keys(GROUPS).forEach(function(k){{
      var g = GROUPS[k];
      if(g.sample !== sample) return;
      var o = document.createElement("option");
      o.value = k;
      o.textContent = g.device + " / " + g.field;
      elGroup.appendChild(o);
    }});
    _highlighted = null;
    render();
  }}

  // ── Colormap rainbow ─────────────────────────────────────
  function rainbow(t){{
    var h = (1 - Math.max(0, Math.min(1, t))) * 270;
    return "hsl(" + h.toFixed(1) + ",88%,45%)";
  }}
  function normVal(v, vmin, vmax){{
    if(COLOR_LOG){{
      if(vmin <= 0 || vmax <= 0 || vmin === vmax) return 0;
      return (Math.log10(v) - Math.log10(vmin)) /
             (Math.log10(vmax) - Math.log10(vmin));
    }}
    if(vmin === vmax) return 0;
    return (v - vmin) / (vmax - vmin);
  }}

  // ── Render ───────────────────────────────────────────────
  function render(){{
    var key  = elGroup.value;
    var kpi1 = elK1.value;
    var kpi2 = elK2.value;
    var g    = GROUPS[key];
    if(!g) return;

    var spectra  = g.spectra;
    var kpiRows  = g.kpi_rows;
    var cvals    = spectra.map(function(s){{ return s.cval; }});
    var cmin     = Math.min.apply(null, cvals);
    var cmax     = Math.max.apply(null, cvals);

    // ── Traces spectre ───────────────────────────────────────
    var tracesS = spectra.map(function(s){{
      var col = rainbow(normVal(s.cval, cmin, cmax));
      var ys  = s.intensity.map(function(v){{ return v + s.offset; }});
      return {{
        x: s.wl,
        y: ys,
        mode: "lines",
        line: {{ color: col, width: 1.5 }},
        _kpi_id:     s.kpi_id,
        _base_color: col,
        hovertemplate:
          "<b>%{{x:.1f}} nm</b><br>Int: %{{y:.3f}}<br>" +
          COLOR_COL + ": " + (s.cval.toExponential ? s.cval.toExponential(2) : s.cval) +
          "<extra></extra>",
        showlegend: false,
      }};
    }});

    // Dummy trace pour colorbar
    var logVals = cvals.map(function(v){{
      return COLOR_LOG ? Math.log10(Math.max(v, 1e-30)) : v;
    }});
    var lmin = Math.min.apply(null, logVals);
    var lmax = Math.max.apply(null, logVals);
    var cbExtra = {{}};
    if(COLOR_LOG){{
      var tvs=[], tts=[];
      for(var p=Math.ceil(lmin); p<=Math.floor(lmax); p++){{
        tvs.push(p); tts.push("10^"+p);
      }}
      if(tvs.length){{ cbExtra.tickvals=tvs; cbExtra.ticktext=tts; }}
    }}
    tracesS.push({{
      x:[null], y:[null], mode:"markers",
      marker: Object.assign({{
        color: [lmin, lmax],
        colorscale: "Rainbow",
        showscale: true,
        cmin: lmin, cmax: lmax,
        colorbar: Object.assign({{
          title: {{ text: COLOR_COL, side: "right" }},
          thickness: 12, len: 0.65,
          tickfont: {{ size: 9 }},
        }}, cbExtra),
      }}),
      hoverinfo: "skip", showlegend: false,
    }});

    Plotly.react(uid+"_spectra", tracesS, {{
      margin: {{ t:24, r:90, b:44, l:24 }},
      xaxis: {{
        title: "Wavelength (nm)",
        tickfont: {{ size:10 }},
        gridcolor: "#eee",
      }},
      yaxis: {{ visible: false }},
      paper_bgcolor: "transparent",
      plot_bgcolor:  "transparent",
      hovermode: "closest",
    }}, PLYCFG);

    // ── KPI traces ───────────────────────────────────────────
    function buildKpi(col){{
      return [{{
        x: kpiRows.map(function(r){{ return r[COLOR_COL]; }}),
        y: kpiRows.map(function(r){{ return r[col]; }}),
        mode: "markers",
        marker: {{
          color: kpiRows.map(function(r){{
            return rainbow(normVal(r[COLOR_COL], cmin, cmax));
          }}),
          size: 8,
          line: {{ width:1, color:"#fff" }},
        }},
        customdata: kpiRows.map(function(r){{ return r["kpi_id"]; }}),
        hovertemplate: "%{{x:.2e}}<br>"+col+": %{{y:.3f}}<extra></extra>",
        showlegend: false,
      }}];
    }}

    function kpiLayout(col){{
      return {{
        margin: {{ t:24, r:10, b:44, l:54 }},
        xaxis: {{
          type: COLOR_LOG ? "log" : "linear",
          title: COLOR_COL,
          tickfont: {{ size:9 }},
          gridcolor: "#eee",
        }},
        yaxis: {{
          title: col,
          tickfont: {{ size:9 }},
          gridcolor: "#eee",
        }},
        paper_bgcolor: "transparent",
        plot_bgcolor:  "transparent",
      }};
    }}

    // ── Highlight ────────────────────────────────────────────
    function highlightSpectre(kid){{
      var n    = spectra.length;
      var idxs = spectra.map(function(_, i){{ return i; }});
      if(_highlighted === kid){{
        _highlighted = null;
        Plotly.restyle(uid+"_spectra",
          {{ "line.width": Array(n).fill(1.5), "opacity": Array(n).fill(1) }},
          idxs);
        elHint.textContent = "Clic sur KPI → highlight spectre";
      }} else {{
        _highlighted = kid;
        var ws=[], ops=[];
        spectra.forEach(function(s){{
          var m = (s.kpi_id === kid);
          ws.push(m ? 3 : 1);
          ops.push(m ? 1 : 0.1);
        }});
        Plotly.restyle(uid+"_spectra",
          {{ "line.width": ws, "opacity": ops }}, idxs);
        var row = kpiRows.find(function(r){{ return r["kpi_id"] === kid; }});
        var lbl = row
          ? (COLOR_COL + ": " + (row[COLOR_COL].toExponential
              ? row[COLOR_COL].toExponential(2)
              : row[COLOR_COL]))
          : kid;
        elHint.textContent = "● " + lbl + "  — clic pour déselectionner";
      }}
    }}

    // Attacher les clics KPI après react (Promise)
    Promise.all([
      Plotly.react(uid+"_kpi1", buildKpi(kpi1), kpiLayout(kpi1), PLYCFG),
      Plotly.react(uid+"_kpi2", buildKpi(kpi2), kpiLayout(kpi2), PLYCFG),
    ]).then(function(){{
      [uid+"_kpi1", uid+"_kpi2"].forEach(function(divId){{
        document.getElementById(divId).on("plotly_click", function(evt){{
          if(!evt||!evt.points||!evt.points.length) return;
          var kid = evt.points[0].customdata;
          if(kid != null) highlightSpectre(kid);
        }});
      }});
    }});
  }}

  // ── Events ───────────────────────────────────────────────
  elSample.addEventListener("change", fillGroups);
  elGroup.addEventListener("change",  function(){{ _highlighted=null; render(); }});
  elK1.addEventListener("change",     render);
  elK2.addEventListener("change",     render);

  fillGroups();

}})();
</script>
"""

    @staticmethod
    def _sel_style() -> str:
        return (
            "font-size:11px;padding:3px 8px;border-radius:5px;"
            "border:1px solid #ddd;background:#fff;color:#222;"
            "font-family:'IBM Plex Mono',monospace;cursor:pointer;outline:none;"
        )

    @staticmethod
    def _pill_btn_style() -> str:
        return (
            "font-size:10px;padding:2px 8px;border-radius:20px;"
            "border:1px solid #ccc;background:#f0f0f0;color:#555;"
            "cursor:pointer;font-family:'IBM Plex Mono',monospace;"
            "transition:all .12s;"
        )

    @staticmethod
    def _lbl_style() -> str:
        return (
            "opacity:.5;font-size:10px;"
            "text-transform:uppercase;letter-spacing:.05em;"
        )