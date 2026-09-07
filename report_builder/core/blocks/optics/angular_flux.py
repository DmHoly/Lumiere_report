from __future__ import annotations
import json
import html as _h
from ..._helpers import Block, _safe_json, _is_vector_col
from ..data.data_mixin import DataMixin, DataArg


class AngularFluxBlock(DataMixin, Block):
    """
    Explorateur interactif de mesures goniomètre (Farfield angulaire).

    Params:
        data        : DataArg — une ligne par mesure : key_col, wafer_col,
                      pos_x_col, pos_y_col, current_col, ratio_col, lambda_col, date_col
        cubes       : dict[key -> summary] — sortie de
                      report_builder.goniometre.analysis.build_measurement_summary,
                      une entrée par mesure, keyée par la même valeur que key_col.
                      Payload hiérarchique non-tabulaire → injecté directement en
                      JSON (pas via DataStore).
        ratio_angle : angle par défaut (°) pour le KPI ratio (défaut 12°)
    """
    needs_plotly = True

    def __init__(
        self,
        data: DataArg,
        cubes: dict,
        key_col: str = "key",
        wafer_col: str = "wafername",
        pos_x_col: str = "pos_x",
        pos_y_col: str = "pos_y",
        current_col: str = "current_mA",
        ratio_col: str = "ratio_12deg",
        lambda_col: str = "lambda_dominant",
        date_col: str = "date",
        current_label_col: str = "current_label",
        process_col: str = "epi_run_type",
        qt_name_col: str = "qt_name",
        eqe_col: str = "eqe_region_median",
        ratio_angle: float = 12.0,
        height: int = 380,
        num: str = "—",
        title: str = "Farfield goniomètre",
        subtitle: str = "",
    ):
        self._init_data(data)
        self.cubes = cubes or {}
        self.key_col = key_col
        self.wafer_col = wafer_col
        self.pos_x_col = pos_x_col
        self.pos_y_col = pos_y_col
        self.current_col = current_col
        self.ratio_col = ratio_col
        self.lambda_col = lambda_col
        self.date_col = date_col
        self.current_label_col = current_label_col
        self.process_col = process_col
        self.qt_name_col = qt_name_col
        self.eqe_col = eqe_col
        self.ratio_angle = ratio_angle
        self.height = height
        self.num = num
        self.title = title
        self.subtitle = subtitle
        self._id = f"af_{id(self)}"

    def render(self, store=None) -> str:
        bid = self._id
        need_cols = [
            self.key_col, self.wafer_col, self.pos_x_col, self.pos_y_col,
            self.current_col, self.ratio_col, self.lambda_col, self.date_col,
            self.current_label_col, self.process_col, self.qt_name_col, self.eqe_col,
        ]

        if self.has_local_data:
            df = self.resolve_df()
            cols = [c for c in need_cols if c in df.columns]
            recs = [
                {c: _safe_json(row[c]) for c in cols if not _is_vector_col(df[c])}
                for _, row in df[cols].iterrows()
            ]
            data_expr = json.dumps(recs)
        else:
            key = self._data_arg
            if store is None:
                raise RuntimeError(
                    f"AngularFluxBlock references store key {key!r} but no DataStore was provided."
                )
            store.resolve(key)  # valide que la clé existe
            data_expr = f"(window.__DATA_STORE__||{{}})[{json.dumps(key)}]||[]"

        cubes_json = json.dumps(self.cubes)
        cfg = {
            "keyCol": self.key_col, "waferCol": self.wafer_col,
            "posXCol": self.pos_x_col, "posYCol": self.pos_y_col,
            "currentCol": self.current_col, "ratioCol": self.ratio_col,
            "lambdaCol": self.lambda_col, "dateCol": self.date_col,
            "currentLabelCol": self.current_label_col,
            "processCol": self.process_col, "qtNameCol": self.qt_name_col, "eqeCol": self.eqe_col,
            "ratioAngle": self.ratio_angle,
        }
        cfg_json = json.dumps(cfg)
        h_px = self.height

        return f"""
<div class="led-block" id="{bid}_wrap">
  <div class="led-block-header">
    <span class="led-block-num">{_h.escape(self.num)}</span>
    <span class="led-block-title">{_h.escape(self.title)}</span>
    <span class="led-block-sub">{_h.escape(self.subtitle)}</span>
  </div>
  <div class="led-block-rule"></div>

  <div style="padding:16px;">
    <div style="display:flex;align-items:center;gap:10px;flex-wrap:wrap;margin-bottom:14px;">
      <div class="wm-select-wrap">
        <span class="wm-tool-label">Wafer</span>
        <select class="wm-select" id="{bid}_sel_wafer" onchange="window['{bid}_onWafer'](this.value)"></select>
      </div>
      <div class="wm-select-wrap">
        <span class="wm-tool-label">Position</span>
        <select class="wm-select" id="{bid}_sel_pos" onchange="window['{bid}_onPos'](this.value)"></select>
      </div>
      <div class="wm-select-wrap">
        <span class="wm-tool-label">Courant</span>
        <select class="wm-select" id="{bid}_sel_current" onchange="window['{bid}_onCurrent'](this.value)"></select>
      </div>
      <div class="wm-sep"></div>
      <button class="wm-btn" id="{bid}_cmp_toggle" onclick="window['{bid}_toggleCompare']()">⇄ Comparer 2 mesures</button>
      <span id="{bid}_cmp_status" style="font-family:'IBM Plex Mono',monospace;font-size:9px;color:#8896BB;"></span>
    </div>

    <div class="wm-kpi-agg-grid" id="{bid}_kpis" style="margin-bottom:14px;">
      <div class="wm-kpi-agg"><div class="wm-kpi-agg-label">Ratio à <span id="{bid}_angle_lbl">12</span>°</div><div class="wm-kpi-agg-val" id="{bid}_kpi_ratio">—</div></div>
      <div class="wm-kpi-agg"><div class="wm-kpi-agg-label">λ dominant</div><div class="wm-kpi-agg-val" id="{bid}_kpi_lambda">—</div></div>
      <div class="wm-kpi-agg"><div class="wm-kpi-agg-label">Courant</div><div class="wm-kpi-agg-val" id="{bid}_kpi_current">—</div></div>
      <div class="wm-kpi-agg" style="display:flex;flex-direction:column;gap:4px;">
        <div class="wm-kpi-agg-label">Angle custom</div>
        <div style="display:flex;gap:4px;align-items:center;">
          <input type="number" id="{bid}_angle_input" value="12" min="1" max="89" step="1"
            style="width:56px;font-family:'IBM Plex Mono',monospace;font-size:11px;padding:2px 4px;border:1px solid rgba(10,36,99,.25);border-radius:4px;">
          <button class="wm-btn" onclick="window['{bid}_recalcRatio']()">↻</button>
        </div>
      </div>
    </div>

    <div style="display:grid;grid-template-columns:1fr 1fr;gap:12px;margin-bottom:12px;">
      <div class="wafer-card-map">
        <div class="wm-tool-label" style="padding:6px 8px;">Farfield 3D</div>
        <div id="{bid}_ff3d" style="height:{h_px}px;"></div>
      </div>
      <div class="wafer-card-map">
        <div class="wm-tool-label" style="padding:6px 8px;">Farfield 2D vs Lambertienne</div>
        <div id="{bid}_ff2d" style="height:{h_px}px;"></div>
      </div>
    </div>

    <div style="display:grid;grid-template-columns:1fr 1fr;gap:12px;margin-bottom:12px;">
      <div class="wafer-card-map">
        <div class="wm-tool-label" style="padding:6px 8px;">Flux cumulé</div>
        <div id="{bid}_flux" style="height:{h_px}px;"></div>
      </div>
      <div class="wafer-card-map">
        <div style="display:flex;align-items:center;gap:8px;padding:6px 8px;">
          <span class="wm-tool-label" style="padding:0;">Diagramme de bande — φ = <span id="{bid}_phi_lbl">—</span>°</span>
        </div>
        <div id="{bid}_band" style="height:{h_px - 34}px;"></div>
        <div style="padding:4px 10px;">
          <input type="range" id="{bid}_phi_slider" min="0" max="0" value="0" style="width:100%;"
            oninput="window['{bid}_onPhiSlider'](this.value)">
        </div>
      </div>
    </div>

    <div class="wafer-card-map" style="margin-bottom:12px;">
      <div class="wm-tool-label" style="padding:6px 8px;">Spectre intégré 0°–<span id="{bid}_spec_angle_lbl">12</span>° (toutes phi, échantillonnage bande)</div>
      <div id="{bid}_spec_int" style="height:{h_px}px;"></div>
    </div>

    <div style="display:grid;grid-template-columns:1fr 1fr;gap:12px;">
      <div class="wafer-card-map">
        <div class="wm-tool-label" style="padding:6px 8px;">Comparaison des mesures — λ dominant vs ratio (taille = courant, ■ MOCVD / ● MBE)</div>
        <div id="{bid}_compare" style="height:{h_px}px;"></div>
      </div>
      <div class="wafer-card-map">
        <div class="wm-tool-label" style="padding:6px 8px;">EQE médian (zone) vs ratio (taille = courant, ■ MOCVD / ● MBE)</div>
        <div id="{bid}_eqe" style="height:{h_px}px;"></div>
      </div>
    </div>

    <div id="{bid}_cmp_wrap" style="display:none;margin-top:12px;">
      <div class="wm-tool-label" style="padding:6px 0;">Comparaison — mode actif : cliquer 2 points sur les graphes ci-dessus</div>
      <div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:12px;">
        <div class="wafer-card-map">
          <div class="wm-tool-label" style="padding:6px 8px;">Spectre (normalisé)</div>
          <div id="{bid}_cmp_spectrum" style="height:{h_px}px;"></div>
        </div>
        <div class="wafer-card-map">
          <div class="wm-tool-label" style="padding:6px 8px;">Farfield 2D</div>
          <div id="{bid}_cmp_farfield" style="height:{h_px}px;"></div>
        </div>
        <div class="wafer-card-map">
          <div class="wm-tool-label" style="padding:6px 8px;">Flux cumulé</div>
          <div id="{bid}_cmp_flux" style="height:{h_px}px;"></div>
        </div>
      </div>
    </div>
  </div>
</div>

<script>
(function(){{
  var bid = "{bid}";
  var CFG = {cfg_json};
  var DATA = {data_expr};
  var CUBES = {cubes_json};

  var PLYCFG = {{responsive:true,displaylogo:false,modeBarButtonsToRemove:["autoScale2d","toggleSpikelines","sendDataToCloud"]}};
  var GSTYLE = {{gridcolor:"#E4E8F4",linecolor:"#E4E8F4",zerolinecolor:"#E4E8F4"}};
  var BASE_LAYOUT = {{
    paper_bgcolor:"rgba(0,0,0,0)",plot_bgcolor:"#F8F9FD",
    font:{{family:"IBM Plex Mono,monospace",color:"#4A5580",size:10}},
    margin:{{t:20,r:16,b:44,l:52}},
  }};

  var st = {{ wafer:null, posKey:null, current:null, phiIdx:0, cube:null, angle: CFG.ratioAngle||12,
              compareMode:false, compareKeys:[] }};

  function uniq(arr){{ var seen={{}},out=[]; arr.forEach(function(v){{var k=String(v);if(!seen[k]){{seen[k]=true;out.push(v);}}}}); return out; }}
  function rowsForWafer(w){{ return DATA.filter(function(r){{return String(r[CFG.waferCol])===String(w);}}); }}
  function posKeyOf(r){{ return r[CFG.posXCol]+"_"+r[CFG.posYCol]; }}
  function rowsForPos(w,pk){{ return rowsForWafer(w).filter(function(r){{return posKeyOf(r)===pk;}}); }}
  function findRow(w,pk,cur){{
    var rows = rowsForPos(w,pk);
    for(var i=0;i<rows.length;i++){{ if(String(rows[i][CFG.currentCol])===String(cur)) return rows[i]; }}
    return rows[0]||null;
  }}
  function rowForKey(key){{ return DATA.filter(function(r){{return String(r[CFG.keyCol])===String(key);}})[0]; }}
  function labelForRow(r){{
    if(!r) return "?";
    var cur = r[CFG.currentLabelCol]||(r[CFG.currentCol]+"mA");
    return r[CFG.waferCol]+" X="+r[CFG.posXCol]+" Y="+r[CFG.posYCol]+" "+cur;
  }}

  function fillSelect(sel, values, labelFn){{
    sel.innerHTML="";
    values.forEach(function(v){{
      var o=document.createElement("option");
      o.value=String(v); o.textContent=labelFn?labelFn(v):String(v);
      sel.appendChild(o);
    }});
  }}

  function initWaferSelect(){{
    var wafers = uniq(DATA.map(function(r){{return r[CFG.waferCol];}})).sort();
    fillSelect(document.getElementById(bid+"_sel_wafer"), wafers);
    st.wafer = wafers[0]||null;
    initPosSelect();
  }}

  function initPosSelect(){{
    var rows = rowsForWafer(st.wafer);
    var posKeys = uniq(rows.map(posKeyOf));
    fillSelect(document.getElementById(bid+"_sel_pos"), posKeys, function(pk){{
      var r = rows.filter(function(r){{return posKeyOf(r)===pk;}})[0];
      return "X="+r[CFG.posXCol]+" Y="+r[CFG.posYCol];
    }});
    st.posKey = posKeys[0]||null;
    initCurrentSelect();
  }}

  function initCurrentSelect(){{
    var rows = rowsForPos(st.wafer, st.posKey);
    var currents = uniq(rows.map(function(r){{return r[CFG.currentCol];}})).sort(function(a,b){{return a-b;}});
    fillSelect(document.getElementById(bid+"_sel_current"), currents, function(c){{
      var r = rows.filter(function(r){{return String(r[CFG.currentCol])===String(c);}})[0];
      return (r && r[CFG.currentLabelCol]) ? r[CFG.currentLabelCol] : c+" mA";
    }});
    st.current = currents[0]||null;
    loadSelection();
  }}

  window[bid+"_onWafer"] = function(v){{ st.wafer=v; initPosSelect(); }};
  window[bid+"_onPos"] = function(v){{ st.posKey=v; initCurrentSelect(); }};
  window[bid+"_onCurrent"] = function(v){{ st.current=v; loadSelection(); }};

  function loadSelection(){{
    var row = findRow(st.wafer, st.posKey, st.current);
    if(!row){{ return; }}
    var cube = CUBES[row[CFG.keyCol]];
    st.cube = cube;
    st.phiIdx = 0;
    if(!cube) return;

    document.getElementById(bid+"_kpi_lambda").textContent = row[CFG.lambdaCol]!=null?Number(row[CFG.lambdaCol]).toFixed(1)+" nm":"—";
    document.getElementById(bid+"_kpi_current").textContent = row[CFG.currentLabelCol]||(row[CFG.currentCol]+" mA");
    document.getElementById(bid+"_angle_input").value = st.angle;
    document.getElementById(bid+"_angle_lbl").textContent = st.angle;
    document.getElementById(bid+"_kpi_ratio").textContent = row[CFG.ratioCol]!=null?Number(row[CFG.ratioCol]).toFixed(3):"—";

    renderFarfield3D(cube);
    renderFarfield2D(cube);
    renderFlux(cube, st.angle);
    initPhiSlider(cube);
    renderIntegratedSpectrum(cube, st.angle);
    renderCompare();
    renderEqeVsRatio();
  }}

  function integratedSpectrum(cube, angleDeg){{
    var thetaB = cube.theta_band||[], phiB = cube.phi_band||[], wl = cube.wavelength_band||[], band = cube.band_diagram||{{}};
    var nWl = wl.length;
    var sums = new Array(nWl).fill(0);
    var nSamples = 0;
    phiB.forEach(function(p){{
      var rows = band[p]||band[String(p)]||[];
      thetaB.forEach(function(t,ti){{
        if(t<=angleDeg){{
          var row = rows[ti]||[];
          for(var i=0;i<nWl;i++){{ sums[i] += (row[i]||0); }}
          nSamples++;
        }}
      }});
    }});
    return {{wl:wl, sums:sums, nSamples:nSamples}};
  }}

  function normalizeArr(arr){{
    var mx = Math.max.apply(null, arr.concat([1e-30]));
    if(mx<=0) return arr.map(function(){{return 0;}});
    return arr.map(function(v){{return v/mx;}});
  }}

  function renderIntegratedSpectrum(cube, angleDeg){{
    document.getElementById(bid+"_spec_angle_lbl").textContent = angleDeg;
    var res = integratedSpectrum(cube, angleDeg);
    var el = document.getElementById(bid+"_spec_int");
    if(!res.nSamples || !res.wl.length){{
      Plotly.react(el, [], Object.assign({{}}, BASE_LAYOUT, {{
        annotations:[{{text:"Aucun échantillon dans [0°, "+angleDeg+"°]",xref:"paper",yref:"paper",x:.5,y:.5,showarrow:false,font:{{size:11,color:"#8896BB"}}}}],
      }}), PLYCFG);
      return;
    }}
    var trace = {{
      type:"scatter", mode:"lines", x:res.wl, y:normalizeArr(res.sums),
      line:{{color:"#8B5CF6",width:2}}, fill:"tozeroy", fillcolor:"rgba(139,92,246,.12)",
      hovertemplate:"λ: %{{x}} nm<br>intensité normalisée: %{{y}}<extra></extra>",
    }};
    var layout = Object.assign({{}}, BASE_LAYOUT, {{
      xaxis:Object.assign({{}},GSTYLE,{{title:{{text:"λ (nm)",font:{{size:11}}}}}}),
      yaxis:Object.assign({{}},GSTYLE,{{title:{{text:"Intensité normalisée",font:{{size:11}}}},range:[0,1.05]}}),
      showlegend:false,
    }});
    Plotly.react(el, [trace], layout, PLYCFG);
  }}

  function renderFarfield3D(cube){{
    var thetaB = cube.theta_band, phiB = cube.phi_band, band = cube.band_diagram;
    if(!thetaB||!phiB||!band) return;
    var X=[],Y=[],Z=[],C=[];
    phiB.forEach(function(p){{
      var rowX=[],rowY=[],rowZ=[],rowC=[];
      var rows = band[p]||band[String(p)]||[];
      thetaB.forEach(function(t,ti){{
        var wlrow = rows[ti]||[];
        var intensity = wlrow.reduce(function(a,b){{return a+b;}},0);
        rowC.push(intensity);
      }});
      var maxC = Math.max.apply(null, rowC.concat([1e-30]));
      thetaB.forEach(function(t,ti){{
        var r = maxC>0 ? rowC[ti]/maxC : 0;
        var th = t*Math.PI/180, ph = p*Math.PI/180;
        rowX.push(r*Math.sin(th)*Math.cos(ph));
        rowY.push(r*Math.sin(th)*Math.sin(ph));
        rowZ.push(r*Math.cos(th));
      }});
      X.push(rowX); Y.push(rowY); Z.push(rowZ); C.push(rowC);
    }});
    var trace = {{type:"surface", x:X, y:Y, z:Z, surfacecolor:C, colorscale:"Viridis", showscale:false}};
    var layout = Object.assign({{}}, BASE_LAYOUT, {{
      scene:{{
        xaxis:{{title:"x",gridcolor:"#E4E8F4"}}, yaxis:{{title:"y",gridcolor:"#E4E8F4"}}, zaxis:{{title:"z",gridcolor:"#E4E8F4"}},
        camera:{{eye:{{x:1.4,y:1.4,z:1.1}}}},
      }},
      margin:{{t:8,r:8,b:8,l:8}},
    }});
    Plotly.react(bid+"_ff3d", [trace], layout, PLYCFG);
  }}

  function renderFarfield2D(cube){{
    var theta = cube.theta_ext, meas = cube.intensity_meas_norm, lamb = cube.intensity_lambertian_norm;
    if(!theta) return;
    var thetaNeg = theta.map(function(t){{return -t;}});
    var traces = [
      {{type:"scatterpolar", theta:theta, r:lamb, mode:"lines", name:"Lambertienne", line:{{color:"#3e92cc",dash:"dash",width:2.5}}}},
      {{type:"scatterpolar", theta:thetaNeg, r:lamb, mode:"lines", name:"Lambertienne", showlegend:false, line:{{color:"#3e92cc",dash:"dash",width:2.5}}}},
      {{type:"scatterpolar", theta:theta, r:meas, mode:"lines", name:"Mesure", line:{{color:"#e85d4a",width:2.5}}}},
      {{type:"scatterpolar", theta:thetaNeg, r:meas, mode:"lines", name:"Mesure", showlegend:false, line:{{color:"#e85d4a",width:2.5}}}},
    ];
    var layout = Object.assign({{}}, BASE_LAYOUT, {{
      polar:{{ sector:[-90,90], angularaxis:{{rotation:90,direction:"clockwise"}}, radialaxis:{{showticklabels:true}} }},
      showlegend:true, legend:{{font:{{size:9}}}},
    }});
    Plotly.react(bid+"_ff2d", traces, layout, PLYCFG);
  }}

  function interp(x, xs, ys){{
    if(x<=xs[0]) return ys[0];
    if(x>=xs[xs.length-1]) return ys[ys.length-1];
    for(var i=1;i<xs.length;i++){{
      if(xs[i]>=x){{
        var t=(x-xs[i-1])/(xs[i]-xs[i-1]);
        return ys[i-1]+t*(ys[i]-ys[i-1]);
      }}
    }}
    return ys[ys.length-1];
  }}

  function renderFlux(cube, angle){{
    var theta = cube.theta_ext, flux = cube.cumulative_flux, fluxL = cube.cumulative_flux_lambertian;
    if(!theta) return;
    var yAtAngle = interp(angle, theta, flux);
    var traces = [
      {{type:"scatter", x:theta, y:fluxL, mode:"lines", name:"Lambertienne", line:{{color:"#3e92cc",dash:"dash",width:2.5}}}},
      {{type:"scatter", x:theta, y:flux, mode:"lines", name:"Mesure", line:{{color:"#e85d4a",width:2.5}}}},
      {{type:"scatter", x:[angle], y:[yAtAngle], mode:"markers", name:angle+"°", marker:{{color:"#D4AF37",size:11,line:{{width:1.5,color:"#0A2463"}}}}}},
    ];
    var layout = Object.assign({{}}, BASE_LAYOUT, {{
      xaxis:Object.assign({{}},GSTYLE,{{title:{{text:"Theta (°)",font:{{size:11}}}}}}),
      yaxis:Object.assign({{}},GSTYLE,{{title:{{text:"Flux cumulé (a.u.)",font:{{size:11}}}}}}),
      showlegend:true, legend:{{font:{{size:9}}}},
    }});
    Plotly.react(bid+"_flux", traces, layout, PLYCFG);
  }}

  function initPhiSlider(cube){{
    var phiB = cube.phi_band||[];
    var slider = document.getElementById(bid+"_phi_slider");
    slider.max = Math.max(0, phiB.length-1);
    slider.value = st.phiIdx;
    renderBand(cube, st.phiIdx);
  }}

  window[bid+"_onPhiSlider"] = function(v){{
    st.phiIdx = parseInt(v);
    if(st.cube) renderBand(st.cube, st.phiIdx);
  }};

  function transpose(m){{
    if(!m.length) return [];
    var out = m[0].map(function(){{return [];}});
    m.forEach(function(row){{ row.forEach(function(v,j){{ out[j].push(v); }}); }});
    return out;
  }}

  function renderBand(cube, idx){{
    var phiB = cube.phi_band||[], thetaB = cube.theta_band||[], wl = cube.wavelength_band||[], band = cube.band_diagram||{{}};
    var p = phiB[idx];
    if(p==null) return;
    document.getElementById(bid+"_phi_lbl").textContent = p;
    // band[p] est [theta][lambda] côté Python — on transpose pour x=theta, y=lambda
    var zRaw = band[p]||band[String(p)]||[];
    var z = transpose(zRaw);
    var trace = {{type:"heatmap", x:thetaB, y:wl, z:z, colorscale:"Viridis", showscale:true, colorbar:{{thickness:10,len:0.9}}}};
    var layout = Object.assign({{}}, BASE_LAYOUT, {{
      xaxis:Object.assign({{}},GSTYLE,{{title:{{text:"Theta (°)",font:{{size:10}}}}}}),
      yaxis:Object.assign({{}},GSTYLE,{{title:{{text:"λ (nm)",font:{{size:10}}}},autorange:"reversed"}}),
      margin:{{t:8,r:10,b:36,l:44}},
    }});
    var el = document.getElementById(bid+"_band");
    if(el.data){{
      Plotly.restyle(el, {{z:[z], x:[thetaB], y:[wl]}}, [0]);
    }} else {{
      Plotly.newPlot(el, [trace], layout, PLYCFG);
    }}
  }}

  window[bid+"_recalcRatio"] = function(){{
    var angle = parseFloat(document.getElementById(bid+"_angle_input").value);
    if(isNaN(angle) || !st.cube) return;
    st.angle = angle;
    document.getElementById(bid+"_angle_lbl").textContent = angle;
    var theta = st.cube.theta_ext, flux = st.cube.cumulative_flux, fluxL = st.cube.cumulative_flux_lambertian;
    var m = interp(angle, theta, flux), l = interp(angle, theta, fluxL);
    var ratio = l!==0 ? m/l : NaN;
    document.getElementById(bid+"_kpi_ratio").textContent = isNaN(ratio)?"—":ratio.toFixed(3);
    renderFlux(st.cube, angle);
    renderIntegratedSpectrum(st.cube, angle);
  }};

  function normSize(vals,mn,mx){{
    var c=vals.map(parseFloat).filter(function(v){{return !isNaN(v);}});
    if(!c.length) return vals.map(function(){{return (mn+mx)/2;}});
    var vi=Math.min.apply(null,c),va=Math.max.apply(null,c);
    return vals.map(function(v){{var n=parseFloat(v);return isNaN(n)?(mn+mx)/2:vi===va?(mn+mx)/2:mn+(n-vi)/(va-vi)*(mx-mn);}});
  }}
  function groupBy(arr,key){{
    return arr.reduce(function(acc,r){{var k=r[key]!=null?String(r[key]):"?";(acc[k]=acc[k]||[]).push(r);return acc;}},{{}});
  }}
  function symbolFor(r){{
    var p = r[CFG.processCol];
    if(p==="MOCVD") return "square";
    if(p==="MBE") return "circle";
    return "diamond";
  }}
  function hoverExtra(r){{
    var curLbl = r[CFG.currentLabelCol]||(r[CFG.currentCol]+"mA");
    var t = "<br>X="+r[CFG.posXCol]+" Y="+r[CFG.posYCol]+"<br>I="+curLbl;
    if(r[CFG.dateCol]) t += "<br>"+r[CFG.dateCol];
    if(r[CFG.processCol]) t += "<br>"+r[CFG.processCol];
    if(r[CFG.qtNameCol]) t += " · "+r[CFG.qtNameCol];
    return t;
  }}

  function selectMeasurement(row){{
    if(!row) return;
    st.wafer = row[CFG.waferCol];
    document.getElementById(bid+"_sel_wafer").value = String(st.wafer);

    var rowsW = rowsForWafer(st.wafer);
    var posKeys = uniq(rowsW.map(posKeyOf));
    fillSelect(document.getElementById(bid+"_sel_pos"), posKeys, function(pk){{
      var r = rowsW.filter(function(r){{return posKeyOf(r)===pk;}})[0];
      return "X="+r[CFG.posXCol]+" Y="+r[CFG.posYCol];
    }});
    st.posKey = posKeyOf(row);
    document.getElementById(bid+"_sel_pos").value = st.posKey;

    var rowsP = rowsForPos(st.wafer, st.posKey);
    var currents = uniq(rowsP.map(function(r){{return r[CFG.currentCol];}})).sort(function(a,b){{return a-b;}});
    fillSelect(document.getElementById(bid+"_sel_current"), currents, function(c){{
      var r = rowsP.filter(function(r){{return String(r[CFG.currentCol])===String(c);}})[0];
      return (r && r[CFG.currentLabelCol]) ? r[CFG.currentLabelCol] : c+" mA";
    }});
    st.current = row[CFG.currentCol];
    document.getElementById(bid+"_sel_current").value = String(st.current);

    loadSelection();
  }}

  window[bid+"_selectByKey"] = function(key){{
    var row = DATA.filter(function(r){{return String(r[CFG.keyCol])===String(key);}})[0];
    if(row) selectMeasurement(row);
  }};

  window[bid+"_toggleCompare"] = function(){{
    st.compareMode = !st.compareMode;
    document.getElementById(bid+"_cmp_toggle").classList.toggle("active", st.compareMode);
    if(!st.compareMode){{
      st.compareKeys = [];
      document.getElementById(bid+"_cmp_wrap").style.display = "none";
    }}
    updateCompareStatus();
  }};

  function updateCompareStatus(){{
    var el = document.getElementById(bid+"_cmp_status");
    if(!st.compareMode){{ el.textContent = ""; return; }}
    if(!st.compareKeys.length){{ el.textContent = "mode actif — cliquer 2 points"; return; }}
    el.textContent = st.compareKeys.map(function(k){{ return labelForRow(rowForKey(k)); }}).join("  vs  ");
  }}

  function toggleCompareKey(key){{
    var idx = st.compareKeys.indexOf(key);
    if(idx>=0){{
      st.compareKeys.splice(idx,1);
    }} else {{
      st.compareKeys.push(key);
      if(st.compareKeys.length>2) st.compareKeys.shift();
    }}
    updateCompareStatus();
    renderCompareCharts();
  }}

  function renderCompareCharts(){{
    var wrap = document.getElementById(bid+"_cmp_wrap");
    if(!st.compareKeys.length){{ wrap.style.display = "none"; return; }}
    wrap.style.display = "block";

    var pal = ["#e85d4a","#3e92cc"];
    var labels = st.compareKeys.map(function(k){{ return labelForRow(rowForKey(k)); }});
    var cubes = st.compareKeys.map(function(k){{ return CUBES[k]; }});

    var specTraces = [];
    cubes.forEach(function(cube,i){{
      if(!cube) return;
      var res = integratedSpectrum(cube, st.angle);
      if(!res.nSamples) return;
      specTraces.push({{type:"scatter", mode:"lines", x:res.wl, y:normalizeArr(res.sums),
        name:labels[i], line:{{color:pal[i],width:2.5}}}});
    }});
    Plotly.react(bid+"_cmp_spectrum", specTraces, Object.assign({{}}, BASE_LAYOUT, {{
      xaxis:Object.assign({{}},GSTYLE,{{title:{{text:"λ (nm)",font:{{size:11}}}}}}),
      yaxis:Object.assign({{}},GSTYLE,{{title:{{text:"Intensité normalisée",font:{{size:11}}}},range:[0,1.05]}}),
      showlegend:true, legend:{{font:{{size:9}},orientation:"h",y:-.2}},
    }}), PLYCFG);

    var ffTraces = [];
    cubes.forEach(function(cube,i){{
      if(!cube||!cube.theta_ext) return;
      var theta = cube.theta_ext, meas = cube.intensity_meas_norm;
      var thetaNeg = theta.map(function(t){{return -t;}});
      ffTraces.push({{type:"scatterpolar", theta:theta, r:meas, mode:"lines", name:labels[i], line:{{color:pal[i],width:2.5}}}});
      ffTraces.push({{type:"scatterpolar", theta:thetaNeg, r:meas, mode:"lines", name:labels[i], showlegend:false, line:{{color:pal[i],width:2.5}}}});
    }});
    Plotly.react(bid+"_cmp_farfield", ffTraces, Object.assign({{}}, BASE_LAYOUT, {{
      polar:{{ sector:[-90,90], angularaxis:{{rotation:90,direction:"clockwise"}}, radialaxis:{{showticklabels:true}} }},
      showlegend:true, legend:{{font:{{size:9}},orientation:"h",y:-.2}},
    }}), PLYCFG);

    var fluxTraces = [];
    cubes.forEach(function(cube,i){{
      if(!cube||!cube.theta_ext) return;
      fluxTraces.push({{type:"scatter", mode:"lines", x:cube.theta_ext, y:cube.cumulative_flux,
        name:labels[i], line:{{color:pal[i],width:2.5}}}});
    }});
    Plotly.react(bid+"_cmp_flux", fluxTraces, Object.assign({{}}, BASE_LAYOUT, {{
      xaxis:Object.assign({{}},GSTYLE,{{title:{{text:"Theta (°)",font:{{size:11}}}}}}),
      yaxis:Object.assign({{}},GSTYLE,{{title:{{text:"Flux cumulé (a.u.)",font:{{size:11}}}}}}),
      showlegend:true, legend:{{font:{{size:9}},orientation:"h",y:-.2}},
    }}), PLYCFG);
  }}

  function wireClickToSelect(el){{
    el.removeAllListeners && el.removeAllListeners("plotly_click");
    el.on("plotly_click", function(e){{
      if(!e || !e.points || !e.points.length) return;
      var key = e.points[0].customdata;
      if(key==null) return;
      if(st.compareMode) toggleCompareKey(key);
      else window[bid+"_selectByKey"](key);
    }});
  }}

  function renderCompare(){{
    var pal = ["#0A2463","#D4AF37","#3e92cc","#e85d4a","#2dc653","#9b5de5"];
    var valid = DATA.filter(function(r){{return r[CFG.lambdaCol]!=null && r[CFG.ratioCol]!=null;}});
    var groups = groupBy(valid, CFG.waferCol);
    var traces = Object.keys(groups).sort().map(function(gk,gi){{
      var rows = groups[gk];
      var sz = normSize(rows.map(function(r){{return r[CFG.currentCol]||0;}}),6,26);
      return {{
        type:"scatter", mode:"markers", name:gk,
        x:rows.map(function(r){{return r[CFG.lambdaCol];}}),
        y:rows.map(function(r){{return r[CFG.ratioCol];}}),
        marker:{{color:pal[gi%pal.length],size:sz,symbol:rows.map(symbolFor),opacity:.85,line:{{width:.5,color:"rgba(0,0,0,.15)"}}}},
        customdata:rows.map(function(r){{return r[CFG.keyCol];}}),
        text:rows.map(function(r){{return gk+hoverExtra(r);}}),
        hovertemplate:"%{{text}}<br>λ: %{{x}}<br>ratio: %{{y}}<br><i>clic → charger cette mesure</i><extra></extra>",
      }};
    }});
    var layout = Object.assign({{}}, BASE_LAYOUT, {{
      xaxis:Object.assign({{}},GSTYLE,{{title:{{text:"λ dominant (nm)",font:{{size:11}}}}}}),
      yaxis:Object.assign({{}},GSTYLE,{{title:{{text:"Ratio 12°",font:{{size:11}}}}}}),
      showlegend:true, legend:{{font:{{size:9}}}},
    }});
    var el = document.getElementById(bid+"_compare");
    Plotly.react(el, traces, layout, PLYCFG).then(function(){{ wireClickToSelect(el); }});
  }}

  function renderEqeVsRatio(){{
    var pal = ["#0A2463","#D4AF37","#3e92cc","#e85d4a","#2dc653","#9b5de5"];
    var valid = DATA.filter(function(r){{return r[CFG.eqeCol]!=null && r[CFG.ratioCol]!=null && r[CFG.eqeCol]>0;}});
    if(!valid.length){{
      Plotly.react(bid+"_eqe", [], Object.assign({{}}, BASE_LAYOUT, {{
        annotations:[{{text:"Pas de donnée EQE (LIV) pour ces mesures",xref:"paper",yref:"paper",x:.5,y:.5,showarrow:false,font:{{size:11,color:"#8896BB"}}}}],
      }}), PLYCFG);
      return;
    }}
    var groups = groupBy(valid, CFG.waferCol);
    var traces = Object.keys(groups).sort().map(function(gk,gi){{
      var rows = groups[gk];
      var sz = normSize(rows.map(function(r){{return r[CFG.currentCol]||0;}}),6,26);
      return {{
        type:"scatter", mode:"markers", name:gk,
        x:rows.map(function(r){{return r[CFG.eqeCol];}}),
        y:rows.map(function(r){{return r[CFG.ratioCol];}}),
        marker:{{color:pal[gi%pal.length],size:sz,symbol:rows.map(symbolFor),opacity:.85,line:{{width:.5,color:"rgba(0,0,0,.15)"}}}},
        customdata:rows.map(function(r){{return r[CFG.keyCol];}}),
        text:rows.map(function(r){{return gk+hoverExtra(r);}}),
        hovertemplate:"%{{text}}<br>EQE médian (zone): %{{x}}<br>ratio: %{{y}}<br><i>clic → charger cette mesure</i><extra></extra>",
      }};
    }});
    var layout = Object.assign({{}}, BASE_LAYOUT, {{
      xaxis:Object.assign({{}},GSTYLE,{{title:{{text:"EQE médian (zone)",font:{{size:11}}}},type:"log"}}),
      yaxis:Object.assign({{}},GSTYLE,{{title:{{text:"Ratio 12°",font:{{size:11}}}}}}),
      showlegend:true, legend:{{font:{{size:9}}}},
    }});
    var el = document.getElementById(bid+"_eqe");
    Plotly.react(el, traces, layout, PLYCFG).then(function(){{ wireClickToSelect(el); }});
  }}

  initWaferSelect();
}})();
</script>
"""
