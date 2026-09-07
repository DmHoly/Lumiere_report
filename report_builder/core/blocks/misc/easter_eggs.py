"""
Core/blocks/easter_eggs.py
──────────────────────────
Bloc easter eggs à injecter une fois dans le rapport (typiquement en fin de
config, dans n'importe quelle page).  Aucune dépendance externe.

Cinq easter eggs :
  1. Taper "why"     → modal qui raconte l'origine du nom LUMIÈRE
                        → au closing, révèle définitivement le nom complet dans
                          .rb-header-lumiere-full
  2. Cliquer logo    → burst de photons RGB + colorisation AL/Ed/ia
  3. Taper "epi"     → cerveau 🧠 pulsant centré au milieu de l'écran (3 s)
  4. Taper "it"      → pluie Matrix (canvas, katakana + symboles, 3 s + fade)
  5. Taper "process" → terminal cleanroom : barre de fabrication en salle blanche
                        CLEAN → DEPOSIT → ETCH → CONTACT → INSPECT → DONE

Le span .rb-header-lumiere-full doit être présent dans le template avec :
  - data-short  : texte par défaut  → "Report Engine"
  - data-full   : HTML complet      → "LED Unified Metrics, Insights, <em>È</em>xploration & Reporting Engine"
  Exemple :
    <span class="rb-header-lumiere-full"
          data-short="Report Engine"
          data-full="<em>L</em>ED <em>U</em>nified <em>M</em>etrics, <em>I</em>nsights,
                     <em>È</em>xploration &amp; <em>R</em>eporting <em>E</em>ngine">
      Report Engine
    </span>

Usage
-----
from .easter_eggs import EasterEggs

runner.add_block(EasterEggs())
# ou dans la config dict :
{"type": "EasterEggs", "params": {}}
"""

from __future__ import annotations
import json
from ..._helpers import Block


# ── Contenu du modal "lumiere" ────────────────────────────────────────────────
_LUMIERE_TITLE = "Pourquoi LUMIÈRE ?"
_LUMIERE_LINES = [
    ("acronyme",  "L·U·M·I·È·R·E",
     "LED Unified Metrics, Insights, Exploration &amp; Reporting Engine"),
    ("physique",  "On fait de la lumière",
     "On travaille sur des LEDs — littéralement des dispositifs qui émettent des photons."),
    ("données",   "On met en lumière les données",
     "Rendre visibles, lisibles et accessibles des résultats enfouis dans des bases de mesure."),
    ("conclusion","Le nom s'est imposé",
     "À la croisée de la physique et de l'outil. Assez naturellement."),
]

# ── Étapes process salle blanche ─────────────────────────────────────────────
_PROCESS_STEPS = [
    ("wetclean",  "WET-CLEAN HF",     "décapage oxyde natif",      14,  380),
    ("drysio2",   "DRY SiO₂",         "dépôt diélectrique PECVD",  28,  420),
    ("wetal2o3",  "WET Al₂O₃",        "gravure humide passivation", 44,  380),
    ("ito",       "ITO DEPOSITION",   "pulvérisation cathodique",   60,  450),
    ("litho",     "LITHO TCO",        "photolithographie TCO",      76,  400),
    ("dryetch",   "DRY ETCH",         "gravure plasma mesa",        90,  380),
    ("done",      "DONE ✓",           "lot libéré",                100,  300),
]


