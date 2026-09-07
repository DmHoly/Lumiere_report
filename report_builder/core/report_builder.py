from __future__ import annotations
import html as _h
import textwrap
from ._assets import _PLOTLY_JS, _MARKED_JS, _CSS, _ALEDIA_LOGO_SVG
from ._helpers import Block
from .navigation import TabView, SlideView
from .blocks.data.data_store import DataStore

_MODES = ("page", "slide")


class ReportBuilder:
    """
    Assemble des blocs en un fichier HTML self-contained.

    ── Mode page (défaut) ───────────────────────────────────────────────────
        report_builder = ReportBuilder(title="LED Explorer Q1")
        report_builder.data.register("main", df)

        tab1 = Tab("Rapport")
        tab1.add(ScatterLED(...))
        report_builder.add(TabView([tab1, tab2]))
        report_builder.save("rapport.html")

    ── Mode slide ───────────────────────────────────────────────────────────
        report_builder = ReportBuilder(title="LED Explorer Q1",
                               subtitle="Run 2025-W22",
                               mode="slide")
        report_builder.data.register("main", df)

        # Slides spéciaux auto-générés
        report_builder.add(SlideView([
            TitleSlide(),                          # page de titre auto

            SectionSlide("Résultats EQE"),         # séparateur de section

            # Slide libre
            s1 := Slide("Introduction"),           # s1.add(...)

            # Slide en grille 2×2
            s2 := Slide("EQE Analysis", nrows=2, ncols=2,
                         col_widths=["1.5fr","1fr"]),
            # s2[0, 0].add(PlotlyChart(...), rowspan=2)
            # s2[0, 1].add(Text(...))
            # s2[1, 1].add(KPIRow(...))

            SummarySlide(),                        # sommaire auto
        ]))
        report_builder.save("rapport.html")
    """

    def __init__(self, title: str = "Rapport", subtitle: str = "",
                 author: str = "Aledia", date: str | None = None,
                 mode: str = "page",
                 data_store: DataStore | None = None):
        if mode not in _MODES:
            raise ValueError(f"mode doit être l'un de {_MODES}, reçu : {mode!r}")
        self.title    = title
        self.subtitle = subtitle
        self.author   = author
        self.date     = date
        self.mode     = mode
        self._blocks: list[Block] = []
        # Injection de dépendance — facilite les tests et la composition
        self.data = data_store if data_store is not None else DataStore()

    def add(self, block: Block) -> "ReportBuilder":
        self._blocks.append(block)
        return self

    def render(self) -> str:
        from datetime import date as _date
        dt = self.date or _date.today().strftime("%d %b %Y")

        # ── Injection des métadonnées (ex: titre report) dans les blocs qui en ont besoin
        meta = dict(title=self.title, subtitle=self.subtitle,
                    author=self.author, date=dt)
        for b in self._blocks:
            b.set_report_meta(meta)

        # ── Détection dépendances JS — traversée récursive via children() ─
        def _collect(items) -> tuple[bool, bool]:
            np_, nm_ = False, False
            for item in items:
                np_ = np_ or getattr(item, "needs_plotly", False)
                nm_ = nm_ or getattr(item, "needs_marked", False)
                ch = getattr(item, "children", None)
                if ch:
                    a, b2 = _collect(ch)
                    np_ = np_ or a
                    nm_ = nm_ or b2
            return np_, nm_

        need_plotly, need_marked = _collect(self._blocks)

        ext = ""
        if need_plotly: ext += f"\n  {_PLOTLY_JS}"
        if need_marked: ext += f"\n  {_MARKED_JS}"

        # ── Render des blocs ──────────────────────────────────────────────
        body_parts = []
        for b in self._blocks:
            if b.is_container:
                body_parts.append(b.render(store=self.data))
            else:
                body_parts.append(
                    f'<div class="rb-body">{b.render(store=self.data)}</div>'
                )

        if self.mode == "slide":
            return self._render_slide(dt, ext, body_parts)
        return self._render_page(dt, ext, body_parts)

    def to_config(self, report_name: str = "my_report", output_dir: str = "output") -> dict:
        """
        Reconstruit le dict de configuration compatible ReportBuilderRunner
        à partir des blocs ajoutés en Python.

        Usage :
            report_builder = ReportBuilder(title="LED Explorer", ...)
            report_builder.add(TabView([tab1, tab2]))
            config = report_builder.to_config(report_name="lot_QRO07")
            runner.generate(config)          # équivalent exact
            hash_str = runner.config_to_hash(config)  # partageable
        """
        from datetime import date as _date
        from .navigation import TabView, Tab

        pages = []

        for block in self._blocks:
            if isinstance(block, TabView):
                for tab in block._tabs:
                    page_blocks = []
                    for b in tab._blocks:
                        try:
                            page_blocks.append(b.to_dict())
                        except NotImplementedError:
                            pass
                        except Exception as exc:
                            print(f"⚠️  to_dict() échoué sur {b.__class__.__name__}: {exc}")
                    pages.append({"name": tab.label, "blocks": page_blocks})
            else:
                # Bloc libre hors TabView → page unique "__root__"
                try:
                    d = block.to_dict()
                    # Cherche si une page __root__ existe déjà
                    root = next((p for p in pages if p["name"] == "__root__"), None)
                    if root is None:
                        root = {"name": "__root__", "blocks": []}
                        pages.append(root)
                    root["blocks"].append(d)
                except NotImplementedError:
                    pass
                except Exception as exc:
                    print(f"⚠️  to_dict() échoué sur {block.__class__.__name__}: {exc}")

        return {
            "meta": {
                "report_name": report_name,
                "title": self.title,
                "subtitle": self.subtitle,
                "author": self.author,
                "output_dir": output_dir,
                "path": [],
                "wafers": [],
            },
            "config": {
                "pages": pages,
            }
        }

    def to_hash(self, report_name: str = "my_report", output_dir: str = "output",
                secret_key: str | None = None) -> str:
        """
        Raccourci : to_config() + config_to_hash() en une ligne.
        Nécessite ReportBuilderRunner pour le hashing — import local pour éviter la circularité.
        """
        from .report_builder_runner import ReportBuilderRunner
        config = self.to_config(report_name=report_name, output_dir=output_dir)
        runner = ReportBuilderRunner(secret_key=secret_key)
        return runner.config_to_hash(config)


    # ── mode='page' ───────────────────────────────────────────────────────
    def _render_page(self, dt: str, ext: str, body_parts: list[str]) -> str:
        sub_h  = (f' <span>— {_h.escape(self.subtitle)}</span>') if self.subtitle else ""
        meta_h = f"{_h.escape(self.author)} · {_h.escape(dt)}"
        return textwrap.dedent(f"""<!DOCTYPE html>
<html lang="fr">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>{_h.escape(self.title)}</title>{ext}
  {self.data.to_js_injection()}
  {_CSS}
</head>
<body>
  <header class="rb-header">
    <div class="rb-header-brand-block">
      {_ALEDIA_LOGO_SVG}
      <div class="rb-header-sep"></div>
      <div class="rb-header-lumiere">
        <span class="rb-header-lumiere-full"
              data-short="LUMIÈRE<br>Report Engine"
              data-full="LUMIÈRE<br><em>L</em>ED <em>U</em>nified <em>M</em>etrics, <em>I</em>nsights, <em>È</em>xploration &amp; <em>R</em>eporting <em>E</em>ngine">
        </span>
      </div>
      <div class="rb-header-sep"></div>
    </div>
    <span class="rb-header-title">{_h.escape(self.title)}{sub_h}</span>
    <button class="rb-header-info-btn" id="rb-info-btn" title="Contact &amp; support">&#9432;</button>
  </header>

  <div id="rb-info-overlay" style="display:none;position:fixed;inset:0;
    background:rgba(10,12,18,.85);z-index:99980;align-items:center;
    justify-content:center;backdrop-filter:blur(4px);">
    <div style="background:#0f1117;border:1px solid #2a3050;border-radius:10px;
      width:min(480px,90vw);overflow:hidden;
      box-shadow:0 0 50px rgba(10,36,99,.4);
      animation:eeLightIn .25s cubic-bezier(.34,1.56,.64,1);">
      <div style="background:#161920;padding:.65rem 1.2rem;display:flex;
        align-items:center;border-bottom:1px solid #1e2230;">
        <span style="font-family:'IBM Plex Mono',monospace;font-size:.68rem;
          color:#4A5580;letter-spacing:2px;text-transform:uppercase;">Questions &amp; Support</span>
        <button id="rb-info-close" style="margin-left:auto;background:none;
          border:none;color:#555;font-size:1.1rem;cursor:pointer;line-height:1;">✕</button>
      </div>
      <div style="padding:1.4rem 1.6rem;display:flex;flex-direction:column;gap:1rem;">
        <p style="font-family:'IBM Plex Mono',monospace;font-size:.72rem;
          color:#8892a8;line-height:1.7;margin:0;">
          Pour toute question relative à ce rapport, aux données ou à l'outil
          <strong style="color:#c8cdd8;">LUMIÈRE</strong>, contactez&nbsp;:
        </p>
        <div style="background:#161920;border:1px solid #1e2230;border-radius:8px;
          padding:.85rem 1.1rem;display:flex;flex-direction:column;gap:.25rem;">
          <span style="font-family:'IBM Plex Mono',monospace;font-size:.6rem;
            color:#D4AF37;letter-spacing:2px;text-transform:uppercase;">Pour les changements de layout / Data / Bug </span>
          <span style="font-family:'Syne',sans-serif;font-size:.95rem;font-weight:700;color:#fff;">Mehdi Daanoune</span>
          <a href="mailto:mehdi.daanoune@aledia.com" style="font-family:'IBM Plex Mono',monospace;
            font-size:.72rem;color:#3e92cc;text-decoration:none;">mehdi.daanoune@aledia.com</a>
        </div>
        <div style="background:#161920;border:1px solid #1e2230;border-radius:8px;
          padding:.85rem 1.1rem;display:flex;flex-direction:column;gap:.25rem;">
          <span style="font-family:'IBM Plex Mono',monospace;font-size:.6rem;
            color:#4A5580;letter-spacing:2px;text-transform:uppercase;">Support IT / Question relative à la generation automatique</span>
          <span style="font-family:'Syne',sans-serif;font-size:.95rem;font-weight:700;color:#fff;">Équipe IT R&amp;D</span>
          <a href="mailto:data_support@aledia.com" style="font-family:'IBM Plex Mono',monospace;
            font-size:.72rem;color:#3e92cc;text-decoration:none;">data_support@aledia.com</a>
        </div>
      </div>
    </div>
  </div>
  <script>
  (function(){{
    var btn=document.getElementById('rb-info-btn');
    var ov=document.getElementById('rb-info-overlay');
    var cl=document.getElementById('rb-info-close');
    function shut(){{ ov.style.display='none'; }}
    btn.addEventListener('click', function(){{ ov.style.display='flex'; }});
    cl.addEventListener('click', shut);
    ov.addEventListener('click', function(e){{ if(e.target===ov) shut(); }});
    document.addEventListener('keydown', function(e){{ if(e.key==='Escape') shut(); }});
  }})();
  </script>
{"".join(body_parts)}
</body>
</html>""")

    # ── mode='slide' ──────────────────────────────────────────────────────
    def _render_slide(self, dt: str, ext: str, body_parts: list[str]) -> str:
        meta_h = f"{_h.escape(self.author)} · {_h.escape(dt)}"
        return textwrap.dedent(f"""<!DOCTYPE html>
<html lang="fr">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>{_h.escape(self.title)}</title>{ext}
  {self.data.to_js_injection()}
  {_CSS}
</head>
<body class="rb-mode-slide">
  <span class="sv-report_builder-meta-src" style="display:none">{meta_h}</span>
{"".join(body_parts)}
</body>
</html>""")

    def save(self, path: str) -> None:
        html = self.render()
        with open(path, "w", encoding="utf-8") as f:
            f.write(html)
        print(f"✓  {path}  ({len(html)//1024} KB)")