from __future__ import annotations
import html as _h
from ._helpers import Block

# ─────────────────────────────────────────────────────────────────────────────
# TAB / TABVIEW  (inchangés — zéro breaking change)
# ─────────────────────────────────────────────────────────────────────────────

_TAB_ICONS = {
    "rapport":     '<svg viewBox="0 0 24 24" width="12" height="12"><path d="M14 2H6c-1.1 0-2 .9-2 2v16c0 1.1.9 2 2 2h12c1.1 0 2-.9 2-2V8l-6-6zm2 16H8v-2h8v2zm0-4H8v-2h8v2zm-3-5V3.5L18.5 9H13z"/></svg>',
    "exploration": '<svg viewBox="0 0 24 24" width="12" height="12"><path d="M3.5 18.49l6-6.01 4 4L22 6.92l-1.41-1.41-7.09 7.97-4-4L2 16.99z"/></svg>',
    "données":     '<svg viewBox="0 0 24 24" width="12" height="12"><path d="M20 13H4c-.55 0-1 .45-1 1v6c0 .55.45 1 1 1h16c.55 0 1-.45 1-1v-6c0-.55-.45-1-1-1zm-2 5h-2v-2h2v2zM4 3h16c.55 0 1 .45 1 1v6c0 .55-.45 1-1 1H4c-.55 0-1-.45-1-1V4c0-.55.45-1 1-1zm14 5h-2V6h2v2z"/></svg>',
    "summary":     '<svg viewBox="0 0 24 24" width="12" height="12"><path d="M19 3H5c-1.1 0-2 .9-2 2v14c0 1.1.9 2 2 2h14c1.1 0 2-.9 2-2V5c0-1.1-.9-2-2-2zM9 17H7v-7h2v7zm4 0h-2V7h2v10zm4 0h-2v-4h2v4z"/></svg>',
    "wafer":       '<svg viewBox="0 0 24 24" width="12" height="12"><circle cx="12" cy="12" r="9" fill="none" stroke="currentColor" stroke-width="2"/><circle cx="12" cy="12" r="3"/></svg>',
    "default":     '<svg viewBox="0 0 24 24" width="12" height="12"><path d="M3 18h18v-2H3v2zm0-5h18v-2H3v2zm0-7v2h18V6H3z"/></svg>',
}

def _tab_icon(label: str) -> str:
    key = label.lower()
    for k, v in _TAB_ICONS.items():
        if k in key:
            return v
    return _TAB_ICONS["default"]


class Tab:
    """Conteneur d'un onglet standard."""
    def __init__(self, label: str):
        self.label = label
        self._blocks: list[Block] = []

    @property
    def needs_plotly(self) -> bool:
        return any(b.needs_plotly for b in self._blocks)

    @property
    def needs_marked(self) -> bool:
        return any(b.needs_marked for b in self._blocks)

    def add(self, block: Block) -> "Tab":
        self._blocks.append(block)
        return self

    @property
    def children(self) -> list:
        return list(self._blocks)

    def render_content(self, store=None) -> str:
        inner = "\n".join(b.render(store=store) for b in self._blocks)
        return f'<div class="rb-body">{inner}</div>'


