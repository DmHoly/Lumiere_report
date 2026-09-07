"""
lot_info_card.py — Bloc LUMIÈRE : carte d'informations d'un lot en cours
=========================================================================

Usage
-----
    from ..lot_info_card import LotInfoCard

    card = LotInfoCard(
        lot_id       = "LOT-2024-05-31",
        produit      = "LED-Blue-450nm",
        process      = "EPI-012 / MOCVD",
        outil        = "Réacteur 04",
        date_debut   = "2024-05-31  08:15",
        etape        = "PL Mapping",
        wafers       = "25 / 25",
        statut       = "En cours",           # "En cours" | "Terminé" | "En attente"
        responsable  = "A. Martin",
        # Champs additionnels libres (clé → valeur) — autant que voulu
        extra        = {
            "Priorité"  : "Haute",
            "Recette"   : "R-GaN-450-V12",
        },
        # Goto : label de l'onglet TabView cible (index 0-based) et texte du bouton
        goto_tab_index = 1,
        goto_label     = "Voir le détail du lot",
        # Identifiant du TabView parent — à renseigner si plusieurs TabView coexistent
        tabview_id     = None,   # ex: "tv_140234567890"  (valeur de TabView._id)
    )

    tab.add(card)

Note sur goto_tab_index / tabview_id
--------------------------------------
Le bouton appelle la fonction JS ``<tabview_id>_show(<goto_tab_index>)``.
Si ``tabview_id`` vaut None, le bloc cherche automatiquement le premier
TabView présent dans la page (heuristique : premier élément dont l'id
commence par ``tv_``).  Dans la grande majorité des cas, c'est suffisant.
"""

from __future__ import annotations
import html as _h
from ..._helpers import Block


# ─────────────────────────────────────────────────────────────────────────────
#  Helpers internes
# ─────────────────────────────────────────────────────────────────────────────

_STATUS_CFG = {
    # statut      : (couleur fond badge, couleur texte, couleur dot, libellé)
    "en cours"    : ("#e8f5e9", "#2e7d32", "#43a047", "En cours"),
    "terminé"     : ("#e3f2fd", "#1565c0", "#1e88e5", "Terminé"),
    "en attente"  : ("#fff8e1", "#f57f17", "#ffa000", "En attente"),
    "bloqué"      : ("#fce4ec", "#b71c1c", "#e53935", "Bloqué"),
    "annulé"      : ("#f3e5f5", "#6a1b9a", "#8e24aa", "Annulé"),
}

def _status_html(statut: str) -> str:
    """Renvoie le HTML d'un badge statut coloré + dot animé si 'en cours'."""
    key = statut.strip().lower()
    bg, fg, dot, label = _STATUS_CFG.get(key, ("#f5f5f5", "#555", "#999", statut))
    pulse = (
        '<span style="display:inline-block;width:8px;height:8px;border-radius:50%;'
        f'background:{dot};margin-right:5px;animation:licPulse 1.6s ease-in-out infinite;"></span>'
        if key == "en cours" else
        f'<span style="display:inline-block;width:8px;height:8px;border-radius:50%;background:{dot};margin-right:5px;"></span>'
    )
    return (
        f'<span style="display:inline-flex;align-items:center;'
        f'padding:2px 9px 2px 6px;border-radius:20px;'
        f'background:{bg};color:{fg};font-weight:600;font-size:11px;">'
        f'{pulse}{_h.escape(label)}</span>'
    )

def _row_html(label: str, value: str, statut_raw: str | None = None, is_last: bool = False) -> str:
    """Génère une ligne label / valeur avec séparateur optionnel."""
    border = "" if is_last else "border-bottom:0.5px solid rgba(10,36,99,.07);"
    val_html = _status_html(value) if statut_raw is not None else (
        f'<span style="font-family:\'IBM Plex Mono\',monospace;font-size:12px;'
        f'color:#0d1b3e;font-weight:500;">{_h.escape(value)}</span>'
    )
    return f"""
      <div style="display:flex;align-items:center;justify-content:space-between;
                  padding:8px 0;{border}">
        <span style="font-family:'IBM Plex Mono',monospace;font-size:11px;
                     color:#8892aa;letter-spacing:.03em;">{_h.escape(label)}</span>
        {val_html}
      </div>"""


# ─────────────────────────────────────────────────────────────────────────────
#  LotInfoCard
# ─────────────────────────────────────────────────────────────────────────────

