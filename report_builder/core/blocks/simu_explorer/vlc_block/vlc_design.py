from __future__ import annotations
import json
import html as _h
import pandas as pd
from ...._helpers import Block, _safe_json


class VLCDesignBlock(Block):
    """
    Simulateur VLC interactif : pJ/bit & BER.

    Porte l'interface Dash (VLC_pJ_bit-BER.ipynb) en bloc HTML autonome
    intégrable dans un rapport ReportBuilder.

    Toute la physique (interpolation LIV/f-3dB, énergie driver/LED/détecteur,
    BER SPAD/APD) est exécutée côté navigateur en JS.

    Parameters
    ----------
    df_liv    : pd.DataFrame  — colonnes: Sample, "Voltage (V)", "J (A/cm²)", "EQE (%)", "L (W)"
    df_f3db   : pd.DataFrame  — colonnes: Sample, Test, "J (A/cm²)", "f-3dB (MHz)"
    n_wires_array : int       — nombre de fils par réseau LED (pour L per wire)
    height    : int           — hauteur des graphes Plotly en px
    num / title / subtitle    — identifiant visuel
    """

    needs_plotly = True

    def __init__(
        self,
        df_liv: pd.DataFrame,
        df_f3db: pd.DataFrame,
        df_liv_rf: pd.DataFrame | None = None,
        n_wires_array: int = 4,
        height: int = 320,
        num: str = "VLC",
        title: str = "VLC System Design – pJ/bit & BER",
        subtitle: str = "Simulation interactive µLED → VLC",
    ):
        self.df_liv = df_liv.copy()
        self.df_f3db = df_f3db.copy()
        self.df_liv_rf = df_liv_rf.copy() if df_liv_rf is not None else None
        self.n_wires_array = int(n_wires_array)
        self.height = height
        self.num = num
        self.title = title
        self.subtitle = subtitle
        self._id = f"vlcdes_{id(self)}"

    # ── sérialisation des données ─────────────────────────────────────────────

    def _serialize_liv(self) -> str:
        df = self.df_liv.copy()
        df["L_per_wire_uW"] = df["L (W)"] * 1e6 / self.n_wires_array
        records = []
        for _, row in df.iterrows():
            records.append({
                "sample": str(row.get("Sample", "")),
                "V":      _safe_json(row.get("Voltage (V)", 0)),
                "J":      _safe_json(row.get("J (A/cm²)", 0)),
                "EQE":    _safe_json(row.get("EQE (%)", 0)),
                "L":      _safe_json(row.get("L (W)", 0)),
                "L_uw":   _safe_json(row["L_per_wire_uW"]),
            })
        return json.dumps(records)

    def _serialize_f3db(self) -> str:
        records = []
        for _, row in self.df_f3db.iterrows():
            records.append({
                "sample": str(row.get("Sample", "")),
                "test":   str(row.get("Test", "")),
                "J":      _safe_json(row.get("J (A/cm²)", 0)),
                "f3db":   _safe_json(row.get("f-3dB (MHz)", 0)),
            })
        return json.dumps(records)

    def _get_samples(self) -> str:
        return json.dumps(sorted(self.df_liv["Sample"].dropna().unique().tolist()))

    def _get_tests(self) -> str:
        return json.dumps(sorted(self.df_f3db["Test"].dropna().unique().tolist()))

    def _serialize_liv_rf(self) -> str:
        if self.df_liv_rf is None:
            return "null"
        records = []
        for _, row in self.df_liv_rf.iterrows():
            records.append({
                "sample": str(row.get("Sample", "")),
                "V":   _safe_json(row.get("Voltage (V)", 0)),
                "J":   _safe_json(row.get("J (A/cm²)", 0)),
                "EQE": _safe_json(row.get("EQE (%)", 0)),
                "L":   _safe_json(row.get("L (W)", 0)),
                "L_uw": _safe_json(row.get("L (W)", 0) * 1e6),
            })
        return json.dumps(records)

    # ── rendu ─────────────────────────────────────────────────────────────────

    def render(self, store=None) -> str:  # noqa: ARG002
        sid      = self._id
        title_h  = _h.escape(self.title)
        sub_h    = _h.escape(self.subtitle)
        num_h    = _h.escape(self.num)
        h        = self.height
        liv_json    = self._serialize_liv()
        f3_json     = self._serialize_f3db()
        liv_rf_json = self._serialize_liv_rf()
        samples     = self._get_samples()
        tests       = self._get_tests()
        n_wires_arr = self.n_wires_array

        return f"""
<div class="led-block" id="{sid}_wrap">
  <div class="led-block-header">
    <span class="led-block-num">{num_h}</span>
    <span class="led-block-title">{title_h}</span>
    <span class="led-block-sub">{sub_h}</span>
  </div>
  <div class="led-block-rule"></div>

  <!-- ── Sélecteurs ── -->
  <div class="vlc-toolbar">
    <div class="vlc-field">
      <label class="vlc-label">SAMPLE</label>
      <select class="vlc-sel" id="{sid}_sel_sample"></select>
    </div>
    <div class="vlc-field">
      <label class="vlc-label">TEST f-3dB</label>
      <select class="vlc-sel" id="{sid}_sel_test"></select>
    </div>
    <div class="vlc-field">
      <label class="vlc-label">J₀ — bit 0 (A/cm²)</label>
      <input class="vlc-inp" id="{sid}_j0" type="number" step="0.001" value="0.2">
    </div>
    <div class="vlc-field">
      <label class="vlc-label">J₁ — bit 1 (A/cm²)</label>
      <input class="vlc-inp" id="{sid}_j1" type="number" step="1" value="100">
    </div>
  </div>

  <!-- ── 4 graphes ── -->
  <div class="vlc-plots-row">
    <div class="vlc-plot-wrap">
      <div class="vlc-plot-title">EQE vs J</div>
      <div id="{sid}_p_eqe" style="height:{h}px;"></div>
    </div>
    <div class="vlc-plot-wrap">
      <div class="vlc-plot-title">L/fil vs J (µW)</div>
      <div id="{sid}_p_luw" style="height:{h}px;"></div>
      <div id="{sid}_warn_luw" class="vlc-warn" style="display:none;">
        ⚠ J₀ ≤ J_min des données — L/fil forcé à 0 (LED éteinte en bit-0)
      </div>
    </div>
    <div class="vlc-plot-wrap">
      <div class="vlc-plot-title">J vs V</div>
      <div id="{sid}_p_jv" style="height:{h}px;"></div>
    </div>
    <div class="vlc-plot-wrap">
      <div class="vlc-plot-title">f-3dB vs J (MHz)</div>
      <div id="{sid}_p_f3db" style="height:{h}px;"></div>
    </div>
  </div>

  <!-- ── Panneaux paramètres ── -->
  <div class="vlc-panels-row">

    <!-- Driver -->
    <div class="vlc-panel">
      <div class="vlc-panel-title">µLEDs driver</div>
      <svg id="{sid}_chron" viewBox="0 0 300 72" width="100%" style="display:block;margin:6px 0 4px;"></svg>
      <div class="vlc-panel-formula">E = P_static/Rb + C_cmos×V_logic² + C_DS×(V₁−V₀)²</div>
      <div class="vlc-field"><label class="vlc-label">Conso statique (mW)</label>
        <input class="vlc-inp" id="{sid}_p_static" type="number" step="0.0001" value="0.02"></div>
      <div class="vlc-field"><label class="vlc-label">C_CMOS grille (fF)</label>
        <input class="vlc-inp" id="{sid}_p_ccmos" type="number" step="1" value="50"></div>
      <div class="vlc-field"><label class="vlc-label">V_logic (V)</label>
        <input class="vlc-inp" id="{sid}_p_vlogic" type="number" step="0.01" value="1.2"></div>
      <div class="vlc-field"><label class="vlc-label">C_DS drain-source (fF)</label>
        <input class="vlc-inp" id="{sid}_p_cds" type="number" step="1" value="50"></div>
      <div class="vlc-field"><label class="vlc-label">Fenêtre bit (ns)</label>
        <input class="vlc-inp" id="{sid}_p_twin" type="number" step="0.01" value="1"></div>
      <div class="vlc-field"><label class="vlc-label">Débit (Gbit/s)</label>
        <input class="vlc-inp" id="{sid}_p_rb" type="number" step="0.001" value="0.125"></div>
      <div class="vlc-field"><label class="vlc-label">Temps montée (ns)</label>
        <input class="vlc-inp" id="{sid}_p_tr" type="number" step="0.001" value="0.5"></div>
      <div class="vlc-field"><label class="vlc-label">Temps descente (ns)</label>
        <input class="vlc-inp" id="{sid}_p_tf" type="number" step="0.001" value="0.5"></div>
    </div>

    <!-- LED array -->
    <div class="vlc-panel">
      <div class="vlc-panel-title">µLEDs réseau &amp; couplage</div>
      <svg id="{sid}_arr" viewBox="0 0 300 106" width="100%" style="display:block;margin:6px 0 4px;"></svg>
      <div class="vlc-panel-formula">E_LED = I × V × T_window</div>
      <div class="vlc-field"><label class="vlc-label">Fils/LED</label>
        <input class="vlc-inp" id="{sid}_p_nwires" type="number" step="1" min="1" value="{n_wires_arr}"></div>
      <div class="vlc-field" style="border-top:1px dashed #C4CEDE;margin-top:4px;padding-top:4px;">
        <label class="vlc-label" style="color:#7C3AED;">Cols visuel (X)</label>
        <input class="vlc-inp" id="{sid}_p_gcols" type="number" step="1" min="1" max="10" value="4"></div>
      <div class="vlc-field"><label class="vlc-label" style="color:#7C3AED;">Rangées visuel (Y)</label>
        <input class="vlc-inp" id="{sid}_p_grows" type="number" step="1" min="1" max="6" value="3"></div>
      <div class="vlc-field"><label class="vlc-label">λ photon (nm)</label>
        <input class="vlc-inp" id="{sid}_p_lambda" type="number" step="1" value="450"></div>
      <div class="vlc-field"><label class="vlc-label">Couplage LED→PD (% SL)</label>
        <input class="vlc-inp" id="{sid}_p_kpl" type="number" step="0.01" value="4"></div>
      <div class="vlc-field"><label class="vlc-label">Xtalk voisins (ppm)</label>
        <input class="vlc-inp" id="{sid}_p_xtalk" type="number" step="0.001" value="0.1"></div>
      <div class="vlc-field"><label class="vlc-label">Pitch x (µm)</label>
        <input class="vlc-inp" id="{sid}_p_xpitch" type="number" step="1" value="22"></div>
      <div class="vlc-field"><label class="vlc-label">Pitch y (µm)</label>
        <input class="vlc-inp" id="{sid}_p_ypitch" type="number" step="1" value="22"></div>
    </div>

    <!-- Détecteur + ampli -->
    <div class="vlc-panel">
      <div class="vlc-panel-title">Photodetecteur</div>
      <svg id="{sid}_det" viewBox="0 0 300 110" width="100%" style="display:block;margin:6px 0 4px;"></svg>
      <div class="vlc-field"><label class="vlc-label">Type</label>
        <select class="vlc-sel" id="{sid}_p_rxtype">
          <option value="SPAD">SPAD</option>
          <option value="APD">APD</option>
        </select></div>
      <div class="vlc-field"><label class="vlc-label">Ratio det/spot</label>
        <input class="vlc-inp" id="{sid}_p_rdet" type="number" step="0.001" value="0.17"></div>
      <div class="vlc-field"><label class="vlc-label">Nb détecteurs</label>
        <input class="vlc-inp" id="{sid}_p_ndet" type="number" step="1" value="2"></div>
      <div id="{sid}_spad_fields">
        <div class="vlc-field"><label class="vlc-label">Q_avalanche (fC)</label>
          <input class="vlc-inp" id="{sid}_p_qa" type="number" value="20"></div>
        <div class="vlc-field"><label class="vlc-label">V_bias (V)</label>
          <input class="vlc-inp" id="{sid}_p_vbias" type="number" value="16"></div>
        <div class="vlc-field"><label class="vlc-label">PDE (%)</label>
          <input class="vlc-inp" id="{sid}_p_pde" type="number" step="0.5" value="20"></div>
        <div class="vlc-field"><label class="vlc-label">DCR (Hz)</label>
          <input class="vlc-inp" id="{sid}_p_dcr" type="number" step="10" value="1000"></div>
        <div class="vlc-field"><label class="vlc-label">Seuil décision (k SPAD)</label>
          <input class="vlc-inp" id="{sid}_p_thresh" type="number" step="1" min="1" value="1"></div>
      </div>
      <div class="vlc-panel-title" style="margin-top:12px;">Ampli lecture</div>
      <div class="vlc-field"><label class="vlc-label">Puissance ampli (mW)</label>
        <input class="vlc-inp" id="{sid}_p_pampli" type="number" step="0.00001" value="0.005"></div>
    </div>
  </div>

  <!-- ── Toast ── -->
  <div class="vlc-toast" id="{sid}_toast">✓ Tableau mis à jour</div>

  <!-- ── Table résumé ── -->
  <div class="vlc-summary-wrap">
    <div style="display:flex;align-items:center;gap:10px;margin-bottom:10px;">
      <div class="vlc-panel-title" style="margin-bottom:0;flex:1;">Récapitulatif</div>
      <button class="vlc-ref-btn" id="{sid}_ref_btn" onclick="{sid}_setRef()" title="Figer l'état actuel comme référence pour le diff">📌 Figer référence</button>
      <button class="vlc-ref-btn vlc-ref-btn--clear" onclick="{sid}_clearRef()" title="Effacer la référence">✕ Réf.</button>
      <input class="vlc-cfg-name" id="{sid}_cfg_name" type="text" placeholder="Nom de la config…">
      <button class="vlc-save-btn" onclick="{sid}_saveConfig()">💾 Sauvegarder</button>
    </div>
    <table class="vlc-tbl" id="{sid}_tbl">
      <thead>
        <tr>
          <th>Paramètre</th>
          <th>J₀ (bit 0)</th>
          <th>J₁ (bit 1)</th>
        </tr>
      </thead>
      <tbody id="{sid}_tbody"></tbody>
    </table>
  </div>
</div>

<style>
#{sid}_wrap .vlc-toolbar {{
  display: flex;
  flex-wrap: wrap;
  gap: 14px;
  align-items: flex-end;
  margin-bottom: 14px;
}}
/* ── Toolbar : label au-dessus, input en-dessous ── */
#{sid}_wrap .vlc-field {{
  display: flex;
  flex-direction: column;
  gap: 3px;
}}
#{sid}_wrap .vlc-label {{
  font-family: "IBM Plex Mono", monospace;
  font-size: 9px;
  font-weight: 700;
  letter-spacing: .1em;
  color: #64748B;
  text-transform: uppercase;
}}
#{sid}_wrap .vlc-sel, #{sid}_wrap .vlc-inp {{
  font-family: "IBM Plex Mono", monospace;
  font-size: 11px;
  font-weight: 600;
  color: #0A2463;
  background: #F8FAFF;
  border: 1px solid #C4CEDE;
  border-radius: 4px;
  padding: 4px 8px;
  min-width: 120px;
}}
#{sid}_wrap .vlc-sel:focus, #{sid}_wrap .vlc-inp:focus {{
  outline: none;
  border-color: #D4AF37;
  background: #fff;
  box-shadow: 0 0 0 2px rgba(212,175,55,.15);
}}

/* ── Panneaux : champ en row label|input ── */
#{sid}_wrap .vlc-panel .vlc-field {{
  flex-direction: row;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  padding: 5px 8px;
  margin: 0 -8px;
  border-radius: 4px;
}}
#{sid}_wrap .vlc-panel .vlc-field:nth-child(odd) {{
  background: #EEF2FB;
}}
#{sid}_wrap .vlc-panel .vlc-field:nth-child(even) {{
  background: #fff;
}}
/* label dans panneau */
#{sid}_wrap .vlc-panel .vlc-label {{
  flex: 1;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  color: #1E3A5F;
  font-weight: 700;
  font-size: 9.5px;
  letter-spacing: .04em;
  text-transform: none;
}}
/* input/select dans panneau */
#{sid}_wrap .vlc-panel .vlc-inp,
#{sid}_wrap .vlc-panel .vlc-sel {{
  min-width: 0;
  width: 88px;
  flex-shrink: 0;
  text-align: right;
  background: #fff;
  border-color: #B0BCCE;
  padding: 3px 6px;
  font-size: 11px;
}}
/* ── Ref button ── */
#{sid}_wrap .vlc-ref-btn {{
  font-family: "IBM Plex Mono", monospace;
  font-size: 9px;
  font-weight: 700;
  letter-spacing: .05em;
  color: #C2410C;
  background: #FFF7ED;
  border: 1px solid #FED7AA;
  border-radius: 5px;
  padding: 5px 10px;
  cursor: pointer;
  white-space: nowrap;
  transition: background .15s;
  opacity: 0.7;
}}
#{sid}_wrap .vlc-ref-btn:hover {{ background: #FFEDD5; opacity:1; }}
#{sid}_wrap .vlc-ref-btn--clear {{
  color: #64748B;
  background: #F1F5F9;
  border-color: #CBD5E1;
}}
#{sid}_wrap .vlc-ref-btn--clear:hover {{ background: #E2E8F0; }}
/* ── Save button ── */
#{sid}_wrap .vlc-save-btn {{
  font-family: "IBM Plex Mono", monospace;
  font-size: 10px;
  font-weight: 700;
  letter-spacing: .06em;
  color: #fff;
  background: #0A2463;
  border: none;
  border-radius: 5px;
  padding: 6px 14px;
  cursor: pointer;
  white-space: nowrap;
  transition: background .15s;
}}
#{sid}_wrap .vlc-save-btn:hover {{ background: #1a3a7a; }}
#{sid}_wrap .vlc-save-btn:active {{ background: #D4AF37; color: #0A2463; }}
#{sid}_wrap .vlc-cfg-name {{
  font-family: "IBM Plex Mono", monospace;
  font-size: 11px;
  color: #0A2463;
  border: 1px solid #C4CEDE;
  border-radius: 4px;
  padding: 5px 10px;
  background: #F8FAFF;
  width: 180px;
}}
#{sid}_wrap .vlc-cfg-name:focus {{ outline:none; border-color:#D4AF37; }}
/* ── Toast ── */
#{sid}_wrap .vlc-toast {{
  position: fixed;
  bottom: 28px;
  right: 28px;
  background: #0A2463;
  color: #D4AF37;
  font-family: "IBM Plex Mono", monospace;
  font-size: 11px;
  font-weight: 700;
  letter-spacing: .08em;
  padding: 8px 16px;
  border-radius: 6px;
  border: 1px solid #D4AF37;
  box-shadow: 0 4px 16px rgba(10,36,99,.18);
  opacity: 0;
  pointer-events: none;
  transition: opacity .2s ease;
  z-index: 9999;
}}
#{sid}_wrap .vlc-toast.show {{
  opacity: 1;
}}
#{sid}_wrap .vlc-plots-row {{
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 10px;
  margin-bottom: 16px;
}}
@media (max-width: 900px) {{
  #{sid}_wrap .vlc-plots-row {{ grid-template-columns: repeat(2, 1fr); }}
}}
#{sid}_wrap .vlc-plot-wrap {{
  background: #F8F9FD;
  border: 1px solid #E4E8F4;
  border-radius: 6px;
  padding: 8px;
}}
#{sid}_wrap .vlc-plot-title {{
  font-family: "IBM Plex Mono", monospace;
  font-size: 9px;
  font-weight: 700;
  letter-spacing: .1em;
  color: #0A2463;
  text-transform: uppercase;
  margin-bottom: 4px;
}}
#{sid}_wrap .vlc-panels-row {{
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 12px;
  margin-bottom: 16px;
}}
@media (max-width: 900px) {{
  #{sid}_wrap .vlc-panels-row {{ grid-template-columns: 1fr; }}
}}
#{sid}_wrap .vlc-panel {{
  background: #fff;
  border: 1px solid #C4CEDE;
  border-top: 3px solid #0A2463;
  border-radius: 8px;
  padding: 12px 16px;
  display: flex;
  flex-direction: column;
  gap: 2px;
  box-shadow: 0 2px 8px rgba(10,36,99,.06);
}}
#{sid}_wrap .vlc-panels-row > .vlc-panel:nth-child(2) {{
  border-top-color: #2563EB;
}}
#{sid}_wrap .vlc-panels-row > .vlc-panel:nth-child(3) {{
  border-top-color: #7C3AED;
}}
#{sid}_wrap .vlc-panel-title {{
  font-family: "IBM Plex Mono", monospace;
  font-size: 10px;
  font-weight: 800;
  letter-spacing: .12em;
  color: #0A2463;
  text-transform: uppercase;
  padding-bottom: 6px;
  margin-bottom: 4px;
  border-bottom: 2px solid #E4E8F4;
}}
#{sid}_wrap .vlc-panel-formula {{
  font-family: "IBM Plex Mono", monospace;
  font-size: 9px;
  color: #3B5280;
  background: #EEF2FB;
  border-left: 3px solid #0A2463;
  border-radius: 0 4px 4px 0;
  padding: 5px 10px;
  margin-bottom: 6px;
  line-height: 1.5;
}}
#{sid}_wrap .vlc-summary-wrap {{
  background: #F8F9FD;
  border: 1px solid #E4E8F4;
  border-radius: 8px;
  padding: 14px;
}}
#{sid}_wrap .vlc-tbl {{
  width: 100%;
  border-collapse: collapse;
  font-family: "IBM Plex Mono", monospace;
  font-size: 11px;
}}
#{sid}_wrap .vlc-tbl th {{
  background: #0A2463;
  color: #fff;
  font-weight: 700;
  padding: 7px 12px;
  text-align: left;
  font-size: 10px;
  letter-spacing: .05em;
}}
#{sid}_wrap .vlc-tbl td {{
  padding: 6px 12px;
  color: #4A5580;
  border-bottom: 1px solid #E4E8F4;
}}
#{sid}_wrap .vlc-tbl tr:nth-child(even) td {{ background: #fff; }}
#{sid}_wrap .vlc-tbl td:first-child {{
  font-weight: 700;
  color: #0A2463;
}}
#{sid}_wrap .vlc-tbl td.highlight {{ color: #D4AF37; font-weight: 700; }}
#{sid}_wrap .vlc-tbl td.changed {{
  color: #C2410C;
  font-weight: 700;
  background: #FFF7ED !important;
  border-left: 3px solid #F97316;
  transition: background .3s, color .3s;
}}
#{sid}_wrap .vlc-tbl td.changed.highlight {{
  color: #C2410C;
}}
#{sid}_wrap .vlc-warn {{
  font-family: "IBM Plex Mono", monospace;
  font-size: 9px;
  font-weight: 700;
  color: #92400E;
  background: #FEF3C7;
  border: 1px solid #FCD34D;
  border-left: 3px solid #F59E0B;
  border-radius: 0 4px 4px 0;
  padding: 4px 8px;
  margin-top: 4px;
}}
</style>

<script>
(function() {{
  var sid = "{sid}";
  var LIV    = {liv_json};
  var LIV_RF = {liv_rf_json};
  var F3DB   = {f3_json};
  var SAMPLES = {samples};
  var TESTS   = {tests};
  var _baseRows = null;   /* référence figée pour le diff persistant (reset manuel) */
  var _lastRows = [];     /* dernier jeu de résultats (pour le save config) */

  /* ── Physique ── */
  var H_PLANCK = 6.626e-34, C_LIGHT = 3e8;
  function ephoton(lnm) {{ return H_PLANCK * C_LIGHT / ((lnm||450)*1e-9); }}

  function interp(arr, j, ycol) {{
    /* interpolation linéaire sur tableau trié par J croissant */
    if (!arr || arr.length === 0) return 0;
    var xs = arr.map(function(r) {{ return r.J; }});
    var ys = arr.map(function(r) {{ return r[ycol]; }});
    if (j <= xs[0]) return ys[0];
    if (j >= xs[xs.length-1]) return ys[xs.length-1];
    for (var i=1; i<xs.length; i++) {{
      if (j <= xs[i]) {{
        var t = (j - xs[i-1]) / (xs[i] - xs[i-1]);
        var v = ys[i-1] + t * (ys[i] - ys[i-1]);
        return isNaN(v) ? 0 : v;
      }}
    }}
    return 0;
  }}

  function comb(n, k) {{
    if (k < 0 || k > n) return 0;
    var res = 1;
    for (var i = 1; i <= k; i++) {{
      res = res * (n - (k - i)) / i;
    }}
    return res;
  }}

  function BER_SPAD(P0_W, P1_W, PDE, DCR, Twindow, Eph, Ndet, Threshold_Ndet, Rdetspot) {{
    var Nph0 = P0_W * Rdetspot * Twindow / Eph;
    var Nph1 = P1_W * Rdetspot * Twindow / Eph;
    var lambda_0 = DCR * Twindow + PDE * Nph0;
    var lambda_1 = lambda_0 + PDE * Nph1;
    var p0 = 1 - Math.exp(-lambda_0);
    var p1 = 1 - Math.exp(-lambda_1);
    var Pfalse = 0;
    for (var k = Threshold_Ndet; k <= Ndet; k++) {{
      Pfalse += comb(Ndet, k) * Math.pow(p0, k) * Math.pow(1 - p0, Ndet - k);
    }}
    var Pmiss = 0;
    for (var j = 0; j < Threshold_Ndet; j++) {{
      Pmiss += comb(Ndet, j) * Math.pow(p1, j) * Math.pow(1 - p1, Ndet - j);
    }}
    var ber = 0.5 * (Pmiss + Pfalse);
    return {{ ber: ber, pmiss: Pmiss, pfalse: Pfalse, Nph0: Nph0, Nph1: Nph1 }};
  }}

  /* ── Peupler les selects ── */
  function fillSel(id, vals, def) {{
    var sel = document.getElementById(id);
    sel.innerHTML = "";
    vals.forEach(function(v) {{
      var o = document.createElement("option");
      o.value = v; o.textContent = v;
      if (v === def) o.selected = true;
      sel.appendChild(o);
    }});
  }}
  fillSel(sid+"_sel_sample", SAMPLES, SAMPLES[0]);
  fillSel(sid+"_sel_test",   TESTS,   TESTS[0]);

  /* ── Toggle SPAD fields ── */
  function toggleDetFields() {{
    var rx = document.getElementById(sid+"_p_rxtype").value;
    document.getElementById(sid+"_spad_fields").style.display = (rx==="SPAD") ? "" : "none";
  }}
  document.getElementById(sid+"_p_rxtype").onchange = function() {{
    toggleDetFields();
    update();
  }};
  toggleDetFields();

  /* ── Helpers getVal ── */
  function $v(id) {{ return parseFloat(document.getElementById(id).value) || 0; }}
  function $s(id) {{ return document.getElementById(id).value; }}

  var PLYCFG = {{responsive:true, displaylogo:false,
    modeBarButtonsToRemove:["autoScale2d","toggleSpikelines","sendDataToCloud"]}};

  function baseLayout(xlog, ylog, xlabel, ylabel) {{
    return {{
      paper_bgcolor:"rgba(0,0,0,0)", plot_bgcolor:"#F8F9FD",
      font:{{family:"IBM Plex Mono,monospace", color:"#4A5580", size:10}},
      margin:{{t:10, r:12, b:46, l:56}},
      xaxis: {{
        type: xlog ? "log" : "-",
        title: {{text: xlabel, font:{{size:11, color:"#0A2463"}}, standoff:6}},
        gridcolor:"#E4E8F4", linecolor:"#E4E8F4", zerolinecolor:"#E4E8F4",
        tickfont:{{size:9}},
      }},
      yaxis: {{
        type: ylog ? "log" : "-",
        title: {{text: ylabel, font:{{size:11, color:"#0A2463"}}, standoff:6}},
        gridcolor:"#E4E8F4", linecolor:"#E4E8F4", zerolinecolor:"#E4E8F4",
        tickfont:{{size:9}},
      }},
      hoverlabel:{{bgcolor:"#0A2463", bordercolor:"#D4AF37",
        font:{{family:"IBM Plex Mono", size:10, color:"white"}}}},
      showlegend:false,
    }};
  }}

  function vline(x, color) {{
    return {{
      type:"line", x0:x, x1:x, y0:0, y1:1,
      xref:"x", yref:"paper",
      line:{{color:color, width:2, dash:"dash"}},
    }};
  }}

  function hline(y, color) {{
    return {{
      type:"line", x0:0, x1:1, y0:y, y1:y,
      xref:"paper", yref:"y",
      line:{{color:color, width:2, dash:"dash"}},
    }};
  }}

  function plotOrReact(elId, traces, layout) {{
    var el = document.getElementById(elId);
    if (el && el.data) Plotly.react(elId, traces, layout, PLYCFG);
    else               Plotly.newPlot(elId, traces, layout, PLYCFG);
  }}

  /* ── SVG helpers ── */
  var NS = "http://www.w3.org/2000/svg";
  function svgEl(tag, attrs) {{
    var el = document.createElementNS(NS, tag);
    Object.keys(attrs).forEach(function(k) {{ el.setAttribute(k, attrs[k]); }});
    return el;
  }}
  function svgText(txt, attrs) {{
    var el = svgEl("text", attrs);
    el.textContent = txt;
    return el;
  }}

  /* ── Chronogramme — 2 périodes, fronts exponentiels ── */
  function drawChrono(Twin_ns, tr_ns, tf_ns, Rb_Gbps) {{
    var sv = document.getElementById(sid+"_chron");
    if (!sv) return;
    sv.innerHTML = "";
    var W=300, H=72, px=28, pr=6, pt=14, pb=24;
    var pw = W - px - pr;
    var ph = H - pt - pb;
    var yH = pt, yL = pt + ph;

    sv.appendChild(svgEl("rect",{{x:0,y:0,width:W,height:H,fill:"#EEF2FB",rx:5}}));

    /* ── constantes physiques ── */
    var Tw  = Math.max(Twin_ns, 0.001);
    var tau_r = Math.max(tr_ns, 0.0001);
    var tau_f = Math.max(tf_ns, 0.0001);
    /* période = 1/débit (Rb en Gbit/s → T_period en ns) */
    var T_period = (Rb_Gbps > 0) ? 1.0 / Rb_Gbps : Tw * 1.5;
    if (T_period < Tw) T_period = Tw;
    var T_dead = T_period - Tw;          /* zone morte */

    /* signal normalisé [0..1] à l'instant t dans une période */
    var s_window = 1 - Math.exp(-Tw / tau_r); /* niveau atteint à la fin de la fenetre */
    function sig(t) {{
      if (t <= 0) return 0;
      if (t <= Tw) return 1 - Math.exp(-t / tau_r);
      return s_window * Math.exp(-(t - Tw) / tau_f);
    }}
    /* y pixel : s=0→yL, s=1→yH */
    function sy(s) {{ return yL - (yL - yH) * Math.max(0, Math.min(1, s)); }}

    /* ── zone morte : fond grisé ── */
    var periodPx = pw / 2;       /* chaque période occupe la moitié du plot */
    var scalePx  = periodPx / T_period;
    var xDeadStart = px + Tw * scalePx;
    var xDeadEnd   = px + T_period * scalePx;
    [0, periodPx].forEach(function(off) {{
      sv.appendChild(svgEl("rect",{{
        x: xDeadStart+off, y: yH,
        width: xDeadEnd - xDeadStart, height: yL - yH,
        fill:"#94a3b8", opacity:"0.12"
      }}));
    }});

    /* ── niveaux de référence (tracé avant la courbe) ── */
    ["#16a34a","#2563eb"].forEach(function(c,i) {{
      var yy = i===0 ? yL : yH;
      sv.appendChild(svgEl("line",{{x1:px,y1:yy,x2:W-pr,y2:yy,
        stroke:c,"stroke-width":"0.7","stroke-dasharray":"3 3",opacity:"0.5"}}));
    }});
    sv.appendChild(svgText("J₁",{{x:px-4,y:yH+3.5,"text-anchor":"end",fill:"#2563eb",
      "font-size":"7","font-family":"IBM Plex Mono,monospace","font-weight":"700"}}));
    sv.appendChild(svgText("J₀",{{x:px-4,y:yL+3.5,"text-anchor":"end",fill:"#16a34a",
      "font-size":"7","font-family":"IBM Plex Mono,monospace","font-weight":"700"}}));

    /* ── tracé des 2 périodes ── */
    var N = 80;
    function buildPeriodPts(xOff) {{
      var pts = [];
      for (var i=0; i<=N; i++) {{
        var t = T_period * i / N;
        pts.push((xOff + t * scalePx).toFixed(2) + "," + sy(sig(t)).toFixed(2));
      }}
      return pts;
    }}

    [0, periodPx].forEach(function(xOff) {{
      var pts = buildPeriodPts(px + xOff);
      /* remplissage */
      var fillPts = [(px+xOff)+","+yL].concat(pts).concat([(px+xOff+periodPx)+","+yL]);
      sv.appendChild(svgEl("polygon",{{points:fillPts.join(" "),fill:"#0A2463",opacity:"0.08"}}));
      /* courbe */
      sv.appendChild(svgEl("polyline",{{points:pts.join(" "),fill:"none",
        stroke:"#0A2463","stroke-width":"1.8","stroke-linejoin":"round"}}));
    }});

    /* séparateur de période */
    var xSep = px + periodPx;
    sv.appendChild(svgEl("line",{{x1:xSep,y1:yH,x2:xSep,y2:yL,
      stroke:"#94a3b8","stroke-width":"0.8","stroke-dasharray":"2 2"}}));

    /* ── annotations τr et τf sur la 1ère période ── */
    /* τr : point à 63% = (1-1/e) de la montée maximale → t = τr */
    var x_tr = px + tau_r * scalePx;
    var y_tr = sy(1 - 1/Math.E);   /* 63% du max théorique */
    if (x_tr < px + Tw * scalePx * 0.9) {{
      sv.appendChild(svgEl("line",{{x1:x_tr,y1:yH+1,x2:x_tr,y2:y_tr,
        stroke:"#0A2463","stroke-width":"0.7","stroke-dasharray":"2 2"}}));
      sv.appendChild(svgEl("line",{{x1:px,y1:y_tr,x2:x_tr,y2:y_tr,
        stroke:"#0A2463","stroke-width":"0.7","stroke-dasharray":"2 2"}}));
      sv.appendChild(svgText("τr="+tr_ns.toFixed(2)+"ns",{{x:x_tr+2,y:y_tr-2,
        fill:"#0A2463","font-size":"5.5","font-family":"IBM Plex Mono,monospace","font-weight":"700"}}));
    }}

    /* τf : point à 37% (1/e) de la descente → t = Tw + τf */
    var x_tf = px + (Tw + tau_f) * scalePx;
    var y_tf = sy(s_window / Math.E);
    if (x_tf < px + periodPx * 0.98) {{
      sv.appendChild(svgEl("line",{{x1:x_tf,y1:yL-1,x2:x_tf,y2:y_tf,
        stroke:"#0A2463","stroke-width":"0.7","stroke-dasharray":"2 2"}}));
      sv.appendChild(svgEl("line",{{x1:x_tf,y1:y_tf,x2:px+periodPx,y2:y_tf,
        stroke:"#0A2463","stroke-width":"0.7","stroke-dasharray":"2 2"}}));
      sv.appendChild(svgText("τf="+tf_ns.toFixed(2)+"ns",{{x:x_tf-2,y:y_tf-2,"text-anchor":"end",
        fill:"#0A2463","font-size":"5.5","font-family":"IBM Plex Mono,monospace","font-weight":"700"}}));
    }}

    /* ── accolades en bas ── */
    var yBrace = yL + 6;
    /* T_bit */
    var xTw = px + Tw * scalePx;
    sv.appendChild(svgEl("line",{{x1:px,y1:yBrace,x2:xTw,y2:yBrace,stroke:"#2563EB","stroke-width":"0.8"}}));
    sv.appendChild(svgEl("line",{{x1:px,y1:yBrace-2,x2:px,y2:yBrace+2,stroke:"#2563EB","stroke-width":"0.8"}}));
    sv.appendChild(svgEl("line",{{x1:xTw,y1:yBrace-2,x2:xTw,y2:yBrace+2,stroke:"#2563EB","stroke-width":"0.8"}}));
    sv.appendChild(svgText("T_bit="+Tw.toFixed(2)+"ns",{{x:(px+xTw)/2,y:yBrace+8,"text-anchor":"middle",
      fill:"#2563EB","font-size":"5.5","font-family":"IBM Plex Mono,monospace","font-weight":"700"}}));

    /* T_dead */
    if (T_dead > 0.001*Tw) {{
      var xPer = px + T_period * scalePx;
      sv.appendChild(svgEl("line",{{x1:xTw,y1:yBrace,x2:xPer,y2:yBrace,stroke:"#94a3b8","stroke-width":"0.8"}}));
      sv.appendChild(svgEl("line",{{x1:xTw,y1:yBrace-2,x2:xTw,y2:yBrace+2,stroke:"#94a3b8","stroke-width":"0.8"}}));
      sv.appendChild(svgEl("line",{{x1:xPer,y1:yBrace-2,x2:xPer,y2:yBrace+2,stroke:"#94a3b8","stroke-width":"0.8"}}));
      sv.appendChild(svgText("T_dead="+T_dead.toFixed(2)+"ns",{{x:(xTw+xPer)/2,y:yBrace+8,"text-anchor":"middle",
        fill:"#94a3b8","font-size":"5","font-family":"IBM Plex Mono,monospace"}}));
    }}

    /* T_période au-dessus */
    var xA=px, xB=px+pw;
    sv.appendChild(svgEl("line",{{x1:xA,y1:pt-5,x2:xB,y2:pt-5,stroke:"#64748B","stroke-width":"0.8"}}));
    sv.appendChild(svgEl("line",{{x1:xA,y1:pt-3,x2:xA,y2:pt-7,stroke:"#64748B","stroke-width":"0.8"}}));
    sv.appendChild(svgEl("line",{{x1:xB,y1:pt-3,x2:xB,y2:pt-7,stroke:"#64748B","stroke-width":"0.8"}}));
    sv.appendChild(svgText("2 × T_période = "+(2*T_period).toFixed(2)+" ns",{{x:(xA+xB)/2,y:pt-7,
      "text-anchor":"middle",fill:"#64748B","font-size":"5.8","font-family":"IBM Plex Mono,monospace"}}));
  }}

  /* ── Réseau LED & couplage (grille 2D) ── */
  function drawArray(Nwires, xpitch, ypitch, kpl_pct, xtalk_ppm, gcols, grows) {{
    var sv = document.getElementById(sid+"_arr");
    if (!sv) return;
    sv.innerHTML = "";
    var W=300, H=106;
    sv.appendChild(svgEl("rect",{{x:0,y:0,width:W,height:H,fill:"#EEF2FB",rx:5}}));

    /* grille pilotée par les params visuels gcols / grows */
    var cols = Math.max(1, Math.round(gcols));
    var rows = Math.max(1, Math.round(grows));
    var ledSize = Math.min(14, Math.floor((W - 60) / (cols + (cols-1)*0.5)));
    var gapX = Math.round(ledSize * 0.55), gapY = Math.round(ledSize * 0.55);
    var gridW = cols*ledSize + (cols-1)*gapX;
    var gridH = rows*ledSize + (rows-1)*gapY;
    var gridX0 = (W - gridW) / 2;
    var gridY0 = 10;

    /* ── Pitch x : double flèche entre col 0 et col 1 ── */
    if (cols > 1) {{
      var ax1 = gridX0 + ledSize/2, ax2 = gridX0 + ledSize + gapX + ledSize/2;
      var ay  = gridY0 + gridH + 7;
      sv.appendChild(svgEl("line",{{x1:ax1,y1:ay,x2:ax2,y2:ay,stroke:"#2563EB","stroke-width":"0.9"}}));
      sv.appendChild(svgEl("line",{{x1:ax1,y1:ay-2,x2:ax1,y2:ay+2,stroke:"#2563EB","stroke-width":"0.9"}}));
      sv.appendChild(svgEl("line",{{x1:ax2,y1:ay-2,x2:ax2,y2:ay+2,stroke:"#2563EB","stroke-width":"0.9"}}));
      sv.appendChild(svgText("Δx="+xpitch+"µm",{{x:(ax1+ax2)/2,y:ay+8,"text-anchor":"middle",
        fill:"#2563EB","font-size":"6","font-family":"IBM Plex Mono,monospace","font-weight":"700"}}));
    }}

    /* ── Pitch y : double flèche entre row 0 et row 1, à droite de la grille ── */
    if (rows > 1) {{
      var by1 = gridY0 + ledSize/2, by2 = gridY0 + ledSize + gapY + ledSize/2;
      var bx  = gridX0 + gridW + 8;
      sv.appendChild(svgEl("line",{{x1:bx,y1:by1,x2:bx,y2:by2,stroke:"#16a34a","stroke-width":"0.9"}}));
      sv.appendChild(svgEl("line",{{x1:bx-2,y1:by1,x2:bx+2,y2:by1,stroke:"#16a34a","stroke-width":"0.9"}}));
      sv.appendChild(svgEl("line",{{x1:bx-2,y1:by2,x2:bx+2,y2:by2,stroke:"#16a34a","stroke-width":"0.9"}}));
      sv.appendChild(svgText("Δy="+ypitch+"µm",{{x:bx+4,y:(by1+by2)/2+2,
        fill:"#16a34a","font-size":"6","font-family":"IBM Plex Mono,monospace","font-weight":"700"}}));
    }}

    /* ── Rayons de couplage vers spot détecteur ── */
    var detX = W/2, detY = H - 14, detR = 10 + Math.min(kpl_pct*0.35, 8);
    var kAlpha = Math.min(kpl_pct / 18, 0.55);
    var shown = 0;
    for (var r=0; r<rows; r++) {{
      for (var c=0; c<cols; c++) {{
        if (shown >= Nwires) break;
        var cx = gridX0 + c*(ledSize+gapX) + ledSize/2;
        var cy = gridY0 + r*(ledSize+gapY) + ledSize;
        sv.appendChild(svgEl("line",{{x1:cx,y1:cy,x2:detX,y2:detY-detR,
          stroke:"#D4AF37","stroke-width":"0.85",opacity:kAlpha.toFixed(2)}}));
        shown++;
      }}
    }}

    /* ── LEDs ── */
    shown = 0;
    for (var r=0; r<rows; r++) {{
      for (var c=0; c<cols; c++) {{
        if (shown >= Nwires) break;
        var lx = gridX0 + c*(ledSize+gapX);
        var ly = gridY0 + r*(ledSize+gapY);
        sv.appendChild(svgEl("rect",{{x:lx,y:ly,width:ledSize,height:ledSize,
          fill:"#0A2463",rx:"2"}}));
        sv.appendChild(svgEl("circle",{{cx:lx+ledSize/2,cy:ly+ledSize/2,r:"1.8",fill:"#D4AF37"}}));
        shown++;
      }}
    }}
    if (Nwires > cols*rows) {{
      sv.appendChild(svgText("… ×"+Nwires+" fils",{{x:gridX0+gridW+8,y:gridY0+gridH/2+3,
        fill:"#0A2463","font-size":"6.5","font-family":"IBM Plex Mono,monospace","font-weight":"700"}}));
    }}

    /* ── Spot détecteur ── */
    var detColor = "#7C3AED";
    sv.appendChild(svgEl("circle",{{cx:detX,cy:detY,r:detR,fill:detColor,opacity:"0.14"}}));
    sv.appendChild(svgEl("circle",{{cx:detX,cy:detY,r:detR,fill:"none",
      stroke:detColor,"stroke-width":"1.4"}}));
    sv.appendChild(svgText("PD",{{x:detX,y:detY+2.5,"text-anchor":"middle",
      fill:detColor,"font-size":"6.5","font-family":"IBM Plex Mono,monospace","font-weight":"800"}}));

    /* k_cpl label */
    sv.appendChild(svgText("k_cpl="+kpl_pct.toFixed(1)+"%",
      {{x:detX-detR-6,y:detY+2,"text-anchor":"end",
        fill:"#D4AF37","font-size":"6.5","font-family":"IBM Plex Mono,monospace","font-weight":"700"}}));
    if (xtalk_ppm > 0) {{
      sv.appendChild(svgText("xtalk="+xtalk_ppm.toFixed(2)+"ppm",
        {{x:detX+detR+6,y:detY+2,
          fill:"#94a3b8","font-size":"5.8","font-family":"IBM Plex Mono,monospace"}}));
    }}
  }}

  /* ── Schéma détecteur ── */
  function drawDetector(rxType, PDE_pct, DCR_hz, Qa_fC, Vbias, Ndet, Rdetspot) {{
    var sv = document.getElementById(sid+"_det");
    if (!sv) return;
    sv.innerHTML = "";
    var W=300, H=110;
    sv.appendChild(svgEl("rect",{{x:0,y:0,width:W,height:H,fill:"#EEF2FB",rx:5}}));

    var nShow = Math.min(Ndet, 5);
    var bw = 34, bh = 22, gap2 = 8;
    var totalW = nShow*bw + (nShow-1)*gap2;
    var bx0 = (W-totalW)/2, by = 48;
    var isSPAD = rxType === "SPAD";
    var detColor = isSPAD ? "#7C3AED" : "#2563EB";

    /* photon arrows from above */
    for (var i=0; i<nShow; i++) {{
      var cx = bx0 + i*(bw+gap2) + bw/2;
      /* 3 arrows per detector */
      [-6,0,6].forEach(function(dx) {{
        var ax = cx+dx;
        sv.appendChild(svgEl("line",{{x1:ax,y1:10,x2:ax,y2:by-3,
          stroke:"#D4AF37","stroke-width":"1.2"}}));
        /* arrowhead */
        sv.appendChild(svgEl("polygon",{{
          points:""+(ax-3)+","+(by-9)+" "+ax+","+(by-3)+" "+(ax+3)+","+(by-9),
          fill:"#D4AF37"}}));
      }});
    }}

    /* photon label */
    sv.appendChild(svgText("hν photons",{{x:W/2,y:8,"text-anchor":"middle",
      fill:"#D4AF37","font-size":"6.5","font-family":"IBM Plex Mono,monospace","font-weight":"700"}}));

    /* detector boxes */
    for (var i=0; i<nShow; i++) {{
      var bx = bx0 + i*(bw+gap2);
      sv.appendChild(svgEl("rect",{{x:bx,y:by,width:bw,height:bh,
        fill:detColor,opacity:"0.18",rx:"3"}}));
      sv.appendChild(svgEl("rect",{{x:bx,y:by,width:bw,height:bh,
        fill:"none",stroke:detColor,"stroke-width":"1.5",rx:"3"}}));
      sv.appendChild(svgText(isSPAD?"SPAD":"APD",{{x:bx+bw/2,y:by+bh/2+2,"text-anchor":"middle",
        fill:detColor,"font-size":"7","font-family":"IBM Plex Mono,monospace","font-weight":"800"}}));
    }}
    if (Ndet > nShow) {{
      sv.appendChild(svgText("×"+Ndet,{{x:bx0+totalW+6,y:by+bh/2+3,
        fill:detColor,"font-size":"7","font-family":"IBM Plex Mono,monospace","font-weight":"700"}}));
    }}

    /* PDE label */
    sv.appendChild(svgText("PDE = "+PDE_pct.toFixed(0)+"%",{{x:W/2,y:by-5,"text-anchor":"middle",
      fill:detColor,"font-size":"7","font-family":"IBM Plex Mono,monospace","font-weight":"700"}}));

    /* output signal / avalanche pulses */
    var ay = by+bh+3, ay2 = by+bh+18;
    for (var i=0; i<nShow; i++) {{
      var cx2 = bx0 + i*(bw+gap2) + bw/2;
      if (isSPAD) {{
        /* spike pulses for SPAD */
        [cx2-8, cx2, cx2+10].forEach(function(px2) {{
          sv.appendChild(svgEl("polyline",{{
            points:""+(px2-2)+","+ay2+" "+px2+","+ay+" "+(px2+2)+","+ay2,
            fill:"none",stroke:"#7C3AED","stroke-width":"1.2"}}));
        }});
      }} else {{
        /* smooth analog for APD */
        sv.appendChild(svgEl("polyline",{{
          points:""+(cx2-12)+","+ay2+" "+(cx2-6)+","+ay+" "+cx2+","+ay+" "+(cx2+6)+","+ay+" "+(cx2+12)+","+ay2,
          fill:"none",stroke:"#2563EB","stroke-width":"1.5","stroke-linejoin":"round"}}));
      }}
    }}

    /* DCR noise bar */
    var dcrLabel = DCR_hz >= 1e6 ? (DCR_hz/1e6).toFixed(1)+"MHz" : DCR_hz >= 1e3 ? (DCR_hz/1e3).toFixed(1)+"kHz" : DCR_hz.toFixed(0)+"Hz";
    var dcrBarW = Math.min(80, Math.log10(Math.max(DCR_hz,1)+1)*12);
    sv.appendChild(svgEl("rect",{{x:(W-dcrBarW)/2,y:H-12,width:dcrBarW,height:5,
      fill:"#94a3b8",rx:"2",opacity:"0.7"}}));
    sv.appendChild(svgText("DCR="+dcrLabel,{{x:W/2,y:H-2,"text-anchor":"middle",
      fill:"#64748B","font-size":"6","font-family":"IBM Plex Mono,monospace"}}));

    /* Qa×Vbias energy label (SPAD only) */
    if (isSPAD) {{
      var Eav_fJ = (Qa_fC * Vbias).toFixed(1);
      sv.appendChild(svgText("Qa×V_bias = "+Eav_fJ+" fJ/pulse",{{x:W/2,y:ay2+10,"text-anchor":"middle",
        fill:"#7C3AED","font-size":"6","font-family":"IBM Plex Mono,monospace","font-weight":"700"}}));
    }}
  }}

  /* ── Update principal ── */
  function update() {{
    var sample = $s(sid+"_sel_sample");
    var test   = $s(sid+"_sel_test");
    var j0 = $v(sid+"_j0");
    var j1 = $v(sid+"_j1");

    /* filtrage */
    var livRows  = LIV.filter(function(r)  {{ return r.sample === sample; }})
                      .sort(function(a,b)  {{ return a.J - b.J; }});
    var f3dbRows = F3DB.filter(function(r) {{ return r.sample === sample && r.test === test; }})
                       .sort(function(a,b) {{ return a.J - b.J; }});
    /* IV brut depuis fichier (overlay J vs V + interpolation Voltage) */
    var livRfRows = LIV_RF
      ? LIV_RF.filter(function(r) {{ return r.sample === sample; }})
              .sort(function(a,b)  {{ return a.J - b.J; }})
      : [];

    /* données graphes */
    var jLiv  = livRows.map(function(r)  {{ return r.J;     }});
    var eqe   = livRows.map(function(r)  {{ return r.EQE;   }});
    var luw   = livRows.map(function(r)  {{ return r.L_uw;  }});
    var vArr  = livRows.map(function(r)  {{ return r.V;     }});
    var jF3db = f3dbRows.map(function(r) {{ return r.J;     }});
    var f3Val = f3dbRows.map(function(r) {{ return r.f3db;  }});

    var lineStyle = {{color:"#0A2463", width:2}};
    var mkStyle   = {{color:"#0A2463", size:5}};

    /* EQE vs J */
    plotOrReact(sid+"_p_eqe",
      [{{type:"scatter", mode:"lines+markers", x:jLiv, y:eqe,
        line:lineStyle, marker:mkStyle,
        hovertemplate:"J=%{{x:.3g}}<br>EQE=%{{y:.2f}}%<extra></extra>"}}],
      Object.assign(baseLayout(true,false,"J (A/cm²)","EQE (%)"), {{
        shapes:[vline(j0,"#16a34a"), vline(j1,"#2563eb")]
      }})
    );

    /* L/fil vs J */
    plotOrReact(sid+"_p_luw",
      [{{type:"scatter", mode:"lines+markers", x:jLiv, y:luw,
        line:lineStyle, marker:mkStyle,
        hovertemplate:"J=%{{x:.3g}}<br>L=%{{y:.3g}} µW<extra></extra>"}}],
      Object.assign(baseLayout(true,true,"J (A/cm²)","L/fil (µW)"), {{
        shapes:[vline(j0,"#16a34a"), vline(j1,"#2563eb")]
      }})
    );

    /* J vs V — GOZER + overlay IV brut fichier */
    var jvTraces = [{{
      type:"scatter", mode:"lines+markers", name:"GOZER",
      x:vArr, y:jLiv,
      line:{{color:"#0A2463", width:2}}, marker:{{color:"#0A2463", size:5}},
      hovertemplate:"V=%{{x:.2f}} V<br>J=%{{y:.3g}} (GOZER)<extra></extra>"
    }}];
    if (livRfRows.length > 0) {{
      jvTraces.push({{
        type:"scatter", mode:"lines+markers", name:"Raw file",
        x:livRfRows.map(function(r){{return r.V;}}),
        y:livRfRows.map(function(r){{return r.J;}}),
        line:{{color:"#D4AF37", width:2, dash:"dot"}}, marker:{{color:"#D4AF37", size:4}},
        hovertemplate:"V=%{{x:.2f}} V<br>J=%{{y:.3g}} (raw)<extra></extra>"
      }});
    }}
    plotOrReact(sid+"_p_jv", jvTraces,
      Object.assign(baseLayout(false,true,"Voltage (V)","J (A/cm²)"), {{
        showlegend: livRfRows.length > 0,
        shapes:[hline(j0,"#16a34a"), hline(j1,"#2563eb")]
      }})
    );

    /* f-3dB vs J */
    plotOrReact(sid+"_p_f3db",
      [{{type:"scatter", mode:"lines+markers", x:jF3db, y:f3Val,
        line:lineStyle, marker:mkStyle,
        hovertemplate:"J=%{{x:.3g}}<br>f3dB=%{{y:.1f}} MHz<extra></extra>"}}],
      Object.assign(baseLayout(true,true,"J (A/cm²)","f-3dB (MHz)"), {{
        shapes:[vline(j0,"#16a34a"), vline(j1,"#2563eb")]
      }})
    );

    /* ── Calculs physique ── */
    /* paramètres driver */
    var p_static_W = $v(sid+"_p_static")  * 1e-3;
    var Ccmos_F    = $v(sid+"_p_ccmos")   * 1e-15;
    var Vlogic     = $v(sid+"_p_vlogic");
    var Cds_F      = $v(sid+"_p_cds")     * 1e-15;
    var Twin_s     = $v(sid+"_p_twin")    * 1e-9;
    var Rb_bs      = $v(sid+"_p_rb")      * 1e9;
    var Tr         = $v(sid+"_p_tr")      * 1e-9;
    var Tf         = $v(sid+"_p_tf")      * 1e-9;

    /* paramètres LED */
    var Nwires     = Math.max(1, Math.round($v(sid+"_p_nwires")));
    var lambda_nm  = $v(sid+"_p_lambda") || 450;
    var k_cpl      = ($v(sid+"_p_kpl") || 0) / 100;
    var k_xt       = ($v(sid+"_p_xtalk") * $v(sid+"_p_kpl") || 0) * 1e-6 / 100;
    var xpitch     = $v(sid+"_p_xpitch") || 22;
    var ypitch     = $v(sid+"_p_ypitch") || 22;
    var Eph        = ephoton(lambda_nm);

    /* paramètres détecteur */
    var rxType    = $s(sid+"_p_rxtype");
    var Rdetspot  = $v(sid+"_p_rdet") || 1;
    var Ndet      = Math.max(1, Math.round($v(sid+"_p_ndet")));
    var Qa_F      = ($v(sid+"_p_qa") || 20) * 1e-15;
    var Vbias     = $v(sid+"_p_vbias") || 16;
    var PDE       = ($v(sid+"_p_pde") || 20) / 100;
    var DCR       = $v(sid+"_p_dcr") || 1000;
    var Threshold_Ndet = Math.max(1, Math.round($v(sid+"_p_thresh")));
    var P_ampli_W = $v(sid+"_p_pampli") * 1e-3;

    /* Utiliser l'IV brut (fichier) pour les tensions si disponible */
    var vSrc = livRfRows.length > 0 ? livRfRows : livRows;

    /* Détection J₀ au minimum des données → LED éteinte */
    var jMin = livRows.length > 0 ? livRows[0].J : 0;
    var j0AtMin = livRows.length > 0 && j0 <= jMin;
    var warnEl = document.getElementById(sid+"_warn_luw");
    if (warnEl) warnEl.style.display = j0AtMin ? "" : "none";

    /* interpolations */
    var V0  = interp(vSrc,     j0, "V");
    var l0  = j0AtMin ? 0 : interp(livRows, j0, "L_uw");
    var EQE0= interp(livRows,  j0, "EQE");
    var f0  = interp(f3dbRows, j0, "f3db");

    var V1  = interp(vSrc,     j1, "V");
    var l1  = interp(livRows,  j1, "L_uw");
    var EQE1= interp(livRows,  j1, "EQE");
    var f1  = interp(f3dbRows, j1, "f3db");

    /* surface active */
    var S = Nwires * 25 * 1e-8; /* cm² (fil 5µm × 5µm) */

    /* puissances optiques reçues (µW → W) */
    var P_sig1_uW, P_sig0_uW;
    if (Tr > 0 && Rb_bs > 0) {{
      P_sig1_uW = l1 * Nwires * k_cpl * (Twin_s - Tr*(1 - Math.exp(-Twin_s/Tr))) / Twin_s;
      var fallTerm = (Tf > 0)
        ? l1 * Nwires * k_cpl * Tf * (Math.exp(-((1/Rb_bs)-Twin_s)/Tf) - Math.exp(-1/(Rb_bs*Tf))) / Twin_s
        : 0;
      P_sig0_uW = l0 * Nwires * k_cpl + fallTerm;
    }} else {{
      P_sig1_uW = l1 * Nwires * k_cpl;
      P_sig0_uW = l0 * Nwires * k_cpl;
    }}
    var P_xt_uW = l1 * Nwires * k_xt;
    var P_PD_1  = (P_sig1_uW + P_xt_uW) * 1e-6;
    var P_PD_0  = (P_sig0_uW + P_xt_uW) * 1e-6;

    /* courants LED */
    var I0 = j0 * S, I1 = j1 * S;
    var Pelec0 = V0 * I0, Pelec1 = V1 * I1;

    /* énergie LED (pJ/bit) */
    var E_led0 = Pelec0 * Twin_s * 1e12;
    var E_led1 = Pelec1 * Twin_s * 1e12;

    /* énergie driver */
    var E_drv = 0;
    if (Rb_bs > 0) {{
      E_drv = (p_static_W/Rb_bs + Ccmos_F*Vlogic*Vlogic + Cds_F*(V1-V0)*(V1-V0)) * 1e12;
    }}

    /* énergie détecteur */
    var E_det = Ndet * Qa_F * Vbias * 1e12;

    /* énergie ampli */
    var E_ampli = (Rb_bs > 0) ? P_ampli_W / Rb_bs * 1e12 : 0;

    /* total */
    var E_tot0 = E_drv + E_led0 + E_det + E_ampli;
    var E_tot1 = E_drv + E_led1 + E_det + E_ampli;

    /* BER */
    var ber_res, ber_str;
    if (rxType === "SPAD") {{
      var r = BER_SPAD(P_PD_0, P_PD_1, PDE, DCR, Twin_s, Eph, Ndet, Threshold_Ndet, Rdetspot);
      ber_res = r;
      ber_str = r.ber.toExponential(3);
    }} else {{
      ber_res = {{ber:1e-9, pmiss:0.5e-9, pfalse:0.5e-9, Nph0:0, Nph1:0}};
      ber_str = "1e-9 (APD model N/A)";
    }}

    /* TBit/s/mm² */
    var Tbit_mm2 = (xpitch*ypitch > 0) ? Rb_bs*1e-12 / (xpitch*ypitch*1e-6) : 0;

    function pct(num, den) {{ return den ? (100*num/den).toFixed(1)+"%" : "—"; }}
    function fmt_e(v) {{ return (v===0) ? "0" : v.toExponential(3); }}

    /* ── Table récapitulative ── */
    var rows = [
      ["J (A/cm²)",            j0.toFixed(0),           j1.toFixed(0)],
      ["Voltage (V)",          V0.toFixed(2),            V1.toFixed(2)],
      ["L/fil (µW)",           l0.toFixed(3),            l1.toFixed(3)],
      ["L réseau Nfils (µW)",  (l0*Nwires).toFixed(3),  (l1*Nwires).toFixed(3)],
      ["L sur chaque SPAD (µW)",(l0*Nwires*k_cpl).toFixed(4),(l1*Nwires*k_cpl).toFixed(4)],
      ["Nph sur chaque SPAD",  ber_res.Nph0.toFixed(0),  ber_res.Nph1.toFixed(0)],
      ["EQE (%)",              EQE0.toFixed(2),          EQE1.toFixed(2)],
      ["f-3dB (MHz)",          f0.toFixed(1),            f1.toFixed(1)],
      ["Énergie totale (pJ/bit)", fmt_e(E_tot0),         fmt_e(E_tot1)],
      ["Contributions",
        "Drv:"+pct(E_drv,E_tot0)+" LED:"+pct(E_led0,E_tot0)+" Det:"+pct(E_det,E_tot0)+" Ampli:"+pct(E_ampli,E_tot0),
        "Drv:"+pct(E_drv,E_tot1)+" LED:"+pct(E_led1,E_tot1)+" Det:"+pct(E_det,E_tot1)+" Ampli:"+pct(E_ampli,E_tot1)],
      ["BER", "—", ber_str],
      ["Contributions BER","—",
        "Miss:"+pct(0.5*ber_res.pmiss, ber_res.ber)+" False:"+pct(0.5*ber_res.pfalse, ber_res.ber)],
      ["TBit/s/mm²", "—", Tbit_mm2.toFixed(3)],
    ];

    var tbody = document.getElementById(sid+"_tbody");
    tbody.innerHTML = "";
    rows.forEach(function(r, ri) {{
      var tr = document.createElement("tr");
      r.forEach(function(cell, ci) {{
        var td = document.createElement("td");
        td.textContent = cell;
        var cls = "";
        if (ci > 0 && (r[0].indexOf("Énergie")>=0 || r[0]==="BER")) cls = "highlight";
        /* diff persistant contre la référence figée */
        if (ci > 0 && _baseRows && _baseRows[ri] && _baseRows[ri][ci] !== cell) {{
          cls = cls ? cls + " changed" : "changed";
        }}
        if (cls) td.className = cls;
        tr.appendChild(td);
      }});
      tbody.appendChild(tr);
    }});
    _lastRows = rows.map(function(r) {{ return r.slice(); }});
    /* mettre à jour le bouton reset : affiche le nombre de différences */
    (function() {{
      var btn = document.getElementById(sid+"_ref_btn");
      if (!btn) return;
      if (!_baseRows) {{ btn.textContent = "📌 Figer référence"; btn.style.opacity="0.7"; return; }}
      var nDiff = 0;
      rows.forEach(function(r,ri) {{
        r.forEach(function(cell,ci) {{
          if (ci>0 && _baseRows[ri] && _baseRows[ri][ci] !== cell) nDiff++;
        }});
      }});
      btn.textContent = nDiff > 0 ? "📌 Réf. : "+nDiff+" diff" : "📌 Réf. figée";
      btn.style.opacity = nDiff > 0 ? "1" : "0.7";
    }})();

    /* ── Schémas dynamiques ── */
    drawChrono(Twin_s*1e9, Tr*1e9, Tf*1e9, Rb_bs*1e-9);
    drawArray(Nwires, xpitch, ypitch, $v(sid+"_p_kpl"), $v(sid+"_p_xtalk"),
              $v(sid+"_p_gcols"), $v(sid+"_p_grows"));
    drawDetector($s(sid+"_p_rxtype"), PDE*100, DCR, Qa_F*1e15, Vbias, Ndet, Rdetspot);

    /* ── Toast ── */
    (function() {{
      var toast = document.getElementById(sid+"_toast");
      if (!toast) return;
      toast.classList.add("show");
      clearTimeout(toast._t);
      toast._t = setTimeout(function() {{ toast.classList.remove("show"); }}, 1400);
    }})();
  }}

  /* ── Listeners ── */
  [sid+"_sel_sample", sid+"_sel_test", sid+"_j0", sid+"_j1"].forEach(function(id) {{
    document.getElementById(id).addEventListener("change", update);
    document.getElementById(id).addEventListener("input",  update);
  }});
  [
    sid+"_p_static", sid+"_p_ccmos", sid+"_p_vlogic", sid+"_p_cds",
    sid+"_p_twin",   sid+"_p_rb",    sid+"_p_tr",     sid+"_p_tf",
    sid+"_p_nwires", sid+"_p_lambda",sid+"_p_kpl",    sid+"_p_xtalk",
    sid+"_p_xpitch", sid+"_p_ypitch",sid+"_p_gcols",  sid+"_p_grows",
    sid+"_p_rdet",   sid+"_p_ndet",
    sid+"_p_qa",     sid+"_p_vbias", sid+"_p_pde",    sid+"_p_dcr",    sid+"_p_thresh",
    sid+"_p_pampli",
  ].forEach(function(id) {{
    var el = document.getElementById(id);
    if (el) {{ el.addEventListener("change", update); el.addEventListener("input", update); }}
  }});

  window.addEventListener("resize", function() {{
    [sid+"_p_eqe", sid+"_p_luw", sid+"_p_jv", sid+"_p_f3db"].forEach(function(id) {{
      var el = document.getElementById(id);
      if (el && el.data) Plotly.Plots.resize(id);
    }});
  }});

  /* ── Save config ── */
  var _cfgCounter = 0;
  window[sid+"_saveConfig"] = function() {{
    _cfgCounter++;
    var nameEl = document.getElementById(sid+"_cfg_name");
    var name   = (nameEl && nameEl.value.trim()) || ("Config " + _cfgCounter);

    /* courbes de la sélection courante (max 80 pts pour limiter la taille) */
    var sample  = $s(sid+"_sel_sample");
    var test    = $s(sid+"_sel_test");
    var livRows = LIV.filter(function(r)  {{ return r.sample === sample; }})
                     .sort(function(a,b)  {{ return a.J - b.J; }});
    var f3Rows  = F3DB.filter(function(r) {{ return r.sample === sample && r.test === test; }})
                      .sort(function(a,b) {{ return a.J - b.J; }});

    function thin(arr, col, n) {{
      if (arr.length <= n) return arr.map(function(r) {{ return r[col]; }});
      var step = arr.length / n, out = [];
      for (var i=0; i<n; i++) out.push(arr[Math.round(i*step)][col]);
      return out;
    }}
    var N = 80;

    var cfg = {{
      id:        "cfg_" + Date.now(),
      name:      name,
      timestamp: new Date().toLocaleString(),
      sample:    sample,
      test:      test,
      params: {{
        "J₀ (A/cm²)":          $v(sid+"_j0"),
        "J₁ (A/cm²)":          $v(sid+"_j1"),
        "Conso statique (mW)":  $v(sid+"_p_static"),
        "C_CMOS (fF)":          $v(sid+"_p_ccmos"),
        "V_logic (V)":          $v(sid+"_p_vlogic"),
        "C_DS (fF)":            $v(sid+"_p_cds"),
        "Fenêtre bit (ns)":     $v(sid+"_p_twin"),
        "Débit (Gbit/s)":       $v(sid+"_p_rb"),
        "Montée (ns)":          $v(sid+"_p_tr"),
        "Descente (ns)":        $v(sid+"_p_tf"),
        "Fils/LED":             $v(sid+"_p_nwires"),
        "λ (nm)":               $v(sid+"_p_lambda"),
        "Couplage (%)":         $v(sid+"_p_kpl"),
        "Xtalk (ppm)":          $v(sid+"_p_xtalk"),
        "Pitch x (µm)":         $v(sid+"_p_xpitch"),
        "Pitch y (µm)":         $v(sid+"_p_ypitch"),
        "Type RX":              $s(sid+"_p_rxtype"),
        "Ratio det/spot":       $v(sid+"_p_rdet"),
        "Nb détecteurs":        $v(sid+"_p_ndet"),
        "Q_avalanche (fC)":     $v(sid+"_p_qa"),
        "V_bias (V)":           $v(sid+"_p_vbias"),
        "PDE (%)":              $v(sid+"_p_pde"),
        "DCR (Hz)":             $v(sid+"_p_dcr"),
        "Seuil décision (k)":   $v(sid+"_p_thresh"),
        "Puissance ampli (mW)": $v(sid+"_p_pampli"),
      }},
      curves: {{
        eqe:  {{ x: thin(livRows,"J",N),  y: thin(livRows,"EQE",N) }},
        luw:  {{ x: thin(livRows,"J",N),  y: thin(livRows,"L_uw",N) }},
        jv:   {{ x: thin(livRows,"V",N),  y: thin(livRows,"J",N) }},
        f3db: {{ x: thin(f3Rows,"J",N),   y: thin(f3Rows,"f3db",N) }},
      }},
      results: _lastRows,
    }};

    window.__VLC_CONFIGS__ = window.__VLC_CONFIGS__ || [];
    window.__VLC_CONFIGS__.push(cfg);
    try {{ localStorage.setItem("vlc_configs", JSON.stringify(window.__VLC_CONFIGS__)); }}
    catch(e) {{ console.warn("localStorage indisponible", e); }}

    window.dispatchEvent(new CustomEvent("vlc-config-saved", {{ detail: cfg }}));

    /* figer la référence au moment du save */
    _baseRows = _lastRows.map(function(r) {{ return r.slice(); }});
    update();

    /* feedback visuel sur le bouton */
    var btn = document.querySelector("#{sid}_wrap .vlc-save-btn");
    if (btn) {{
      var orig = btn.textContent;
      btn.textContent = "✓ Sauvegardé";
      btn.style.background = "#16a34a";
      setTimeout(function() {{ btn.textContent = orig; btn.style.background = ""; }}, 1600);
    }}
    if (nameEl) nameEl.value = "";
  }};

  /* ── Figer la référence manuellement ── */
  window[sid+"_setRef"] = function() {{
    _baseRows = _lastRows.map(function(r) {{ return r.slice(); }});
    update();
  }};

  /* ── Effacer la référence ── */
  window[sid+"_clearRef"] = function() {{
    _baseRows = null;
    update();
  }};


  update();
}})();
</script>
"""

    def to_dict(self) -> dict:
        return {"type": "VLCDesignBlock", "params": {
            "n_wires_array": self.n_wires_array,
            "height": self.height,
            "num": self.num,
            "title": self.title,
            "subtitle": self.subtitle,
        }}