class TabView(Block):
    """Barre d'onglets — accepte Tab, GraphBuilderV2, ou tout objet avec render_content()."""
    needs_plotly  = True
    is_container  = True

    def __init__(self, tabs: list):
        self._tabs = tabs
        self._id   = f"tv_{id(self)}"

    @property
    def children(self) -> list:
        return list(self._tabs)

    @property
    def needs_marked(self) -> bool:
        return any(getattr(t, "needs_marked", False) for t in self._tabs)

    def render(self, store=None) -> str:
        vid = self._id
        btns = []
        for i, tab in enumerate(self._tabs):
            label  = getattr(tab, "label", None) or getattr(tab, "title", f"Tab {i+1}")
            icon   = _tab_icon(label)
            active = "active" if i == 0 else ""
            btns.append(
                f'<button class="rb-tab-btn {active}" id="{vid}_btn_{i}" '
                f'onclick="{vid}_show({i})">{icon}'
                f'<span class="tab-initial">{_h.escape(label[0])}</span>{_h.escape(label[1:])}</button>'
            )
        panels = []
        for i, tab in enumerate(self._tabs):
            active    = "active" if i == 0 else ""
            extra_cls = getattr(tab, "panel_css_class", "")
            content   = tab.render_content(store=store)
            panels.append(
                f'<div class="rb-tab-panel {extra_cls} {active}" id="{vid}_panel_{i}">{content}</div>'
            )

        glow_id = f"{vid}_glow"
        sep_id  = f"{vid}_sep"
        switch_js = f"""<script>
(function(){{
  var GLOW_W = 340;
  function {vid}_moveGlow(btn) {{
    var glow = document.getElementById("{glow_id}");
    var sep  = document.getElementById("{sep_id}");
    if (!glow || !sep) return;
    var sepRect = sep.getBoundingClientRect();
    var btnRect = btn.getBoundingClientRect();
    var center  = btnRect.left - sepRect.left + btnRect.width / 2;
    glow.style.left = (center - GLOW_W / 2) + "px";
  }}
  window.{vid}_show = function(idx) {{
    var n = {len(self._tabs)};
    for (var i = 0; i < n; i++) {{
      document.getElementById("{vid}_panel_"+i).classList.toggle("active", i===idx);
      var btn = document.getElementById("{vid}_btn_"+i);
      btn.classList.toggle("active", i===idx);
    }}
    {vid}_moveGlow(document.getElementById("{vid}_btn_"+idx));
    requestAnimationFrame(function() {{
      window.dispatchEvent(new Event('resize'));
      var panel = document.getElementById("{vid}_panel_"+idx);
      panel.querySelectorAll("[id]").forEach(function(el){{if(el._fullLayout)Plotly.Plots.resize(el);}});
    }});
  }};
  /* init glow on first active tab */
  window.addEventListener("load", function() {{
    var btn = document.getElementById("{vid}_btn_0");
    if (btn) {vid}_moveGlow(btn);
  }});
  window.addEventListener("resize", function() {{
    var active = document.querySelector("#{vid}_btn_0.active") ||
                 Array.from(document.querySelectorAll('[id^="{vid}_btn_"]')).find(function(b){{return b.classList.contains("active");}});
    if (active) {vid}_moveGlow(active);
  }});
}})();
</script>"""
        separator = (f'<div class="rb-nav-separator" id="{sep_id}">'
                     f'<div class="rb-sep-glow" id="{glow_id}"></div></div>')
        return (separator
                + '<div class="rb-tabbar">' + "".join(btns) + '</div>\n'
                + "\n".join(panels) + switch_js)


# ─────────────────────────────────────────────────────────────────────────────
# SLIDE GRID SYSTEM
# ─────────────────────────────────────────────────────────────────────────────

class SlideCell:
    """
    Cellule d'une grille de slide.
    Accès via slide[row, col] — ne pas instancier directement.
    """
    def __init__(self, row: int, col: int):
        self.row    = row
        self.col    = col
        self._items: list[tuple[Block, int, int]] = []  # (block, rowspan, colspan)

    def add(self, block: Block, rowspan: int = 1, colspan: int = 1) -> "SlideCell":
        self._items.append((block, rowspan, colspan))
        return self

    @property
    def needs_plotly(self) -> bool:
        return any(b.needs_plotly for b, _, __ in self._items)

    @property
    def needs_marked(self) -> bool:
        return any(b.needs_marked for b, _, __ in self._items)

    def render(self, store=None) -> str:
        return "\n".join(b.render(store=store) for b, _, __ in self._items)


# ─────────────────────────────────────────────────────────────────────────────
# SLIDE
# ─────────────────────────────────────────────────────────────────────────────

