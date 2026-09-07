"""
DesignMatrixBlock — Grille de designs LED pour expériences QT.
Layout: grille à gauche, panneau spectres normalisés 4/3 à droite.
Filtres highlight pitch/diamètre multi-sélection.
"""
from __future__ import annotations
import json, math, uuid
import numpy as np
import pandas as pd
from report_builder.core._helpers import Block
from report_builder.core.blocks.data.data_mixin import DataMixin
from report_builder.core.blocks.types import DataArg


def _s(v):
    if v is None: return None
    if isinstance(v, (np.floating, np.integer)): v = v.item()
    if isinstance(v, float) and (math.isnan(v) or math.isinf(v)): return None
    return v

def _sl(lst):
    if lst is None: return []
    try: return [_s(x) for x in lst]
    except Exception: return []


class DesignMatrixBlock(DataMixin, Block):
    _KPI_DEFAULTS = [
        "Max EQE","V at Max EQE","Lambda Peak at Max EQE",
        "Lambda Dom at Max EQE","L at Max EQE","L max",
        "EQE at 3.0V","V_25A_cm2","Lambda_Dom_25A_cm2",
    ]

    def __init__(
        self, data: DataArg,
        wafer_col: str = "wafername", led_name_col: str = "Led_Name",
        kpi_col: str = "Max EQE",
        kpi_options: list[str] | None = None, grid_cols: int | None = None,
        i_col: str = "I", v_col: str = "V", l_col: str = "L",
        w_col: str = "W", eqe_col: str = "EQE", j_col: str = "J",
        spectra_col: str = "Spectra", wavelength_col: str = "Wavelength",
        pitch_col: str = "pitch_nm", diameter_col: str = "diameter_nm",
        size_x_col: str = "size_x_um", size_y_col: str = "size_y_um",
        num: str = "—", title: str = "Design Matrix", subtitle: str = "",
    ):
        self._init_data(data)
        self.wafer_col, self.led_name_col = wafer_col, led_name_col
        self.kpi_col     = kpi_col
        self.kpi_options = kpi_options or self._KPI_DEFAULTS
        self.grid_cols = grid_cols
        self.i_col, self.v_col, self.l_col = i_col, v_col, l_col
        self.w_col, self.eqe_col, self.j_col = w_col, eqe_col, j_col
        self.spectra_col, self.wavelength_col = spectra_col, wavelength_col
        self.pitch_col, self.diameter_col = pitch_col, diameter_col
        self.size_x_col, self.size_y_col = size_x_col, size_y_col
        self.num, self.title, self.subtitle = num, title, subtitle

    def _field_map(self, df):
        counts = df.groupby(self.wafer_col)[self.led_name_col].count()
        ref    = counts.idxmax()
        names  = df[df[self.wafer_col]==ref][self.led_name_col].dropna().astype(str).tolist()
        n      = len(names)
        nc     = self.grid_cols or int(math.ceil(math.sqrt(n)))
        nr     = int(math.ceil(n / nc))
        pos    = {}
        for i, nm in enumerate(names):
            if nm not in pos:
                pos[nm] = [i % nc, i // nc]
        extra = n
        for nm in df[self.led_name_col].dropna().astype(str).unique():
            if nm not in pos:
                pos[nm] = [extra % nc, extra // nc]
                extra += 1
        nr = max(nr, int(math.ceil(extra / nc)))
        return pos, nc, nr

    def _to_records(self, df):
        kpi_cols   = [c for c in self.kpi_options if c in df.columns]
        curve_cols = [c for c in [self.i_col,self.v_col,self.l_col,
                                   self.w_col,self.eqe_col,self.j_col] if c in df.columns]
        meta_cols  = [c for c in [self.pitch_col,self.diameter_col,
                                   self.size_x_col,self.size_y_col] if c in df.columns]
        recs = []
        for _, row in df.iterrows():
            r = {
                "_w": str(row.get(self.wafer_col,"")),
                "_n": str(row.get(self.led_name_col,"")),
            }
            wl = row.get(self.wavelength_col)
            r["_wl"] = _sl(wl) if isinstance(wl,(list,np.ndarray)) else []
            for c in kpi_cols:
                r[c] = _s(row[c])
            for c in curve_cols:
                v = row[c]
                r[c] = _sl(v) if isinstance(v,(list,np.ndarray)) else []
            sp = row.get(self.spectra_col)
            r["_sp"] = [_sl(s) for s in sp] if isinstance(sp,(list,np.ndarray)) else []
            for c in meta_cols:
                r[c] = _s(row[c])
            recs.append(r)
        return recs

    def render(self, store=None):
        uid = "dm" + uuid.uuid4().hex[:8]
        df  = self.resolve_df(store)

        pos, nc, nr = self._field_map(df)
        wafers    = sorted(df[self.wafer_col].dropna().astype(str).unique().tolist())
        kpi_valid = [k for k in self.kpi_options if k in df.columns]

        cfg = {
            "ledPos": pos, "nCols": nc, "nRows": nr,
            "kpiOpts": kpi_valid,
            "defKpi":  self.kpi_col if self.kpi_col in kpi_valid else (kpi_valid[0] if kpi_valid else ""),
            "iCol": self.i_col, "vCol": self.v_col, "lCol": self.l_col,
            "wCol": self.w_col, "eCol": self.eqe_col, "jCol": self.j_col,
        }

        recs    = self._to_records(df)
        data_js = (
            f"var _CFG={json.dumps(cfg)};\n"
            f"  var _rows={json.dumps(recs)};"
        )

        wafers_json     = json.dumps(wafers)
        kpi_json        = json.dumps(kpi_valid)
        def_kpi_j       = json.dumps(cfg["defKpi"])
        sub_html        = (f'<div style="font-size:11px;color:#9999bb;margin-top:2px">'
                           f'{self.subtitle}</div>') if self.subtitle else ""
        pitch_col_js    = json.dumps(self.pitch_col)
        diameter_col_js = json.dumps(self.diameter_col)
        sx_col_js       = json.dumps(self.size_x_col)
        sy_col_js       = json.dumps(self.size_y_col)

        return f"""
<style>
.{uid}-wrap{{background:#1a1a2e;border-radius:12px;padding:20px;font-family:'Inter','Segoe UI',sans-serif;color:#e0e0f0;position:relative;}}
.{uid}-hdr{{display:flex;align-items:center;gap:12px;margin-bottom:14px;}}
.{uid}-num{{background:linear-gradient(135deg,#6366f1,#8b5cf6);color:#fff;font-size:13px;font-weight:700;padding:4px 10px;border-radius:6px;}}
.{uid}-ttl{{font-size:16px;font-weight:600;color:#e0e0f0;flex:1;}}
.{uid}-ctrl{{display:flex;gap:10px;margin-bottom:10px;flex-wrap:wrap;align-items:center;}}
.{uid}-sel{{background:#2a2a4a;border:1px solid #444466;color:#e0e0f0;padding:5px 10px;border-radius:6px;font-size:12px;}}
.{uid}-lbl{{font-size:11px;color:#9999bb;white-space:nowrap;}}
.{uid}-sep{{width:1px;height:20px;background:#333355;margin:0 4px;}}
/* highlight multi-select dropdown */
.{uid}-hldrop{{position:relative;display:inline-block;}}
.{uid}-hlbtn{{background:#2a2a4a;border:1px solid #444466;color:#e0e0f0;padding:5px 10px;border-radius:6px;font-size:12px;cursor:pointer;white-space:nowrap;}}
.{uid}-hlbtn.active{{border-color:#f59e0b;color:#f59e0b;}}
.{uid}-hlpanel{{display:none;position:absolute;top:calc(100% + 4px);left:0;background:#1e1e3f;border:1px solid #444466;border-radius:8px;padding:8px;z-index:500;min-width:160px;max-height:220px;overflow-y:auto;box-shadow:0 4px 20px rgba(0,0,0,.6);}}
.{uid}-hlpanel.open{{display:block;}}
.{uid}-hlpanel label{{display:flex;align-items:center;gap:7px;padding:3px 4px;border-radius:4px;font-size:11px;color:#c0c0dd;cursor:pointer;}}
.{uid}-hlpanel label:hover{{background:#2a2a55;}}
.{uid}-hlpanel input[type=checkbox]{{accent-color:#f59e0b;width:13px;height:13px;cursor:pointer;}}
/* legend */
.{uid}-lgd{{display:flex;align-items:center;gap:10px;margin-bottom:8px;font-size:11px;color:#9999bb;}}
.{uid}-cbar{{height:10px;width:160px;border-radius:5px;background:linear-gradient(to right,#00429d,#96ffea,#ff005e);}}
/* body: grid left + spectra right */
.{uid}-body{{display:flex;gap:16px;align-items:flex-start;}}
.{uid}-left{{flex:0 0 auto;}}
.{uid}-grid{{display:inline-grid;gap:2px;border:1px solid #333355;border-radius:6px;padding:4px;background:#111128;}}
.{uid}-cell{{width:34px;height:34px;border-radius:3px;cursor:pointer;transition:transform .1s,box-shadow .1s;position:relative;}}
.{uid}-cell:hover{{transform:scale(1.18);z-index:10;box-shadow:0 0 8px rgba(255,255,255,.4);}}
.{uid}-cell.cmp{{outline:3px solid #0ff;z-index:5;}}
.{uid}-cell.hl{{outline:3px solid #f59e0b;z-index:4;}}
.{uid}-cell.cmp.hl{{outline:3px solid #0ff;}}
.{uid}-cell[data-empty]{{background:#1a1a30!important;cursor:default;opacity:.35;pointer-events:none;}}
.{uid}-tip{{position:fixed;background:#1e1e3f;border:1px solid #4444aa;border-radius:6px;padding:6px 10px;font-size:11px;color:#e0e0f0;pointer-events:none;z-index:9999;display:none;line-height:1.6;}}
/* spectra right panel */
.{uid}-right{{flex:1 1 0;min-width:0;}}
.{uid}-sppanel{{background:#0f0f22;border-radius:10px;padding:12px;height:100%;}}
.{uid}-sphead{{font-size:11px;color:#7777aa;font-weight:600;text-transform:uppercase;letter-spacing:.5px;margin-bottom:8px;display:flex;align-items:center;gap:10px;}}
.{uid}-spstep{{background:#2a2a4a;border:1px solid #444466;color:#e0e0f0;padding:3px 8px;border-radius:5px;font-size:11px;}}
.{uid}-spinfo{{font-size:10px;color:#9999bb;margin-left:auto;}}
.{uid}-spempty{{display:flex;align-items:center;justify-content:center;height:280px;font-size:12px;color:#444466;flex-direction:column;gap:8px;}}
/* modal */
.{uid}-ov{{display:none;position:fixed;inset:0;background:rgba(0,0,0,.78);z-index:10000;align-items:center;justify-content:center;}}
.{uid}-ov.open{{display:flex;}}
.{uid}-mod{{background:#15152a;border:1px solid #333366;border-radius:14px;width:min(96vw,1080px);max-height:92vh;overflow-y:auto;padding:24px;position:relative;}}
.{uid}-mcl{{position:absolute;top:14px;right:18px;background:none;border:none;color:#9999bb;font-size:22px;cursor:pointer;}}
.{uid}-mttl{{font-size:15px;font-weight:700;color:#e0e0f0;margin-bottom:4px;}}
.{uid}-mmeta{{font-size:11px;color:#9999bb;margin-bottom:14px;display:flex;gap:14px;flex-wrap:wrap;}}
.{uid}-mcharts{{display:grid;grid-template-columns:1fr 1fr;gap:12px;}}
.{uid}-cbox{{background:#0f0f22;border-radius:8px;padding:8px;}}
.{uid}-clbl{{font-size:10px;color:#7777aa;margin-bottom:4px;font-weight:600;text-transform:uppercase;letter-spacing:.5px;}}
.{uid}-spc{{display:flex;align-items:center;gap:8px;margin-top:6px;font-size:11px;color:#9999bb;}}
.{uid}-spc input{{flex:1;accent-color:#6366f1;}}
/* comparison zone */
.{uid}-cmpz{{margin-top:18px;border-top:1px solid #333355;padding-top:14px;display:none;}}
.{uid}-cmpz.v{{display:block;}}
.{uid}-cmpttl{{font-size:13px;font-weight:600;color:#c0c0dd;margin-bottom:10px;}}
.{uid}-tags{{display:flex;gap:6px;flex-wrap:wrap;margin-bottom:10px;}}
.{uid}-tag{{background:#2a2a50;border:1px solid #4444aa;border-radius:12px;padding:3px 10px;font-size:11px;color:#c0c0ff;cursor:pointer;}}
.{uid}-cchart{{display:grid;grid-template-columns:1fr 1fr;gap:12px;}}
</style>

<div class="{uid}-wrap">
  <div class="{uid}-hdr">
    <span class="{uid}-num">{self.num}</span>
    <div><div class="{uid}-ttl">{self.title}</div>{sub_html}</div>
  </div>

  <!-- Controls row -->
  <div class="{uid}-ctrl">
    <span class="{uid}-lbl">Wafer :</span>
    <select class="{uid}-sel" id="{uid}-wsel"></select>
    <span class="{uid}-lbl" style="margin-left:8px">KPI :</span>
    <select class="{uid}-sel" id="{uid}-ksel"></select>
    <div class="{uid}-sep"></div>
    <!-- Highlight pitch -->
    <span class="{uid}-lbl">Highlight pitch :</span>
    <div class="{uid}-hldrop" id="{uid}-pdrop">
      <button class="{uid}-hlbtn" id="{uid}-pbtn">Tous ▾</button>
      <div class="{uid}-hlpanel" id="{uid}-ppanel"></div>
    </div>
    <!-- Highlight diameter -->
    <span class="{uid}-lbl">Ø :</span>
    <div class="{uid}-hldrop" id="{uid}-ddrop">
      <button class="{uid}-hlbtn" id="{uid}-dbtn">Tous ▾</button>
      <div class="{uid}-hlpanel" id="{uid}-dpanel"></div>
    </div>
    <span class="{uid}-lbl" style="margin-left:auto;font-size:10px;opacity:.6">Ctrl+clic = comparer</span>
  </div>

  <!-- Legend -->
  <div class="{uid}-lgd">
    <span>Min</span><div class="{uid}-cbar"></div><span>Max</span>
    <span id="{uid}-rng" style="color:#e0e0f0;margin-left:6px"></span>
  </div>

  <!-- Body: grid + spectra panel -->
  <div class="{uid}-body">
    <div class="{uid}-left">
      <div class="{uid}-grid" id="{uid}-grid"></div>
    </div>
    <div class="{uid}-right">
      <div class="{uid}-sppanel">
        <div class="{uid}-sphead">
          <span>Spectres normalisés</span>
          <select class="{uid}-spstep" id="{uid}-ccs"></select>
          <span class="{uid}-spinfo" id="{uid}-ccsi"></span>
        </div>
        <div id="{uid}-spempty" class="{uid}-spempty">
          <span style="font-size:22px">〜</span>
          <span>Ctrl+clic sur un design pour comparer les spectres</span>
        </div>
        <div id="{uid}-cc2" style="display:none"></div>
      </div>
    </div>
  </div>

  <div class="{uid}-tip" id="{uid}-tip"></div>

  <!-- Modal (single design detail) -->
  <div class="{uid}-ov" id="{uid}-ov">
    <div class="{uid}-mod">
      <button class="{uid}-mcl" id="{uid}-mcl">✕</button>
      <div class="{uid}-mttl" id="{uid}-mttl"></div>
      <div class="{uid}-mmeta" id="{uid}-mmeta"></div>
      <div class="{uid}-mcharts">
        <div class="{uid}-cbox"><div class="{uid}-clbl">LIV — L et I vs V</div><div id="{uid}-c0" style="height:220px"></div></div>
        <div class="{uid}-cbox"><div class="{uid}-clbl">EQE vs J (log)</div><div id="{uid}-c1" style="height:220px"></div></div>
        <div class="{uid}-cbox"><div class="{uid}-clbl">L vs W (log-log)</div><div id="{uid}-c2" style="height:220px"></div></div>
        <div class="{uid}-cbox">
          <div class="{uid}-clbl">Spectres (normalisés)</div>
          <div id="{uid}-c3" style="height:190px"></div>
          <div class="{uid}-spc"><span>Pas J :</span><input type="range" id="{uid}-sl" min="0" value="0"><span id="{uid}-slv"></span></div>
        </div>
      </div>
    </div>
  </div>

  <!-- Comparison zone (EQE/LW charts) -->
  <div class="{uid}-cmpz" id="{uid}-cmpz">
    <div class="{uid}-cmpttl">⊕ Comparaison</div>
    <div class="{uid}-tags" id="{uid}-tags"></div>
    <div class="{uid}-cchart">
      <div class="{uid}-cbox"><div class="{uid}-clbl">EQE vs J</div><div id="{uid}-cc0" style="height:240px"></div></div>
      <div class="{uid}-cbox"><div class="{uid}-clbl">L vs W</div><div id="{uid}-cc1" style="height:240px"></div></div>
    </div>
  </div>
</div>

<script>
(function(){{
  {data_js}

  var ALL_W  = {wafers_json};
  var KPI_O  = {kpi_json};
  var ST = {{ w: ALL_W[0]||"", kpi: {def_kpi_j}, cmp: [], hlPitch: [], hlDiam: [], DATA: {{}} }};

  /* ── Rebuild nested data ─────────────────────────────── */
  _rows.forEach(function(r){{
    var w=r._w, n=r._n;
    if(!ST.DATA[w]) ST.DATA[w]={{}};
    ST.DATA[w][n]=r;
  }});

  /* ── Colormap ────────────────────────────────────────── */
  function kpiColor(v,mn,mx){{
    if(v===null||v===undefined) return "#1e1e35";
    var t=(mx>mn)?Math.max(0,Math.min(1,(v-mn)/(mx-mn))):0.5;
    var c1=[0,66,157],c2=[150,255,234],c3=[255,0,94];
    var base=t<0.5?[c1,c2,t*2]:[c2,c3,(t-0.5)*2];
    var rgb=base[0].map(function(a,i){{return Math.round(a+(base[1][i]-a)*base[2]);}});
    return "rgb("+rgb+")";
  }}
  var COLORS=["#6366f1","#f59e0b","#10b981","#ef4444","#3b82f6","#ec4899","#84cc16","#f97316"];

  /* ── Helpers ─────────────────────────────────────────── */
  function fmt(v,d){{ return (v===null||v===undefined||isNaN(v))?"—":Number(v).toFixed(d||3); }}
  function zip2(a,b){{
    var o=[]; var n=Math.min((a||[]).length,(b||[]).length);
    for(var i=0;i<n;i++){{ if(a[i]!=null&&b[i]!=null&&!isNaN(a[i])&&!isNaN(b[i])) o.push([a[i],b[i]]); }}
    return o;
  }}
  function normalize(arr){{
    var mx=Math.max.apply(null,arr.filter(function(v){{return v!=null&&!isNaN(v);}}));
    if(!mx||mx===0) return arr;
    return arr.map(function(v){{return v!=null?v/mx:v;}});
  }}
  var PC={{staticPlot:false,responsive:true,displayModeBar:false}};
  var BL={{paper_bgcolor:"#0f0f22",plot_bgcolor:"#0f0f22",
    font:{{color:"#c0c0dd",size:10}},margin:{{t:6,r:8,b:36,l:46}},
    xaxis:{{gridcolor:"#222244",zerolinecolor:"#333355"}},
    yaxis:{{gridcolor:"#222244",zerolinecolor:"#333355"}}}};
  function ml(ex){{
    var l=JSON.parse(JSON.stringify(BL));
    Object.keys(ex||{{}}).forEach(function(k){{l[k]=ex[k];}});
    return l;
  }}

  /* ── Selectors ───────────────────────────────────────── */
  var wsel=document.getElementById("{uid}-wsel");
  var ksel=document.getElementById("{uid}-ksel");
  ALL_W.forEach(function(w){{ var o=document.createElement("option");o.value=w;o.textContent=w;wsel.appendChild(o); }});
  KPI_O.forEach(function(k){{ var o=document.createElement("option");o.value=k;o.textContent=k;ksel.appendChild(o); }});
  wsel.value=ST.w; ksel.value=ST.kpi;
  wsel.onchange=function(){{ST.w=this.value;ST.hlPitch=[];ST.hlDiam=[];buildHighlightDropdowns();buildGrid();}};
  ksel.onchange=function(){{ST.kpi=this.value;buildGrid();}};

  /* ── Highlight dropdowns ─────────────────────────────── */
  function _uniqueSorted(wd, col){{
    var seen={{}}, vals=[];
    Object.keys(wd).forEach(function(nm){{
      var v=wd[nm][col];
      if(v!=null&&!seen[v]){{seen[v]=1;vals.push(v);}}
    }});
    return vals.sort(function(a,b){{return Number(a)-Number(b);}});
  }}

  function _makeDropdown(panelId, btnId, vals, getter, setter){{
    var panel=document.getElementById(panelId);
    var btn=document.getElementById(btnId);
    panel.innerHTML="";
    vals.forEach(function(v){{
      var lbl=document.createElement("label");
      var cb=document.createElement("input");
      cb.type="checkbox"; cb.value=v;
      cb.checked=getter().indexOf(String(v))>=0;
      cb.onchange=function(){{
        var cur=getter();
        var sv=String(v);
        if(this.checked){{if(cur.indexOf(sv)<0) cur.push(sv);}}
        else{{var i=cur.indexOf(sv);if(i>=0)cur.splice(i,1);}}
        setter(cur);
        _updateBtn(btn,getter());
        buildGrid();
      }};
      lbl.appendChild(cb);
      lbl.appendChild(document.createTextNode(" "+v+" nm"));
      panel.appendChild(lbl);
    }});
    _updateBtn(btn,getter());
  }}

  function _updateBtn(btn, cur){{
    if(!cur.length){{btn.textContent="Tous ▾";btn.classList.remove("active");}}
    else{{btn.textContent=cur.join(", ")+" ▾";btn.classList.add("active");}}
  }}

  function buildHighlightDropdowns(){{
    var wd=ST.DATA[ST.w]||{{}};
    var pitches=_uniqueSorted(wd,{pitch_col_js});
    var diams=_uniqueSorted(wd,{diameter_col_js});
    _makeDropdown("{uid}-ppanel","{uid}-pbtn",pitches,
      function(){{return ST.hlPitch;}}, function(v){{ST.hlPitch=v;}});
    _makeDropdown("{uid}-dpanel","{uid}-dbtn",diams,
      function(){{return ST.hlDiam;}}, function(v){{ST.hlDiam=v;}});
  }}

  /* toggle panels */
  document.getElementById("{uid}-pbtn").onclick=function(e){{
    e.stopPropagation();
    document.getElementById("{uid}-ppanel").classList.toggle("open");
    document.getElementById("{uid}-dpanel").classList.remove("open");
  }};
  document.getElementById("{uid}-dbtn").onclick=function(e){{
    e.stopPropagation();
    document.getElementById("{uid}-dpanel").classList.toggle("open");
    document.getElementById("{uid}-ppanel").classList.remove("open");
  }};
  document.addEventListener("click",function(){{
    document.getElementById("{uid}-ppanel").classList.remove("open");
    document.getElementById("{uid}-dpanel").classList.remove("open");
  }});

  /* ── Grid init ───────────────────────────────────────── */
  var LP=_CFG.ledPos||{{}}, NC=_CFG.nCols||14, NR=_CFG.nRows||14;
  var gel=document.getElementById("{uid}-grid");
  var tip=document.getElementById("{uid}-tip");
  gel.style.gridTemplateColumns="repeat("+NC+",34px)";
  gel.style.gridTemplateRows="repeat("+NR+",34px)";

  var CELLS={{}};
  (function(){{
    var mat=[];
    for(var r=0;r<NR;r++){{mat.push([]);for(var c=0;c<NC;c++)mat[r].push(null);}}
    Object.keys(LP).forEach(function(nm){{
      var p=LP[nm]; if(p[1]<NR&&p[0]<NC) mat[p[1]][p[0]]=nm;
    }});
    for(var r=0;r<NR;r++) for(var c=0;c<NC;c++){{
      var el=document.createElement("div");
      el.className="{uid}-cell";
      el.style.gridColumn=(c+1)+""; el.style.gridRow=(r+1)+"";
      var nm=mat[r][c];
      if(nm){{
        el.dataset.led=nm; CELLS[nm]=el;
        (function(nm,el){{
          el.addEventListener("click",function(e){{
            if(e.ctrlKey||e.metaKey) toggleCmp(nm); else openModal(nm);
          }});
          el.addEventListener("mouseenter",function(e){{showTip(e,nm);}});
          el.addEventListener("mouseleave",function(){{tip.style.display="none";}});
          el.addEventListener("mousemove",function(e){{tip.style.left=(e.clientX+14)+"px";tip.style.top=(e.clientY-10)+"px";}});
        }})(nm,el);
      }} else {{
        el.dataset.empty="1"; el.style.background="#111128";
      }}
      gel.appendChild(el);
    }}
  }})();

  function _isHighlighted(rec){{
    if(!rec) return false;
    var matchP=!ST.hlPitch.length||ST.hlPitch.indexOf(String(rec[{pitch_col_js}]))>=0;
    var matchD=!ST.hlDiam.length||ST.hlDiam.indexOf(String(rec[{diameter_col_js}]))>=0;
    return matchP&&matchD;
  }}

  function buildGrid(){{
    var wd=ST.DATA[ST.w]||{{}};
    var vals=Object.keys(wd).map(function(n){{var v=wd[n][ST.kpi];return (v!==null&&v!==undefined&&!isNaN(v))?v:null;}}).filter(function(v){{return v!==null;}});
    var mn=vals.length?Math.min.apply(null,vals):0;
    var mx=vals.length?Math.max.apply(null,vals):1;
    document.getElementById("{uid}-rng").textContent="["+fmt(mn,4)+" — "+fmt(mx,4)+"]";
    var hasFilter=ST.hlPitch.length||ST.hlDiam.length;
    Object.keys(CELLS).forEach(function(nm){{
      var el=CELLS[nm], rec=wd[nm];
      if(!rec){{ el.style.background="#1e1e35"; el.dataset.empty="1"; }}
      else {{
        delete el.dataset.empty;
        var baseColor=kpiColor(rec[ST.kpi],mn,mx);
        if(hasFilter&&!_isHighlighted(rec)){{
          /* dim non-matching cells */
          el.style.background=baseColor;
          el.style.opacity="0.18";
        }} else {{
          el.style.background=baseColor;
          el.style.opacity="1";
        }}
      }}
      /* compare outline */
      if(ST.cmp.indexOf(nm)>=0) el.classList.add("cmp"); else el.classList.remove("cmp");
      /* highlight outline (only if matching filter, and not already cmp) */
      if(hasFilter&&_isHighlighted(rec)&&rec&&ST.cmp.indexOf(nm)<0)
        el.classList.add("hl");
      else
        el.classList.remove("hl");
    }});
  }}
  buildGrid();
  buildHighlightDropdowns();

  /* ── Tooltip ─────────────────────────────────────────── */
  function showTip(e,nm){{
    var rec=(ST.DATA[ST.w]||{{}})[nm];
    var pitch=rec?rec[{pitch_col_js}]:null;
    var diam=rec?rec[{diameter_col_js}]:null;
    tip.innerHTML=rec
      ? "<b>"+nm+"</b><br>"+ST.kpi+": "+fmt(rec[ST.kpi],4)
        +(pitch?"<br>Pitch: "+pitch+" nm":"")
        +(diam?"<br>Ø: "+diam+" nm":"")
      : "<b>"+nm+"</b><br><i>non mesuré</i>";
    tip.style.display="block";
    tip.style.left=(e.clientX+14)+"px"; tip.style.top=(e.clientY-10)+"px";
  }}

  /* ── Modal ───────────────────────────────────────────── */
  var ov=document.getElementById("{uid}-ov");
  document.getElementById("{uid}-mcl").onclick=function(){{ov.classList.remove("open");}};
  ov.addEventListener("click",function(e){{if(e.target===ov)ov.classList.remove("open");}});

  function openModal(nm){{
    var rec=(ST.DATA[ST.w]||{{}})[nm]; if(!rec) return;
    ov.classList.add("open");
    document.getElementById("{uid}-mttl").textContent=nm+"  —  "+ST.w;
    var pitch=rec[{pitch_col_js}], diam=rec[{diameter_col_js}];
    var sx=rec[{sx_col_js}], sy=rec[{sy_col_js}];
    document.getElementById("{uid}-mmeta").innerHTML=
      "<span>Pitch: <b>"+(pitch||"?")+" nm</b></span>"+
      "<span>Ø: <b>"+(diam||"?")+" nm</b></span>"+
      "<span>Size: <b>"+(sx||"?")+"×"+(sy||"?")+" µm</b></span>"+
      "<span>"+ST.kpi+": <b>"+fmt(rec[ST.kpi],4)+"</b></span>";
    plotModal(rec);
  }}

  function plotModal(rec){{
    var V=rec[_CFG.vCol]||[],L=rec[_CFG.lCol]||[],I=rec[_CFG.iCol]||[];
    var J=rec[_CFG.jCol]||[],EQE=rec[_CFG.eCol]||[],W=rec[_CFG.wCol]||[];
    var SP=rec._sp||[], WL=rec._wl||[];

    /* LIV */
    var livT=[];
    var plv=zip2(V,L); if(plv.length) livT.push({{x:plv.map(function(p){{return p[0];}}),y:plv.map(function(p){{return p[1];}}),name:"L",type:"scatter",mode:"lines+markers",marker:{{size:4}},yaxis:"y2",line:{{color:"#facc15"}}}});
    var piv=zip2(V,I); if(piv.length) livT.push({{x:piv.map(function(p){{return p[0];}}),y:piv.map(function(p){{return p[1];}}),name:"I (A)",type:"scatter",mode:"lines+markers",marker:{{size:4}},line:{{color:"#60a5fa"}}}});
    Plotly.newPlot("{uid}-c0",livT,ml({{yaxis2:{{title:"L",overlaying:"y",side:"right",color:"#facc15",gridcolor:"#222244"}},xaxis:{{title:"V (V)"}},yaxis:{{title:"I (A)"}},legend:{{x:0,y:1,bgcolor:"rgba(0,0,0,.3)",font:{{size:9}}}}}}),PC);

    /* EQE vs J */
    var pje=zip2(J,EQE).filter(function(p){{return p[0]>0;}});
    Plotly.newPlot("{uid}-c1",[{{x:pje.map(function(p){{return p[0];}}),y:pje.map(function(p){{return p[1];}}),type:"scatter",mode:"lines+markers",marker:{{size:4,color:"#a78bfa"}},line:{{color:"#a78bfa"}}}}],ml({{xaxis:{{title:"J (A/cm²)",type:"log"}},yaxis:{{title:"EQE (%)"}}}}),PC);

    /* L vs W */
    var pwl=zip2(W,L).filter(function(p){{return p[0]>0&&p[1]>0;}});
    Plotly.newPlot("{uid}-c2",[{{x:pwl.map(function(p){{return p[0];}}),y:pwl.map(function(p){{return p[1];}}),type:"scatter",mode:"lines+markers",marker:{{size:4,color:"#34d399"}},line:{{color:"#34d399"}}}}],ml({{xaxis:{{title:"W (W)",type:"log"}},yaxis:{{title:"L",type:"log"}}}}),PC);

    /* Spectres normalisés */
    var sl=document.getElementById("{uid}-sl");
    sl.max=Math.max(0,SP.length-1); sl.value=0;
    function drawSp(idx){{
      var sp=normalize(SP[idx]||[]);
      document.getElementById("{uid}-slv").textContent="pas "+idx+(J[idx]!=null?" ("+Number(J[idx]).toExponential(2)+" A/cm²)":"");
      Plotly.newPlot("{uid}-c3",[{{x:WL,y:sp,type:"scatter",mode:"lines",line:{{color:"#fb923c"}}}}],ml({{xaxis:{{title:"λ (nm)"}},yaxis:{{title:"Intensité norm.",range:[0,1.05]}},margin:{{t:4,r:8,b:36,l:46}}}}),PC);
    }}
    drawSp(0);
    sl.oninput=function(){{drawSp(parseInt(this.value));}};
  }}

  /* ── Comparaison ─────────────────────────────────────── */
  function toggleCmp(nm){{
    var i=ST.cmp.indexOf(nm);
    if(i>=0) ST.cmp.splice(i,1); else if(ST.cmp.length<8) ST.cmp.push(nm);
    buildGrid(); renderCmp();
  }}

  /* ── Spectra step selector ───────────────────────────── */
  var _cmpStepSel  = document.getElementById("{uid}-ccs");
  var _cmpStepInfo = document.getElementById("{uid}-ccsi");
  var _spEmpty     = document.getElementById("{uid}-spempty");
  var _spChart     = document.getElementById("{uid}-cc2");
  _cmpStepSel.onchange = function(){{ drawCmpSpectra(); }};

  function _buildStepOptions(){{
    var wd=ST.DATA[ST.w]||{{}};
    var maxSteps=0;
    ST.cmp.forEach(function(nm){{
      var rec=wd[nm]; if(!rec) return;
      if((rec._sp||[]).length>maxSteps) maxSteps=rec._sp.length;
    }});
    var cur=parseInt(_cmpStepSel.value)||0;
    _cmpStepSel.innerHTML="";
    for(var i=0;i<maxSteps;i++){{
      var o=document.createElement("option");
      o.value=i; o.textContent="Pas "+i;
      _cmpStepSel.appendChild(o);
    }}
    _cmpStepSel.value=Math.min(cur,Math.max(0,maxSteps-1));
  }}

  function drawCmpSpectra(){{
    var wd=ST.DATA[ST.w]||{{}};
    if(!ST.cmp.length){{
      _spEmpty.style.display="flex"; _spChart.style.display="none"; return;
    }}
    _spEmpty.style.display="none"; _spChart.style.display="block";
    var idx=parseInt(_cmpStepSel.value)||0;
    var traces=[];
    var iLabel="";
    ST.cmp.forEach(function(nm,ci){{
      var rec=wd[nm]; if(!rec) return;
      var col=COLORS[ci%COLORS.length];
      var sp=normalize((rec._sp||[])[idx]||[]);
      var wl=rec._wl||[];
      if(!sp.length||!wl.length) return;
      var Jc=rec[_CFG.jCol]||[];
      var iVal=Jc[idx]!=null?Number(Jc[idx]).toExponential(2)+" A/cm²":"";
      if(!iLabel&&iVal) iLabel="J ≈ "+iVal;
      var pitch=rec[{pitch_col_js}], diam=rec[{diameter_col_js}];
      var meta=[];
      if(pitch) meta.push("p="+pitch+"nm");
      if(diam)  meta.push("Ø="+diam+"nm");
      var label=nm+(meta.length?" ("+meta.join(", ")+")":"");
      traces.push({{x:wl,y:sp,name:label,type:"scatter",mode:"lines",line:{{color:col,width:1.8}}}});
    }});
    _cmpStepInfo.textContent=iLabel;
    /* 4:3 height = container width × 0.75 — use responsive:true, Plotly handles it */
    Plotly.newPlot("{uid}-cc2",traces,ml({{
      xaxis:{{title:"λ (nm)"}},
      yaxis:{{title:"Intensité norm.",range:[0,1.05]}},
      legend:{{font:{{size:9}},orientation:"v"}},
      margin:{{t:6,r:8,b:40,l:50}},
      aspectratio:{{x:4,y:3}}
    }}),{{staticPlot:false,responsive:true,displayModeBar:false}});
  }}

  function renderCmp(){{
    var cz=document.getElementById("{uid}-cmpz");
    var tz=document.getElementById("{uid}-tags");
    /* always update spectra panel */
    _buildStepOptions();
    drawCmpSpectra();
    if(!ST.cmp.length){{cz.classList.remove("v");return;}}
    cz.classList.add("v"); tz.innerHTML="";
    var wd=ST.DATA[ST.w]||{{}};
    ST.cmp.forEach(function(nm,ci){{
      var rec=wd[nm]||{{}};
      var pitch=rec[{pitch_col_js}], diam=rec[{diameter_col_js}];
      var meta=[];
      if(pitch) meta.push("p="+pitch+"nm");
      if(diam)  meta.push("Ø="+diam+"nm");
      var t=document.createElement("div");
      t.className="{uid}-tag";
      t.style.borderColor=COLORS[ci%COLORS.length];
      t.innerHTML='<span style="color:'+COLORS[ci%COLORS.length]+'">■</span> '+nm
        +(meta.length?' <span style="opacity:.7;font-size:10px">('+meta.join(", ")+')</span>':'')
        +' <b style="margin-left:4px">×</b>';
      t.onclick=function(){{toggleCmp(nm);}};
      tz.appendChild(t);
    }});
    plotCmp();
  }}

  function plotCmp(){{
    var wd=ST.DATA[ST.w]||{{}};
    var te=[],tw=[];
    ST.cmp.forEach(function(nm,ci){{
      var rec=wd[nm]; if(!rec) return;
      var col=COLORS[ci%COLORS.length];
      var J=rec[_CFG.jCol]||[],EQE=rec[_CFG.eCol]||[];
      var pje=zip2(J,EQE).filter(function(p){{return p[0]>0;}});
      if(pje.length) te.push({{x:pje.map(function(p){{return p[0];}}),y:pje.map(function(p){{return p[1];}}),name:nm,type:"scatter",mode:"lines",line:{{color:col}}}});
      var W=rec[_CFG.wCol]||[],L=rec[_CFG.lCol]||[];
      var pwl=zip2(W,L).filter(function(p){{return p[0]>0&&p[1]>0;}});
      if(pwl.length) tw.push({{x:pwl.map(function(p){{return p[0];}}),y:pwl.map(function(p){{return p[1];}}),name:nm,type:"scatter",mode:"lines",line:{{color:col}}}});
    }});
    Plotly.newPlot("{uid}-cc0",te,ml({{xaxis:{{title:"J (A/cm²)",type:"log"}},yaxis:{{title:"EQE (%)"}},legend:{{font:{{size:9}}}}}}),PC);
    Plotly.newPlot("{uid}-cc1",tw,ml({{xaxis:{{title:"W (W)",type:"log"}},yaxis:{{title:"L",type:"log"}},legend:{{font:{{size:9}}}}}}),PC);
  }}

}})();
</script>
"""
