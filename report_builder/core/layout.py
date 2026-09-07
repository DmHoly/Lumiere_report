"""
Core.layout — Blocs de mise en page pour le mode page
======================================================

Trois primitives complémentaires :

  Row   — ligne horizontale à N colonnes, largeurs libres
  Col   — colonne isolée (utilisée par Row, ou standalone)
  Grid  — grille 2-D libre avec rowspan/colspan, accès matriciel grid[r, c]

Usage typique
-------------
from .layout import Row, Grid

# ── Ligne 3 colonnes inégales ──────────────────────────────────────────
row = Row(col_widths=["1.5fr", "1fr", "1fr"], gap=12)
row[0].add(ScatterLED(...))
row[1].add(WaferMaps(...))
row[2].add(PLSpectraBlock(...))
tab.add(row)

# ── Grille 2×2 ──────────────────────────────────────────────────────────
g = Grid(nrows=2, ncols=3, col_widths=["2fr", "1fr", "1fr"], gap=10)
g[0, 0].add(ScatterLED(...), rowspan=2)   # occupe 2 lignes
g[0, 1].add(KPIRow(...))
g[0, 2].add(PlotlyChart(...))
g[1, 1].add(Text(...))
g[1, 2].add(DataTable(...))
tab.add(g)

Notes
-----
- Row et Grid sont des Block → utilisables partout où un Block est attendu
  (Tab.add, Slide.add, ReportBuilder.add…)
- Les cellules vides dans Grid restent transparentes (pas de fond visible)
- Chaque bloc enfant conserve son propre style (card, padding, etc.)
- Le contenu d'une cellule est scrollable si overflow vertical
"""
from __future__ import annotations
from ._helpers import Block


# ─────────────────────────────────────────────────────────────────────────────
# Col — colonne simple (utilisée par Row)
# ─────────────────────────────────────────────────────────────────────────────

class Col:
    """
    Conteneur vertical d'une colonne dans un Row.
    Ne s'instancie pas directement — accès via row[i].
    """
    def __init__(self):
        self._blocks: list[Block] = []

    def add(self, block: Block) -> "Col":
        self._blocks.append(block)
        return self

    @property
    def needs_plotly(self) -> bool:
        return any(b.needs_plotly for b in self._blocks)

    @property
    def needs_marked(self) -> bool:
        return any(b.needs_marked for b in self._blocks)

    def render(self, store=None) -> str:
        inner = "\n".join(b.render(store=store) for b in self._blocks)
        return f'<div class="pg-col">{inner}</div>'


# ─────────────────────────────────────────────────────────────────────────────
# Row — ligne horizontale à N colonnes
# ─────────────────────────────────────────────────────────────────────────────

class Row(Block):
    """
    Ligne horizontale à N colonnes, largeurs libres.

    Paramètres
    ----------
    col_widths : list[str]
        Fractions CSS pour chaque colonne, ex. ["2fr", "1fr", "1fr"].
        La longueur détermine le nombre de colonnes.
        Défaut : None → 1 colonne (équivalent à un bloc direct).
    ncols : int
        Alternative à col_widths si on veut N colonnes égales.
        Ignoré si col_widths est fourni.
    gap : int
        Espace entre colonnes en px (défaut 12).
    align : str
        Alignement vertical des colonnes CSS align-items : "start" | "stretch" (défaut).

    Accès
    -----
    row[i]  → Col  (0-indexed)
    """
    needs_plotly = False  # recalculé dynamiquement

    def __init__(self,
                 col_widths: list[str] | None = None,
                 ncols: int = 2,
                 gap: int = 12,
                 align: str = "stretch"):
        if col_widths:
            self._cw = col_widths
        else:
            self._cw = ["1fr"] * ncols
        self._cols  = [Col() for _ in self._cw]
        self._gap   = gap
        self._align = align

    # ── Accès colonne ────────────────────────────────────────────────────
    def __getitem__(self, idx: int) -> Col:
        if not (0 <= idx < len(self._cols)):
            raise IndexError(
                f"Colonne {idx} hors limites (Row a {len(self._cols)} colonnes)"
            )
        return self._cols[idx]

    # ── Shorthand : ajouter dans la prochaine colonne libre ─────────────
    def push(self, block: Block) -> "Row":
        """Ajoute block dans la prochaine colonne non encore utilisée."""
        for col in self._cols:
            if not col._blocks:
                col.add(block)
                return self
        raise ValueError("Toutes les colonnes sont déjà occupées — utilisez row[i].add()")

    # ── Propriétés Block ─────────────────────────────────────────────────
    @property
    def needs_plotly(self) -> bool:                       # type: ignore[override]
        return any(c.needs_plotly for c in self._cols)

    @property
    def needs_marked(self) -> bool:
        return any(c.needs_marked for c in self._cols)

    # ── Render ───────────────────────────────────────────────────────────
    def render(self, store=None) -> str:
        cols_css = " ".join(self._cw)
        cols_html = "\n".join(c.render(store=store) for c in self._cols)
        return (
            f'<div class="pg-row" '
            f'style="grid-template-columns:{cols_css};'
            f'gap:{self._gap}px;align-items:{self._align};">'
            + cols_html
            + "</div>"
        )


