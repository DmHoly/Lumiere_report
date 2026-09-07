from __future__ import annotations
import html as _h
from ...._helpers import Block


_COLORS = [
    "#2563EB", "#DC2626", "#16A34A", "#D97706",
    "#7C3AED", "#0891B2", "#DB2777", "#65A30D",
]


class VLCCompareBlock(Block):
    """
    Bloc de comparaison de configurations VLC.

    Ce bloc est autonome (aucune donnée Python) : il reçoit les configs
    sauvegardées depuis VLCDesignBlock via un CustomEvent JS ``vlc-config-saved``
    et via ``localStorage`` (persistence entre rechargements).

    Usage
    -----
    ::
        tab_cmp = Tab("Comparaison")
        tab_cmp.add(VLCCompareBlock())

    Le bloc communique avec VLCDesignBlock uniquement côté navigateur.
    Aucun paramètre Python requis.
    """

    needs_plotly = True

    def __init__(
        self,
        height: int = 300,
        num: str = "CMP",
        title: str = "Comparaison de configurations VLC",
        subtitle: str = "Sélectionner ≥ 2 configs pour comparer",
    ):
        self.height   = height
        self.num      = num
        self.title    = title
        self.subtitle = subtitle
        self._id      = f"vlccmp_{id(self)}"

    def render(self, store=None) -> str:
        sid     = self._id
        h       = self.height
        num_h   = _h.escape(self.num)
        title_h = _h.escape(self.title)
        sub_h   = _h.escape(self.subtitle)
        colors  = repr(_COLORS)

        return f"""
<div class="led-block" id="{sid}_wrap">
  <div class="led-block-header">
    <span class="led-block-num">{num_h}</span>
    <span class="led-block-title">{title_h}</span>
    <span class="led-block-sub">{sub_h}</span>
  </div>
  <div class="led-block-rule"></div>

  <div class="cmp-layout">

    <!-- ── Panneau gauche : liste des configs ── -->
    <div class="cmp-sidebar">
      <div class="cmp-sidebar-header">
        <span class="cmp-section-title">CONFIGS SAUVEGARDÉES</span>
        <span class="cmp-badge" id="{sid}_count">0</span>
      </div>
      <div class="cmp-list" id="{sid}_list">
        <div class="cmp-empty">Aucune config sauvegardée.<br>Utilisez le bouton 💾 dans l'onglet VLC Design.</div>
      </div>
      <div class="cmp-sidebar-actions">
        <button class="cmp-btn cmp-btn--primary" onclick="{sid}_compare()">⇄ Comparer la sélection</button>
        <div class="cmp-btn-row">
          <button class="cmp-btn cmp-btn--export" onclick="{sid}_exportSelected()" title="Télécharger les configs sélectionnées en JSON">⬇ Exporter</button>
          <button class="cmp-btn cmp-btn--export" onclick="{sid}_triggerImport()" title="Importer un fichier JSON de config">⬆ Importer</button>
        </div>
        <button class="cmp-btn cmp-btn--ghost"   onclick="{sid}_clearAll()">✕ Tout effacer</button>
      </div>
      <input type="file" id="{sid}_file_input" accept=".json" style="display:none"
             onchange="{sid}_importFile(this)"
             onclick="this.value=null">
      <div class="cmp-import-toast" id="{sid}_import_toast"></div>
    </div>

    <!-- ── Zone droite : résultats ── -->
    <div class="cmp-main" id="{sid}_main">
      <div class="cmp-placeholder">
        <span style="font-size:2em;">⇄</span>
        <div>Sélectionnez ≥ 2 configs et cliquez <strong>Comparer</strong></div>
      </div>
    </div>

  </div>
</div>

<style>
/* ── Layout ── */
#{sid}_wrap .cmp-layout {{
  display: grid;
  grid-template-columns: 280px 1fr;
  gap: 14px;
  margin-top: 10px;
}}
@media (max-width: 860px) {{
  #{sid}_wrap .cmp-layout {{ grid-template-columns: 1fr; }}
}}

/* ── Sidebar ── */
#{sid}_wrap .cmp-sidebar {{
  background: #fff;
  border: 1px solid #C4CEDE;
  border-top: 3px solid #0A2463;
  border-radius: 8px;
  padding: 12px;
  display: flex;
  flex-direction: column;
  gap: 10px;
  box-shadow: 0 2px 8px rgba(10,36,99,.06);
}}
#{sid}_wrap .cmp-sidebar-header {{
  display: flex;
  align-items: center;
  justify-content: space-between;
}}
#{sid}_wrap .cmp-section-title {{
  font-family: "IBM Plex Mono", monospace;
  font-size: 9px;
  font-weight: 800;
  letter-spacing: .12em;
  color: #0A2463;
  text-transform: uppercase;
}}
#{sid}_wrap .cmp-badge {{
  font-family: "IBM Plex Mono", monospace;
  font-size: 10px;
  font-weight: 700;
  background: #0A2463;
  color: #fff;
  border-radius: 10px;
  padding: 1px 8px;
  min-width: 22px;
  text-align: center;
}}
#{sid}_wrap .cmp-list {{
  flex: 1;
  overflow-y: auto;
  max-height: 340px;
  display: flex;
  flex-direction: column;
  gap: 5px;
}}
#{sid}_wrap .cmp-empty {{
  font-family: "IBM Plex Mono", monospace;
  font-size: 10px;
  color: #9AA3BF;
  text-align: center;
  padding: 24px 8px;
  line-height: 1.6;
}}
/* config card */
#{sid}_wrap .cmp-card {{
  display: flex;
  align-items: center;
  gap: 8px;
  background: #F8FAFF;
  border: 1px solid #E2E8F0;
  border-radius: 6px;
  padding: 7px 10px;
  cursor: pointer;
  transition: border-color .15s, background .15s;
}}
#{sid}_wrap .cmp-card:hover {{ border-color: #93C5FD; background: #EFF6FF; }}
#{sid}_wrap .cmp-card.selected {{ border-color: #2563EB; background: #EFF6FF; }}
#{sid}_wrap .cmp-swatch {{
  width: 10px; height: 10px;
  border-radius: 2px;
  flex-shrink: 0;
}}
#{sid}_wrap .cmp-card-body {{ flex: 1; min-width: 0; }}
#{sid}_wrap .cmp-card-name {{
  font-family: "IBM Plex Mono", monospace;
  font-size: 10px;
  font-weight: 700;
  color: #0A2463;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}}
#{sid}_wrap .cmp-card-meta {{
  font-family: "IBM Plex Mono", monospace;
  font-size: 8px;
  color: #9AA3BF;
  margin-top: 1px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}}
#{sid}_wrap .cmp-card-exp {{
  background: none;
  border: none;
  color: #94A3B8;
  font-size: 11px;
  cursor: pointer;
  padding: 0 2px;
  flex-shrink: 0;
  line-height: 1;
}}
#{sid}_wrap .cmp-card-exp:hover {{ color: #2563EB; }}
#{sid}_wrap .cmp-card-del {{
  background: none;
  border: none;
  color: #CBD5E1;
  font-size: 12px;
  cursor: pointer;
  padding: 0 2px;
  flex-shrink: 0;
  line-height: 1;
}}
#{sid}_wrap .cmp-card-del:hover {{ color: #EF4444; }}

/* ── Sidebar actions ── */
#{sid}_wrap .cmp-sidebar-actions {{
  display: flex;
  flex-direction: column;
  gap: 6px;
}}
#{sid}_wrap .cmp-btn {{
  font-family: "IBM Plex Mono", monospace;
  font-size: 10px;
  font-weight: 700;
  letter-spacing: .06em;
  border-radius: 5px;
  padding: 7px 12px;
  cursor: pointer;
  border: none;
  transition: background .15s, color .15s;
}}
#{sid}_wrap .cmp-btn--primary {{
  background: #0A2463;
  color: #fff;
}}
#{sid}_wrap .cmp-btn--primary:hover {{ background: #1a3a7a; }}
#{sid}_wrap .cmp-btn--ghost {{
  background: #F1F5F9;
  color: #475569;
  border: 1px solid #CBD5E1;
}}
#{sid}_wrap .cmp-btn--ghost:hover {{ background: #E2E8F0; }}
#{sid}_wrap .cmp-btn-row {{
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 6px;
}}
#{sid}_wrap .cmp-btn--export {{
  background: #EFF6FF;
  color: #2563EB;
  border: 1px solid #BFDBFE;
  font-size: 10px;
  padding: 6px 8px;
}}
#{sid}_wrap .cmp-btn--export:hover {{ background: #DBEAFE; }}
#{sid}_wrap .cmp-import-toast {{
  font-family: "IBM Plex Mono", monospace;
  font-size: 9px;
  padding: 5px 8px;
  border-radius: 4px;
  text-align: center;
  display: none;
}}
#{sid}_wrap .cmp-import-toast.ok  {{ background:#D1FAE5; color:#065F46; display:block; }}
#{sid}_wrap .cmp-import-toast.err {{ background:#FEE2E2; color:#991B1B; display:block; }}

/* ── Zone principale ── */
#{sid}_wrap .cmp-main {{
  display: flex;
  flex-direction: column;
  gap: 14px;
  min-width: 0;
}}
#{sid}_wrap .cmp-placeholder {{
  height: 200px;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 10px;
  color: #94A3B8;
  font-family: "IBM Plex Mono", monospace;
  font-size: 12px;
  border: 2px dashed #E2E8F0;
  border-radius: 10px;
}}
#{sid}_wrap .cmp-plots {{
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 10px;
}}
@media (max-width: 1100px) {{
  #{sid}_wrap .cmp-plots {{ grid-template-columns: repeat(2,1fr); }}
}}
#{sid}_wrap .cmp-plot-wrap {{
  background: #fff;
  border: 1px solid #C4CEDE;
  border-radius: 6px;
  padding: 8px;
}}
#{sid}_wrap .cmp-plot-title {{
  font-family: "IBM Plex Mono", monospace;
  font-size: 8px;
  font-weight: 800;
  letter-spacing: .12em;
  color: #0A2463;
  text-transform: uppercase;
  margin-bottom: 4px;
}}
/* ── Légende configs ── */
#{sid}_wrap .cmp-legend {{
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  padding: 8px 12px;
  background: #F8FAFF;
  border: 1px solid #C4CEDE;
  border-radius: 6px;
}}
#{sid}_wrap .cmp-leg-item {{
  display: flex;
  align-items: center;
  gap: 5px;
  font-family: "IBM Plex Mono", monospace;
  font-size: 9px;
  font-weight: 600;
  color: #1E3A5F;
}}
#{sid}_wrap .cmp-leg-dot {{
  width: 10px; height: 10px;
  border-radius: 50%;
  flex-shrink: 0;
}}
/* ── Tables diff ── */
#{sid}_wrap .cmp-tbl-wrap {{
  background: #fff;
  border: 1px solid #C4CEDE;
  border-radius: 8px;
  overflow: hidden;
}}
#{sid}_wrap .cmp-tbl-title {{
  font-family: "IBM Plex Mono", monospace;
  font-size: 9px;
  font-weight: 800;
  letter-spacing: .12em;
  color: #fff;
  background: #0A2463;
  padding: 7px 12px;
  text-transform: uppercase;
}}
#{sid}_wrap .cmp-tbl {{
  width: 100%;
  border-collapse: collapse;
  font-family: "IBM Plex Mono", monospace;
  font-size: 11px;
}}
#{sid}_wrap .cmp-tbl th {{
  background: #EEF2FB;
  color: #0A2463;
  font-weight: 700;
  font-size: 9px;
  padding: 6px 12px;
  text-align: left;
  border-bottom: 2px solid #C4CEDE;
  white-space: nowrap;
}}
#{sid}_wrap .cmp-tbl td {{
  padding: 5px 12px;
  color: #334155;
  border-bottom: 1px solid #E8EEF6;
  white-space: nowrap;
}}
#{sid}_wrap .cmp-tbl tr:nth-child(even) td {{ background: #F8FAFF; }}
#{sid}_wrap .cmp-tbl td:first-child {{
  font-weight: 700;
  color: #1E3A5F;
  background: #F1F5F9 !important;
  border-right: 2px solid #C4CEDE;
}}
#{sid}_wrap .cmp-tbl td.diff {{
  color: #C2410C;
  font-weight: 700;
  background: #FFF7ED !important;
  border-left: 3px solid #F97316;
}}
</style>

<script>
(function() {{
  var sid    = "{sid}";
  var COLORS = {colors};
  var h      = {h};

  /* ── Store local ── */
  var _configs  = [];    /* tableau de config objects */
  var _selected = {{}};  /* id → true si coché */

  /* ── Charger localStorage au boot ── */
  (function() {{
    try {{
      var raw = localStorage.getItem("vlc_configs");
      if (raw) {{
        _configs = JSON.parse(raw) || [];
        _selected = {{}};
      }}
    }} catch(e) {{}}
    renderList();
  }})();

  /* ── Écouter les nouvelles configs depuis VLCDesignBlock ── */
  window.addEventListener("vlc-config-saved", function(e) {{
    _configs.push(e.detail);
    renderList();
  }});

  /* ── Render liste ── */
  function renderList() {{
    var list  = document.getElementById(sid+"_list");
    var badge = document.getElementById(sid+"_count");
    badge.textContent = _configs.length;

    if (!_configs.length) {{
      list.innerHTML = '<div class="cmp-empty">Aucune config sauvegardée.<br>Utilisez le bouton \U0001f4be dans l&#39;onglet VLC Design.</div>';
      return;
    }}

    list.innerHTML = "";
    _configs.forEach(function(cfg, ci) {{
      var color = COLORS[ci % COLORS.length];
      var card  = document.createElement("div");
      card.className = "cmp-card" + (_selected[cfg.id] ? " selected" : "");
      card.innerHTML =
        '<div class="cmp-swatch" style="background:'+color+'"></div>'
        + '<div class="cmp-card-body">'
        +   '<div class="cmp-card-name">'+_esc(cfg.name)+'</div>'
        +   '<div class="cmp-card-meta">'+_esc(cfg.sample)+'  ·  '+_esc(cfg.timestamp)+'</div>'
        + '</div>'
        + '<button class="cmp-card-exp" title="Exporter cette config" onclick="event.stopPropagation();'+sid+'_exportOne(\\\''+cfg.id+'\\\')">⬇</button>'
        + '<button class="cmp-card-del" title="Supprimer" onclick="event.stopPropagation();'+sid+'_deleteConfig(\\\''+cfg.id+'\\\')">✕</button>';
      card.onclick = function() {{
        _selected[cfg.id] = !_selected[cfg.id];
        card.classList.toggle("selected", !!_selected[cfg.id]);
      }};
      list.appendChild(card);
    }});
  }}

  /* ── Supprimer une config ── */
  window[sid+"_deleteConfig"] = function(id) {{
    _configs = _configs.filter(function(c) {{ return c.id !== id; }});
    delete _selected[id];
    try {{ localStorage.setItem("vlc_configs", JSON.stringify(_configs)); }} catch(e) {{}}
    renderList();
  }};

  /* ── Tout effacer ── */
  window[sid+"_clearAll"] = function() {{
    if (!confirm("Effacer toutes les configs sauvegardées ?")) return;
    _configs = []; _selected = {{}};
    try {{ localStorage.removeItem("vlc_configs"); }} catch(e) {{}}
    renderList();
    document.getElementById(sid+"_main").innerHTML =
      '<div class="cmp-placeholder"><span style="font-size:2em;">⇄</span>'
      + '<div>Sélectionnez ≥ 2 configs et cliquez <strong>Comparer</strong></div></div>';
  }};

  /* ── Comparer ── */
  window[sid+"_compare"] = function() {{
    var sel = _configs.filter(function(c) {{ return _selected[c.id]; }});
    if (sel.length < 2) {{
      alert("Sélectionnez au moins 2 configs dans la liste.");
      return;
    }}
    renderComparison(sel);
  }};

  /* ── Rendu comparaison ── */
  function renderComparison(sel) {{
    var main = document.getElementById(sid+"_main");
    main.innerHTML = "";

    /* ── Légende ── */
    var leg = document.createElement("div");
    leg.className = "cmp-legend";
    sel.forEach(function(cfg, i) {{
      var color = COLORS[_configs.indexOf(cfg) % COLORS.length];
      leg.innerHTML +=
        '<div class="cmp-leg-item">'
        + '<div class="cmp-leg-dot" style="background:'+color+'"></div>'
        + _esc(cfg.name)
        + '</div>';
    }});
    main.appendChild(leg);

    /* ── 4 graphes ── */
    var plotsWrap = document.createElement("div");
    plotsWrap.className = "cmp-plots";

    var graphDefs = [
      {{ id: "eqe",  title: "EQE vs J",         xlog:true,  ylog:false, xlabel:"J (A/cm²)",   ylabel:"EQE (%)" }},
      {{ id: "luw",  title: "L/fil vs J (µW)",  xlog:true,  ylog:true,  xlabel:"J (A/cm²)",   ylabel:"L/fil (µW)" }},
      {{ id: "jv",   title: "J vs V",            xlog:false, ylog:true,  xlabel:"Voltage (V)", ylabel:"J (A/cm²)" }},
      {{ id: "f3db", title: "f-3dB vs J (MHz)",  xlog:true,  ylog:true,  xlabel:"J (A/cm²)",   ylabel:"f-3dB (MHz)" }},
    ];

    graphDefs.forEach(function(gd) {{
      var wrap = document.createElement("div");
      wrap.className = "cmp-plot-wrap";
      var titleDiv = document.createElement("div");
      titleDiv.className = "cmp-plot-title";
      titleDiv.textContent = gd.title;
      var plotDiv = document.createElement("div");
      plotDiv.id = sid+"_g_"+gd.id;
      plotDiv.style.height = h+"px";
      wrap.appendChild(titleDiv);
      wrap.appendChild(plotDiv);
      plotsWrap.appendChild(wrap);
    }});
    main.appendChild(plotsWrap);

    /* tracer après insertion dans le DOM */
    requestAnimationFrame(function() {{
      var PLYCFG = {{responsive:true,displaylogo:false,
        modeBarButtonsToRemove:["autoScale2d","toggleSpikelines","sendDataToCloud"]}};

      graphDefs.forEach(function(gd) {{
        var traces = sel.map(function(cfg, i) {{
          var color = COLORS[_configs.indexOf(cfg) % COLORS.length];
          var cv = cfg.curves[gd.id] || {{x:[],y:[]}};
          return {{
            type:"scatter", mode:"lines",
            name: cfg.name,
            x: cv.x, y: cv.y,
            line: {{color:color, width:2}},
            hovertemplate: cfg.name+"<br>%{{x:.3g}} / %{{y:.3g}}<extra></extra>",
          }};
        }});
        var layout = {{
          paper_bgcolor:"rgba(0,0,0,0)", plot_bgcolor:"#F8FAFF",
          font:{{family:"IBM Plex Mono,monospace",color:"#4A5580",size:10}},
          margin:{{t:6,r:10,b:46,l:56}},
          xaxis:{{ type:gd.xlog?"log":"-", title:{{text:gd.xlabel,font:{{size:10,color:"#0A2463"}},standoff:4}},
            gridcolor:"#E2E8F0",linecolor:"#E2E8F0",tickfont:{{size:8}} }},
          yaxis:{{ type:gd.ylog?"log":"-", title:{{text:gd.ylabel,font:{{size:10,color:"#0A2463"}},standoff:4}},
            gridcolor:"#E2E8F0",linecolor:"#E2E8F0",tickfont:{{size:8}} }},
          showlegend:false,
          hoverlabel:{{bgcolor:"#0A2463",bordercolor:"#D4AF37",
            font:{{family:"IBM Plex Mono",size:9,color:"white"}}}},
        }};
        Plotly.newPlot(sid+"_g_"+gd.id, traces, layout, PLYCFG);
      }});
    }});

    /* ── Table diff inputs ── */
    main.appendChild(_buildDiffTable("PARAMÈTRES — Différences", sel, "params", false));

    /* ── Table diff outputs ── */
    main.appendChild(_buildDiffTable("RÉSULTATS — Comparaison", sel, "results", true));
  }}

  /* ── Helpers export ── */
  function _download(filename, data) {{
    var blob = new Blob([JSON.stringify(data, null, 2)], {{type:"application/json"}});
    var url  = URL.createObjectURL(blob);
    var a    = document.createElement("a");
    a.href = url; a.download = filename;
    document.body.appendChild(a); a.click();
    document.body.removeChild(a);
    setTimeout(function() {{ URL.revokeObjectURL(url); }}, 1000);
  }}

  /* ── Exporter une seule config ── */
  window[sid+"_exportOne"] = function(id) {{
    var cfg = _configs.find(function(c) {{ return c.id === id; }});
    if (!cfg) return;
    var fname = cfg.name.replace(/[^a-zA-Z0-9_-]/g,"_") + ".json";
    _download(fname, [cfg]);
  }};

  /* ── Exporter la sélection (ou tout si rien sélectionné) ── */
  window[sid+"_exportSelected"] = function() {{
    var sel = _configs.filter(function(c) {{ return _selected[c.id]; }});
    if (!sel.length) sel = _configs;
    if (!sel.length) {{ alert("Aucune config à exporter."); return; }}
    var fname = sel.length === 1 ? sel[0].name.replace(/[^a-zA-Z0-9_-]/g,"_")+".json" : "vlc_configs.json";
    _download(fname, sel);
  }};

  /* ── Ouvrir le sélecteur de fichier ── */
  window[sid+"_triggerImport"] = function() {{
    document.getElementById(sid+"_file_input").click();
  }};

  /* ── Lire et importer un fichier JSON ── */
  window[sid+"_importFile"] = function(input) {{
    var file = input.files[0];
    if (!file) return;
    var toast = document.getElementById(sid+"_import_toast");
    var reader = new FileReader();
    reader.onload = function(e) {{
      try {{
        var data = JSON.parse(e.target.result);
        if (!Array.isArray(data)) data = [data];
        var added = 0;
        data.forEach(function(cfg) {{
          if (!cfg || !cfg.id || !cfg.name) return;
          /* éviter les doublons par id */
          if (_configs.find(function(c) {{ return c.id === cfg.id; }})) {{
            /* renommer si même nom différent auteur */
            cfg.id = cfg.id + "_imp";
            cfg.name = cfg.name + " (importé)";
          }}
          _configs.push(cfg);
          added++;
        }});
        try {{ localStorage.setItem("vlc_configs", JSON.stringify(_configs)); }} catch(e) {{}}
        renderList();
        toast.className = "cmp-import-toast ok";
        toast.textContent = added + " config(s) importée(s)";
      }} catch(err) {{
        toast.className = "cmp-import-toast err";
        toast.textContent = "Fichier invalide : " + err.message;
      }}
      setTimeout(function() {{ toast.className = "cmp-import-toast"; }}, 3000);
    }};
    reader.readAsText(file);
  }};

  /* ── Construction d'une table de diff ── */
  function _buildDiffTable(titleText, sel, field, isResults) {{
    var wrap = document.createElement("div");
    wrap.className = "cmp-tbl-wrap";

    var titleDiv = document.createElement("div");
    titleDiv.className = "cmp-tbl-title";
    titleDiv.textContent = titleText;
    wrap.appendChild(titleDiv);

    var tbl = document.createElement("table");
    tbl.className = "cmp-tbl";

    /* header */
    var thead = tbl.createTHead();
    var hr = thead.insertRow();
    function th(txt, color) {{
      var cell = document.createElement("th");
      cell.textContent = txt;
      if (color) cell.style.borderBottom = "3px solid "+color;
      hr.appendChild(cell);
    }}
    th("Paramètre");
    sel.forEach(function(cfg, i) {{
      th(cfg.name, COLORS[_configs.indexOf(cfg) % COLORS.length]);
    }});

    var tbody = tbl.createTBody();

    if (isResults) {{
      /* results : tableau de [label, val_j0, val_j1] */
      var nRows = sel[0].results ? sel[0].results.length : 0;
      for (var ri=0; ri<nRows; ri++) {{
        /* ligne J₀ */
        var rowJ0 = tbody.insertRow();
        var ref0  = sel[0].results[ri] ? sel[0].results[ri][1] : "";
        _td(rowJ0, (sel[0].results[ri]||[])[0]+" (J₀)");
        sel.forEach(function(cfg) {{
          var v = (cfg.results && cfg.results[ri]) ? cfg.results[ri][1] : "—";
          _td(rowJ0, v, v!=="—" && v!==ref0);
        }});
        /* ligne J₁ */
        var rowJ1 = tbody.insertRow();
        var ref1  = sel[0].results[ri] ? sel[0].results[ri][2] : "";
        _td(rowJ1, (sel[0].results[ri]||[])[0]+" (J₁)");
        sel.forEach(function(cfg) {{
          var v = (cfg.results && cfg.results[ri]) ? cfg.results[ri][2] : "—";
          _td(rowJ1, v, v!=="—" && v!==ref1);
        }});
      }}
    }} else {{
      /* params : objet clé → valeur */
      var allKeys = {{}};
      sel.forEach(function(cfg) {{
        Object.keys(cfg.params||{{}}).forEach(function(k) {{ allKeys[k]=1; }});
      }});
      Object.keys(allKeys).forEach(function(key) {{
        var row  = tbody.insertRow();
        var ref  = sel[0].params ? sel[0].params[key] : "";
        _td(row, key);
        sel.forEach(function(cfg) {{
          var v   = (cfg.params && cfg.params[key] !== undefined) ? String(cfg.params[key]) : "—";
          var ref = String(sel[0].params ? (sel[0].params[key]!==undefined ? sel[0].params[key] : "—") : "—");
          _td(row, v, v !== ref);
        }});
      }});
    }}

    wrap.appendChild(tbl);
    return wrap;
  }}

  function _td(row, text, isDiff) {{
    var td = row.insertCell();
    td.textContent = text;
    if (isDiff) td.className = "diff";
  }}

  function _esc(s) {{
    return String(s||"").replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;");
  }}

  window.addEventListener("resize", function() {{
    ["eqe","luw","jv","f3db"].forEach(function(k) {{
      var el = document.getElementById(sid+"_g_"+k);
      if (el && el.data) Plotly.Plots.resize(el);
    }});
  }});
}})();
</script>
"""

    def to_dict(self) -> dict:
        return {"type": "VLCCompareBlock", "params": {
            "height": self.height,
            "num": self.num,
            "title": self.title,
            "subtitle": self.subtitle,
        }}