class Slide:
    """
    Conteneur d'une slide.

    Mode libre (sans grille) :
        s = Slide("Titre")
        s.add(KPIRow(...))
        s.add(PlotlyChart(...))

    Mode grille avec indexation matricielle :
        s = Slide("Titre", nrows=2, ncols=2)
        s[0, 0].add(PlotlyChart(...))              # cellule simple
        s[0, 1].add(Text(...), rowspan=2)           # span 2 lignes
        s[1, 0].add(KPIRow(...))

    Paramètres
    ----------
    title        : titre affiché dans la barre de la slide
    nrows        : nombre de lignes  (défaut 1 = mode libre)
    ncols        : nombre de colonnes (défaut 1 = mode libre)
    gap          : espace entre cellules en px (défaut 12)
    row_heights  : fractions CSS ex. ["2fr","1fr"]  — len = nrows
    col_widths   : fractions CSS ex. ["1.5fr","1fr"] — len = ncols
    """
    def __init__(self, title: str,
                 nrows: int = 1, ncols: int = 1,
                 gap: int = 12,
                 row_heights: list[str] | None = None,
                 col_widths:  list[str] | None = None):
        self.title   = title
        self.nrows   = nrows
        self.ncols   = ncols
        self.gap     = gap
        self._rh     = row_heights or ["1fr"] * nrows
        self._cw     = col_widths  or ["1fr"] * ncols
        self._cells: dict[tuple[int, int], SlideCell] = {}
        self._free:  list[Block] = []

    # ── Accès cellule ───────────────────────────────────────────────────
    def __getitem__(self, key: tuple[int, int]) -> SlideCell:
        if not isinstance(key, tuple) or len(key) != 2:
            raise KeyError("Utilisez slide[row, col]")
        r, c = key
        if not (0 <= r < self.nrows and 0 <= c < self.ncols):
            raise IndexError(
                f"Cellule ({r},{c}) hors grille {self.nrows}x{self.ncols}"
            )
        if key not in self._cells:
            self._cells[key] = SlideCell(r, c)
        return self._cells[key]

    # ── Mode libre ──────────────────────────────────────────────────────
    def add(self, block: Block) -> "Slide":
        self._free.append(block)
        return self

    @property
    def children(self) -> list:
        cell_blocks = [b for cell in self._cells.values() for b, _, __ in cell._items]
        return list(self._free) + cell_blocks

    # ── Propriétés ──────────────────────────────────────────────────────
    @property
    def needs_plotly(self) -> bool:
        return (any(cell.needs_plotly for cell in self._cells.values())
                or any(b.needs_plotly for b in self._free))

    @property
    def needs_marked(self) -> bool:
        return (any(cell.needs_marked for cell in self._cells.values())
                or any(b.needs_marked for b in self._free))

    def _is_grid_mode(self) -> bool:
        return self.nrows > 1 or self.ncols > 1 or bool(self._cells)

    # ── Render ──────────────────────────────────────────────────────────
    def render_content(self, store=None) -> str:
        if self._is_grid_mode():
            return self._render_grid(store)
        inner = "\n".join(b.render(store=store) for b in self._free)
        return f'<div class="rb-body">{inner}</div>'

    def _render_grid(self, store=None) -> str:
        rows_css = " ".join(self._rh)
        cols_css = " ".join(self._cw)

        # Calculer les zones occupées (pour le span)
        occupied: dict[tuple[int,int], tuple[int,int]] = {}  # pos -> (rs, cs)
        for (r, c), cell in self._cells.items():
            rs = cs = 1
            if cell._items:
                _, rs, cs = cell._items[0]
            for dr in range(rs):
                for dc in range(cs):
                    occupied[(r+dr, c+dc)] = (rs, cs)

        cells_html = []

        # Cellules définies
        for (r, c), cell in self._cells.items():
            rs = cs = 1
            if cell._items:
                _, rs, cs = cell._items[0]
            inner = cell.render(store=store)
            cells_html.append(
                f'<div class="sv-cell" '
                f'style="grid-row:{r+1}/{r+1+rs};grid-column:{c+1}/{c+1+cs};">'
                f'<div class="sv-cell-inner">{inner}</div>'
                f'</div>'
            )

        # Cellules vides
        for r in range(self.nrows):
            for c in range(self.ncols):
                if (r, c) not in occupied:
                    cells_html.append(
                        f'<div class="sv-cell sv-cell-empty" '
                        f'style="grid-row:{r+1}/{r+2};grid-column:{c+1}/{c+2};">'
                        f'</div>'
                    )

        return (
            f'<div class="sv-grid" '
            f'style="grid-template-rows:{rows_css};'
            f'grid-template-columns:{cols_css};gap:{self.gap}px;">'
            + "\n".join(cells_html)
            + "</div>"
        )


