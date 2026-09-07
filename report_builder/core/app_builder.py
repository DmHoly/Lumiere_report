"""
AppBuilder — mode application autonome pour le report builder.

Même DataStore, mêmes blocs, même moteur de rendu que ReportBuilder,
mais avec une enveloppe applicative : sidebar, topbar, pages, navigation JS.

Usage::

    from report_builder.core import AppBuilder, Page
    from report_builder.core import KPIRow, KPI, WaferMaps, GraphBuilderV3

    app = AppBuilder(
        title="Lumière", subtitle="LED Explorer",
        sources=[{"label": "Mock LED — Lot A", "key": "main"}],
    )
    app.data.register("main", df)

    app.add_page(Page("Accueil", icon="⌂", blocks=[
        KPIRow([KPI("LEDs", len(df)), KPI("Wafers", df["wafername"].nunique())]),
    ]))
    app.add_page(Page("Graph Builder", icon="◈", fullscreen=True, blocks=[
        GraphBuilderV3("main", height=800),
    ]))

    app.save("output/lumiere_app.html")
"""
from __future__ import annotations
import html as _h
from ._assets import _PLOTLY_JS, _MARKED_JS, _ALEDIA_LOGO_SVG
from ._helpers import Block
from .blocks.data.data_store import DataStore


