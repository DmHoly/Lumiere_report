"""
Core/blocks/lumiere_tour.py
───────────────────────────
Bloc tutoriel interactif LUMIÈRE — tour guidé style "spotlight onboarding".

Au clic sur le bouton (injecté dans le header), un overlay sombre se pose
sur le rapport, met en lumière les éléments clés un par un et affiche
des tooltips animés.

IMPORTANT : l'overlay, l'écran de fin et le bouton sont déplacés vers
<body> au montage (via JS), de sorte qu'ils ne soient jamais enfants d'un
.rb-tab-panel masqué par display:none.

Paramètres de chaque étape (dict)
──────────────────────────────────
tab_index   int | None  – onglet à activer avant l'étape (None = garder l'actif)
selector    str         – sélecteur CSS de l'élément à cibler
fallback    str | None  – sélecteur de repli si selector ne trouve rien
title       str         – titre du tooltip
tag         str         – badge doré (ex. "⚡ L — Unified Metrics")
body        str         – texte explicatif
side        str         – "top" | "bottom"  (défaut "bottom")
align       str         – "left" | "center" | "right"  (défaut "left")

Paramètres du bloc
──────────────────
steps          list[dict] | None  – étapes custom ; None → étapes génériques
trigger_label  str                – libellé du bouton dans le header
auto_start     bool               – démarrer auto à l'ouverture (défaut False)
"""

from __future__ import annotations
import json
from ..._helpers import Block


_DEFAULT_STEPS = [
    {
        "tab_index": None,
        "selector":  ".rb-header",
        "title":     "Header du rapport",
        "tag":       "✦ Identité & traçabilité",
        "body":      "Chaque rapport affiche le titre du projet, l'auteur et la date. "
                     "Le moteur LUMIÈRE génère ce fichier HTML autonome — aucun serveur requis.",
        "side": "bottom", "align": "left",
    },
    {
        "tab_index": None,
        "selector":  ".rb-tabbar",
        "title":     "Navigation par onglets",
        "tag":       "📑 Pages configurables",
        "body":      "Chaque onglet est une page définie dans la config Python. "
                     "Vous choisissez les pages et leur ordre — sans toucher au moteur.",
        "side": "bottom", "align": "left",
    },
    {
        "tab_index": 0,
        "selector":  ".rb-tab-panel.active .led-block:nth-of-type(1)",
        "fallback":  ".rb-tab-panel.active .led-block",
        "title":     "Scatter LED — EQE vs J",
        "tag":       "⚡ LED Unified Metrics",
        "body":      "Chaque point = une LED mesurée. "
                     "Cliquez pour ouvrir la courbe JV + spectre PL. "
                     "Le lasso sélectionne une région pour comparaison.",
        "side": "bottom", "align": "left",
    },
    {
        "tab_index": 0,
        "selector":  ".rb-tab-panel.active .led-block:nth-of-type(2)",
        "fallback":  ".rb-tab-panel.active .led-block",
        "title":     "Summary Box Plots",
        "tag":       "📊 I — Insights automatiques",
        "body":      "Distributions EQE et Vf par wafer. "
                     "La bande dorée matérialise votre spec cible — "
                     "au premier coup d'œil vous voyez qui passe.",
        "side": "bottom", "align": "right",
    },
    {
        "tab_index": 1,
        "selector":  ".rb-tab-panel.active .led-block",
        "title":     "Wafer Maps",
        "tag":       "🗺️ È — Exploration spatiale",
        "body":      "Distribution des KPIs sur le wafer. "
                     "Dropdown colormap, lasso région, clic = courbe complète.",
        "side": "bottom", "align": "left",
    },
    {
        "tab_index": 3,
        "selector":  ".rb-tab-panel.active",
        "fallback":  ".rb-tabbar",
        "title":     "Graph Builder v2",
        "tag":       "🔍 È — Exploration libre",
        "body":      "Sélectionnez X, Y, couleur et mode (Scalaire, Vectoriel, CIE, Facet…). "
                     "Aucune ligne de code. Les données sont embarquées dans le HTML.",
        "side": "top", "align": "center",
    },
    {
        "tab_index": None,
        "selector":  ".rb-header",
        "title":     "Reporting Engine",
        "tag":       "⚙️ R·E — Une ligne de code",
        "body":      "runner.generate(config) — c'est tout. "
                     "Le fichier .html est autonome, envoyable par mail, "
                     "lisible sans installation ni connexion.",
        "side": "bottom", "align": "center",
    },
]