# ─────────────────────────────────────────────────────────────────────────────
# SLIDES SPÉCIAUX
# ─────────────────────────────────────────────────────────────────────────────

class TitleSlide:
    """
    Page de titre pleine page, auto-générée depuis les métadonnées du report_builder.
    Placée en première position dans SlideView, elle reçoit les infos via
    _inject_meta() avant le render.
    """
    title = "Titre"
    _meta: dict = {}

    def _inject_meta(self, meta: dict) -> None:
        self._meta = meta

    @property
    def needs_plotly(self) -> bool: return False

    @property
    def needs_marked(self) -> bool: return False

    def render_content(self, store=None) -> str:
        m      = self._meta
        title  = _h.escape(m.get("title",    "Rapport"))
        sub    = _h.escape(m.get("subtitle", ""))
        author = _h.escape(m.get("author",   ""))
        date   = _h.escape(m.get("date",     ""))
        sub_h  = f'<div class="sv-title-sub">{sub}</div>' if sub else ""
        return f"""<div class="sv-title-page">
  <div class="sv-title-deco"></div>
  <div class="sv-title-content">
    <div class="sv-title-eyebrow">Aledia &nbsp;·&nbsp; LUMIÈRE</div>
    <div class="sv-title-main">{title}</div>
    {sub_h}
    <div class="sv-title-divider"></div>
    <div class="sv-title-meta">{author} &nbsp;·&nbsp; {date}</div>
  </div>
</div>"""


class SectionSlide:
    """
    Séparateur de section — titre centré, fond navy, pleine page.

    Usage :
        SectionSlide("Résultats EQE")
        SectionSlide("Analyse", subtitle="DOE 2025-W22")
    """
    def __init__(self, title: str, subtitle: str = ""):
        self.title    = title
        self.subtitle = subtitle

    @property
    def needs_plotly(self) -> bool: return False

    @property
    def needs_marked(self) -> bool: return False

    def render_content(self, store=None) -> str:
        sub_h = (f'<div class="sv-section-sub">{_h.escape(self.subtitle)}</div>'
                 if self.subtitle else "")
        return f"""<div class="sv-section-page">
  <div class="sv-section-content">
    <div class="sv-section-label">Section</div>
    <div class="sv-section-title">{_h.escape(self.title)}</div>
    {sub_h}
  </div>
</div>"""


class SummarySlide:
    """
    Slide récapitulatif automatique — liste les titres de toutes les slides
    normales, groupées par sections. Injectée via _inject_titles() par SlideView.
    """
    title  = "Sommaire"
    _items: list[tuple[int, str, str]] = []

    def _inject_titles(self, items: list[tuple[int, str, str]]) -> None:
        self._items = items

    @property
    def needs_plotly(self) -> bool: return False

    @property
    def needs_marked(self) -> bool: return False

    def render_content(self, store=None) -> str:
        rows = []
        for num, kind, label in self._items:
            if kind == "section":
                rows.append(
                    f'<div class="sv-summary-section">{_h.escape(label)}</div>'
                )
            else:
                rows.append(
                    f'<div class="sv-summary-item">'
                    f'<span class="sv-summary-num">{num:02d}</span>'
                    f'<span class="sv-summary-label">{_h.escape(label)}</span>'
                    f'</div>'
                )
        return f"""<div class="sv-summary-page">
  <div class="sv-summary-heading">Sommaire</div>
  <div class="sv-summary-list">{"".join(rows)}</div>
</div>"""