# ─── App shell CSS ────────────────────────────────────────────────────────────
_APP_CSS = """<style>
@import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@300;400;500&family=DM+Sans:wght@300;400;500;600&display=swap');

/* ── Variables — même palette que les rapports ───────────────────────────── */
:root {
  --ab-navy:    #0d1b3e;
  --ab-navy-d:  #0a1530;
  --ab-navy-m:  #122052;
  --ab-navy-l:  #1a2f6a;
  --ab-gold:    #c9a84c;
  --ab-gold-l:  #e8c97a;
  --ab-bg:      #f0f2f8;
  --ab-surface: #ffffff;
  --ab-border:  #dde1ef;
  --ab-text:    #0d1b3e;
  --ab-muted:   #8892aa;
  --ab-fm:      'IBM Plex Mono', 'Courier New', monospace;
  --ab-fd:      'DM Sans', 'Helvetica Neue', Arial, sans-serif;
  --ab-sidebar-w: 228px;
  --ab-sidebar-collapsed-w: 52px;
  --ab-topbar-h: 56px;
  --ab-radius: 8px;
  --ab-shadow: 0 1px 3px rgba(13,27,62,.10), 0 1px 2px rgba(13,27,62,.06);
  --ab-transition: width 0.22s cubic-bezier(.4,0,.2,1);
}

/* ── Reset ───────────────────────────────────────────────────────────────── */
*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
html, body.ab-app { height: 100%; overflow: hidden; }
body.ab-app { font-family: var(--ab-fd); background: var(--ab-bg); color: var(--ab-text); }

/* ── Layout ──────────────────────────────────────────────────────────────── */
.ab-layout { display: flex; height: 100vh; }

/* ═══════════════════════════════════════════════════
   SIDEBAR — navy foncé, même couleur que rb-header
═══════════════════════════════════════════════════ */
.ab-sidebar {
  width: var(--ab-sidebar-w);
  flex-shrink: 0;
  background: linear-gradient(180deg, #0a1530 0%, #0d1b3e 60%, #111e44 100%);
  display: flex; flex-direction: column;
  overflow: hidden;
  transition: var(--ab-transition);
  z-index: 10;
  box-shadow: 2px 0 8px rgba(0,0,0,.18);
}
.ab-sidebar.ab-collapsed { width: var(--ab-sidebar-collapsed-w); }

/* Brand block */
.ab-sidebar-brand {
  height: var(--ab-topbar-h);
  display: flex; align-items: center; gap: 10px;
  padding: 0 14px;
  border-bottom: 1px solid rgba(255,255,255,.08);
  flex-shrink: 0; overflow: hidden;
}
.ab-brand-glyph {
  font-size: 1.1rem; color: var(--ab-gold);
  flex-shrink: 0; width: 24px; text-align: center;
}
.ab-brand-name {
  font-family: var(--ab-fd);
  font-size: 12px; font-weight: 600; letter-spacing: 4px;
  text-transform: uppercase; color: #fff;
  white-space: nowrap; overflow: hidden;
  transition: opacity 0.18s;
}
.ab-sidebar.ab-collapsed .ab-brand-name { opacity: 0; }

/* Nav items */
.ab-nav { padding: 8px 0; flex: 1; overflow-y: auto; overflow-x: hidden; }
.ab-nav::-webkit-scrollbar { width: 3px; }
.ab-nav::-webkit-scrollbar-thumb { background: rgba(255,255,255,.12); border-radius: 2px; }

.ab-nav-item {
  display: flex; align-items: center; gap: 10px;
  padding: 0 14px; height: 38px;
  cursor: pointer;
  border-left: 2px solid transparent;
  overflow: hidden; white-space: nowrap;
  color: rgba(255,255,255,.5);
  font-family: var(--ab-fd); font-size: 13px; font-weight: 400;
  transition: background 0.13s, color 0.13s, border-color 0.13s;
  user-select: none; position: relative;
}
.ab-nav-item:hover { background: rgba(255,255,255,.06); color: rgba(255,255,255,.88); }
.ab-nav-item.ab-nav-active {
  background: rgba(201,168,76,.12);
  color: var(--ab-gold-l);
  border-left-color: var(--ab-gold);
  font-weight: 500;
}
.ab-nav-icon { font-size: 1rem; flex-shrink: 0; width: 22px; text-align: center; }
.ab-nav-label { flex: 1; overflow: hidden; text-overflow: ellipsis; transition: opacity 0.15s; }
.ab-sidebar.ab-collapsed .ab-nav-label { opacity: 0; pointer-events: none; }

/* Tooltip items quand collapsed */
.ab-sidebar.ab-collapsed .ab-nav-item::after {
  content: attr(data-label);
  position: fixed; left: calc(var(--ab-sidebar-collapsed-w) + 8px); top: auto;
  background: var(--ab-navy); color: #fff;
  font-size: 11px; font-family: var(--ab-fd);
  padding: 4px 10px; border-radius: 4px; white-space: nowrap;
  pointer-events: none; opacity: 0;
  transition: opacity 0.15s; z-index: 200;
  box-shadow: var(--ab-shadow);
}
.ab-sidebar.ab-collapsed .ab-nav-item:hover::after { opacity: 1; }

/* ═══════════════════════════════════════════════════
   TOPBAR — même gradient que rb-header
═══════════════════════════════════════════════════ */
.ab-main { flex: 1; display: flex; flex-direction: column; overflow: hidden; min-width: 0; }

.ab-topbar {
  height: var(--ab-topbar-h); flex-shrink: 0;
  background: linear-gradient(90deg, #060e22 0%, #0d1b3e 30%, #122052 65%, #1a2f6a 100%);
  display: flex; align-items: center;
  padding: 0 20px; gap: 12px;
  box-shadow: 0 2px 6px rgba(0,0,0,.22);
  z-index: 5;
}

/* Hamburger toggle — dans le topbar, pas la sidebar */
.ab-topbar-toggle {
  background: none; border: none; cursor: pointer;
  display: flex; flex-direction: column; justify-content: center; gap: 4px;
  width: 28px; height: 28px; padding: 4px;
  flex-shrink: 0; opacity: .7; transition: opacity .15s;
}
.ab-topbar-toggle:hover { opacity: 1; }
.ab-topbar-toggle span {
  display: block; height: 2px; border-radius: 1px;
  background: rgba(255,255,255,.85);
  transition: width .2s;
}
.ab-topbar-toggle span:nth-child(2) { width: 75%; }

/* Séparateur vertical */
.ab-topbar-sep {
  width: 1px; height: 28px;
  background: rgba(255,255,255,.15); flex-shrink: 0;
}

.ab-topbar-title {
  font-family: var(--ab-fd);
  font-size: 13px; font-weight: 600; color: rgba(255,255,255,.92);
  letter-spacing: .3px; white-space: nowrap;
}
.ab-topbar-sub {
  font-size: 11px; font-weight: 300;
  color: rgba(255,255,255,.4); margin-left: 4px;
}

/* Sélecteur de source */
.ab-source-selector {
  display: flex; align-items: center; gap: 8px;
  margin-left: auto;
}
.ab-source-label {
  font-family: var(--ab-fm); font-size: 9px;
  color: rgba(255,255,255,.35); letter-spacing: 1.5px; text-transform: uppercase;
  white-space: nowrap;
}
.ab-source-select {
  font-family: var(--ab-fm); font-size: 11px;
  color: rgba(255,255,255,.82);
  background: rgba(255,255,255,.07);
  border: 1px solid rgba(255,255,255,.15);
  border-radius: 5px;
  padding: 4px 28px 4px 10px;
  outline: none; cursor: pointer;
  appearance: none;
  background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='10' height='6'%3E%3Cpath d='M0 0l5 6 5-6z' fill='rgba(255,255,255,.4)'/%3E%3C/svg%3E");
  background-repeat: no-repeat; background-position: right 8px center;
  transition: border-color .15s, background-color .15s;
  max-width: 220px;
}
.ab-source-select:hover { border-color: rgba(201,168,76,.5); }
.ab-source-select:focus { border-color: var(--ab-gold); }
.ab-source-select option { background: #0d1b3e; color: #fff; }

/* Loading pill */
.ab-source-loading {
  display: none; align-items: center; gap: 6px;
  font-family: var(--ab-fm); font-size: 9px;
  color: var(--ab-gold-l); letter-spacing: 1px;
}
.ab-source-loading.ab-visible { display: flex; }
.ab-source-spinner {
  width: 12px; height: 12px; border-radius: 50%;
  border: 2px solid rgba(201,168,76,.25);
  border-top-color: var(--ab-gold);
  animation: ab-spin .7s linear infinite;
}
@keyframes ab-spin { to { transform: rotate(360deg); } }

/* ═══════════════════════════════════════════════════
   CONTENT — fond clair, même que les rapports
═══════════════════════════════════════════════════ */
.ab-content { flex: 1; overflow-y: auto; background: var(--ab-bg); position: relative; }
.ab-page { display: none; min-height: 100%; }
.ab-page.ab-page-active { display: block; }

/* Page fullscreen — pas de header, content = 100% hauteur */
.ab-page.ab-page-fullscreen { min-height: unset; }
.ab-page.ab-page-fullscreen.ab-page-active {
  display: flex; flex-direction: column;
  height: 100%;
}

/* Page header — fine barre gold, comme rb-section */
.ab-page-header {
  display: flex; align-items: center; gap: 10px;
  padding: 18px 28px 12px;
  border-bottom: 1px solid var(--ab-border);
}
.ab-page-header-bar { width: 2px; height: 18px; background: var(--ab-gold); flex-shrink: 0; }
.ab-page-title {
  font-family: var(--ab-fd); font-size: 15px; font-weight: 600; color: var(--ab-text);
  display: flex; align-items: center; gap: 7px;
}
.ab-page-title-icon { font-size: 1rem; }

/* Block wrapper — identique à .rb-body */
.ab-body {
  max-width: 100%;
  padding: 16px 28px 0;
  display: flex; flex-direction: column; gap: 20px;
}
</style>"""


