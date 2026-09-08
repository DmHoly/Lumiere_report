from __future__ import annotations
import json
import html as _h
import numpy as np
from dataclasses import dataclass, asdict
from typing import Any
import pandas as pd
from ..._helpers import Block, _is_vector_col, _safe_json
from ..data.data_mixin import DataMixin
from ..types import DataArg
import plotly.io as pio

class Section(Block):
    def __init__(self, title: str, subtitle: str = ""):
        self.title = title; self.subtitle = subtitle
    def render(self, store=None) -> str:
        sub = f'<span class="rb-section-sub">— {_h.escape(self.subtitle)}</span>' if self.subtitle else ""
        return (f'<div class="rb-section"><div class="rb-section-bar"></div>'
                f'<h2>{_h.escape(self.title)}{sub}</h2></div>')


import json

class Text(Block):
    needs_marked = True

    def __init__(self, content: str | dict):
        """
        content: str            → monolingual, rendered as markdown
        content: {"en": ..., "fr": ...} → bilingual with toggle buttons
        """
        self.content = content
        self._id = f"txt_{id(self)}"

    def render(self, store=None) -> str:
        # ── Monolingual (comportement original inchangé) ──────────────────────
        if isinstance(self.content, str):
            return (
                f'<div class="rb-text" id="{self._id}"></div>'
                f'<script>document.getElementById("{self._id}").innerHTML='
                f'marked.parse({json.dumps(self.content)});</script>'
            )

        # ── Bilingual ─────────────────────────────────────────────────────────
        langs   = list(self.content.keys())          # ex: ["en", "fr"]
        default = langs[0]
        id_text = self._id
        id_grp  = f"{self._id}_grp"
        content_json = json.dumps(self.content)      # {"en": "...", "fr": "..."}

        buttons_html = "".join(
            f'<button id="{self._id}_btn_{lang}" '
            f'onclick="{self._id}_setLang(\'{lang}\')" '
            f'class="rb-lang-btn{" rb-lang-active" if lang == default else ""}">'
            f'{lang.upper()}</button>'
            for lang in langs
        )

        return f"""
<div class="rb-text-bilingual">
  <div class="rb-lang-bar" id="{id_grp}">{buttons_html}</div>
  <div class="rb-text" id="{id_text}"></div>
</div>
<style>
  .rb-lang-bar {{ display:flex; gap:6px; margin-bottom:0.6rem; }}
  .rb-lang-btn {{
    padding: 3px 12px;
    font-size: 12px;
    border: 0.5px solid #ccc;
    border-radius: 6px;
    background: transparent;
    cursor: pointer;
    color: #666;
  }}
  .rb-lang-active {{
    background: #f0f0f0;
    color: #111;
    font-weight: 500;
    border-color: #999;
  }}
</style>
<script>
(function() {{
  const _content = {content_json};
  const _id      = "{id_text}";
  const _grp     = "{id_grp}";
  const _prefix  = "{self._id}";
  const _langs   = {json.dumps(langs)};

  window[_prefix + "_setLang"] = function(lang) {{
    document.getElementById(_id).innerHTML = marked.parse(_content[lang] || "");
    _langs.forEach(function(l) {{
      const btn = document.getElementById(_prefix + "_btn_" + l);
      btn.className = "rb-lang-btn" + (l === lang ? " rb-lang-active" : "");
    }});
  }};

  window[_prefix + "_setLang"]("{default}");
}})();
</script>
"""


@dataclass
class KPI:
    label:    str
    value:    Any
    unit:     str = ""
    delta:    str = ""
    subtitle: str = ""

    def _render_card(self) -> str:
        delta_html = ""
        if self.delta:
            cls  = "pos" if self.delta.startswith("+") else ("neg" if self.delta.startswith("-") else "neu")
            icon = "▲"   if self.delta.startswith("+") else ("▼"   if self.delta.startswith("-") else "●")
            delta_html = f'<span class="rb-kpi-delta {cls}">{icon} {_h.escape(self.delta)}</span>'
        unit_html = f'<span class="rb-kpi-unit">{_h.escape(self.unit)}</span>' if self.unit else ""
        sub_html  = f'<div class="rb-kpi-sub">{_h.escape(self.subtitle)}</div>' if self.subtitle else ""
        return (f'<div class="rb-kpi"><div class="rb-kpi-label">{_h.escape(self.label)}</div>'
                f'<div><span class="rb-kpi-value">{_h.escape(str(self.value))}</span>{unit_html}</div>'
                f'{delta_html}{sub_html}</div>')


