"""
merge_store.py — Bloc interactif pour fusionner le store d'un autre rapport HTML.

Usage :
    tab = Tab("Fusion")
    tab.add(MergeStoreBlock(key="main"))

Fonctionnement :
  - Drop-zone dans le HTML : l'utilisateur dépose un autre rapport HTML
  - JS extrait window.__DATA_STORE__[key] du fichier déposé
  - Concat avec le store courant (déduplique par rapport aux rows existantes si identiques)
  - Affiche les stats du merge (N rows ajoutées, wafers nouveaux)
  - Bouton "Télécharger rapport fusionné" : génère un nouveau HTML self-contained
    avec le store mis à jour (le script __DATA_STORE__ est réécrit dans le blob)
  - Sans sauvegarder : la fusion est temporaire (perdue au rechargement)
"""
from __future__ import annotations
import uuid
from ..._helpers import Block


class MergeStoreBlock(Block):
    """
    Bloc interactif de fusion de stores.

    Paramètres
    ----------
    key : str
        Clé DataStore à fusionner (ex: ``"main"``).
    wafer_col : str
        Colonne utilisée pour compter les wafers dans les stats de merge.
    title : str
        Titre affiché dans le bloc.
    """
    needs_plotly = False
    needs_marked = False

    def __init__(
        self,
        key: str = "main",
        wafer_col: str = "wafername",
        title: str = "Fusionner un rapport",
    ):
        self.key = key
        self.wafer_col = wafer_col
        self.title = title

    def render(self, store=None) -> str:
        uid = uuid.uuid4().hex[:8]
        key = self.key
        wafer_col = self.wafer_col
        title = self.title

        return f"""
<div class="rb-merge-block" id="mrg-{uid}">
  <style>
    #mrg-{uid} {{
      font-family: "IBM Plex Mono", monospace;
      background: #f8f9fd;
      border: 1.5px solid #e4e8f4;
      border-radius: 10px;
      padding: 24px 28px 20px;
      margin: 12px 0;
      max-width: 720px;
    }}
    #mrg-{uid} h3 {{
      margin: 0 0 16px;
      font-size: 14px;
      color: #4a5580;
      font-weight: 600;
      letter-spacing: 0.04em;
      text-transform: uppercase;
    }}
    #mrg-{uid} .mrg-drop {{
      border: 2px dashed #b0b8d8;
      border-radius: 8px;
      padding: 32px 20px;
      text-align: center;
      cursor: pointer;
      transition: border-color 0.2s, background 0.2s;
      background: #fff;
      color: #7a84a8;
      font-size: 13px;
    }}
    #mrg-{uid} .mrg-drop.drag-over {{
      border-color: #6366f1;
      background: #eef0ff;
      color: #4f46e5;
    }}
    #mrg-{uid} .mrg-drop input[type=file] {{
      display: none;
    }}
    #mrg-{uid} .mrg-drop label {{
      cursor: pointer;
      display: block;
    }}
    #mrg-{uid} .mrg-icon {{
      font-size: 28px;
      display: block;
      margin-bottom: 8px;
    }}
    #mrg-{uid} .mrg-stats {{
      display: none;
      margin-top: 16px;
      padding: 14px 16px;
      background: #eef9f0;
      border: 1.5px solid #a3d9ae;
      border-radius: 8px;
      font-size: 12px;
      color: #2d6a3f;
      line-height: 1.8;
    }}
    #mrg-{uid} .mrg-stats.error {{
      background: #fff0f0;
      border-color: #f0a0a0;
      color: #8b2020;
    }}
    #mrg-{uid} .mrg-kpi-row {{
      display: flex;
      gap: 20px;
      margin: 8px 0 12px;
    }}
    #mrg-{uid} .mrg-kpi {{
      background: #fff;
      border: 1px solid #c8e6cc;
      border-radius: 6px;
      padding: 8px 14px;
      text-align: center;
      min-width: 90px;
    }}
    #mrg-{uid} .mrg-kpi .mrg-kpi-val {{
      font-size: 20px;
      font-weight: 700;
      color: #1a6b35;
      display: block;
    }}
    #mrg-{uid} .mrg-kpi .mrg-kpi-lbl {{
      font-size: 10px;
      color: #5a8a66;
      text-transform: uppercase;
      letter-spacing: 0.05em;
    }}
    #mrg-{uid} .mrg-source {{
      font-size: 11px;
      color: #5a7a66;
      margin-bottom: 4px;
      word-break: break-all;
    }}
    #mrg-{uid} .mrg-actions {{
      display: none;
      gap: 10px;
      margin-top: 14px;
      flex-wrap: wrap;
    }}
    #mrg-{uid} .mrg-btn {{
      padding: 8px 18px;
      border-radius: 6px;
      border: none;
      cursor: pointer;
      font-family: inherit;
      font-size: 12px;
      font-weight: 600;
      letter-spacing: 0.03em;
      transition: opacity 0.15s;
    }}
    #mrg-{uid} .mrg-btn:hover {{ opacity: 0.85; }}
    #mrg-{uid} .mrg-btn-save {{
      background: #4f46e5;
      color: #fff;
    }}
    #mrg-{uid} .mrg-btn-refresh {{
      background: #0e9f6e;
      color: #fff;
    }}
    #mrg-{uid} .mrg-btn-reset {{
      background: #e4e8f4;
      color: #4a5580;
    }}
    @keyframes mrg-spin {{ to {{ transform: rotate(360deg); }} }}
    #mrg-{uid} .mrg-badge {{
      display: inline-block;
      background: #6366f1;
      color: #fff;
      border-radius: 4px;
      padding: 1px 7px;
      font-size: 10px;
      font-weight: 700;
      letter-spacing: 0.04em;
      vertical-align: middle;
      margin-left: 8px;
    }}
  </style>

  <h3>⊕ {title}<span class="mrg-badge" id="mrg-{uid}-badge" style="display:none">FUSIONNÉ</span></h3>

  <div class="mrg-drop" id="mrg-{uid}-drop">
    <label for="mrg-{uid}-input">
      <span class="mrg-icon">⊕</span>
      Déposer un rapport HTML ici<br>
      <span style="font-size:11px;opacity:0.7">ou cliquer pour choisir un fichier</span>
    </label>
    <input type="file" id="mrg-{uid}-input" accept=".html">
  </div>

  <div class="mrg-stats" id="mrg-{uid}-stats"></div>
  <div class="mrg-actions" id="mrg-{uid}-actions">
    <button class="mrg-btn mrg-btn-refresh" id="mrg-{uid}-refresh">↺ Rafraîchir les blocs</button>
    <button class="mrg-btn mrg-btn-save" id="mrg-{uid}-save">⬇ Télécharger rapport fusionné</button>
    <button class="mrg-btn mrg-btn-reset" id="mrg-{uid}-reset">✕ Annuler la fusion</button>
  </div>

  <script>
  (function() {{
    var KEY       = {key!r};
    var WAFER_COL = {wafer_col!r};
    var drop      = document.getElementById("mrg-{uid}-drop");
    var input     = document.getElementById("mrg-{uid}-input");
    var statsBox  = document.getElementById("mrg-{uid}-stats");
    var actions   = document.getElementById("mrg-{uid}-actions");
    var badge     = document.getElementById("mrg-{uid}-badge");
    var _original = null;   // snapshot du store avant merge pour pouvoir annuler

    // ── Overlay plein-écran pendant le drag ──────────────────────────────────
    var overlay = document.createElement('div');
    overlay.id  = 'mrg-overlay-{uid}';
    Object.assign(overlay.style, {{
      display:'none', position:'fixed', inset:'0', zIndex:'99998',
      background:'rgba(79,70,229,.13)', backdropFilter:'blur(2px)',
      border:'3px dashed #6366f1', boxSizing:'border-box',
      alignItems:'center', justifyContent:'center', flexDirection:'column',
      fontFamily:'"IBM Plex Mono",monospace', color:'#4f46e5',
      fontSize:'18px', fontWeight:'600', gap:'12px', pointerEvents:'none',
    }});
    overlay.innerHTML = '<span style="font-size:48px">⊕</span>Déposer le rapport ici';
    document.body.appendChild(overlay);

    var _dragCounter = 0;   // counter pour ignorer les dragleave sur enfants

    document.addEventListener('dragenter', function(e) {{
      if (!e.dataTransfer || !e.dataTransfer.types) return;
      var hasFile = Array.prototype.indexOf.call(e.dataTransfer.types, 'Files') !== -1;
      if (!hasFile) return;
      _dragCounter++;
      overlay.style.display = 'flex';
    }});
    document.addEventListener('dragleave', function() {{
      _dragCounter--;
      if (_dragCounter <= 0) {{ _dragCounter = 0; overlay.style.display = 'none'; }}
    }});
    document.addEventListener('dragover', function(e) {{ e.preventDefault(); }});
    document.addEventListener('drop', function(e) {{
      e.preventDefault();
      _dragCounter = 0;
      overlay.style.display = 'none';
      var f = e.dataTransfer && e.dataTransfer.files && e.dataTransfer.files[0];
      if (f && f.name.endsWith('.html')) processFile(f);
    }});

    // Drop sur la zone locale (redondant mais garde l'état drag-over)
    drop.addEventListener("dragover",  function(e) {{ e.preventDefault(); drop.classList.add("drag-over"); }});
    drop.addEventListener("dragleave", function()  {{ drop.classList.remove("drag-over"); }});
    drop.addEventListener("drop",      function()  {{ drop.classList.remove("drag-over"); }});

    input.addEventListener("change", function() {{
      if (input.files[0]) processFile(input.files[0]);
    }});

    // ── Extraction du store depuis le HTML source ─────────────────────────────
    function extractStore(htmlText, key) {{
      // Cherche le marqueur textuel (indexOf, pas de regex) puis extrait le JSON
      // par comptage de brackets pour éviter les pb d'escaping regex/f-string Python.
      var markers = [
        'window.__DATA_STORE__[' + JSON.stringify(key) + '] = ',
        "window.__DATA_STORE__['" + key + "'] = ",
      ];
      var start = -1;
      for (var mi = 0; mi < markers.length; mi++) {{
        var idx = htmlText.indexOf(markers[mi]);
        if (idx !== -1) {{ start = htmlText.indexOf('[', idx); break; }}
      }}
      if (start === -1) return null;
      // Bracket counter pour trouver la fin du tableau JSON
      var depth = 0, inStr = false;
      for (var i = start; i < htmlText.length; i++) {{
        var c = htmlText[i];
        if (inStr) {{
          if (c === '\\\\') {{ i++; continue; }}
          if (c === '"')  inStr = false;
        }} else {{
          if (c === '"')  {{ inStr = true; continue; }}
          if (c === '[')  depth++;
          else if (c === ']') {{ depth--; if (depth === 0) {{ try {{ return JSON.parse(htmlText.slice(start, i + 1)); }} catch(e) {{ return null; }} }} }}
        }}
      }}
      return null;
    }}

    // ── Traitement du fichier ─────────────────────────────────────────────────
    function processFile(file) {{
      setLoading(true);
      var reader = new FileReader();
      reader.onload = function(e) {{
        var html   = e.target.result;
        var rows   = extractStore(html, KEY);

        if (!rows || !Array.isArray(rows)) {{
          showError("Clé " + KEY + " introuvable dans ce fichier.<br>Vérifiez que c&#39;est bien un rapport généré par Lumière.");
          return;
        }}

        var current = (window.__DATA_STORE__ || {{}})[KEY] || [];

        // Stats avant merge
        var before   = current.length;
        var wBefore  = uniqueVals(current, WAFER_COL);

        // Snapshot pour annulation
        _original = JSON.parse(JSON.stringify(current));

        // Concat
        var merged   = current.concat(rows);
        window.__DATA_STORE__ = window.__DATA_STORE__ || {{}};
        window.__DATA_STORE__[KEY] = merged;

        // Stats après
        var added    = rows.length;
        var wAfter   = uniqueVals(merged, WAFER_COL);
        var newWafers = wAfter.filter(function(w) {{ return wBefore.indexOf(w) === -1; }});

        showSuccess(file.name, before, added, newWafers);
      }};
      reader.readAsText(file);
    }}

    function uniqueVals(rows, col) {{
      var seen = {{}};
      rows.forEach(function(r) {{ if (r[col] != null) seen[r[col]] = 1; }});
      return Object.keys(seen);
    }}

    // ── Toast global (visible quel que soit l'onglet actif) ──────────────────
    function toast(msg, ok) {{
      var t = document.getElementById('mrg-toast-{uid}');
      if (!t) {{
        t = document.createElement('div');
        t.id = 'mrg-toast-{uid}';
        Object.assign(t.style, {{
          position:'fixed', top:'18px', right:'22px', zIndex:'99999',
          fontFamily:'"IBM Plex Mono",monospace', fontSize:'13px',
          padding:'12px 20px', borderRadius:'8px', maxWidth:'380px',
          boxShadow:'0 4px 24px rgba(0,0,0,.22)',
          transition:'opacity .35s, transform .35s',
          pointerEvents:'none',
        }});
        document.body.appendChild(t);
      }}
      t.style.background = ok ? '#0e9f6e' : '#e53e3e';
      t.style.color = '#fff';
      t.style.border = '1.5px solid ' + (ok ? '#0a7a55' : '#c53030');
      t.innerHTML = msg;
      t.style.opacity = '1';
      t.style.transform = 'translateY(0)';
      clearTimeout(t._timer);
      t._timer = setTimeout(function() {{
        t.style.opacity = '0';
        t.style.transform = 'translateY(-8px)';
      }}, ok ? 4000 : 6000);
    }}

    // ── Loading sur la drop zone ──────────────────────────────────────────────
    function setLoading(on) {{
      drop.style.opacity   = on ? '.5' : '1';
      drop.style.cursor    = on ? 'wait' : 'pointer';
      drop.querySelector('label').innerHTML = on
        ? '<span class="mrg-icon" style="animation:mrg-spin 1s linear infinite;display:inline-block">⟳</span>Lecture en cours…'
        : '<span class="mrg-icon">⊕</span>Déposer un rapport HTML ici<br><span style="font-size:11px;opacity:0.7">ou cliquer pour choisir un fichier</span>';
    }}

    // ── Affichage stats ───────────────────────────────────────────────────────
    function showSuccess(filename, before, added, newWafers) {{
      setLoading(false);
      statsBox.className = "mrg-stats";
      statsBox.innerHTML =
        '<div class="mrg-source">📄 ' + filename + '</div>' +
        '<div class="mrg-kpi-row">' +
          kpiCard("+" + added, "lignes ajoutées") +
          kpiCard("+" + newWafers.length, "wafers nouveaux") +
          kpiCard(before + added, "total lignes") +
        '</div>' +
        (newWafers.length > 0
          ? '<div style="font-size:11px;color:#3a7a50">Wafers ajoutés : <b>' + newWafers.join(", ") + '</b></div>'
          : '') +
        '<div style="font-size:11px;color:#5a8a66;margin-top:4px">⚠ Fusion temporaire — rechargement de la page la réinitialise.</div>';
      statsBox.style.display = "block";
      actions.style.display  = "flex";
      badge.style.display    = "inline-block";
      toast('✓ Fusion réussie — +' + added + ' lignes, +' + newWafers.length + ' wafer(s)', true);
    }}

    function showError(msg) {{
      setLoading(false);
      statsBox.className = "mrg-stats error";
      statsBox.innerHTML = "⚠ " + msg;
      statsBox.style.display = "block";
      toast('⚠ Fusion échouée — ' + msg.replace(/<[^>]+>/g, ''), false);
      actions.style.display  = "none";
    }}

    function kpiCard(val, lbl) {{
      return '<div class="mrg-kpi"><span class="mrg-kpi-val">' + val +
             '</span><span class="mrg-kpi-lbl">' + lbl + '</span></div>';
    }}

    // ── Annulation ────────────────────────────────────────────────────────────
    document.getElementById("mrg-{uid}-reset").addEventListener("click", function() {{
      if (_original !== null) {{
        window.__DATA_STORE__[KEY] = _original;
        _original = null;
      }}
      statsBox.style.display = "none";
      actions.style.display  = "none";
      badge.style.display    = "none";
      input.value = "";
    }});

    // ── Génère le HTML mergé (commun à refresh et save) ──────────────────────
    function buildMergedHtml() {{
      var store = window.__DATA_STORE__ || {{}};
      var scriptLines = ["window.__DATA_STORE__ = window.__DATA_STORE__ || {{}};"];
      Object.keys(store).forEach(function(k) {{
        // Escape </ pour éviter de casser les tags script dans le blob généré
        var safe = JSON.stringify(store[k]).split('<' + '/').join('<\\/');
        scriptLines.push("window.__DATA_STORE__[" + JSON.stringify(k) + "] = " + safe + ";");
      }});
      var newScript = "<script>\\n" + scriptLines.join("\\n") + "\\n<" + "/script>";
      var html = document.documentElement.outerHTML;
      var storeRx = new RegExp('<script>[\\\\s\\\\S]*?window\\\\.__DATA_STORE__[\\\\s\\\\S]*?<' + '/script>');
      var replaced = html.replace(storeRx, newScript);
      if (replaced === html) replaced = html.replace('<' + '/body>', newScript + '<' + '/body>');
      return replaced;
    }}

    // ── Refresh : ouvre le rapport mergé en blob URL (évite quota sessionStorage)
    document.getElementById("mrg-{uid}-refresh").addEventListener("click", function() {{
      try {{
        var merged = buildMergedHtml();
        var blob   = new Blob([merged], {{ type: "text/html;charset=utf-8" }});
        var url    = URL.createObjectURL(blob);
        window.location.href = url;
      }} catch(e) {{
        toast("⚠ Erreur refresh : " + e.message, false);
      }}
    }});

    // ── Téléchargement rapport fusionné ───────────────────────────────────────
    document.getElementById("mrg-{uid}-save").addEventListener("click", function() {{
      var blob = new Blob([buildMergedHtml()], {{ type: "text/html;charset=utf-8" }});
      var a    = document.createElement("a");
      a.href   = URL.createObjectURL(blob);
      a.download = "rapport_fusionné_" + new Date().toISOString().slice(0, 10) + ".html";
      a.click();
      URL.revokeObjectURL(a.href);
    }});

  }})();
  </script>
</div>
"""