# ─────────────────────────────────────────────────────────────────────────────
# Page
# ─────────────────────────────────────────────────────────────────────────────
class Page:
    """
    Conteneur d'une page applicative.

    Paramètres
    ----------
    name : str
        Nom affiché dans la sidebar et le topbar.
    icon : str
        Emoji ou caractère Unicode affiché dans la sidebar (défaut: "◈").
    fullscreen : bool
        Si True, le bloc remplit toute la zone contenu sans header ni padding.
        Utile pour GraphBuilderV2/V3 qui ont leur propre chrome.
    blocks : list[Block] | None
        Blocs à inclure. Peuvent aussi être ajoutés via ``add()``.
    """

    def __init__(
        self,
        name: str,
        icon: str = "◈",
        fullscreen: bool = False,
        blocks: list[Block] | None = None,
    ):
        self.name = name
        self.icon = icon
        self.fullscreen = fullscreen
        self._blocks: list[Block] = list(blocks) if blocks else []
        slug = name.lower().replace(" ", "-")
        for ch in "/\\.,;:!?'\"()[]{}":
            slug = slug.replace(ch, "-")
        self.id = f"ab-page-{slug}"

    def add(self, block: Block) -> "Page":
        self._blocks.append(block)
        return self

    @property
    def children(self) -> list[Block]:
        return self._blocks

    def render(self, store=None) -> str:
        parts: list[str] = []
        for b in self._blocks:
            if self.fullscreen:
                # plein écran : pas de wrapper, le bloc gère lui-même son layout
                parts.append(b.render(store=store))
            elif getattr(b, "is_container", False):
                parts.append(b.render(store=store))
            else:
                parts.append(f'<div class="ab-body">{b.render(store=store)}</div>')
        return "\n".join(parts)


