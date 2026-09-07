from __future__ import annotations
from abc import ABC, abstractmethod
import numpy as np
import pandas as pd

_PLOTLY_CFG_JS = """{
  responsive:true, displaylogo:false,
  modeBarButtonsToRemove:["autoScale2d","toggleSpikelines","sendDataToCloud"],
}"""

_SHARED_LAYOUT_JS = """{
  paper_bgcolor:"rgba(0,0,0,0)", plot_bgcolor:"#F8F9FD",
  font:{family:"IBM Plex Mono, monospace", color:"#4A5580", size:11},
}"""

_GRID_STYLE_JS = """{
  gridcolor:"#E4E8F4", linecolor:"#E4E8F4", zerolinecolor:"#E4E8F4",
}"""


# ─────────────────────────────────────────────────────────────────────────────
# BASE BLOCK
# ─────────────────────────────────────────────────────────────────────────────
class Block(ABC):
    needs_plotly:    bool = False
    needs_marked:    bool = False
    # True → le bloc gère son propre wrapper externe (pas de <div class="rb-body"> ajouté)
    is_container:    bool = False
    # False → to_dict() lève NotImplementedError (bloc non-sérialisable)
    serializable:    bool = True
    # Classe CSS supplémentaire pour le panneau dans TabView (ex: "gb-panel")
    panel_css_class: str  = ""
    # True → bloc plein-écran (pas de rb-body wrapper, gb-panel remonté au niveau panel)
    needs_full_panel: bool = False

    @abstractmethod
    def render(self, store=None) -> str: ...

    def render_content(self, store=None) -> str:
        """
        Protocole Tab-item : tout ce qui peut être placé dans TabView doit
        implémenter render_content(). Par défaut délègue à render().
        Les conteneurs (Tab, GraphBuilderV2) surchargent cette méthode.
        """
        return self.render(store=store)

    def set_report_meta(self, meta: dict) -> None:
        """
        Appelé par ReportBuilder pour injecter les métadonnées (titre, auteur…).
        No-op par défaut — seul SlideView le surcharge.
        """

    @property
    def children(self) -> list:
        """
        Liste des blocs/items enfants directs, pour la traversée récursive
        des dépendances JS. Retourne [] par défaut (feuille).
        Les conteneurs (TabView, SlideView, Tab…) surchargent.
        """
        return []

    def to_dict(self) -> dict:
        """
        Sérialise le bloc en dict {type, params} compatible ReportBuilderRunner.
        Lève NotImplementedError si serializable=False.
        """
        if not self.serializable:
            raise NotImplementedError(
                f"{self.__class__.__name__}.to_dict() n'est pas supporté : "
                f"ce bloc contient des données non-sérialisables en JSON "
                f"(ex: figure Plotly Python). Utilisez un bloc avec clé store "
                f"ou PlotlyChartJSON à la place."
            )

        import json

        def _jsonable(v):
            try:
                json.dumps(v)
                return True
            except (TypeError, ValueError):
                return False

        params = {
            k: v for k, v in self.__dict__.items()
            if not k.startswith("_") and _jsonable(v)
        }

        # Cas DataMixin : la source est stockée dans self._data_arg,
        # donc ignorée par le filtre précédent.
        if hasattr(self, "data_key") and self.data_key is not None:
            params["data"] = self.data_key

        return {
            "type": self.__class__.__name__,
            "params": params,
        }


# ─────────────────────────────────────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────────────────────────────────────
def _is_vector_col(series: pd.Series) -> bool:
    """Détecte si une colonne contient des listes/arrays (vectorielle)."""
    sample = series.dropna()
    if len(sample) == 0:
        return False
    first = sample.iloc[0]
    return isinstance(first, (list, np.ndarray))


def _col_analysis(df: pd.DataFrame) -> dict:
    """Retourne les colonnes classées par type."""
    scalar_num, scalar_cat, vector = [], [], []
    for col in df.columns:
        if _is_vector_col(df[col]):
            vector.append(col)
        elif pd.api.types.is_numeric_dtype(df[col]):
            scalar_num.append(col)
        else:
            scalar_cat.append(col)
    return {"scalar_num": scalar_num, "scalar_cat": scalar_cat, "vector": vector,
            "scalar": scalar_num + scalar_cat, "all": list(df.columns)}


def _html_safe_dumps(obj) -> str:
    """json.dumps avec échappement de </ pour éviter de casser les tags <script>."""
    import json as _json
    return _json.dumps(obj).replace('</', '<\\/')


def _safe_json(v):
    """Convertit les types numpy/nan en types JSON-sérialisables."""
    if isinstance(v, float) and np.isnan(v):
        return None
    if isinstance(v, (np.integer,)):
        return int(v)
    if isinstance(v, (np.floating,)):
        return float(v)
    if isinstance(v, np.ndarray):
        return v.tolist()
    return v


# Importé depuis color_utils pour respecter SRP — la physique optique
# n'a pas sa place dans le module de base ABC.
from .blocks.charts.color_utils import lambda_to_srgb as _lambda_to_srgb


def _df_to_led_records(df: pd.DataFrame) -> list[dict]:
    """Sérialise un df avec colonnes mixtes scalaire/vectoriel en liste de dicts JSON-safe."""
    records = []
    for _, row in df.iterrows():
        rec = {}
        for col in df.columns:
            v = row[col]
            if isinstance(v, np.ndarray):
                rec[col] = [_safe_json(x) for x in v]
            elif isinstance(v, list):
                rec[col] = [_safe_json(x) for x in v]
            elif isinstance(v, float) and np.isnan(v):
                rec[col] = None
            else:
                rec[col] = _safe_json(v)
        records.append(rec)
    return records