class LumiereTour(Block):
    """
    Bloc tutoriel interactif — overlay spotlight + tooltip par étape.
    no_wrapper=True : aucun div rb-body autour.
    Tout le HTML est déplacé vers <body> au montage pour éviter d'être
    caché par display:none d'un .rb-tab-panel inactif.
    """

    no_wrapper = True

    def __init__(
        self,
        steps:         list[dict] | None = None,
        trigger_label: str  = "🔦 Tutoriel",
        auto_start:    bool = False,
    ):
        self.steps         = steps if steps is not None else _DEFAULT_STEPS
        self.trigger_label = trigger_label
        self.auto_start    = auto_start

    def render(self, store=None) -> str:
        steps_json = json.dumps(self.steps, ensure_ascii=True)
        n_steps    = len(self.steps)
        auto_js    = "true" if self.auto_start else "false"

        return f"""
<!-- ═══════════════════════════════════ LUMIÈRE TOUR ══ -->
<style>
#lmt-overlay{{
  position:fixed;inset:0;z-index:88000;
  display:none;pointer-events:none;
}}
#lmt-overlay.lmt-on{{display:block;}}

#lmt-backdrop{{
  position:fixed;inset:0;width:100%;height:100%;
  pointer-events:all;
}}

#lmt-ring{{
  position:fixed;border:2px solid #D4AF37;border-radius:7px;
  pointer-events:none;z-index:88010;
  box-shadow:0 0 0 4px rgba(212,175,55,.12),0 0 22px rgba(212,175,55,.2);
  transition:left .3s cubic-bezier(.25,.46,.45,.94),
             top  .3s cubic-bezier(.25,.46,.45,.94),
             width .3s cubic-bezier(.25,.46,.45,.94),
             height .3s cubic-bezier(.25,.46,.45,.94);
  animation:lmtPulse 2s ease-in-out infinite;
}}
@keyframes lmtPulse{{
  0%,100%{{box-shadow:0 0 0 4px rgba(212,175,55,.12),0 0 22px rgba(212,175,55,.2);}}
  50%    {{box-shadow:0 0 0 7px rgba(212,175,55,.2), 0 0 34px rgba(212,175,55,.32);}}
}}

#lmt-tooltip{{
  position:fixed;width:310px;
  background:#0d1a3a;
  border:1px solid rgba(212,175,55,.38);border-radius:10px;
  padding:18px 20px 16px;
  box-shadow:0 16px 48px rgba(0,0,0,.75),0 0 0 1px rgba(212,175,55,.08);
  pointer-events:all;z-index:88020;
  transition:opacity .2s,transform .2s;
}}
#lmt-tooltip.lmt-hidden{{opacity:0;transform:translateY(8px);pointer-events:none;}}

.lmt-step-lbl{{font-family:'IBM Plex Mono',monospace;font-size:9px;color:#D4AF37;
  letter-spacing:.2em;text-transform:uppercase;margin-bottom:8px;}}
.lmt-ttl{{font-family:'DM Serif Display','Georgia',serif;font-size:19px;color:#fff;
  line-height:1.15;margin-bottom:7px;}}
.lmt-tag{{display:inline-flex;align-items:center;padding:3px 9px;
  background:rgba(212,175,55,.1);border:1px solid rgba(212,175,55,.22);
  border-radius:3px;font-family:'IBM Plex Mono',monospace;font-size:9px;
  color:#f2dc8a;margin-bottom:11px;}}
.lmt-bdy{{font-family:'Outfit','Segoe UI',sans-serif;font-size:13px;
  color:rgba(255,255,255,.62);line-height:1.62;margin-bottom:14px;}}
.lmt-foot{{display:flex;flex-direction:column;gap:10px;}}
.lmt-prog{{display:flex;gap:4px;}}
.lmt-dot{{width:18px;height:3px;border-radius:2px;background:rgba(255,255,255,.14);
  transition:background .22s,width .22s;}}
.lmt-dot.lmt-cur{{background:#D4AF37;width:26px;}}
.lmt-dot.lmt-done{{background:rgba(212,175,55,.38);}}
.lmt-nav{{display:flex;gap:8px;justify-content:flex-end;}}
.lmt-btn{{height:30px;padding:0 14px;border-radius:5px;
  font-family:'Outfit','Segoe UI',sans-serif;font-size:12px;font-weight:500;
  cursor:pointer;border:none;transition:all .14s;}}
.lmt-skip{{background:none;color:rgba(255,255,255,.4);
  border:1px solid rgba(255,255,255,.12);}}
.lmt-skip:hover{{color:rgba(255,255,255,.8);border-color:rgba(255,255,255,.3);}}
.lmt-next{{background:#D4AF37;color:#060e22;font-weight:600;}}
.lmt-next:hover{{background:#f2dc8a;}}

#lmt-end{{
  position:fixed;inset:0;background:rgba(6,14,34,.92);backdrop-filter:blur(8px);
  z-index:89000;display:none;
  flex-direction:column;align-items:center;justify-content:center;
  gap:14px;text-align:center;
}}
#lmt-end.lmt-on{{display:flex;}}
.lmt-end-ico{{width:56px;height:56px;border-radius:50%;
  background:rgba(212,175,55,.1);border:1px solid rgba(212,175,55,.3);
  display:flex;align-items:center;justify-content:center;font-size:24px;}}
.lmt-end-ttl{{font-family:'DM Serif Display','Georgia',serif;font-size:28px;color:#fff;}}
.lmt-end-bdy{{font-family:'Outfit','Segoe UI',sans-serif;font-size:13px;
  color:rgba(255,255,255,.5);max-width:340px;line-height:1.6;}}
.lmt-end-btns{{display:flex;gap:10px;}}
.lmt-end-restart{{padding:10px 22px;background:none;
  border:1px solid rgba(255,255,255,.18);border-radius:6px;
  color:rgba(255,255,255,.75);font-family:'Outfit','Segoe UI',sans-serif;
  font-size:13px;cursor:pointer;transition:all .14s;}}
.lmt-end-restart:hover{{border-color:rgba(255,255,255,.45);background:rgba(255,255,255,.05);}}
.lmt-end-close{{padding:10px 22px;background:#D4AF37;color:#060e22;border:none;
  border-radius:6px;font-family:'Outfit','Segoe UI',sans-serif;
  font-size:13px;font-weight:600;cursor:pointer;transition:all .14s;}}
.lmt-end-close:hover{{background:#f2dc8a;}}

#lmt-trigger{{
  display:inline-flex;align-items:center;gap:6px;
  padding:4px 12px 4px 8px;height:26px;
  background:rgba(212,175,55,.08);
  border:1px solid rgba(212,175,55,.25);border-radius:20px;
  color:#D4AF37;font-family:'IBM Plex Mono',monospace;
  font-size:10px;font-weight:500;letter-spacing:.04em;
  cursor:pointer;flex-shrink:0;
  margin-left:20px;margin-right:20px;
  transition:all .18s;
}}
#lmt-trigger:hover{{background:rgba(212,175,55,.18);border-color:rgba(212,175,55,.5);}}
#lmt-trigger.lmt-hidden{{display:none;}}
.lmt-led{{width:6px;height:6px;border-radius:50%;background:#D4AF37;flex-shrink:0;
  box-shadow:0 0 6px #D4AF37,0 0 12px rgba(212,175,55,.5);
  animation:lmtBlink 1.6s ease-in-out infinite;}}
@keyframes lmtBlink{{0%,100%{{opacity:1;}}50%{{opacity:.4;}}}}
</style>

<!-- Ces éléments seront déplacés dans <body> par mountAll() -->
<div id="lmt-overlay">
  <svg id="lmt-backdrop" xmlns="http://www.w3.org/2000/svg">
    <defs>
      <mask id="lmt-mask">
        <rect width="100%" height="100%" fill="white"/>
        <rect id="lmt-hole" x="0" y="0" width="0" height="0" rx="8" fill="black"/>
      </mask>
    </defs>
    <rect width="100%" height="100%" fill="rgba(6,14,34,0.82)" mask="url(#lmt-mask)"/>
  </svg>
  <div id="lmt-ring"></div>
  <div id="lmt-tooltip" class="lmt-hidden">
    <div class="lmt-step-lbl" id="lmt-lbl">Étape 1 / {n_steps}</div>
    <div class="lmt-ttl"      id="lmt-ttl"></div>
    <div class="lmt-tag"      id="lmt-tag-text"></div>
    <div class="lmt-bdy"      id="lmt-bdy"></div>
    <div class="lmt-foot">
      <div class="lmt-prog" id="lmt-prog"></div>
      <div class="lmt-nav">
        <button class="lmt-btn lmt-skip" id="lmt-skip">Passer</button>
        <button class="lmt-btn lmt-next" id="lmt-next">Suivant →</button>
      </div>
    </div>
  </div>
</div>

<div id="lmt-end">
  <div class="lmt-end-ico">✦</div>
  <div class="lmt-end-ttl">Prêt à explorer</div>
  <p class="lmt-end-bdy">
    Vous connaissez maintenant les composantes clés de LUMIÈRE.<br>
    Le rapport est autonome : aucun serveur requis, aucune installation. 
    Il peut etre ouvert directement dans un navigateur et partage par mail ou sur un drive.  </p>
  <div class="lmt-end-btns">
    <button class="lmt-end-restart" id="lmt-restart">↩ Revoir le tour</button>
    <button class="lmt-end-close"   id="lmt-close-end">Fermer</button>
  </div>
</div>

<button id="lmt-trigger">
  <div class="lmt-led"></div>
  {self.trigger_label}
</button>

<script>
(function(){{
  var STEPS   = {steps_json};
  var N       = STEPS.length;
  var AUTO    = {auto_js};
  var current = -1;

  /* Refs — initialisées dans mountAll() après body.appendChild */
  var overlay, ring, tooltip, hole, endScreen, trigger, backdrop;

  /* ── Switch onglet ───────────────────────────────────────────── */
  function switchTab(idx) {{
    if (idx === null || idx === undefined) return;
    var keys = Object.keys(window).filter(function(k) {{
      return /^tv\d+_show$/.test(k);
    }});
    if (keys.length) window[keys[0]](idx);
    else {{
      var btn = document.querySelectorAll('.rb-tab-btn')[idx];
      if (btn) btn.click();
    }}
  }}

  /* ── Résolution sélecteur ────────────────────────────────────── */
  function resolveEl(step) {{
    var el = document.querySelector(step.selector);
    if (!el && step.fallback) el = document.querySelector(step.fallback);
    return el || null;
  }}

  /* ── Spotlight (tout en coords viewport = fixed) ─────────────── */
  function spotlight(rect, pad) {{
    pad = pad || 8;
    var x=rect.left-pad, y=rect.top-pad;
    var w=rect.width+pad*2, h=rect.height+pad*2;
    hole.setAttribute('x',x); hole.setAttribute('y',y);
    hole.setAttribute('width',w); hole.setAttribute('height',h);
    ring.style.left=x+'px'; ring.style.top=y+'px';
    ring.style.width=w+'px'; ring.style.height=h+'px';
  }}

  function noSpotlight() {{
    hole.setAttribute('width',0); hole.setAttribute('height',0);
    ring.style.width=ring.style.height='0';
  }}

  /* ── Position tooltip ────────────────────────────────────────── */
  function placeTooltip(rect, side, align) {{
    var ttW=310,ttH=260,pad=14,vpad=10;
    var vw=window.innerWidth, vh=window.innerHeight;
    var top, left;
    if (side==='top') {{
      top=rect.top-ttH-pad;
      if (top<vpad) top=rect.top+rect.height+pad;
    }} else {{
      top=rect.top+rect.height+pad;
      if (top+ttH>vh-vpad) top=rect.top-ttH-pad;
    }}
    if      (align==='right')  left=rect.left+rect.width-ttW;
    else if (align==='center') left=rect.left+rect.width/2-ttW/2;
    else                       left=rect.left;
    left=Math.max(vpad,Math.min(vw-ttW-vpad,left));
    top =Math.max(vpad,Math.min(vh-ttH-vpad,top));
    tooltip.style.left=left+'px'; tooltip.style.top=top+'px';
  }}

  /* ── Dots ────────────────────────────────────────────────────── */
  function buildProg(idx) {{
    var p=document.getElementById('lmt-prog');
    p.innerHTML='';
    for (var i=0;i<N;i++) {{
      var d=document.createElement('div');
      d.className='lmt-dot'+(i===idx?' lmt-cur':(i<idx?' lmt-done':''));
      p.appendChild(d);
    }}
  }}

  /* ── Afficher une étape ──────────────────────────────────────── */
  function showStep(idx) {{
    var step=STEPS[idx];
    var vw=window.innerWidth, vh=window.innerHeight;
    if (step.tab_index!==null && step.tab_index!==undefined) switchTab(step.tab_index);
    var delay=(step.tab_index!==null && step.tab_index!==undefined) ? 80 : 0;

    setTimeout(function() {{
      var el=resolveEl(step);
      document.getElementById('lmt-lbl').textContent='Étape '+(idx+1)+' / '+N;
      document.getElementById('lmt-ttl').textContent=step.title||'';
      document.getElementById('lmt-tag-text').textContent=step.tag||'';
      document.getElementById('lmt-bdy').textContent=step.body||'';
      buildProg(idx);
      document.getElementById('lmt-next').textContent=idx===N-1?'Terminer ✓':'Suivant →';

      if (!el) {{
        noSpotlight();
        placeTooltip({{top:vh/2-40,left:vw/2-155,width:310,height:80}},
          step.side||'bottom', step.align||'left');
        tooltip.classList.remove('lmt-hidden');
        return;
      }}

      el.scrollIntoView({{block:'nearest'}});
      requestAnimationFrame(function() {{
        requestAnimationFrame(function() {{
          var rect=el.getBoundingClientRect();
          spotlight(rect);
          placeTooltip(rect, step.side||'bottom', step.align||'left');
          tooltip.classList.remove('lmt-hidden');
        }});
      }});
    }}, delay);
  }}

  /* ── Contrôle ────────────────────────────────────────────────── */
  function startTour() {{
    trigger.classList.add('lmt-hidden');
    endScreen.classList.remove('lmt-on');
    overlay.classList.add('lmt-on');
    current=0; tooltip.classList.add('lmt-hidden');
    showStep(current);
  }}
  function nextStep() {{
    tooltip.classList.add('lmt-hidden');
    current++;
    if (current>=N) {{ finish(); return; }}
    setTimeout(function(){{ showStep(current); }}, 180);
  }}
  function finish() {{
    switchTab(0);
    overlay.classList.remove('lmt-on');
    endScreen.classList.add('lmt-on');
  }}
  function close() {{
    switchTab(0);
    overlay.classList.remove('lmt-on');
    endScreen.classList.remove('lmt-on');
    trigger.classList.remove('lmt-hidden');
    current=-1;
  }}
  function restart() {{
    endScreen.classList.remove('lmt-on');
    overlay.classList.add('lmt-on');
    current=0; tooltip.classList.add('lmt-hidden');
    setTimeout(function(){{ showStep(current); }}, 80);
  }}

  /* ── Listeners ───────────────────────────────────────────────── */
  function bindListeners() {{
    trigger.addEventListener('click', startTour);
    document.getElementById('lmt-next').addEventListener('click', nextStep);
    document.getElementById('lmt-skip').addEventListener('click', close);
    document.getElementById('lmt-restart').addEventListener('click', restart);
    document.getElementById('lmt-close-end').addEventListener('click', close);
    backdrop.addEventListener('click', function(e) {{
      if (!tooltip.contains(e.target)) close();
    }});
    document.addEventListener('keydown', function(e) {{
      if (!overlay.classList.contains('lmt-on')) return;
      if (e.key==='ArrowRight'||e.key==='Enter') nextStep();
      if (e.key==='Escape') close();
    }});
    window.addEventListener('resize', function() {{
      if (current<0||!overlay.classList.contains('lmt-on')) return;
      var el=resolveEl(STEPS[current]); if (!el) return;
      requestAnimationFrame(function() {{
        var rect=el.getBoundingClientRect();
        spotlight(rect);
        placeTooltip(rect,STEPS[current].side||'bottom',STEPS[current].align||'left');
      }});
    }});
    if (AUTO) setTimeout(startTour, 700);
  }}

  /* ── Mount : déplace overlay + end vers <body> ───────────────── */
  /* CRITIQUE : ces éléments ne doivent PAS rester dans un
     .rb-tab-panel → display:none masquerait tout au changement
     d'onglet, même avec position:fixed sur les enfants.           */
  function mountAll() {{
    overlay   = document.getElementById('lmt-overlay');
    endScreen = document.getElementById('lmt-end');
    trigger   = document.getElementById('lmt-trigger');

    document.body.appendChild(overlay);
    document.body.appendChild(endScreen);

    /* Relire les enfants après déplacement */
    ring     = document.getElementById('lmt-ring');
    tooltip  = document.getElementById('lmt-tooltip');
    hole     = document.getElementById('lmt-hole');
    backdrop = document.getElementById('lmt-backdrop');

    /* Bouton → header après .rb-header-title */
    var header  = document.querySelector('.rb-header');
    var titleEl = document.querySelector('.rb-header-title');
    if (header && titleEl && titleEl.nextSibling) {{
      header.insertBefore(trigger, titleEl.nextSibling);
    }} else if (header) {{
      header.insertBefore(trigger, document.getElementById('rb-info-btn')||null);
    }}

    bindListeners();
  }}

  if (document.readyState==='loading') {{
    document.addEventListener('DOMContentLoaded', mountAll);
  }} else {{
    mountAll();
  }}

}})();
</script>
<!-- ════════════════════════════════════════════════════════════ -->
"""