class KPIRow(Block):
    def __init__(self, kpis: list[KPI]):
        self.kpis = kpis
    def render(self, store=None) -> str:
        return f'<div class="rb-kpi-row">{"".join(k._render_card() for k in self.kpis)}</div>'
    def to_dict(self) -> dict:
        # self.kpis contient des dataclasses KPI, non JSON-sérialisables telles
        # quelles — le filtre générique de Block.to_dict() les ignorerait.
        return {"type": "KPIRow", "params": {"kpis": [asdict(k) for k in self.kpis]}}


class PlotlyChart(Block):
    needs_plotly = True
    # La figure Plotly Python n'est pas JSON-sérialisable via to_dict()
    # Utiliser PlotlyChartJSON pour les rapports sérialisables
    serializable = False

    def __init__(self, fig, height: int = 420, caption: str = "", config: dict | None = None):
        self.fig = fig; self.height = height; self.caption = caption
        self.config = config or {"responsive": True, "displaylogo": False}
        self._id = f"chart_{id(self)}"
    def render(self, store=None) -> str:
        import plotly.io as pio
        fig_json = pio.to_json(self.fig)
        cfg_json = json.dumps(self.config)
        cap = f'<div class="rb-chart-caption">{_h.escape(self.caption)}</div>' if self.caption else ""
        return (f'<div class="rb-chart-wrap"><div id="{self._id}" style="height:{self.height}px;"></div>{cap}</div>'
                f'<script>(function(){{var s={fig_json};'
                f'var l=Object.assign({{paper_bgcolor:"transparent",plot_bgcolor:"transparent",'
                f'margin:{{t:40,r:20,b:40,l:50}},font:{{family:"IBM Plex Mono,monospace",size:11,color:"#4A5580"}},'
                f'colorway:["#0A2463","#D4AF37","#3e92cc","#e85d4a","#2dc653","#9b5de5"]}},s.layout);'
                f'Plotly.newPlot("{self._id}",s.data,l,{cfg_json});}})();</script>')