class EasterEggs(Block):
    """
    Bloc sans rendu visuel — injecte uniquement du JS/CSS en fin de rapport.
    Peut être placé n'importe où dans la config ; le HTML généré est invisible.
    """

    # Signale au renderer qu'aucun wrapper rb-block ne doit être ajouté
    no_wrapper = True

    def render(self, store=None) -> str:
        lumiere_data    = json.dumps(_LUMIERE_LINES)
        process_steps   = json.dumps(_PROCESS_STEPS)

        return f"""
<!-- ═══════════════════════════════════════════════════════ EASTER EGGS ══ -->

<!-- ── EE1 : modal LUMIÈRE ──────────────────────────────────────────── -->
<div id="ee-lumiere-overlay" style="display:none;position:fixed;inset:0;
  background:rgba(10,12,18,.88);z-index:99990;align-items:center;
  justify-content:center;backdrop-filter:blur(4px);">
  <div id="ee-lumiere-box" style="
    background:#0f1117;border:1px solid #D4AF37;border-radius:10px;
    width:min(560px,92vw);padding:0;overflow:hidden;
    box-shadow:0 0 60px rgba(212,175,55,.2);
    animation:eeLightIn .3s cubic-bezier(.34,1.56,.64,1);">
    <div style="background:#161920;padding:.7rem 1.2rem;display:flex;
      align-items:center;border-bottom:1px solid #1e2230;">
      <span style="font-family:'IBM Plex Mono',monospace;font-size:.7rem;
        color:#D4AF37;letter-spacing:2px;">LUMIÈRE — origine du nom</span>
      <button id="ee-lumiere-close"
        style="margin-left:auto;background:none;border:none;color:#555;
        font-size:1.1rem;cursor:pointer;line-height:1;">✕</button>
    </div>
    <div style="padding:1.4rem 1.6rem;display:flex;flex-direction:column;gap:1rem;"
         id="ee-lumiere-body"></div>
  </div>
</div>

<!-- ── EE3 : cerveau EPI — overlay centré ───────────────────────────── -->
<div id="ee-epi-overlay" style="
  display:none;position:fixed;inset:0;z-index:99985;
  background:rgba(10,12,18,.90);backdrop-filter:blur(3px);
  align-items:center;justify-content:center;flex-direction:column;gap:1.2rem;">
  <div id="ee-epi-icon" style="font-size:6rem;line-height:1;"></div>
  <div id="ee-epi-label" style="
    font-family:'IBM Plex Mono',monospace;font-size:.6rem;
    letter-spacing:3px;color:#a78bfa;text-transform:uppercase;"></div>
</div>

<!-- ── EE4 : Matrix IT ───────────────────────────────────────────────── -->
<div id="ee-matrix-overlay" style="
  display:none;position:fixed;inset:0;z-index:99984;
  background:#000;overflow:hidden;">
  <canvas id="ee-matrix-canvas" style="position:absolute;inset:0;width:100%;height:100%;"></canvas>
  <div style="position:absolute;bottom:1.6rem;left:50%;transform:translateX(-50%);
    font-family:'IBM Plex Mono',monospace;font-size:.55rem;letter-spacing:3px;
    color:#22c55e;text-transform:uppercase;opacity:.75;pointer-events:none;">
    IT DEPT — ACCESS GRANTED
  </div>
</div>

<!-- ── EE5 : terminal PROCESS ────────────────────────────────────────── -->
<div id="ee-process-overlay" style="
  display:none;position:fixed;inset:0;z-index:99983;
  background:rgba(10,12,18,.93);backdrop-filter:blur(4px);
  align-items:center;justify-content:center;">
  <div id="ee-process-box" style="
    width:min(500px,92vw);background:#0d1117;
    border:1px solid #1e3a5f;border-radius:10px;overflow:hidden;
    box-shadow:0 0 50px rgba(96,165,250,.12);
    animation:eeLightIn .3s cubic-bezier(.34,1.56,.64,1);">
    <div style="background:#0f1825;padding:.65rem 1rem;border-bottom:1px solid #1e3a5f;
      display:flex;align-items:center;gap:.55rem;">
      <div style="width:8px;height:8px;border-radius:50%;background:#ff5f57;"></div>
      <div style="width:8px;height:8px;border-radius:50%;background:#febc2e;"></div>
      <div style="width:8px;height:8px;border-radius:50%;background:#28c840;"></div>
      <span style="font-family:'IBM Plex Mono',monospace;font-size:.6rem;
        letter-spacing:2px;color:#60a5fa;margin-left:.4rem;">CLEANROOM SCHEDULER</span>
    </div>
    <div style="padding:1.3rem 1.4rem;">
      <div id="ee-proc-lot" style="font-family:'IBM Plex Mono',monospace;
        font-size:.6rem;letter-spacing:2px;color:#60a5fa;margin-bottom:.9rem;"></div>
      <div style="height:5px;background:#1e2230;border-radius:3px;overflow:hidden;margin-bottom:1.1rem;">
        <div id="ee-proc-bar" style="height:100%;width:0%;background:#60a5fa;
          border-radius:3px;transition:width .4s ease;"></div>
      </div>
      <div id="ee-proc-steps" style="display:flex;flex-direction:column;gap:.5rem;"></div>
      <div id="ee-proc-status" style="font-family:'IBM Plex Mono',monospace;
        margin-top:1rem;font-size:.55rem;letter-spacing:2px;color:#3a4560;min-height:1.3em;"></div>
    </div>
  </div>
</div>


<style>
/* ── animations globales ── */
@keyframes eeLightIn {{
  from {{ transform:scale(.82); opacity:0; }}
  to   {{ transform:scale(1);   opacity:1; }}
}}
/* ── EE3 : cerveau ── */
@keyframes eeEpiBrain {{
  0%,100% {{ transform:scale(1)    rotate(0deg);  filter:brightness(1);   }}
  30%     {{ transform:scale(1.30) rotate(-5deg); filter:brightness(1.65);}}
  60%     {{ transform:scale(1.12) rotate(4deg);  filter:brightness(1.3); }}
}}
/* ── fade in/out widget EPI ── */
@keyframes eeFadeIn  {{ from {{ opacity:0; }} to {{ opacity:1; }} }}
@keyframes eeFadeOut {{ from {{ opacity:1; }} to {{ opacity:0; }} }}

/* ── cartes modal LUMIÈRE ── */
.ee-card {{
  background:#161920;border:1px solid #1e2230;border-radius:8px;
  padding:.9rem 1.1rem;
}}
.ee-card-tag {{
  font-family:'IBM Plex Mono',monospace;font-size:.6rem;color:#D4AF37;
  letter-spacing:2px;text-transform:uppercase;margin-bottom:.35rem;
}}
.ee-card-title {{
  font-family:'Syne',sans-serif;font-size:1.05rem;font-weight:700;
  color:#fff;margin-bottom:.25rem;
}}
.ee-card-body {{
  font-family:'IBM Plex Mono',monospace;font-size:.72rem;
  color:#8892a8;line-height:1.6;
}}

/* ── étapes process ── */
.proc-step {{
  display:flex;align-items:center;gap:.7rem;
  font-family:'IBM Plex Mono',monospace;font-size:.63rem;
  color:#3a4560;transition:color .3s;
}}
.proc-step.done   {{ color:#60a5fa; }}
.proc-step.active {{ color:#93c5fd; }}
.proc-step-dot {{
  width:8px;height:8px;border-radius:50%;flex-shrink:0;
  border:1px solid #3a4560;transition:all .3s;
}}
.proc-step.done   .proc-step-dot {{ background:#60a5fa;border-color:#60a5fa; }}
.proc-step.active .proc-step-dot {{ background:#93c5fd;border-color:#93c5fd;
  box-shadow:0 0 6px rgba(96,165,250,.7); }}
</style>


<script>
(function() {{

  /* ══════════════════════════════════════════════════════════════════════
     Helpers : nom complet LUMIÈRE
  ══════════════════════════════════════════════════════════════════════ */
  var eeUnlocked = false;

  function initShortName() {{
    var el = document.querySelector('.rb-header-lumiere-full');
    if (!el) return;
    var short = el.getAttribute('data-short');
    if (short) el.innerHTML = short;
  }}

  function revealFullName() {{
    if (eeUnlocked) return;
    eeUnlocked = true;
    var el = document.querySelector('.rb-header-lumiere-full');
    if (!el) return;
    var full = el.getAttribute('data-full');
    if (!full) return;
    el.style.transition = 'opacity .5s';
    el.style.opacity    = '0';
    setTimeout(function() {{
      el.innerHTML     = full;
      el.style.opacity = '1';
    }}, 500);
  }}

  if (document.readyState === 'loading') {{
    document.addEventListener('DOMContentLoaded', initShortName);
  }} else {{
    initShortName();
  }}


  /* ══════════════════════════════════════════════════════════════════════
     EE1 : Taper "why" → modal LUMIÈRE
  ══════════════════════════════════════════════════════════════════════ */
  var LINES = {lumiere_data};

  function buildLumiereModal() {{
    var body = document.getElementById('ee-lumiere-body');
    if (body.children.length) return;
    LINES.forEach(function(item) {{
      var tag = item[0], title = item[1], text = item[2];
      var card = document.createElement('div');
      card.className = 'ee-card';
      card.innerHTML =
        '<div class="ee-card-tag">'   + tag   + '</div>' +
        '<div class="ee-card-title">' + title + '</div>' +
        '<div class="ee-card-body">'  + text  + '</div>';
      body.appendChild(card);
    }});
  }}

  function closeModal() {{
    var ov = document.getElementById('ee-lumiere-overlay');
    ov.style.opacity    = '0';
    ov.style.transition = 'opacity .25s';
    setTimeout(function() {{
      ov.style.display    = 'none';
      ov.style.opacity    = '';
      ov.style.transition = '';
      revealFullName();
    }}, 250);
  }}

  document.getElementById('ee-lumiere-close').addEventListener('click', closeModal);


  /* ══════════════════════════════════════════════════════════════════════
     EE3 : Taper "epi" → cerveau 🧠 centré (5 s)
  ══════════════════════════════════════════════════════════════════════ */
  var _epiTimer = null;

  function triggerEpi() {{
    if (_epiTimer) {{ clearTimeout(_epiTimer); _epiTimer = null; }}

    var ov    = document.getElementById('ee-epi-overlay');
    var icon  = document.getElementById('ee-epi-icon');
    var label = document.getElementById('ee-epi-label');

    icon.textContent  = '🧠';
    label.textContent = 'EPI';
    icon.style.animation = 'none';
    /* force reflow pour reset l'animation */
    void icon.offsetWidth;
    icon.style.animation = 'eeEpiBrain 1.3s ease-in-out infinite';

    ov.style.animation = 'eeFadeIn .4s ease forwards';
    ov.style.display   = 'flex';

    _epiTimer = setTimeout(function() {{
      ov.style.animation = 'eeFadeOut .4s ease forwards';
      setTimeout(function() {{
        ov.style.display   = 'none';
        ov.style.animation = '';
        _epiTimer = null;
      }}, 400);
    }}, 1500);
  }}


  /* ══════════════════════════════════════════════════════════════════════
     EE4 : Taper "it" → pluie Matrix (5 s + fade)
  ══════════════════════════════════════════════════════════════════════ */
  var _matrixRAF   = null;
  var _matrixTimer = null;

  var MATRIX_CHARS = 'アイウエオカキクケコサシスセソタチツテトナニヌネノ' +
                     '01λνhcℏ∇∆∑∏√∞≠≈∂ΓΩΨΦφθLUMIERE';

  function triggerMatrix() {{
    if (_matrixRAF)   {{ cancelAnimationFrame(_matrixRAF); _matrixRAF = null; }}
    if (_matrixTimer) {{ clearTimeout(_matrixTimer); _matrixTimer = null; }}

    var ov  = document.getElementById('ee-matrix-overlay');
    var cvs = document.getElementById('ee-matrix-canvas');

    ov.style.opacity    = '1';
    ov.style.transition = '';
    ov.style.display    = 'block';

    var W  = window.innerWidth;
    var H  = window.innerHeight;
    cvs.width  = W;
    cvs.height = H;
    var ctx = cvs.getContext('2d');
    var fs  = 14;
    var cols = Math.floor(W / fs);
    var drops = [];
    for (var c = 0; c < cols; c++) {{
      drops[c] = (Math.random() * -60) | 0;
    }}

    function draw() {{
      ctx.fillStyle = 'rgba(0,0,0,0.13)';
      ctx.fillRect(0, 0, W, H);
      for (var i = 0; i < drops.length; i++) {{
        /* tête de colonne : vert vif */
        ctx.fillStyle = '#86efac';
        ctx.font = fs + 'px monospace';
        var ch = MATRIX_CHARS[Math.floor(Math.random() * MATRIX_CHARS.length)];
        ctx.fillText(ch, i * fs, drops[i] * fs);
        /* corps : vert standard */
        ctx.fillStyle = '#16a34a';
        if (drops[i] > 1) {{
          var ch2 = MATRIX_CHARS[Math.floor(Math.random() * MATRIX_CHARS.length)];
          ctx.fillText(ch2, i * fs, (drops[i] - 1) * fs);
        }}
        if (drops[i] * fs > H && Math.random() > 0.975) drops[i] = 0;
        drops[i]++;
      }}
      _matrixRAF = requestAnimationFrame(draw);
    }}
    draw();

    _matrixTimer = setTimeout(function() {{
      ov.style.transition = 'opacity .6s ease';
      ov.style.opacity    = '0';
      setTimeout(function() {{
        cancelAnimationFrame(_matrixRAF);
        ov.style.display    = 'none';
        ov.style.opacity    = '1';
        ov.style.transition = '';
        _matrixRAF   = null;
        _matrixTimer = null;
      }}, 600);
    }}, 1500);
  }}

  /* Fermeture anticipée au clic */
  document.getElementById('ee-matrix-overlay').addEventListener('click', function() {{
    if (_matrixTimer) {{ clearTimeout(_matrixTimer); _matrixTimer = null; }}
    if (_matrixRAF)   {{ cancelAnimationFrame(_matrixRAF); _matrixRAF = null; }}
    this.style.display = 'none';
  }});


  /* ══════════════════════════════════════════════════════════════════════
     EE5 : Taper "process" → terminal cleanroom
  ══════════════════════════════════════════════════════════════════════ */
  var PROC_STEPS   = {process_steps};
  var _procTimers  = [];

  function stopProcess() {{
    _procTimers.forEach(clearTimeout);
    _procTimers = [];
    var ov = document.getElementById('ee-process-overlay');
    ov.style.display = 'none';
    /* reset barre */
    document.getElementById('ee-proc-bar').style.background = '#60a5fa';
  }}

  /* Fermeture au clic hors de la boîte */
  document.getElementById('ee-process-overlay').addEventListener('click', function(ev) {{
    if (ev.target === this) stopProcess();
  }});

  /* Numéro de lot fictif aléatoire */
  function fakeLot() {{
    var y = new Date().getFullYear();
    var n = String(Math.floor(Math.random() * 900) + 100);
    return 'LOT · W' + y + '-PROC-' + n + ' · EN COURS';
  }}

  function triggerProcess() {{
    stopProcess();

    var ov    = document.getElementById('ee-process-overlay');
    var bar   = document.getElementById('ee-proc-bar');
    var stDiv = document.getElementById('ee-proc-steps');
    var stat  = document.getElementById('ee-proc-status');
    var lot   = document.getElementById('ee-proc-lot');

    /* Reset visuel */
    stDiv.innerHTML    = '';
    bar.style.width    = '0%';
    bar.style.background = '#60a5fa';
    stat.textContent   = '';
    lot.textContent    = fakeLot();

    /* Construire les lignes d'étapes */
    PROC_STEPS.forEach(function(s) {{
      var id = s[0], label = s[1], desc = s[2];
      var row = document.createElement('div');
      row.className = 'proc-step';
      row.id = 'ps-' + id;
      row.innerHTML =
        '<div class="proc-step-dot"></div>' +
        '<span style="min-width:5.5rem;letter-spacing:1.5px;">' + label + '</span>' +
        '<span style="color:#3a4560;">— ' + desc + '</span>';
      stDiv.appendChild(row);
    }});

    ov.style.display = 'flex';

    /* Déroulement progressif */
    var delay = 400;
    PROC_STEPS.forEach(function(s, i) {{
      var id = s[0], label = s[1], pct = s[3], ms = s[4];
      var t = setTimeout(function() {{
        bar.style.width = pct + '%';
        /* Marquer les précédentes comme done */
        for (var j = 0; j < i; j++) {{
          var prev = document.getElementById('ps-' + PROC_STEPS[j][0]);
          if (prev) {{ prev.classList.remove('active'); prev.classList.add('done'); }}
        }}
        var row = document.getElementById('ps-' + id);
        if (row) row.classList.add('active');
        stat.textContent = '▶  ' + label;
      }}, delay);
      _procTimers.push(t);
      delay += ms;
    }});

    /* Finalisation */
    var tFin = setTimeout(function() {{
      var lastRow = document.getElementById('ps-done');
      if (lastRow) {{ lastRow.classList.remove('active'); lastRow.classList.add('done'); }}
      bar.style.background = '#22c55e';
      stat.textContent     = '✓  LOT LIBÉRÉ — transfert vers caractérisation';
      var tClose = setTimeout(stopProcess, 1500);
      _procTimers.push(tClose);
    }}, delay + 300);
    _procTimers.push(tFin);
  }}


  /* ══════════════════════════════════════════════════════════════════════
     Saisie clavier — tous les triggers
     Buffer : 7 caractères (couvre "process")
  ══════════════════════════════════════════════════════════════════════ */
  var typeBuf = '';

  document.addEventListener('keydown', function(e) {{
    if (e.key.length !== 1) {{
      if (e.key === 'Escape') closeModal();
      return;
    }}
    typeBuf = (typeBuf + e.key.toLowerCase()).slice(-7);

    /* EE1 — why */
    if (typeBuf.slice(-3) === 'why') {{
      typeBuf = '';
      buildLumiereModal();
      var ov = document.getElementById('ee-lumiere-overlay');
      ov.style.display = 'flex';
      ov.onclick = function(ev) {{ if (ev.target === ov) closeModal(); }};
      return;
    }}

    /* EE3 — epi */
    if (typeBuf.slice(-3) === 'epi') {{
      typeBuf = '';
      triggerEpi();
      return;
    }}

    /* EE4 — it  (2 caractères exactement, pas dans un mot plus long) */
    if (typeBuf.slice(-2) === 'it' &&
        (typeBuf.length === 2 || !' abcdefghijklmnopqrstuvwxyz'.includes(typeBuf.slice(-3, -2)))) {{
      typeBuf = '';
      triggerMatrix();
      return;
    }}

    /* EE5 — process */
    if (typeBuf.slice(-7) === 'process') {{
      typeBuf = '';
      triggerProcess();
    }}
  }});


  /* ══════════════════════════════════════════════════════════════════════
     EE2 : Clic logo Aledia → burst de photons RGB
  ══════════════════════════════════════════════════════════════════════ */
  function triggerPhotonBurst(originEl) {{
    /* ── Colorisation RGB cyclique des <path> du SVG ── */
    var svg   = originEl.closest('svg') || originEl.querySelector('svg') || originEl;
    var paths = svg ? svg.querySelectorAll('path') : [];
    var RGB_STEPS = [
      ['#ff4444','#44dd44','#4488ff'],
      ['#4488ff','#ff4444','#44dd44'],
      ['#44dd44','#4488ff','#ff4444'],
    ];
    var step = 0;
    var interval = setInterval(function() {{
      if (step >= RGB_STEPS.length) {{
        clearInterval(interval);
        paths.forEach(function(p) {{
          p.style.transition = 'fill .4s';
          p.style.fill = '';
        }});
        return;
      }}
      var colors = RGB_STEPS[step];
      paths.forEach(function(p, i) {{
        p.style.transition = 'fill .15s';
        p.style.fill = colors[i % colors.length];
      }});
      step++;
    }}, 180);

    /* ── Burst de particules depuis le centre du SVG ── */
    var rect = (svg || originEl).getBoundingClientRect();
    var cx   = rect.left + rect.width  / 2;
    var cy   = rect.top  + rect.height / 2;
    var COUNT        = 24;
    var BURST_COLORS = ['#ff4444','#44dd44','#4488ff','#D4AF37'];
    for (var i = 0; i < COUNT; i++) {{
      var dot   = document.createElement('div');
      var angle = (i / COUNT) * Math.PI * 2;
      var dist  = 50 + Math.random() * 50;
      var size  = 3  + Math.random() * 6;
      var tx    = Math.cos(angle) * dist;
      var ty    = Math.sin(angle) * dist;
      var color = BURST_COLORS[i % BURST_COLORS.length];
      dot.style.cssText = [
        'position:fixed','border-radius:50%','pointer-events:none','z-index:99970',
        'width:'  + size  + 'px','height:' + size  + 'px',
        'left:'   + cx    + 'px','top:'    + cy    + 'px',
        'background:' + color,
        'transform:translate(-50%,-50%)',
        'transition:transform .6s cubic-bezier(.2,.8,.4,1), opacity .6s ease',
        'opacity:1',
      ].join(';');
      document.body.appendChild(dot);
      requestAnimationFrame((function(tx, ty, dot) {{
        return function() {{
          dot.style.transform = 'translate(calc(-50% + ' + tx + 'px), calc(-50% + ' + ty + 'px))';
          dot.style.opacity   = '0';
        }};
      }})(tx, ty, dot));
      setTimeout((function(d) {{ return function() {{ d.remove(); }}; }})(dot), 750);
    }}
  }}

  function attachLogoClick() {{
    ['[data-ee-logo]','.rb-logo','.aledia-logo','#rb-header-logo'].forEach(function(sel) {{
      document.querySelectorAll(sel).forEach(function(el) {{
        if (!el._eeAttached) {{
          el.style.cursor = 'pointer';
          el.addEventListener('click', function() {{ triggerPhotonBurst(el); }});
          el._eeAttached = true;
        }}
      }});
    }});
    document.querySelectorAll('header *, .rb-header *').forEach(function(el) {{
      if (!el._eeAttached && el.children.length === 0 &&
          el.textContent.trim().toLowerCase().includes('aledia')) {{
        el.style.cursor = 'pointer';
        el.addEventListener('click', function() {{ triggerPhotonBurst(el); }});
        el._eeAttached = true;
      }}
    }});
  }}

  if (document.readyState === 'loading') {{
    document.addEventListener('DOMContentLoaded', attachLogoClick);
  }} else {{
    attachLogoClick();
  }}
  new MutationObserver(attachLogoClick).observe(document.body, {{childList:true, subtree:true}});

}})();
</script>
<!-- ══════════════════════════════════════════════════════════════════════ -->
"""