from __future__ import annotations
import json
import html as _h
from ..._helpers import Block


class CoreShellULEDBlock(Block):
    """
    Explorateur interactif du modèle électro-optique compact pour µLEDs à
    nanofils core-shell InGaN/GaN (Tsormpatzoglou et al., J. Appl. Phys. 140,
    014501 (2026)).

    Toute la physique (Eq. 2, 3, 5, 6, 8, 9 du papier) est portée en JS et
    évaluée côté navigateur — aucune donnée à fournir : les paramètres sont
    des sliders continus initialisés sur les valeurs extraites dans le papier
    (voir ``report_builder/core/blocks/simu_explorer/physics/core_shell_uled.py``
    pour l'équivalent Python : fonctions pures + pipeline de fit scipy).

    5 onglets internes :
      - Régime I  — densité de courant SCLC piégé (Eq. 2), J en A/cm²
      - p_inj & Puissance — concentration injectée + loi carrée (Eq. 5, 6)
      - EQE — modèle ABC classique vs ABC(p_inj) avec Auger PSF (Eq. 3, 8)
      - Bande passante -3dB (Eq. 9)
      - IV complète — diode simple (n) + Rs série + Rp parallèle, courbe J(V)
        entre 0.01 et 2000 A/cm², avec carte KPI (tension de seuil, n, Rs, Rp)

    Parameters
    ----------
    height  : int  — hauteur des graphes Plotly en px
    num / title / subtitle — identifiant visuel du bloc
    """

    needs_plotly = True

    def __init__(
        self,
        height: int = 380,
        num: str = "—",
        title: str = "Modèle électro-optique — µLED core-shell InGaN/GaN",
        subtitle: str = "Tsormpatzoglou et al., J. Appl. Phys. 140, 014501 (2026)",
    ):
        self.height = height
        self.num = num
        self.title = title
        self.subtitle = subtitle
        self._id = f"uled_{id(self)}"

    def render(self, store=None) -> str:  # noqa: ARG002
        sid = self._id
        h = self.height
        title_h = _h.escape(self.title)
        sub_h = _h.escape(self.subtitle)
        num_h = _h.escape(self.num)

        # Définition des 4 onglets : chaque slider est [key, label, min, max, default, log?, unit]
        tabs = [
            {
                "id": "sclc", "label": "Régime I — SCLC (Eq. 2)",
                "sliders": [
                    ["Dp", "Dp — diffusion trous (cm²/s)", 1e-7, 1e-4, 4.1e-6, True],
                    ["m", "m = kTc/kT", 2, 25, 12.5, False],
                    ["kTcEV", "kTc — énergie pièges (eV)", 0.05, 0.6, 0.322, False],
                    ["Nt", "Nt — densité pièges (cm⁻³)", 1e18, 1e21, 1.33e20, True],
                    ["epsR", "εr EBL (AlGaN)", 6, 12, 8.9, False],
                    ["tEbl", "t_EBL (cm)", 5e-7, 5e-6, 2e-6, True],
                    ["Snw", "S_nw — surface active (cm²)", 1e-9, 1e-6, 3.6e-8, True],
                ],
            },
            {
                "id": "pinj", "label": "p_inj & Puissance (Eq. 5, 6)",
                "sliders": [
                    ["Ldif", "L_dif — long. diffusion (cm)", 5e-7, 5e-6, 14.5e-7, True],
                    ["Dp", "Dp — diffusion trous (cm²/s)", 1e-7, 1e-4, 4.1e-6, True],
                    ["Snw", "S_nw — surface active (cm²)", 1e-9, 1e-6, 3.6e-8, True],
                    ["B", "B — recombinaison radiative (cm³/s)", 1e-11, 1e-7, 3e-9, True],
                    ["LEE", "LEE — extraction lumineuse", 0.05, 0.9, 0.35, False],
                    ["hvEV", "hν — énergie photon (eV)", 2.0, 3.4, 2.7, False],
                    ["Vactive", "V_active — volume QW (cm³)", 1e-16, 1e-13, 5e-15, True],
                ],
            },
            {
                "id": "eqe", "label": "EQE — ABC vs ABC+PSF (Eq. 3, 8)",
                "sliders": [
                    ["A", "A — SRH non-radiatif (s⁻¹)", 1e4, 1e8, 2.3e6, True],
                    ["B", "B — radiatif (cm³/s)", 1e-11, 1e-7, 3e-9, True],
                    ["C0", "C0 — Auger faible injection (cm⁶/s)", 1e-28, 1e-24, 3e-26, True],
                    ["pinj0", "p_inj0 — seuil PSF (cm⁻³)", 1e15, 1e19, 1.1e17, True],
                    ["LEE", "LEE — extraction lumineuse", 0.05, 0.9, 0.35, False],
                ],
            },
            {
                "id": "bw", "label": "Bande passante -3dB (Eq. 9)",
                "sliders": [
                    ["B", "B — recombinaison radiative (cm³/s)", 1e-11, 1e-7, 3e-9, True],
                    ["tQw", "t_QW — épaisseur puits (cm)", 1e-7, 3e-6, 8e-7, True],
                ],
            },
            {
                "id": "iv", "label": "IV complète — Diode + Rs + Rp",
                "sliders": [
                    ["J0", "J0 — densité sat. inverse (A/cm²)", 1e-18, 1e-6, 1e-12, True],
                    ["n", "n — facteur d'idéalité", 1.0, 3.0, 1.8, False],
                    ["Rs", "Rs — résistance série (Ω·cm²)", 0.01, 50, 2.0, False],
                    ["Rp", "Rp — résistance parallèle/shunt (Ω·cm²)", 10, 1e7, 1e5, True],
                ],
            },
        ]
        tabs_json = json.dumps(tabs)

        tab_buttons = "".join(
            f'<button class="uled-tab{" active" if i == 0 else ""}" '
            f'onclick="{sid}_showTab({i})" id="{sid}_tabbtn{i}">{_h.escape(t["label"])}</button>\n'
            for i, t in enumerate(tabs)
        )

        panels = ""
        for i, t in enumerate(tabs):
            disp = "block" if i == 0 else "none"
            panels += f"""
    <div class="uled-slide" id="{sid}_slide{i}" style="display:{disp};">
      <div class="uled-layout">
        <div class="uled-panel" id="{sid}_ctrl{i}"></div>
        <div class="uled-chartwrap">
          <div id="{sid}_plot{i}" style="height:{h}px;"></div>
          <div class="uled-readout" id="{sid}_readout{i}"></div>
        </div>
      </div>
    </div>
"""

        return f"""
<div class="led-block" id="{sid}_wrap">
  <div class="led-block-header">
    <span class="led-block-num">{num_h}</span>
    <span class="led-block-title">{title_h}</span>
    <span class="led-block-sub">{sub_h}</span>
  </div>
  <div class="led-block-rule"></div>

  <div class="uled-tabs" id="{sid}_tabs">{tab_buttons}</div>
  {panels}
</div>

<style>
#{sid}_wrap .uled-tabs {{
  display: flex; flex-wrap: wrap; gap: 4px;
  border-bottom: 1px solid #E4E8F4; margin-bottom: 14px;
}}
#{sid}_wrap .uled-tab {{
  font-family: "IBM Plex Mono", monospace; font-size: 10.5px; font-weight: 700;
  letter-spacing: .03em; color: #64748B; background: none; border: none;
  padding: 8px 12px; cursor: pointer; border-bottom: 2px solid transparent; margin-bottom: -1px;
}}
#{sid}_wrap .uled-tab.active {{ color: #0A2463; border-bottom-color: #D4AF37; }}
#{sid}_wrap .uled-tab:hover:not(.active) {{ color: #0A2463; }}
#{sid}_wrap .uled-layout {{ display: grid; grid-template-columns: 260px 1fr; gap: 16px; }}
@media (max-width: 900px) {{ #{sid}_wrap .uled-layout {{ grid-template-columns: 1fr; }} }}
#{sid}_wrap .uled-panel {{
  background: #F8F9FD; border: 1px solid #E4E8F4; border-radius: 8px; padding: 12px 14px;
}}
#{sid}_wrap .uled-ctrl {{ margin-bottom: 12px; }}
#{sid}_wrap .uled-ctrl label {{
  display: flex; justify-content: space-between; align-items: baseline;
  font-family: "IBM Plex Mono", monospace; font-size: 9.5px; font-weight: 700;
  color: #1E3A5F; margin-bottom: 3px; gap: 6px;
}}
#{sid}_wrap .uled-ctrl .uled-val {{ color: #0A2463; font-weight: 800; white-space: nowrap; }}
#{sid}_wrap .uled-ctrl input[type=range] {{ width: 100%; accent-color: #0A2463; }}
#{sid}_wrap .uled-chartwrap {{
  background: #F8F9FD; border: 1px solid #E4E8F4; border-radius: 8px; padding: 10px;
}}
#{sid}_wrap .uled-readout {{
  font-family: "IBM Plex Mono", monospace; font-size: 10.5px; color: #4A5580;
  border-top: 1px dashed #C4CEDE; margin-top: 8px; padding-top: 8px; line-height: 1.8;
}}
#{sid}_wrap .uled-readout b {{ color: #0A2463; }}
#{sid}_wrap .uled-kpi-grid {{
  display: grid; grid-template-columns: repeat(auto-fit, minmax(120px, 1fr)); gap: 8px;
  margin-top: 4px;
}}
#{sid}_wrap .uled-kpi-card {{
  background: #FFFFFF; border: 1px solid #E4E8F4; border-left: 3px solid #D4AF37;
  border-radius: 6px; padding: 8px 10px;
}}
#{sid}_wrap .uled-kpi-card .uled-kpi-label {{
  font-family: "IBM Plex Mono", monospace; font-size: 8.5px; font-weight: 700;
  letter-spacing: .03em; color: #64748B; text-transform: uppercase; display: block; margin-bottom: 3px;
}}
#{sid}_wrap .uled-kpi-card .uled-kpi-value {{
  font-family: "IBM Plex Mono", monospace; font-size: 15px; font-weight: 800; color: #0A2463;
}}
#{sid}_wrap .uled-kpi-card .uled-kpi-unit {{ font-size: 10px; font-weight: 600; color: #4A5580; margin-left: 2px; }}
</style>

<script>
(function() {{
  var sid = "{sid}";
  var TABS = {tabs_json};

  /* ── Constantes physiques ── */
  var q = 1.602176634e-19, kB = 1.380649e-23, eps0 = 8.8541878128e-14, T = 300.0;

  /* ── Équations du papier ── */
  function sclcCurrent(V, Dp, m, kTcEV, Nt, epsR, tEbl, Snw, Nv) {{
    var muP = q * Dp / (kB * T);
    var I0 = q * muP * Nv * Snw;
    var pref = Math.pow(eps0 * epsR * m / (q * Nt * (m + 1)), m) * Math.pow((2 * m + 1) / (m + 1), m + 1);
    return V.map(function(v) {{ return I0 * pref * Math.pow(v, m + 1) / Math.pow(tEbl, 2 * m + 1); }});
  }}
  function pinjFromCurrent(I, Ldif, Dp, Snw) {{
    return I.map(function(i) {{ return i * Ldif / (q * Snw * Dp); }});
  }}
  function powerVsPinj(pinj, B, LEE, hvEV, Vactive) {{
    var hvJ = hvEV * q;
    return pinj.map(function(p) {{ return LEE * hvJ * Vactive * B * p * p; }});
  }}
  function eqeAbc(pinj, A, B, C, LEE) {{
    return pinj.map(function(p) {{
      var num = B * p * p, den = A * p + B * p * p + C * p * p * p;
      return LEE * num / den;
    }});
  }}
  function cPsf(p, C0, pinj0) {{ return C0 / (1 + p / pinj0); }}
  function eqeAbcPsf(pinj, A, B, C0, pinj0, LEE) {{
    return pinj.map(function(p) {{
      var C = cPsf(p, C0, pinj0);
      var num = B * p * p, den = A * p + B * p * p + C * p * p * p;
      return LEE * num / den;
    }});
  }}
  function bandwidth3dB(B, J, tQw) {{
    return J.map(function(j) {{ return (Math.sqrt(3) / (2 * Math.PI)) * Math.sqrt(Math.max(B * j / (q * tQw), 0)); }});
  }}
  /* Diode simple + Rp en shunt, paramétrée par la tension interne de jonction Vd
     (explicite — pas d'itération) : Jd(Vd) = J0*(exp(qVd/nkT)-1) + Vd/Rp
     puis V = Vd + Jd*Rs (chute ohmique série). */
  function diodeIV(Vd, J0, n, Rs, Rp) {{
    var kTq = kB * T / q;
    var J = Vd.map(function(vd) {{ return J0 * (Math.exp(vd / (n * kTq)) - 1) + vd / Rp; }});
    var V = Vd.map(function(vd, idx) {{ return vd + J[idx] * Rs; }});
    return {{ V: V, J: J }};
  }}
  /* Interpolation linéaire (V,J monotones croissants) — retourne V pour un J cible. */
  function interpVatJ(V, J, target) {{
    for (var k = 1; k < J.length; k++) {{
      if (J[k] >= target) {{
        var t = (target - J[k - 1]) / (J[k] - J[k - 1]);
        return V[k - 1] + t * (V[k] - V[k - 1]);
      }}
    }}
    return NaN;
  }}
  /* Résistance différentielle locale dV/dJ à l'indice donné (Ω·cm²). */
  function diffR(V, J, idx) {{
    var i0 = Math.max(0, idx - 2), i1 = Math.min(V.length - 1, idx + 2);
    if (i1 === i0) return NaN;
    return (V[i1] - V[i0]) / (J[i1] - J[i0]);
  }}
  function linspace(a, b, n) {{ var out = []; for (var i = 0; i < n; i++) out.push(a + (b - a) * i / (n - 1)); return out; }}
  function logspace(a, b, n) {{ return linspace(a, b, n).map(function(x) {{ return Math.pow(10, x); }}); }}
  function fmt(x, digits) {{
    digits = digits || 3;
    if (x === 0) return "0";
    if (!isFinite(x)) return "—";
    var ax = Math.abs(x);
    if (ax >= 1e4 || ax < 1e-3) return x.toExponential(digits - 1);
    return x.toPrecision(digits);
  }}

  var PLYCFG = {{ responsive: true, displaylogo: false,
    modeBarButtonsToRemove: ["autoScale2d", "toggleSpikelines", "sendDataToCloud"] }};

  function baseLayout(xlog, ylog, xlabel, ylabel) {{
    return {{
      paper_bgcolor: "rgba(0,0,0,0)", plot_bgcolor: "#F8F9FD",
      font: {{ family: "IBM Plex Mono,monospace", color: "#4A5580", size: 10 }},
      margin: {{ t: 10, r: 14, b: 46, l: 60 }},
      xaxis: {{ type: xlog ? "log" : "-", title: {{ text: xlabel, font: {{ size: 11, color: "#0A2463" }}, standoff: 6 }},
        gridcolor: "#E4E8F4", linecolor: "#E4E8F4", zerolinecolor: "#E4E8F4", tickfont: {{ size: 9 }} }},
      yaxis: {{ type: ylog ? "log" : "-", title: {{ text: ylabel, font: {{ size: 11, color: "#0A2463" }}, standoff: 6 }},
        gridcolor: "#E4E8F4", linecolor: "#E4E8F4", zerolinecolor: "#E4E8F4", tickfont: {{ size: 9 }} }},
      hoverlabel: {{ bgcolor: "#0A2463", bordercolor: "#D4AF37", font: {{ family: "IBM Plex Mono", size: 10, color: "white" }} }},
      showlegend: true, legend: {{ font: {{ size: 9 }}, orientation: "h", x: .5, xanchor: "center", y: 1.12 }},
    }};
  }}
  function plotOrReact(elId, traces, layout) {{
    var el = document.getElementById(elId);
    if (el && el.data) Plotly.react(elId, traces, layout, PLYCFG);
    else Plotly.newPlot(elId, traces, layout, PLYCFG);
  }}

  var STATE = TABS.map(function(t) {{
    var s = {{}};
    t.sliders.forEach(function(sl) {{ s[sl[0]] = sl[4]; }});
    return s;
  }});

  var RENDERERS = [
    /* 0 — SCLC — densité de courant J = I/Snw (A/cm²), gamme cible 0.01 – 2000 A/cm² */
    function(p, i) {{
      var V = linspace(0.5, 4.5, 200), Nv = 3e19;
      var I = sclcCurrent(V, p.Dp, p.m, p.kTcEV, p.Nt, p.epsR * eps0, p.tEbl, p.Snw, Nv);
      var J = I.map(function(iv) {{ return iv / p.Snw; }});
      plotOrReact(sid + "_plot" + i,
        [{{ name: "J(V) SCLC", x: V, y: J, mode: "lines", line: {{ color: "#0A2463", width: 2.2 }} }}],
        Object.assign(baseLayout(false, true, "Tension V (V)", "Densité de courant J (A/cm²)"),
          {{ yaxis: Object.assign(baseLayout(false, true, "", "").yaxis, {{ range: [Math.log10(0.01), Math.log10(2000)] }}) }}));
      var muP = q * p.Dp / (kB * T);
      document.getElementById(sid + "_readout" + i).innerHTML =
        "µ_p = <b>" + fmt(muP) + "</b> cm²/V·s &nbsp;|&nbsp; J(4V) = <b>" + fmt(J[J.length - 1]) + "</b> A/cm²";
    }},
    /* 1 — p_inj & Puissance */
    function(p, i) {{
      var I = logspace(-9, -3, 200);
      var pinj = pinjFromCurrent(I, p.Ldif, p.Dp, p.Snw);
      var P = powerVsPinj(pinj, p.B, p.LEE, p.hvEV, p.Vactive);
      plotOrReact(sid + "_plot" + i,
        [{{ name: "P(p_inj) ∝ p²", x: pinj, y: P, mode: "lines", line: {{ color: "#1baf7a", width: 2.2 }} }}],
        baseLayout(true, true, "p_inj (cm⁻³)", "Puissance optique P (W)"));
      var pAt1uA = pinjFromCurrent([1e-6], p.Ldif, p.Dp, p.Snw)[0];
      document.getElementById(sid + "_readout" + i).innerHTML =
        "p_inj à I = 1 µA : <b>" + fmt(pAt1uA) + "</b> cm⁻³";
    }},
    /* 2 — EQE ABC vs PSF */
    function(p, i) {{
      var pinj = logspace(14, 19, 220);
      var classic = eqeAbc(pinj, p.A, p.B, p.C0, p.LEE);
      var psf = eqeAbcPsf(pinj, p.A, p.B, p.C0, p.pinj0, p.LEE);
      plotOrReact(sid + "_plot" + i, [
        {{ name: "ABC classique", x: pinj, y: classic, mode: "lines", line: {{ color: "#e34948", width: 2.2 }} }},
        {{ name: "ABC(p_inj) + PSF", x: pinj, y: psf, mode: "lines", line: {{ color: "#2a78d6", width: 2.2 }} }},
      ], baseLayout(true, false, "p_inj (cm⁻³)", "EQE"));
      var iMax = psf.indexOf(Math.max.apply(null, psf));
      document.getElementById(sid + "_readout" + i).innerHTML =
        "EQE_max (PSF) = <b>" + fmt(psf[iMax]) + "</b> à p_inj = <b>" + fmt(pinj[iMax]) + "</b> cm⁻³";
    }},
    /* 3 — Bandwidth */
    function(p, i) {{
      var J = logspace(-3, 1, 200);
      var f = bandwidth3dB(p.B, J, p.tQw).map(function(v) {{ return v / 1e6; }});
      plotOrReact(sid + "_plot" + i,
        [{{ name: "f_-3dB", x: J, y: f, mode: "lines", line: {{ color: "#4a3aa7", width: 2.2 }} }}],
        baseLayout(true, true, "Densité de courant J (A/cm²)", "f_-3dB (MHz)"));
      var fAt10 = bandwidth3dB(p.B, [10], p.tQw)[0] / 1e6;
      document.getElementById(sid + "_readout" + i).innerHTML =
        "f_-3dB à J = 10 A/cm² : <b>" + fmt(fAt10) + "</b> MHz";
    }},
    /* 4 — IV complète : diode simple + Rp (shunt) + Rs (série), J de 0.01 à 2000 A/cm² */
    function(p, i) {{
      var Vd = linspace(0.0005, 4.0, 500);
      var r = diodeIV(Vd, p.J0, p.n, p.Rs, p.Rp);
      plotOrReact(sid + "_plot" + i,
        [{{ name: "J(V) diode+Rs+Rp", x: r.V, y: r.J, mode: "lines", line: {{ color: "#0A2463", width: 2.2 }} }}],
        Object.assign(baseLayout(false, true, "Tension V (V)", "Densité de courant J (A/cm²)"),
          {{ yaxis: Object.assign(baseLayout(false, true, "", "").yaxis, {{ range: [Math.log10(0.01), Math.log10(2000)] }}) }}));

      var Vth = interpVatJ(r.V, r.J, 1.0);           // tension de seuil, définie à J = 1 A/cm²
      var idxHigh = r.J.length - 5;                   // Rs différentiel en haut de courbe (régime ohmique)
      var idxLow = r.J.findIndex(function(j) {{ return j > 0.02; }});
      var RsFit = diffR(r.V, r.J, idxHigh);
      var RpFit = idxLow > 1 ? diffR(r.V, r.J, idxLow) : NaN;

      document.getElementById(sid + "_readout" + i).innerHTML =
        '<div class="uled-kpi-grid">' +
          '<div class="uled-kpi-card"><span class="uled-kpi-label">Tension de seuil</span>' +
            '<span class="uled-kpi-value">' + fmt(Vth) + '</span><span class="uled-kpi-unit">V</span></div>' +
          '<div class="uled-kpi-card"><span class="uled-kpi-label">Facteur d\\'idéalité n</span>' +
            '<span class="uled-kpi-value">' + fmt(p.n) + '</span></div>' +
          '<div class="uled-kpi-card"><span class="uled-kpi-label">Résistance série Rs</span>' +
            '<span class="uled-kpi-value">' + fmt(p.Rs) + '</span><span class="uled-kpi-unit">Ω·cm²</span></div>' +
          '<div class="uled-kpi-card"><span class="uled-kpi-label">Résistance parallèle Rp</span>' +
            '<span class="uled-kpi-value">' + fmt(p.Rp) + '</span><span class="uled-kpi-unit">Ω·cm²</span></div>' +
          '<div class="uled-kpi-card"><span class="uled-kpi-label">Rs différentiel (fit)</span>' +
            '<span class="uled-kpi-value">' + fmt(RsFit) + '</span><span class="uled-kpi-unit">Ω·cm²</span></div>' +
          '<div class="uled-kpi-card"><span class="uled-kpi-label">Rp différentiel (fit)</span>' +
            '<span class="uled-kpi-value">' + fmt(RpFit) + '</span><span class="uled-kpi-unit">Ω·cm²</span></div>' +
        '</div>';
    }},
  ];

  function toSlider(sl, v) {{
    return sl[5] ? (Math.log10(v / sl[2]) / Math.log10(sl[3] / sl[2])) * 1000 : (v - sl[2]) / (sl[3] - sl[2]) * 1000;
  }}
  function fromSlider(sl, s) {{
    return sl[5] ? sl[2] * Math.pow(sl[3] / sl[2], s / 1000) : sl[2] + (s / 1000) * (sl[3] - sl[2]);
  }}

  function buildPanel(i) {{
    var t = TABS[i];
    var ctrl = document.getElementById(sid + "_ctrl" + i);
    ctrl.innerHTML = "";
    t.sliders.forEach(function(sl) {{
      var key = sl[0], label = sl[1];
      var wrap = document.createElement("div"); wrap.className = "uled-ctrl";
      var lab = document.createElement("label");
      var nameSpan = document.createElement("span"); nameSpan.textContent = label;
      var valSpan = document.createElement("span"); valSpan.className = "uled-val";
      valSpan.textContent = fmt(STATE[i][key]);
      lab.appendChild(nameSpan); lab.appendChild(valSpan);
      var input = document.createElement("input");
      input.type = "range"; input.min = 0; input.max = 1000; input.step = 1;
      input.value = toSlider(sl, STATE[i][key]);
      input.addEventListener("input", function() {{
        STATE[i][key] = fromSlider(sl, +input.value);
        valSpan.textContent = fmt(STATE[i][key]);
        RENDERERS[i](STATE[i], i);
      }});
      wrap.appendChild(lab); wrap.appendChild(input);
      ctrl.appendChild(wrap);
    }});
  }}

  window[sid + "_showTab"] = function(i) {{
    for (var k = 0; k < TABS.length; k++) {{
      document.getElementById(sid + "_slide" + k).style.display = (k === i) ? "block" : "none";
      document.getElementById(sid + "_tabbtn" + k).classList.toggle("active", k === i);
    }}
    RENDERERS[i](STATE[i], i);
  }};

  TABS.forEach(function(_, i) {{ buildPanel(i); }});
  RENDERERS[0](STATE[0], 0);
}})();
</script>
"""