class DataTable(DataMixin, Block):
    def __init__(self, data: DataArg, title: str = "", page_size: int = 15,
                 numeric_cols: list[str] | None = None, fmt: dict[str, str] | None = None):
        self._init_data(data)
        self.title = title; self.page_size = page_size
        self.numeric_cols = numeric_cols; self.fmt = fmt or {}
        self._id = f"tbl_{id(self)}"

    def _df_to_json(self, df: pd.DataFrame) -> str:
        """Sérialisation inline pour les dfs locaux uniquement."""
        df = df.copy()
        for col, f in self.fmt.items():
            if col in df.columns:
                df[col] = df[col].map(lambda v, _f=f: _f.format(v) if pd.notna(v) else "")
        rows = df.astype(object).where(pd.notnull(df), "").values.tolist()
        return json.dumps([[str(v) for v in row] for row in rows])

    def _numeric_col_names(self, df: pd.DataFrame, cols: list[str]) -> list[str]:
        if self.numeric_cols is not None:
            return [c for c in self.numeric_cols if c in cols]
        return [c for c in cols if pd.api.types.is_numeric_dtype(df[c])]

    @staticmethod
    def _fmt_to_js(fmt: dict[str, str]) -> dict[str, int]:
        """Convertit {"col": "{:.2f}"} → {"col": 2} pour toFixed() en JS."""
        import re
        result = {}
        for col, f in fmt.items():
            m = re.search(r'\.(\d+)f', f)
            if m:
                result[col] = int(m.group(1))
        return result

    # Logique de rendu commune — attend C, D, N, PS déjà définis dans le scope
    _TABLE_RENDER_JS = """\
  var s={{sc:-1,sd:1,q:"",p:0,f:D}};window["{tid}_s"]=s;
  var H=document.getElementById("{tid}_h"),htr=document.createElement("tr");
  C.forEach(function(c,i){{var th=document.createElement("th");th.innerHTML=c+'<span class="sort-icon">⇅</span>';th.onclick=function(){{if(s.sc===i)s.sd*=-1;else{{s.sc=i;s.sd=1;}}srt();rnd();}};htr.appendChild(th);}});
  H.appendChild(htr);
  s.filter=function(q){{s.q=q;s.p=0;flt();srt();rnd();}};
  function flt(){{var q=s.q.toLowerCase();s.f=q?D.filter(function(r){{return r.some(function(v){{return String(v).toLowerCase().includes(q);}});}}):D;}}
  function srt(){{if(s.sc<0)return;var ci=s.sc,d=s.sd;s.f=s.f.slice().sort(function(a,b){{var an=parseFloat(a[ci]),bn=parseFloat(b[ci]);return(!isNaN(an)&&!isNaN(bn))?(an-bn)*d:a[ci].localeCompare(b[ci])*d;}});Array.from(H.querySelectorAll("th")).forEach(function(th,i){{th.classList.remove("sorted-asc","sorted-desc");if(i===s.sc)th.classList.add(s.sd===1?"sorted-asc":"sorted-desc");}});}}
  function rnd(){{var tot=s.f.length,pages=Math.max(1,Math.ceil(tot/PS));s.p=Math.min(s.p,pages-1);
    var B=document.getElementById("{tid}_b");B.innerHTML="";
    s.f.slice(s.p*PS,(s.p+1)*PS).forEach(function(row){{var tr=document.createElement("tr");row.forEach(function(v,i){{var td=document.createElement("td");if(N.has(i))td.className="rb-num";td.textContent=v;tr.appendChild(td);}});B.appendChild(tr);}});
    document.getElementById("{tid}_cnt").textContent=tot+" ligne"+(tot>1?"s":"");
    document.getElementById("{tid}_inf").textContent="Page "+(s.p+1)+" / "+pages+" · "+tot+" lignes";
    var pg=document.getElementById("{tid}_pg");pg.innerHTML="";
    function btn(l,p,dis,act){{var b=document.createElement("button");b.className="rb-page-btn"+(act?" active":"");b.textContent=l;b.disabled=dis;b.onclick=function(){{s.p=p;rnd();}};pg.appendChild(b);}}
    btn("←",s.p-1,s.p===0,false);var lo=Math.max(0,s.p-2),hi=Math.min(pages-1,s.p+2);for(var p=lo;p<=hi;p++)btn(p+1,p,false,p===s.p);btn("→",s.p+1,s.p>=pages-1,false);
  }}
  flt();srt();rnd();"""

    def render(self, store=None) -> str:
        tid = self._id
        th = f'<span class="rb-table-title">{_h.escape(self.title)}</span>' if self.title else '<span></span>'
        shell = f"""<div class="rb-table-wrap">
  <div class="rb-table-toolbar">{th}
    <input class="rb-table-search" placeholder="Filtrer…" oninput="{tid}_s.filter(this.value)">
    <span class="rb-table-count" id="{tid}_cnt"></span>
  </div>
  <div class="rb-table-scroll"><table class="rb-table"><thead id="{tid}_h"></thead><tbody id="{tid}_b"></tbody></table></div>
  <div class="rb-table-footer"><span id="{tid}_inf"></span><div class="rb-pagination" id="{tid}_pg"></div></div>
</div>"""
        render_js = self._TABLE_RENDER_JS.format(tid=tid)

        if self.has_local_data:
            # Df local : sérialisation inline — filtrage vectoriel au render (pas au __init__)
            df       = self.resolve_df()
            cols     = [c for c in df.columns if not _is_vector_col(df[c])]
            df       = df[cols]
            num_idx  = [cols.index(c) for c in self._numeric_col_names(df, cols)]
            init_js  = (f"var C={json.dumps(cols)},"
                        f"D={self._df_to_json(df)},"
                        f"N=new Set({json.dumps(num_idx)}),"
                        f"PS={self.page_size};")
        else:
            # Clé store : zéro copie — JS lit window.__DATA_STORE__
            key = self._data_arg
            if store is None:
                raise RuntimeError(
                    f"DataTable references store key {key!r} but no DataStore was provided. "
                    f"Pass store=report.data when calling render()."
                )
            df          = store.resolve(key)
            scalar_cols = [c for c in df.columns if not _is_vector_col(df[c])]
            num_names   = self._numeric_col_names(df, scalar_cols)
            num_idx     = [scalar_cols.index(c) for c in num_names]
            cfg      = {"key": key, "cols": scalar_cols,
                        "num": num_idx, "fmt": self._fmt_to_js(self.fmt)}
            cfg_json = json.dumps(cfg)
            init_js  = (
                f"var _c={cfg_json},"
                f"_r=(window.__DATA_STORE__||{{}})[_c.key]||[],"
                f"C=_c.cols||(_r.length?Object.keys(_r[0]).filter("
                f"function(k){{return!Array.isArray(_r[0][k]);}}):[]),"
                f"D=_r.map(function(row){{return C.map(function(c){{"
                f"var v=row[c];if(v===null||v===undefined)return'';"
                f"if(_c.fmt&&_c.fmt[c]!==undefined&&typeof v==='number')"
                f"return v.toFixed(_c.fmt[c]);return String(v);}});}}), "
                f"N=new Set(_c.num),PS={self.page_size};"
            )

        return shell + f"<script>(function(){{\n  {init_js}\n{render_js}\n}})();</script>"