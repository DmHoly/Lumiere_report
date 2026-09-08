"""
block_registry.py — Introspecte le catalogue report_builder.core pour exposer
une bibliothèque de blocs utilisable par le front-end du builder.

Pour chaque bloc placable dans un rapport, on décrit :
  - name        : nom de la classe (= "type" dans la config JSON du builder)
  - category    : regroupement pour la palette (dérivé du module Python)
  - description : première ligne de la docstring de la classe, si présente
  - params      : liste de {name, kind, default, required} par paramètre
                  constructeur (hors self/data/*args/**kwargs)
  - usable      : False si le bloc ne peut pas être piloté depuis une config
                  JSON générique (ex: nécessite un objet Figure Plotly Python
                  ou plusieurs DataFrames bruts) — le front l'affiche grisé.
  - unusable_reason : explication courte quand usable=False

Un paramètre "kind" pilote le widget de formulaire côté front :
  text          — champ texte libre
  int / float   — champ numérique
  bool          — case à cocher
  column        — <select> peuplé par les colonnes du dataset choisi
  column_multi  — liste de colonnes (saisie "col1, col2", séparateur virgule)
  range         — deux champs numériques -> [min, max] ou null
  dataset_ref   — <select> peuplé par les datasets enregistrés (clé DataStore)
  kpi_list      — sous-formulaire répétable {label, value, unit, delta, subtitle}
  json          — zone de texte, valeur collée en JSON brut (cas avancés/rares)
"""
from __future__ import annotations

import inspect
import re
from dataclasses import dataclass, field
from typing import Any

from report_builder import core as C

# Blocs structurels / hors périmètre du builder (mode page + TabView uniquement) :
# gérés autrement (onglets = pages du builder, lignes = mode grille) ou
# appartenant au mode 'slide' de ReportBuilder, non supporté par le builder.
_EXCLUDED = {
    "AppBuilder", "Page",            # mode application, pas mode rapport
    "Block",                          # ABC
    "ReportBuilder",                  # objet racine, pas un bloc plaçable
    "Tab", "TabView",                 # = les pages/onglets du builder lui-même
    "Row", "Col", "Grid",             # = le mode grille du builder lui-même
    "Slide", "SlideView", "TitleSlide", "SectionSlide", "SummarySlide",  # mode slide
    "PlotlyChart",                    # nécessite un objet Figure Python, non JSON-isable
    "KPI",                             # sous-composant de KPIRow uniquement, pas un Block
}

# Paramètres à masquer du formulaire pour certains blocs : alias legacy
# redondants avec "data" (déjà géré séparément), sans intérêt pour l'UI.
_SKIP_PARAMS = {
    "ELMatrixBlock": {"df"},
    "Imageviewer": {"df"},
}

# Overrides ponctuels de kind quand l'heuristique générique donne un résultat
# moins pratique que le cas d'usage réel du paramètre.
_KIND_OVERRIDES = {
    ("Text", "content"): "text",
}

_CATEGORY_LABELS = {
    "primitives": "Primitives",
    "charts": "Charts",
    "wafer": "Wafer",
    "spectra": "Spectres",
    "stats": "Stats",
    "tables": "Tables",
    "images": "Images",
    "misc": "Divers",
    "optics": "Optique",
    "simu_explorer": "Simulation / VLC",
}

_COLUMN_LIST_NAMES = {"targets", "features"}


def _category_for(cls: type) -> str:
    mod = cls.__module__  # ex: report_builder.core.blocks.charts.scatter_led
    parts = mod.split(".")
    if "blocks" in parts:
        i = parts.index("blocks")
        if i + 1 < len(parts) and parts[i + 1] in _CATEGORY_LABELS:
            return _CATEGORY_LABELS[parts[i + 1]]
    if "graph_builder" in mod or "graph_builder_v3" in mod:
        return "Graph Builder"
    return "Divers"


def _param_kind(name: str, annotation: str, default: Any) -> str:
    if name == "kpis":
        return "kpi_list"
    if name in ("store_key",):
        return "dataset_ref"
    if "range" in name:
        return "range"
    is_numericish = any(t in annotation for t in ("int", "float", "bool")) and "list" not in annotation
    if name.endswith("_col") or name == "kpi_col":
        return "column"
    if (name.endswith("_cols") or name in _COLUMN_LIST_NAMES) and not is_numericish:
        return "column_multi"
    if "DataArg" in annotation:
        return "dataset_ref"
    if "bool" in annotation or isinstance(default, bool):
        return "bool"
    if "float" in annotation or isinstance(default, float):
        return "float"
    if "int" in annotation or isinstance(default, int):
        return "int"
    if "dict" in annotation or "list" in annotation or "tuple" in annotation:
        return "json"
    return "text"