# ─────────────────────────────────────────────────────────────────────────────
# SLIDEVIEW
# ─────────────────────────────────────────────────────────────────────────────

_SPECIAL_TYPES = (TitleSlide, SectionSlide, SummarySlide)


class SlideView(Block):
    """
    Moteur de présentation — remplace TabView en mode='slide'.

    Accepte : Slide, TitleSlide, SectionSlide, SummarySlide
    (Tab accepté par compatibilité — label lu via .label ou .title).

    report_meta est injecté automatiquement par ReportBuilder via set_report_meta().
    """
    needs_plotly = True
    is_container = True

    def __init__(self, slides: list, report_meta: dict | None = None):
        self._slides      = slides
        self._id          = f"sv_{id(self)}"
        self._report_meta = report_meta or {}

    def set_report_meta(self, meta: dict) -> None:
        """Injecté par ReportBuilder — élimine le isinstance(b, SlideView) côté assembleur."""
        self._report_meta = meta

    @property
    def children(self) -> list:
        return list(self._slides)

    # ── Injection métadonnées ────────────────────────────────────────────
    def _prepare(self) -> None:
        slide_num = 0
        items: list[tuple[int, str, str]] = []
        for s in self._slides:
            if isinstance(s, (TitleSlide, SummarySlide)):
                continue
            if isinstance(s, SectionSlide):
                items.append((0, "section", s.title))
                continue
            slide_num += 1
            label = getattr(s, "title", None) or getattr(s, "label", f"Slide {slide_num}")
            items.append((slide_num, "slide", label))

        for s in self._slides:
            if isinstance(s, TitleSlide):
                s._inject_meta(self._report_meta)
            if isinstance(s, SummarySlide):
                s._inject_titles(items)

    @property
    def needs_marked(self) -> bool:
        return any(getattr(s, "needs_marked", False) for s in self._slides)

    # ── Render ──────────────────────────────────────────────────────────
    def render(self, store=None) -> str:
        self._prepare()
        vid = self._id
        n   = len(self._slides)

        # Logo Aledia inline SVG (miniature topbar)
        from ._assets import _ALEDIA_LOGO_SVG as _LOGO
        # On réutilise le SVG existant en surchargeant juste la classe pour la topbar
        _logo_topbar = _LOGO.replace(
            'id="rb-header-logo"',
            'class="sv-topbar-logo"'
        ).replace('height:30px', 'height:36px')

        panels = []
        for i, slide in enumerate(self._slides):
            title     = getattr(slide, "title", None) or getattr(slide, "label", f"Slide {i+1}")
            is_spe    = isinstance(slide, _SPECIAL_TYPES)
            content   = slide.render_content(store=store)

            # Topbar avec logo (slides normales seulement)
            if is_spe:
                topbar_h = ""
            else:
                topbar_h = (
                    f'<div class="sv-slide-topbar">'
                    f'{_logo_topbar}'
                    f'<div class="sv-topbar-sep"></div>'
                    f'<span class="sv-topbar-label">LUMIÈRE · Aledia</span>'
                    f'<div class="sv-topbar-controls">'
                    f'  <button class="sv-ctrl-btn" id="{vid}_fsbtn_{i}" '
                    f'    onclick="{vid}_openFS()" title="Plein écran (F)">⛶ Plein écran</button>'
                    f'  <button class="sv-ctrl-btn" id="{vid}_zoombtn_{i}" '
                    f'    onclick="{vid}_toggleZoom()" title="Zoom molette actif/inactif (Z)">⊕ Focus</button>'
                    f'  <button class="sv-ctrl-btn" id="{vid}_fntbtn_{i}" '
                    f'    onclick="{vid}_toggleFont()" title="Taille des polices">Aₐ</button>'
                    f'</div>'
                    f'</div>'
                )

            titlebar_h = "" if is_spe else (
                f'<div class="sv-slide-titlebar">'
                f'<span class="sv-slide-title">{_h.escape(title)}</span>'
                f'</div>'
            )
            body_cls  = "sv-slide-body-special" if is_spe else ""

            dots = "".join(
                f'<span class="sv-dot {"active" if j == i else ""}" '
                f'onclick="{vid}_go({j})"></span>'
                for j in range(n)
            )

            # La zone zoomable englobe titlebar + body (hors topbar et footer)
            if is_spe:
                zoomable_h = f'<div class="sv-slide-body {body_cls}">{content}</div>'
            else:
                zoomable_h = (
                    f'<div class="sv-slide-zoomable" id="{vid}_zoomable_{i}">'
                    f'{titlebar_h}'
                    f'<div class="sv-slide-body {body_cls}">{content}</div>'
                    f'</div>'
                )
                titlebar_h = ""  # déjà inclus dans zoomable

            panels.append(f"""
<div class="sv-slide {"sv-slide-special" if is_spe else ""} {"active" if i == 0 else ""}"
     id="{vid}_slide_{i}">
  {topbar_h}
  {zoomable_h}
  <div class="sv-slide-footer">
    <span class="sv-footer-left sv-report_builder-meta"></span>
    <div class="sv-footer-nav">
      <button class="sv-nav-btn" onclick="{vid}_go({i}-1)"
        {"disabled" if i == 0 else ""}>&#8592;</button>
      <div class="sv-dots">{dots}</div>
      <button class="sv-nav-btn" onclick="{vid}_go({i}+1)"
        {"disabled" if i == n-1 else ""}>&#8594;</button>
    </div>
    <span class="sv-slide-index">Slide {i+1} / {n}</span>
  </div>
</div>""")

        # ── Panneau taille de police (flottant global) ────────────────────
        font_panel = f"""
<div class="sv-fontsize-panel" id="{vid}_font_panel">
  <span class="sv-fontsize-label">Taille des polices</span>
  <div class="sv-fontsize-row">
    <input type="range" class="sv-fontsize-slider" id="{vid}_font_slider"
      min="70" max="200" value="100" step="5"
      oninput="{vid}_applyFont(this.value)">
    <span class="sv-fontsize-val" id="{vid}_font_val">100%</span>
  </div>
  <button class="sv-fontsize-reset" onclick="{vid}_applyFont(100)">Réinitialiser</button>
</div>"""

        nav_js = f"""<script>
(function(){{
  /* ── État global ── */
  var _n={n}, _cur=0, _vid="{vid}";
  var _zoomActive = false;
  /* zoom : scale + translation pour garder le point sous le curseur fixe */
  var _zScale = 1, _zTx = 0, _zTy = 0;
  var _SCALE_MIN = 1, _SCALE_MAX = 8;

  /* ══════════════════════════════════
     UTILITAIRES
  ══════════════════════════════════ */
  function _getZoomable() {{
    return document.getElementById(_vid+"_zoomable_"+_cur);
  }}

  function _applyTransform(z) {{
    if (!z) return;
    z.style.transform = "translate("+_zTx+"px,"+_zTy+"px) scale("+_zScale+")";
  }}

  function _resetZoom() {{
    _zScale = 1; _zTx = 0; _zTy = 0;
    var z = _getZoomable();
    if (z) z.style.transform = "";
  }}

  function _resizePlotly(slideEl) {{
    if (!slideEl) return;
    requestAnimationFrame(function() {{
      slideEl.querySelectorAll("[id]").forEach(function(el) {{
        if (el._fullLayout) Plotly.Plots.resize(el);
      }});
    }});
  }}

  /* ══════════════════════════════════
     NAVIGATION
  ══════════════════════════════════ */
  window[_vid+"_go"] = function(idx) {{
    if (idx < 0 || idx >= _n) return;
    var prev = document.getElementById(_vid+"_slide_"+_cur);
    var next = document.getElementById(_vid+"_slide_"+idx);
    var dir  = idx > _cur ? 1 : -1;

    // Reset zoom sur la slide qu'on quitte
    _resetZoom();

    prev.classList.remove("active");
    prev.classList.add(dir > 0 ? "sv-exit-left" : "sv-exit-right");

    next.style.transform = dir > 0 ? "translateX(40px)" : "translateX(-40px)";
    next.style.opacity   = "0";
    next.style.pointerEvents = "none";
    void next.offsetWidth; // reflow

    _cur = idx;
    next.classList.add("active");
    next.style.transform = "";
    next.style.opacity   = "";
    next.style.pointerEvents = "";

    setTimeout(function() {{
      prev.classList.remove("sv-exit-left","sv-exit-right");
    }}, 380);

    // Sync dots
    document.querySelectorAll("#"+_vid+" .sv-dots .sv-dot").forEach(function(d, di) {{
      d.classList.toggle("active", di % _n === idx);
    }});

    _resizePlotly(next);
  }};

  /* ── Clavier ── */
  document.addEventListener("keydown", function(e) {{
    var tag = (e.target.tagName||"").toLowerCase();
    if (tag === "input" || tag === "select" || tag === "textarea") return;
    if (e.key === "Escape")      {{ if (_zoomActive) _resetZoom(); }}
    if (e.key === "ArrowRight" || e.key === "ArrowDown") window[_vid+"_go"](_cur+1);
    if (e.key === "ArrowLeft"  || e.key === "ArrowUp")   window[_vid+"_go"](_cur-1);
    if (e.key === "f" || e.key === "F") {vid}_openFS();
    if (e.key === "z" || e.key === "Z") {vid}_toggleZoom();
    if (e.key === "0") _resetZoom();
  }});

  /* ── Métadonnées footer ── */
  var _metaSrc = document.querySelector(".sv-report_builder-meta-src");
  if (_metaSrc) document.querySelectorAll(".sv-report_builder-meta")
    .forEach(function(el) {{ el.textContent = _metaSrc.textContent; }});

  /* ══════════════════════════════════
     ZOOM MOLETTE
     — scale centré sur le curseur,
       clampe translation pour ne pas
       sortir du conteneur
  ══════════════════════════════════ */
  window[_vid+"_toggleZoom"] = function() {{
    _zoomActive = !_zoomActive;
    document.querySelectorAll("[id^='{vid}_zoombtn_']").forEach(function(b) {{
      b.classList.toggle("active", _zoomActive);
      b.title = _zoomActive ? "Zoom actif — molette pour zoomer, 0 pour réinitialiser (Z)" : "Zoom molette actif/inactif (Z)";
    }});
    var z = _getZoomable();
    if (z) z.classList.toggle("zoom-active", _zoomActive);
    if (!_zoomActive) _resetZoom();
  }};

  /* Écouteur molette sur le wrapper entier */
  var _wrapper = document.getElementById(_vid);
  if (_wrapper) {{
    _wrapper.addEventListener("wheel", function(e) {{
      if (!_zoomActive) return;
      var z = _getZoomable();
      if (!z) return;
      e.preventDefault();

      /* Facteur de zoom par cran */
      var delta  = e.deltaY < 0 ? 1.12 : 1/1.12;
      var newScale = Math.max(_SCALE_MIN, Math.min(_SCALE_MAX, _zScale * delta));
      if (newScale === _zScale) return;

      /* Coordonnées du curseur relatives au zoomable (avant transform) */
      var rect = z.getBoundingClientRect();
      /* Point curseur dans l'espace de l'élément transformé */
      var cx = (e.clientX - rect.left - _zTx) / _zScale;
      var cy = (e.clientY - rect.top  - _zTy) / _zScale;

      /* Nouvelle translation pour que cx,cy reste sous le curseur */
      _zTx = e.clientX - rect.left - cx * newScale;
      _zTy = e.clientY - rect.top  - cy * newScale;

      /* Clamp : on ne peut pas aller au-delà du bord haut-gauche
         ni faire apparaître du vide à droite/bas */
      var zW = z.offsetWidth  * newScale;
      var zH = z.offsetHeight * newScale;
      _zTx = Math.min(0, Math.max(z.offsetWidth  - zW, _zTx));
      _zTy = Math.min(0, Math.max(z.offsetHeight - zH, _zTy));

      _zScale = newScale;
      _applyTransform(z);
    }}, {{ passive: false }});
  }}

  /* ══════════════════════════════════
     TAILLE DE POLICE
     — CSS custom property --sv-fs-scale
       sur chaque slide ; les éléments
       qui déclarent font-size en rem
       ou utilisent var(--sv-fs-scale)
       suivent automatiquement.
       Pour les px fixes on injecte
       une règle <style> dynamique.
  ══════════════════════════════════ */
  var _fsStyleEl = null;

  window[_vid+"_toggleFont"] = function() {{
    var p = document.getElementById(_vid+"_font_panel");
    p.classList.toggle("open");
  }};

  window[_vid+"_applyFont"] = function(pct) {{
    pct = Math.max(70, Math.min(200, parseInt(pct)));
    var slider = document.getElementById(_vid+"_font_slider");
    var val    = document.getElementById(_vid+"_font_val");
    if (slider) slider.value = pct;
    if (val)    val.textContent = pct + "%";

    var ratio = pct / 100;

    /* Injection d'une règle CSS dynamique qui surcharge les tailles fixes
       via le scale sur les wrappers zoomables */
    if (!_fsStyleEl) {{
      _fsStyleEl = document.createElement("style");
      document.head.appendChild(_fsStyleEl);
    }}
    /* On utilise un zoom CSS (non-standard mais universel) sur la zone texte.
       transform:scale déplace le rendu visuellement mais garde la géo intacte.
       zoom est plus adapté ici car il reflow le contenu. */
    _fsStyleEl.textContent =
      "#"+_vid+" .sv-slide-zoomable .rb-text," +
      "#"+_vid+" .sv-slide-zoomable .sv-slide-title," +
      "#"+_vid+" .sv-slide-zoomable .rb-kpi-value," +
      "#"+_vid+" .sv-slide-zoomable .rb-kpi-label," +
      "#"+_vid+" .sv-slide-zoomable .rb-kpi-unit," +
      "#"+_vid+" .sv-slide-zoomable .rb-section h2," +
      "#"+_vid+" .sv-slide-zoomable .rb-section-sub," +
      "#"+_vid+" .sv-slide-zoomable .sv-cell-inner," +
      "#"+_vid+" .sv-slide-zoomable .led-block-title {{" +
      "  zoom: "+ratio+"; }}";

    /* Resize Plotly sur la slide courante */
    _resizePlotly(document.getElementById(_vid+"_slide_"+_cur));
  }};

  /* ══════════════════════════════════
     PLEIN ÉCRAN (Fullscreen API)
  ══════════════════════════════════ */
  window[_vid+"_openFS"] = function() {{
    var wrapper = document.getElementById(_vid);
    if (!wrapper) return;
    if (document.fullscreenElement) {{
      document.exitFullscreen && document.exitFullscreen();
    }} else {{
      var req = wrapper.requestFullscreen || wrapper.webkitRequestFullscreen
                || wrapper.mozRequestFullScreen || wrapper.msRequestFullscreen;
      req && req.call(wrapper);
    }}
  }};

  document.addEventListener("fullscreenchange", function() {{
    var isFS = !!document.fullscreenElement;
    document.querySelectorAll("[id^='{vid}_fsbtn_']").forEach(function(b) {{
      b.classList.toggle("active", isFS);
      b.innerHTML = isFS ? "⛶ Quitter" : "⛶ Plein écran";
    }});
    setTimeout(function() {{
      _resizePlotly(document.getElementById(_vid+"_slide_"+_cur));
    }}, 300);
  }});

}})();
</script>"""

        return (
            f'<div class="sv-wrapper" id="{vid}">'
            + "\n".join(panels)
            + "</div>"
            + font_panel
            + nav_js
        )