class LotInfoCard(Block):
    """
    Carte d'informations d'un lot en cours, fidèle au style LUMIÈRE.

    Paramètres obligatoires
    -----------------------
    lot_id, produit, process, outil, date_debut, etape, wafers, statut, responsable

    Paramètres optionnels
    ---------------------
    extra          : dict[str, str] de lignes supplémentaires (max ~3 recommandé)
    goto_tab_index : index (0-based) du tab cible dans le TabView parent
    goto_label     : texte du bouton CTA  (défaut : "Voir le détail du lot")
    tabview_id     : id JS du TabView parent ; None = auto-détection
    title          : titre de la carte  (défaut : "INFORMATIONS LOT EN COURS")
    """

    needs_plotly = False
    needs_marked = False

    def __init__(
        self,
        lot_id:          str,
        produit:         str,
        process:         str,
        outil:           str,
        date_debut:      str,
        etape:           str,
        wafers:          str,
        statut:          str       = "En cours",
        responsable:     str       = "",
        extra:           dict | None = None,
        goto_tab_index:  int       = 1,
        goto_label:      str       = "Voir le détail du lot",
        tabview_id:      str | None = None,
        title:           str       = "INFORMATIONS LOT EN COURS",
    ):
        self.lot_id         = lot_id
        self.produit        = produit
        self.process        = process
        self.outil          = outil
        self.date_debut     = date_debut
        self.etape          = etape
        self.wafers         = wafers
        self.statut         = statut
        self.responsable    = responsable
        self.extra          = extra or {}
        self.goto_tab_index = goto_tab_index
        self.goto_label     = goto_label
        self.tabview_id     = tabview_id
        self.title          = title
        self._id            = f"lic_{id(self)}"

    # ── Render ────────────────────────────────────────────────────────────────

    def render(self, store=None) -> str:
        sid = self._id

        # ── Statut badge (coin supérieur droit de la carte) ──────────────────
        status_key = self.statut.strip().lower()
        bg, fg, dot, label = _STATUS_CFG.get(
            status_key, ("#f5f5f5", "#555", "#999", self.statut)
        )
        badge_html = (
            f'<span style="display:inline-flex;align-items:center;'
            f'padding:3px 10px 3px 7px;border-radius:20px;'
            f'background:{bg};color:{fg};font-weight:600;font-size:11px;'
            f'white-space:nowrap;">'
            f'<span style="display:inline-block;width:7px;height:7px;border-radius:50%;'
            f'background:{dot};margin-right:5px;'
            f'{"animation:licPulse 1.6s ease-in-out infinite;" if status_key == "en cours" else ""}'
            f'"></span>{_h.escape(label)}</span>'
        )

        # ── Lignes de données ─────────────────────────────────────────────────
        fixed_rows = [
            ("Lot ID",        self.lot_id,      None),
            ("Produit",       self.produit,     None),
            ("Process",       self.process,     None),
            ("Outil",         self.outil,       None),
            ("Date de début", self.date_debut,  None),
            ("Étape",         self.etape,       None),
            ("Wafers",        self.wafers,      None),
            ("Statut",        self.statut,      self.statut),   # ← rendu coloré
            ("Responsable",   self.responsable, None),
        ]
        extra_rows = [(k, v, None) for k, v in self.extra.items()]
        all_rows   = fixed_rows + extra_rows

        rows_html = ""
        for i, (lbl, val, st) in enumerate(all_rows):
            rows_html += _row_html(lbl, val, st, is_last=(i == len(all_rows) - 1))

        # ── Goto JS ──────────────────────────────────────────────────────────
        if self.tabview_id:
            onclick = f"{self.tabview_id}_show({self.goto_tab_index})"
        else:
            # Auto-détection : cherche le premier TabView de la page
            onclick = (
                f"(function(){{"
                f"var btns=document.querySelectorAll('[id^=\"tv_\"][id$=\"_btn_0\"]');"
                f"if(btns.length){{var pfx=btns[0].id.replace('_btn_0','');"
                f"window[pfx+'_show']({self.goto_tab_index});}}"
                f"}})();"
            )

        arrow_svg = (
            '<svg viewBox="0 0 16 16" width="14" height="14" fill="currentColor" '
            'style="flex-shrink:0;">'
            '<path d="M3 8h8.586L8.293 4.707 9.707 3.293l5 5a1 1 0 010 1.414l-5 5-1.414-1.414'
            ' 3.293-3.293H3V8z"/></svg>'
        )

        pulse_keyframes = """
@keyframes licPulse {
  0%,100% { opacity:1; transform:scale(1); }
  50%      { opacity:.55; transform:scale(1.25); }
}"""

        return f"""
<!-- LotInfoCard {sid} -->
<style>{pulse_keyframes}</style>

<div id="{sid}_wrap" style="
  background:#ffffff;
  border:1px solid rgba(10,36,99,.12);
  border-radius:12px;
  box-shadow:0 2px 16px rgba(10,36,99,.08);
  overflow:hidden;
  max-width:480px;
  font-family:'DM Sans','IBM Plex Mono',sans-serif;
">

  <!-- ── Header ─────────────────────────────────────────────────── -->
  <div style="
    display:flex;align-items:center;justify-content:space-between;
    padding:14px 18px 12px;
    border-bottom:1px solid rgba(10,36,99,.09);
    background:linear-gradient(135deg,#f8f9fc 0%,#ffffff 100%);
  ">
    <span style="
      font-family:'IBM Plex Mono',monospace;
      font-size:11px;font-weight:600;
      letter-spacing:.12em;
      text-transform:uppercase;
      color:#0d1b3e;
    ">{_h.escape(self.title)}</span>
    {badge_html}
  </div>

  <!-- ── Lignes ─────────────────────────────────────────────────── -->
  <div style="padding:0 18px;">
    {rows_html}
  </div>

  <!-- ── Footer / CTA ───────────────────────────────────────────── -->
  <div style="padding:12px 18px 14px;">
    <button
      onclick="{_h.escape(onclick)}"
      style="
        display:flex;align-items:center;justify-content:center;gap:8px;
        width:100%;padding:9px 14px;
        border:1px solid rgba(10,36,99,.20);border-radius:8px;
        background:#ffffff;color:#0d1b3e;
        font-family:'IBM Plex Mono',monospace;
        font-size:12px;font-weight:600;letter-spacing:.04em;
        cursor:pointer;transition:all .18s;
      "
      onmouseover="this.style.background='#0d1b3e';this.style.color='#e8c97a';this.style.borderColor='#0d1b3e';"
      onmouseout="this.style.background='#ffffff';this.style.color='#0d1b3e';this.style.borderColor='rgba(10,36,99,.20)';"
    >
      {_h.escape(self.goto_label)} {arrow_svg}
    </button>
  </div>

</div>
"""