# ─────────────────────────────────────────────────────────────────────────────
# GridCell — cellule d'une Grid
# ─────────────────────────────────────────────────────────────────────────────

class GridCell:
    """
    Cellule d'une Grid.  Accès via grid[row, col].
    Le rowspan/colspan se définit au moment du add().
    """
    def __init__(self, row: int, col: int):
        self.row = row
        self.col = col
        self._items: list[tuple[Block, int, int]] = []   # (block, rowspan, colspan)

    def add(self, block: Block, rowspan: int = 1, colspan: int = 1) -> "GridCell":
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

    def _span(self) -> tuple[int, int]:
        """Retourne (rowspan, colspan) du premier item, ou (1,1)."""
        if self._items:
            _, rs, cs = self._items[0]
            return rs, cs
        return 1, 1


# ─────────────────────────────────────────────────────────────────────────────
# Grid — grille 2-D libre
# ─────────────────────────────────────────────────────────────────────────────

class Grid(Block):
    """
    Grille 2-D libre avec rowspan/colspan, accès matriciel.

    Paramètres
    ----------
    nrows, ncols : int
        Dimensions de la grille.
    gap : int
        Espace entre cellules en px (défaut 12).
    row_heights : list[str]
        Fractions CSS pour chaque ligne, ex. ["2fr", "1fr"].
        Défaut : None → toutes les lignes égales ("1fr").
    col_widths : list[str]
        Fractions CSS pour chaque colonne, ex. ["1.5fr", "1fr", "1fr"].
        Défaut : None → toutes les colonnes égales ("1fr").
    min_row_height : str
        Hauteur minimale d'une ligne, ex. "200px" (défaut "180px").
        Évite les lignes trop comprimées si le contenu est variable.

    Accès
    -----
    grid[row, col]           → GridCell
    grid[row, col].add(bloc)                         # cellule simple
    grid[row, col].add(bloc, rowspan=2, colspan=1)   # span

    Comportement cellules vides
    ---------------------------
    Les positions non définies restent vides (transparent, pas de fond).
    """
    needs_plotly = False   # recalculé dynamiquement

    def __init__(self,
                 nrows: int = 1,
                 ncols: int = 2,
                 gap: int = 12,
                 row_heights: list[str] | None = None,
                 col_widths:  list[str] | None = None,
                 min_row_height: str = "180px"):
        self.nrows = nrows
        self.ncols = ncols
        self._gap  = gap
        self._rh   = row_heights or ["1fr"] * nrows
        self._cw   = col_widths  or ["1fr"] * ncols
        self._min_rh = min_row_height
        self._cells: dict[tuple[int, int], GridCell] = {}

    # ── Accès cellule ────────────────────────────────────────────────────
    def __getitem__(self, key: tuple[int, int]) -> GridCell:
        if not isinstance(key, tuple) or len(key) != 2:
            raise KeyError("Utilisez grid[row, col]")
        r, c = key
        if not (0 <= r < self.nrows and 0 <= c < self.ncols):
            raise IndexError(
                f"Cellule ({r},{c}) hors grille {self.nrows}×{self.ncols}"
            )
        if key not in self._cells:
            self._cells[key] = GridCell(r, c)
        return self._cells[key]

    # ── Propriétés Block ─────────────────────────────────────────────────
    @property
    def needs_plotly(self) -> bool:                       # type: ignore[override]
        return any(cell.needs_plotly for cell in self._cells.values())

    @property
    def needs_marked(self) -> bool:
        return any(cell.needs_marked for cell in self._cells.values())

    # ── Render ───────────────────────────────────────────────────────────
    def render(self, store=None) -> str:
        rows_css = " ".join(
            f"minmax({self._min_rh},{h})" for h in self._rh
        )
        cols_css = " ".join(self._cw)

        # Calcul des zones occupées (pour les spans)
        occupied: dict[tuple[int, int], bool] = {}
        for (r, c), cell in self._cells.items():
            rs, cs = cell._span()
            for dr in range(rs):
                for dc in range(cs):
                    occupied[(r + dr, c + dc)] = True

        cells_html: list[str] = []

        # Cellules définies
        for (r, c), cell in self._cells.items():
            rs, cs = cell._span()
            inner  = cell.render(store=store)
            cells_html.append(
                f'<div class="pg-grid-cell" '
                f'style="grid-row:{r+1}/{r+1+rs};grid-column:{c+1}/{c+1+cs};">'
                f'{inner}'
                f'</div>'
            )

        # Positions vides — div transparent (préserve la grille)
        for r in range(self.nrows):
            for c in range(self.ncols):
                if (r, c) not in occupied:
                    cells_html.append(
                        f'<div class="pg-grid-cell pg-grid-cell-empty" '
                        f'style="grid-row:{r+1}/{r+2};grid-column:{c+1}/{c+2};">'
                        f'</div>'
                    )

        return (
            f'<div class="pg-grid" '
            f'style="grid-template-rows:{rows_css};'
            f'grid-template-columns:{cols_css};gap:{self._gap}px;">'
            + "\n".join(cells_html)
            + "</div>"
        )