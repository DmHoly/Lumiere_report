from __future__ import annotations
import json
import html as _h
import numpy as np
import pandas as pd
from typing import Any

from ..._helpers import Block, _safe_json
from ..data.data_mixin import DataMixin, DataArg


class SpiderChart(DataMixin, Block):
    """
    Spider / Radar chart — comparaison KPI par wafer.

    Un polygon par wafer, empilés en transparence.
    Par défaut seul le wafer qui couvre la plus grande surface du spider est
    affiché ; l'utilisateur coche/décoche les autres depuis la légende.

    Paramètres
    ----------
    data : DataArg
        Clé DataStore (str) ou pd.DataFrame direct.
    kpis : list[dict]
        Définition des axes. Chaque dict :
          {
            "label"  : str,           # ex. "Yield"
            "col"    : str,           # colonne du df à agréger par wafer
            "agg"    : str = "mean",  # "mean" | "median" | "max" | "min"
            "unit"   : str = "",      # affiché dans le tooltip
            "min"    : float = None,  # borne basse de l'axe (auto si omis)
            "max"    : float = None,  # borne haute de l'axe (auto si omis)
            "invert" : bool = False,  # True si valeur basse = meilleure
                                      # ex. Defects: moins = mieux
          }
    wafer_col : str
        Colonne identifiant le wafer (défaut "wafername").
    title, num, subtitle : str
        Métadonnées du bloc.
    height : int
        Hauteur du canvas en pixels (défaut 440).

    Exemple
    -------
    report.data.register("main", df)

    tab.add(SpiderChart(
        data="main",
        wafer_col="wafername",
        kpis=[
            {"label": "Yield",        "col": "Yield",     "unit": "%",   "agg": "mean"},
            {"label": "Peak WL",      "col": "Lambda",    "unit": "nm",  "min": 445, "max": 460},
            {"label": "PL Intensity", "col": "PL_Int",    "unit": "a.u."},
            {"label": "EQE",          "col": "max_EQE",   "unit": "%"},
            {"label": "Uniformity",   "col": "Uniformity","unit": "%"},
            {"label": "Defects",      "col": "Defects",   "unit": "ppm", "invert": True},
        ],
        num="02",
        title="Spider Chart — KPI Comparaison",
        subtitle="Agrégé par wafer",
    ))
    """

    needs_plotly = False

    _PALETTE = [
        "#0d1b3e", "#c9a84c", "#3e92cc", "#e85d4a",
        "#2dc653", "#9b5de5", "#f77f00", "#4cc9f0",
        "#b5179e", "#06d6a0",
    ]

    def __init__(
        self,
        data: DataArg,
        kpis: list[dict[str, Any]],
        wafer_col: str = "wafername",
        title: str = "Spider Chart — KPI Comparaison",
        num: str = "",
        subtitle: str = "",
        height: int = 440,
    ):
        self._init_data(data)
        self.kpis      = kpis
        self.wafer_col = wafer_col
        self.title     = title
        self.num       = num
        self.subtitle  = subtitle
        self.height    = height
        self._uid      = f"spider_{id(self)}"

    # ── Payload Python → JS ───────────────────────────────────────────────────

    def _build_payload(self, df: pd.DataFrame):
        """Retourne (axes_def, wafers_data) sérialisables en JSON."""

        # 1. Résoudre les bornes globales pour chaque axe
        axes = []
        for k in self.kpis:
            col = k["col"]
            if col not in df.columns:
                continue
            vals = pd.to_numeric(df[col], errors="coerce").dropna()
            lo   = k.get("min", float(vals.min()) if len(vals) else 0.0)
            hi   = k.get("max", float(vals.max()) if len(vals) else 1.0)
            if lo == hi:
                hi = lo + 1.0
            axes.append({
                "label":  k["label"],
                "col":    col,
                "agg":    k.get("agg", "mean"),
                "unit":   k.get("unit", ""),
                "min":    lo,
                "max":    hi,
                "invert": k.get("invert", False),
            })

        N = len(axes)
        if N == 0:
            return [], []

        def _agg(series, method):
            s = pd.to_numeric(series, errors="coerce").dropna()
            if len(s) == 0:
                return float("nan")
            return {"mean":   s.mean,
                    "median": s.median,
                    "max":    s.max,
                    "min":    s.min}.get(method, s.mean)()

        def _polygon_area(norms):
            """Shoelace sur polygon radar (axes régulièrement espacés)."""
            n = len(norms)
            if n < 3:
                return 0.0
            angs = [2 * np.pi * i / n - np.pi / 2 for i in range(n)]
            xs = [r * np.cos(a) for r, a in zip(norms, angs)]
            ys = [r * np.sin(a) for r, a in zip(norms, angs)]
            area = 0.0
            for i in range(n):
                j = (i + 1) % n
                area += xs[i] * ys[j] - xs[j] * ys[i]
            return abs(area) / 2.0

        # 2. Agréger par wafer
        wafers_data = []
        groups = (df.groupby(self.wafer_col)
                  if self.wafer_col in df.columns
                  else [("all", df)])

        for idx, (wafer_name, grp) in enumerate(groups):
            raw_vals  = []
            norm_vals = []
            for ax in axes:
                raw  = _agg(grp[ax["col"]], ax["agg"])
                span = ax["max"] - ax["min"]
                norm = (raw - ax["min"]) / span if not np.isnan(raw) else 0.0
                norm = max(0.0, min(1.0, norm))
                if ax["invert"]:
                    norm = 1.0 - norm
                raw_vals.append(raw)
                norm_vals.append(norm)

            color = self._PALETTE[idx % len(self._PALETTE)]
            wafers_data.append({
                "name":   str(wafer_name),
                "color":  color,
                "values": [round(v, 4) for v in norm_vals],
                "raw":    [round(r, 4) if not np.isnan(r) else None
                           for r in raw_vals],
                "area":   round(_polygon_area(norm_vals), 6),
            })

        # Tri décroissant sur l'aire → le premier = wafer affiché par défaut
        wafers_data.sort(key=lambda w: w["area"], reverse=True)

        # Axes exportés vers JS (sans clés internes Python)
        axes_out = [
            {k: v for k, v in ax.items() if k not in ("col", "agg")}
            for ax in axes
        ]
        return axes_out, wafers_data

    # ── Render ────────────────────────────────────────────────────────────────

    def render(self, store=None) -> str:
        df           = self.resolve_df(store)
        axes, wafers = self._build_payload(df)

        uid          = self._uid
        axes_json    = json.dumps(axes)
        wafers_json  = json.dumps(wafers)
        h            = self.height
        title_h      = _h.escape(self.title)
        num_h        = _h.escape(self.num)
        sub_h        = _h.escape(self.subtitle)

        num_span = f'<span class="led-block-num">{num_h}</span>' if num_h else ""
        sub_span = f'<span class="led-block-sub">{sub_h}</span>' if sub_h else ""

        return f"""
<!-- SpiderChart {uid} -->
<div class="led-block" id="{uid}_wrap">

  <div class="led-block-header">
    {num_span}
    <span class="led-block-title">{title_h}</span>
    {sub_span}
  </div>
  <div class="led-block-rule"></div>

  <div style="display:flex;align-items:flex-start;gap:0;
              padding:14px 16px 18px;flex-wrap:wrap;">

    <!-- Canvas -->
    <div style="flex:1 1 300px;display:flex;justify-content:center;">
      <canvas id="{uid}_canvas" width="460" height="{h}"
              style="max-width:100%;display:block;"></canvas>
    </div>

    <!-- Légende -->
    <div id="{uid}_legend"
         style="flex:0 0 auto;min-width:150px;max-width:210px;
                padding:8px 0 0 14px;
                font-family:var(--fm);font-size:10px;color:var(--slate-600);
                display:flex;flex-direction:column;gap:4px;"></div>
  </div>

  <!-- Tooltip -->
  <div id="{uid}_tip"
       style="position:fixed;display:none;pointer-events:none;
              background:rgba(13,27,62,.93);color:#fff;
              font-family:var(--fm);font-size:11px;
              padding:8px 12px;border-radius:6px;
              border:1px solid rgba(201,168,76,.35);
              box-shadow:0 4px 16px rgba(0,0,0,.28);
              white-space:nowrap;z-index:9999;line-height:1.7;"></div>
</div>

<script>
(function() {{

  var AXES   = {axes_json};
  var WAFERS = {wafers_json};   /* trié: plus grande aire en premier */
  var UID    = "{uid}";
  var N      = AXES.length;

  /* État : par défaut seul le 1er wafer (plus grande surface) est visible */
  var visible = {{}};
  WAFERS.forEach(function(w, i) {{ visible[w.name] = (i === 0); }});

  var canvas = document.getElementById(UID + "_canvas");
  var legend = document.getElementById(UID + "_legend");
  var tip    = document.getElementById(UID + "_tip");
  if (!canvas) return;
  var ctx = canvas.getContext("2d");
  var W = canvas.width, H = canvas.height;
  var CX = W/2, CY = H/2, R = Math.min(W,H)*0.34;

  function angle(i) {{ return 2*Math.PI*i/N - Math.PI/2; }}
  function pt(norm, i) {{
    var a = angle(i);
    return [CX + norm*R*Math.cos(a), CY + norm*R*Math.sin(a)];
  }}
  function hexAlpha(hex, a) {{
    var r=parseInt(hex.slice(1,3),16), g=parseInt(hex.slice(3,5),16), b=parseInt(hex.slice(5,7),16);
    return "rgba("+r+","+g+","+b+","+a+")";
  }}

  /* ── dessin ── */
  function draw() {{
    ctx.clearRect(0,0,W,H);

    /* Anneaux de grille */
    for (var s=1; s<=5; s++) {{
      var frac = s/5;
      ctx.beginPath();
      for (var i=0; i<N; i++) {{ var p=pt(frac,i); i===0?ctx.moveTo(p[0],p[1]):ctx.lineTo(p[0],p[1]); }}
      ctx.closePath();
      ctx.strokeStyle = s===5?"#c8cdd8":"#e2e6f0";
      ctx.lineWidth   = s===5?1.4:0.7;
      ctx.stroke();
      if (s<5) {{
        var pLbl=pt(frac,0);
        ctx.fillStyle="#b0b8c8"; ctx.font="8px 'IBM Plex Mono',monospace";
        ctx.textAlign="center"; ctx.fillText(Math.round(frac*100)+"%",pLbl[0]+3,pLbl[1]-5);
      }}
    }}

    /* Rayons */
    for (var i=0; i<N; i++) {{
      var o=pt(1,i);
      ctx.beginPath(); ctx.moveTo(CX,CY); ctx.lineTo(o[0],o[1]);
      ctx.strokeStyle="#e2e6f0"; ctx.lineWidth=0.7; ctx.stroke();
    }}

    /* Polygones (du + petit au + grand pour que le + grand soit en fond) */
    for (var wi=WAFERS.length-1; wi>=0; wi--) {{
      var w=WAFERS[wi];
      if (!visible[w.name]) continue;

      ctx.beginPath();
      for (var i=0; i<N; i++) {{
        var p=pt(Math.min(1,Math.max(0,w.values[i])),i);
        i===0?ctx.moveTo(p[0],p[1]):ctx.lineTo(p[0],p[1]);
      }}
      ctx.closePath();
      ctx.fillStyle=hexAlpha(w.color,0.13); ctx.fill();
      ctx.strokeStyle=w.color; ctx.lineWidth=2.0; ctx.stroke();

      /* Dots */
      for (var i=0; i<N; i++) {{
        var p=pt(Math.min(1,Math.max(0,w.values[i])),i);
        ctx.beginPath(); ctx.arc(p[0],p[1],3.8,0,Math.PI*2);
        ctx.fillStyle=w.color; ctx.fill();
        ctx.strokeStyle="#fff"; ctx.lineWidth=1.4; ctx.stroke();
      }}
    }}

    /* Labels des axes */
    for (var i=0; i<N; i++) {{
      var a=angle(i);
      var lx=CX+(R+20)*Math.cos(a), ly=CY+(R+20)*Math.sin(a);
      var align="center";
      if (Math.cos(a)>0.25) align="left";
      if (Math.cos(a)<-0.25) align="right";
      ctx.fillStyle="#4a5568";
      ctx.font="600 11px 'DM Sans',Arial,sans-serif";
      ctx.textAlign=align; ctx.textBaseline="middle";
      ctx.fillText(AXES[i].label,lx,ly);
    }}
  }}

  /* ── légende avec checkboxes ── */
  function buildLegend() {{
    legend.innerHTML="";

    var hdr=document.createElement("div");
    hdr.style.cssText="font-size:9px;letter-spacing:.1em;text-transform:uppercase;"
      +"color:var(--slate-400);margin-bottom:5px;padding-bottom:4px;"
      +"border-bottom:1px solid var(--border);";
    hdr.textContent="Wafers"; legend.appendChild(hdr);

    WAFERS.forEach(function(w) {{
      var row=document.createElement("label");
      row.style.cssText="display:flex;align-items:center;gap:7px;cursor:pointer;"
        +"padding:3px 5px;border-radius:4px;transition:background .12s;";
      row.onmouseover=function(){{this.style.background="var(--slate-100)";}};
      row.onmouseout =function(){{this.style.background="";}};

      var cb=document.createElement("input");
      cb.type="checkbox"; cb.checked=!!visible[w.name];
      cb.style.cssText="accent-color:"+w.color+";width:12px;height:12px;flex-shrink:0;cursor:pointer;";
      (function(_w){{
        cb.addEventListener("change",function(){{visible[_w.name]=this.checked;draw();}});
      }})(w);

      var sw=document.createElement("span");
      sw.style.cssText="display:inline-block;width:10px;height:10px;border-radius:2px;"
        +"flex-shrink:0;background:"+w.color+";";

      var nm=document.createElement("span");
      nm.style.cssText="flex:1;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;font-size:10px;";
      nm.textContent=w.name; nm.title=w.name;

      row.appendChild(cb); row.appendChild(sw); row.appendChild(nm);
      legend.appendChild(row);
    }});

    /* Boutons globaux */
    var btns=document.createElement("div");
    btns.style.cssText="display:flex;gap:5px;margin-top:8px;flex-wrap:wrap;";
    function makeBtn(label,state){{
      var b=document.createElement("button");
      b.textContent=label;
      b.style.cssText="font-family:var(--fm);font-size:9px;padding:3px 8px;"
        +"border:1px solid var(--border);border-radius:4px;"
        +"background:none;cursor:pointer;color:var(--slate-600);transition:all .12s;";
      b.onmouseover=function(){{this.style.background="var(--slate-100)";}};
      b.onmouseout =function(){{this.style.background="";}};
      b.addEventListener("click",function(){{WAFERS.forEach(function(w){{visible[w.name]=state;}});buildLegend();draw();}});
      return b;
    }}
    btns.appendChild(makeBtn("Tout afficher",true));
    btns.appendChild(makeBtn("Tout masquer",false));
    legend.appendChild(btns);
  }}

  /* ── tooltip ── */
  function hitTest(mx,my){{
    var bestW=null,bestAxis=-1,bestD=16;
    WAFERS.forEach(function(w){{
      if(!visible[w.name]) return;
      for(var i=0;i<N;i++){{
        var p=pt(Math.min(1,Math.max(0,w.values[i])),i);
        var d=Math.hypot(mx-p[0],my-p[1]);
        if(d<bestD){{bestD=d;bestW=w;bestAxis=i;}}
      }}
    }});
    return{{wafer:bestW,axis:bestAxis}};
  }}

  canvas.addEventListener("mousemove",function(e){{
    var rect=canvas.getBoundingClientRect();
    var scaleX=canvas.width/rect.width, scaleY=canvas.height/rect.height;
    var mx=(e.clientX-rect.left)*scaleX, my=(e.clientY-rect.top)*scaleY;
    var hit=hitTest(mx,my);
    if(!hit.wafer){{tip.style.display="none";return;}}
    var ax=AXES[hit.axis], raw=hit.wafer.raw[hit.axis];
    var unit=ax.unit?"\u00a0"+ax.unit:"";
    var pct=Math.round(hit.wafer.values[hit.axis]*100);
    tip.innerHTML="<b style='color:#e8c97a'>"+ax.label+"</b>"
      +" &nbsp;<span style='opacity:.5;font-size:9px;'>"+hit.wafer.name+"</span><br>"
      +(raw!==null
        ?"<span style='opacity:.7'>Valeur\u00a0: </span><b>"
          +(typeof raw==="number"?raw.toFixed(3):raw)+unit+"</b>"
          +" &nbsp;<span style='opacity:.45;font-size:9px;'>("+pct+"%)</span>"
        :"<span style='opacity:.5'>N/A</span>");
    tip.style.display="block";
    tip.style.left=(e.clientX+14)+"px";
    tip.style.top=(e.clientY-10)+"px";
  }});
  canvas.addEventListener("mouseleave",function(){{tip.style.display="none";}});

  buildLegend();
  draw();

}})();
</script>
"""