# ─────────────────────────────────────────────────────────────────────────────
# AppBuilder
# ─────────────────────────────────────────────────────────────────────────────
class AppBuilder:
    """
    Assemble des pages en une application HTML autonome.

    Paramètres
    ----------
    title, subtitle : str
        Affichés dans le topbar.
    sources : list[dict] | None
        Liste de sources mock ``[{"label": "Lot A", "key": "main"}, ...]``.
        Affiche un sélecteur dans le topbar. Quand l'utilisateur change de source,
        l'événement JS ``ab:source-changed`` est dispatché avec ``{detail: {key}}``.
    data_store : DataStore | None
        Injection de dépendance — utile pour les tests.
    """

    def __init__(
        self,
        title: str = "Lumière",
        subtitle: str = "",
        author: str = "Aledia",
        sources: list[dict] | None = None,
        data_store: DataStore | None = None,
    ):
        self.title = title
        self.subtitle = subtitle
        self.author = author
        self.sources = sources or []
        self._pages: list[Page] = []
        self.data = data_store if data_store is not None else DataStore()

    def add_page(self, page: Page) -> "AppBuilder":
        self._pages.append(page)
        return self

    def _collect_deps(self) -> tuple[bool, bool]:
        need_plotly = need_marked = False

        def _walk(items):
            nonlocal need_plotly, need_marked
            for item in items:
                need_plotly = need_plotly or getattr(item, "needs_plotly", False)
                need_marked = need_marked or getattr(item, "needs_marked", False)
                ch = getattr(item, "children", None)
                if ch:
                    _walk(ch)

        for page in self._pages:
            _walk(page.children)
        return need_plotly, need_marked

    def _render_source_selector(self) -> str:
        if not self.sources:
            return ""
        opts = "".join(
            f'<option value="{_h.escape(str(s.get("key", "")))}">'
            f'{_h.escape(str(s.get("label", s.get("key", ""))))}'
            f'</option>'
            for s in self.sources
        )
        return (
            f'<div class="ab-source-selector">'
            f'<span class="ab-source-label">Dataset</span>'
            f'<select class="ab-source-select" id="ab-source-select" onchange="abSourceChange(this)">'
            f'{opts}'
            f'</select>'
            f'<div class="ab-source-loading" id="ab-source-loading">'
            f'<div class="ab-source-spinner"></div>'
            f'<span>Chargement…</span>'
            f'</div>'
            f'</div>'
        )

    def render(self) -> str:
        if not self._pages:
            raise ValueError("AppBuilder: aucune page ajoutée — utilisez add_page().")

        need_plotly, need_marked = self._collect_deps()
        ext = ""
        if need_plotly:
            ext += f"\n  {_PLOTLY_JS}"
        if need_marked:
            ext += f"\n  {_MARKED_JS}"

        # ── Sidebar nav items ──────────────────────────────────────────────────
        nav_items: list[str] = []
        for i, page in enumerate(self._pages):
            active_cls = " ab-nav-active" if i == 0 else ""
            nav_items.append(
                f'<div class="ab-nav-item{active_cls}" '
                f'data-target="{page.id}" data-label="{_h.escape(page.name)}" onclick="abNav(this)">'
                f'<span class="ab-nav-icon">{_h.escape(page.icon)}</span>'
                f'<span class="ab-nav-label">{_h.escape(page.name)}</span>'
                f'</div>'
            )

        # ── Page panels ────────────────────────────────────────────────────────
        page_panels: list[str] = []
        for i, page in enumerate(self._pages):
            active_cls = " ab-page-active" if i == 0 else ""
            fs_cls = " ab-page-fullscreen" if page.fullscreen else ""
            content = page.render(store=self.data)

            if page.fullscreen:
                # pas de header, contenu direct
                page_panels.append(
                    f'<div class="ab-page{fs_cls}{active_cls}" id="{page.id}">'
                    f'{content}'
                    f'</div>'
                )
            else:
                page_panels.append(
                    f'<div class="ab-page{active_cls}" id="{page.id}">'
                    f'<div class="ab-page-header">'
                    f'<div class="ab-page-header-bar"></div>'
                    f'<div class="ab-page-title">'
                    f'<span class="ab-page-title-icon">{_h.escape(page.icon)}</span>'
                    f'<span>{_h.escape(page.name)}</span>'
                    f'</div>'
                    f'</div>'
                    f'{content}'
                    f'</div>'
                )

        sub_h = (
            f' <span class="ab-topbar-sub">— {_h.escape(self.subtitle)}</span>'
            if self.subtitle else ""
        )
        first_page = _h.escape(self._pages[0].name) if self._pages else ""
        source_sel = self._render_source_selector()

        return f"""<!DOCTYPE html>
<html lang="fr">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>{_h.escape(self.title)}</title>{ext}
  {self.data.to_js_injection()}
  {_APP_CSS}
</head>
<body class="ab-app">
<div class="ab-layout">

  <!-- ── Sidebar ─────────────────────────────────────────── -->
  <aside class="ab-sidebar" id="ab-sidebar">
    <div class="ab-sidebar-brand">
      <span class="ab-brand-glyph">◈</span>
      <span class="ab-brand-name">LUMIÈRE</span>
    </div>
    <nav class="ab-nav">
      {"".join(nav_items)}
    </nav>
  </aside>

  <!-- ── Main ────────────────────────────────────────────── -->
  <div class="ab-main">
    <header class="ab-topbar">

      <!-- Toggle hamburger -->
      <button class="ab-topbar-toggle" onclick="abToggle()" title="Réduire / Agrandir la sidebar" aria-label="Toggle sidebar">
        <span></span><span></span><span></span>
      </button>

      <div class="ab-topbar-sep"></div>

      <!-- Logo Aledia -->
      {_ALEDIA_LOGO_SVG}

      <div class="ab-topbar-sep"></div>

      <!-- Titre -->
      <span class="ab-topbar-title">{_h.escape(self.title)}{sub_h}</span>

      <!-- Sélecteur de source (si défini) -->
      {source_sel}

    </header>
    <div class="ab-content" id="ab-content">
      {"".join(page_panels)}
    </div>
  </div>

</div>
<script>
(function() {{

  /* ── Navigation ─────────────────────────────────────────── */
  function abNav(el) {{
    var target = el.getAttribute('data-target');
    document.querySelectorAll('.ab-nav-item').forEach(function(n) {{
      n.classList.remove('ab-nav-active');
    }});
    el.classList.add('ab-nav-active');
    document.querySelectorAll('.ab-page').forEach(function(p) {{
      p.classList.toggle('ab-page-active', p.id === target);
    }});
    requestAnimationFrame(function() {{
      window.dispatchEvent(new Event('resize'));
      document.querySelectorAll('[id]').forEach(function(node) {{
        if (node._fullLayout) {{ try {{ Plotly.Plots.resize(node); }} catch(e) {{}} }}
      }});
    }});
  }}

  /* ── Toggle sidebar ─────────────────────────────────────── */
  function abToggle() {{
    document.getElementById('ab-sidebar').classList.toggle('ab-collapsed');
    // laisser la transition se terminer avant de resize Plotly
    setTimeout(function() {{
      window.dispatchEvent(new Event('resize'));
      document.querySelectorAll('[id]').forEach(function(node) {{
        if (node._fullLayout) {{ try {{ Plotly.Plots.resize(node); }} catch(e) {{}} }}
      }});
    }}, 240);
  }}

  /* ── Source selector ────────────────────────────────────── */
  function abSourceChange(sel) {{
    var key    = sel.value;
    var loader = document.getElementById('ab-source-loading');
    if (loader) {{ loader.classList.add('ab-visible'); }}
    // Simule un appel API — retire le spinner après 800 ms
    setTimeout(function() {{
      if (loader) loader.classList.remove('ab-visible');
      window.dispatchEvent(new CustomEvent('ab:source-changed', {{ detail: {{ key: key }} }}));
    }}, 800);
  }}

  window.abNav          = abNav;
  window.abToggle       = abToggle;
  window.abSourceChange = abSourceChange;

}})();
</script>
</body>
</html>"""

    def save(self, path: str) -> None:
        html = self.render()
        with open(path, "w", encoding="utf-8") as f:
            f.write(html)
        print(f"✓  {path}  ({len(html) // 1024} KB)")