@dataclass
class ParamSpec:
    name: str
    kind: str
    required: bool
    default: Any = None


@dataclass
class BlockSpec:
    name: str
    category: str
    description: str
    params: list[ParamSpec] = field(default_factory=list)
    usable: bool = True
    unusable_reason: str | None = None


def _jsonable_default(v: Any) -> Any:
    """Réduit une valeur par défaut Python à quelque chose de sérialisable en JSON."""
    if v is None or isinstance(v, (str, int, float, bool)):
        return v
    if isinstance(v, (list, tuple)):
        return [_jsonable_default(x) for x in v]
    if isinstance(v, dict):
        return {k: _jsonable_default(x) for k, x in v.items()}
    return None


def introspect_block(name: str, cls: type) -> BlockSpec | None:
    try:
        sig = inspect.signature(cls.__init__)
    except (TypeError, ValueError):
        return None

    # cls.__doc__ direct (non hérité) — inspect.getdoc() remonterait sinon
    # jusqu'à la docstring générique de Block(ABC) pour les classes sans doc.
    doc = (cls.__doc__ or "").strip().splitlines()
    description = doc[0].strip() if doc else ""

    params: list[ParamSpec] = []
    unusable_reason: str | None = None
    skip = _SKIP_PARAMS.get(name, set())

    for pname, p in sig.parameters.items():
        if pname in ("self", "data") or pname in skip:
            continue
        if p.kind in (p.VAR_POSITIONAL, p.VAR_KEYWORD):
            continue

        ann = "" if p.annotation is inspect.Parameter.empty else str(p.annotation)
        required = p.default is inspect.Parameter.empty
        default = None if required else _jsonable_default(p.default)

        # Un paramètre requis attendant un DataFrame brut (pas une clé DataArg)
        # ne peut pas être fourni par une config JSON générique.
        if required and "DataFrame" in ann and "DataArg" not in ann and unusable_reason is None:
            unusable_reason = (
                f"nécessite un ou plusieurs DataFrame(s) directs "
                f"(ex: '{pname}'), non supporté par le builder"
            )

        kind = _KIND_OVERRIDES.get((name, pname)) or _param_kind(pname, ann, default)
        params.append(ParamSpec(name=pname, kind=kind, required=required, default=default))

    takes_data = "data" in sig.parameters
    spec = BlockSpec(
        name=name,
        category=_category_for(cls),
        description=description,
        params=params,
        usable=unusable_reason is None,
        unusable_reason=unusable_reason,
    )
    # Info utile pour le front : le bloc consomme-t-il le dataset principal
    # automatiquement (comme tous les blocs DataMixin) ?
    spec.__dict__["takes_main_data"] = takes_data
    return spec


def build_registry() -> list[BlockSpec]:
    registry: list[BlockSpec] = []
    for name in sorted(set(C.__all__)):
        if name in _EXCLUDED:
            continue
        cls = getattr(C, name, None)
        if not inspect.isclass(cls):
            continue
        spec = introspect_block(name, cls)
        if spec is None:
            continue
        registry.append(spec)
    return registry


def registry_as_dict() -> dict:
    """Sérialise le registre pour GET /api/blocks, groupé par catégorie."""
    by_category: dict[str, list[dict]] = {}
    for spec in build_registry():
        entry = {
            "name": spec.name,
            "category": spec.category,
            "description": spec.description,
            "usable": spec.usable,
            "unusable_reason": spec.unusable_reason,
            "takes_main_data": spec.__dict__.get("takes_main_data", False),
            "params": [
                {
                    "name": p.name,
                    "kind": p.kind,
                    "required": p.required,
                    "default": p.default,
                }
                for p in spec.params
            ],
        }
        by_category.setdefault(spec.category, []).append(entry)
    for cat_list in by_category.values():
        cat_list.sort(key=lambda e: e["name"])
    return dict(sorted(by_category.items()))
