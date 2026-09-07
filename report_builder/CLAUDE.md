# CLAUDE.md — Report Builder

Documentation technique et décisions d'architecture pour le module `report_builder/`.
Mis à jour : juin 2026 — fiabilisation complète (ABC, types centralisés, sous-dossiers, tests, GraphBuilder V2/V3 intégrés) + zéro-copie store (juin 2026) + outlier scalaire EQE_max + point pivot Courbes (juin 2026).

---

## Vue d'ensemble

Le report builder est un système de génération de rapports HTML standalone.
Chaque rapport est un assemblage de **blocs** (composants visuels) organisés dans des onglets ou des slides.
Les données sont injectées au moment de la génération ; le rapport HTML résultant est auto-contenu (zéro dépendance serveur).

---

## Structure des fichiers

```
report_builder/
├── core/
│   ├── _helpers.py               # Classe de base Block (ABC)
│   ├── _assets.py                # JS/CSS embarqués (Plotly, Marked, styles)
│   ├── report_builder.py         # ReportBuilder — assembleur principal
│   ├── report_builder_runner.py  # Exécution depuis config JSON
│   ├── navigation.py             # Tab, TabView, Slide, SlideView, TitleSlide…
│   ├── layout.py                 # Row, Col, Grid
│   ├── mock_led_dataset.py       # Générateur de données LED de test
│   ├── graph_builder_block.py    # GraphBuilderV2 — stable
│   ├── graph_builder/            # Code source du builder V2
│   ├── graph_builder_v3/         # GraphBuilderV3 — expérimental
│   │   ├── graph_builder_v3_block.py
│   │   └── static/               # JS/CSS vendorisés (voir note ci-dessous)
│   ├── __init__.py               # API publique : tous les blocs + GraphBuilderV2/V3
│   └── blocks/
│       ├── types.py              # DataArg — source de vérité unique
│       ├── __init__.py           # Re-exporte tout — API publique inchangée
│       ├── data/
│       │   ├── data_store.py     # DataStore
│       │   └── data_mixin.py     # DataMixin
│       ├── primitives/
│       │   ├── base.py           # Section, Text, KPI, KPIRow, PlotlyChart, DataTable
│       │   └── plotly_chart_json.py
│       ├── charts/               # ScatterLED, ScatterSummary, SummaryBoxPlots, ScatterPoint, SpiderChart, CIEDiagram
│       ├── wafer/                # WaferMaps, WaferComparator, BestWaferMapBlock, SEM*, EQELambdaBoxplot
│       ├── spectra/              # PLSpectraBlock, LambdaShiftBlock
│       ├── stats/                # StatAnalysis, AnomalyBlock
│       ├── tables/               # RawDataTableBlock, LotSummaryTable, LotInfoCard
│       ├── images/               # Imageviewer
│       └── misc/                 # KPISparkBlock, TrendlineKPICard, EasterEggs, LumiereTour
├── test_blocks_contract.py       # 29 tests de contrat (pytest)
├── test_report_mock.py           # Rapport complet 8 onglets sur données mock
├── __init__.py
└── CLAUDE.md                     # Ce fichier
```

---

## Concepts fondamentaux

### Block (ABC)

Tout composant visuel hérite de `Block` (défini dans `core/_helpers.py`).
`Block` est une **classe abstraite** (ABC) depuis la fiabilisation de juin 2026.

```python
from abc import ABC, abstractmethod

class Block(ABC):
    needs_plotly: bool = False   # True → Plotly.js injecté dans le HTML final
    needs_marked: bool = False   # True → marked.js injecté dans le HTML final

    @abstractmethod
    def render(self, store=None) -> str: ...

    def to_dict(self) -> dict: ...   # sérialisation {type, params} pour le runner
```

**Contrat minimum d'un bloc :**
- Implémenter `render(store=None) -> str` — retourne du HTML **fragment** (jamais `<html>/<head>/<body>`)
- Déclarer `needs_plotly = True` si le bloc utilise Plotly
- Si le bloc consomme un DataFrame → hériter de `DataMixin`

Un bloc sans `render()` lève `TypeError` à l'instanciation (garanti par ABC).

### DataArg — type centralisé

`DataArg = Union[str, pd.DataFrame]` est défini **une seule fois** dans `blocks/types.py`.
Tous les blocs et mixins l'importent depuis cet unique endroit.

```python
from report_builder.core.blocks.types import DataArg
```

### DataStore

Registre central des DataFrames d'un rapport.

```python
report = ReportBuilder(title="Mon rapport")
report.data.register("main", df)          # enregistre une fois
report.data.register("summary", df_agg)   # dataset secondaire
```

Chaque dataset est sérialisé **une seule fois** dans le HTML via `to_js_injection()` :

```js
window.__DATA_STORE__ = window.__DATA_STORE__ || {};
window.__DATA_STORE__["main"] = [...];
window.__DATA_STORE__["summary"] = [...];
```

### DataMixin

Tout bloc consommant un DataFrame hérite de `DataMixin`. Accepte :
- une **clé string** `"main"` → référence au DataStore
- un **DataFrame direct** → override local, indépendant du store

```python
class MonBloc(DataMixin, Block):
    def __init__(self, data: DataArg, ...):
        self._init_data(data)

    def render(self, store=None) -> str:
        df = self.resolve_df(store)   # résolution au moment du render
        ...
```

---

## GraphBuilder V2 et V3

### Principe d'intégration

Les deux builders sont des apps standalone (full-page) réutilisées dans les rapports.
Pour l'intégration dans un onglet, chaque builder expose **deux méthodes** :

| Méthode | Retourne | Usage |
|---|---|---|
| `render(store=None)` | Fragment HTML embeddable | **Intégration dans un rapport** |
| `render_standalone()` | Page HTML complète (`<!DOCTYPE html>`) | Export standalone indépendant |

### GraphBuilderV2 (`graph_builder_block.py`)

Stable, utilisé en production. `render()` délègue à `render_fragment()`.

```python
from report_builder.core import GraphBuilderV2
tab = Tab("Builder")
tab.add(GraphBuilderV2("main"))   # "main" = clé DataStore
```

### GraphBuilderV3 (`graph_builder_v3/graph_builder_v3_block.py`)

**Expérimental** — conservé en parallèle de V2. Intégré dans `core/__init__.py` et `core/blocks/__init__.py`.

**Assets vendorisés** : V3 charge ses JS/CSS (`graph_builder.core.js`, `graph_builder.data.js`, extensions scatter/line/bar/boxplot/histogram/wafer_map/curves/linked_views…) depuis `graph_builder_v3/static/`. Ces fichiers sont une copie figée de `app/pages/graph_builder/static/` de lumiere-suite, prise au moment de l'extraction de ce dépôt (dépôt principal = source canonique de l'app interactive ; ce dépôt = copie utilisée par le renderer standalone). En cas d'évolution du Graph Builder interactif dans lumiere-suite, resynchroniser manuellement les fichiers concernés dans `graph_builder_v3/static/`.

| Paramètre | Type | Description |
|---|---|---|
| `data` | `DataArg` | DataFrame ou clé DataStore |
| `title` | `str` | Titre du builder |
| `exclude_cols` | `list[str]` | Colonnes vectorielles exclues (ex: `["Spectra", "WL"]`) |
| `max_vector_pts` | `int` | Max points pour colonnes vectorielles (défaut: 50) |
| `height` | `int` | Hauteur en px du bloc intégré (défaut: 700) |

```python
from report_builder.core import GraphBuilderV3
tab = Tab("Builder V3 ✦")
tab.add(GraphBuilderV3(
    data           = df,
    title          = "Graph Builder V3",
    exclude_cols   = ["Spectra", "WL", "I", "V", "L", "EQE"],
    max_vector_pts = 50,
    height         = 700,
))
```

**Mécanisme d'embedding de V3 dans `render()` :**

Le template V3 est une app full-page (`body.gb-runtime { height: 100vh; display: flex }`).
L'embedding extrait et réassemble les composants :

1. Extraire le bloc `<style>` du `<head>` (CSS du builder)
2. Extraire le contenu du `<body>`
3. Remplacer `window.addEventListener('DOMContentLoaded', ...)` par `window.LumiereGraphBuilder.boot()` direct (l'event est déjà passé quand le fragment est inséré dans le rapport)
4. Envelopper le body dans `<div id="gb3-embed-{uid}-root" class="gb-runtime">` avec hauteur explicite — réplique les règles CSS de `body.gb-runtime` (flex column, overflow hidden) via un `<style>` scopé par ID

Sans l'étape 4, `.gbr-workspace { flex: 1 }` n'a pas de parent de hauteur définie et la zone graphique ne s'affiche pas.

### Bugs d'intégration connus et résolus

#### V2 : zone graphique invisible dans un onglet non-actif au chargement

**Symptôme** : quand V2 est dans un tab autre que le premier, la zone graphique et la sidebar ne s'affichent pas après avoir cliqué sur l'onglet.

**Cause** : `fit()` (le JS qui calcule la hauteur de `.gb-app.gb-embedded`) se déclenche via `requestAnimationFrame` au chargement. Si l'onglet V2 est caché (`display:none`), `getBoundingClientRect()` retourne `{width:0, height:0, top:0}` → mauvaise hauteur calculée, jamais recalculée au changement d'onglet.

**Fix** (`navigation.py` — `TabView._show()`) : dispatcher un `window.resize` synthétique dans le `requestAnimationFrame` du changement d'onglet → déclenche `fit()` avec les bonnes dimensions visibles.

```js
requestAnimationFrame(function() {
  window.dispatchEvent(new Event('resize'));  // ← déclenche fit() de V2
  panel.querySelectorAll("[id]").forEach(function(el){if(el._fullLayout)Plotly.Plots.resize(el);});
});
```

`fit()` ignore les éléments réellement cachés via `if(r.width===0 && r.height===0) return` (plus fiable que `top===0` qui peut être valide).

#### V2 + V3 dans le même rapport : `.gb-main` de V2 caché

**Symptôme** : dès que V2 et V3 sont dans le même rapport, la zone `.gb-main` de V2 (sidebar + canvas) ne s'affiche pas, même en cliquant sur l'onglet.

**Cause** : le CSS global de V3 (issu de `graph_builder.css`) contient `.gb-main { display: none; }` — règle conçue pour masquer les onglets internes de V3 en attente. Ce CSS est injecté globalement dans le rapport et écrase le `.gb-main { display: flex; }` de V2.

**Fix** (`graph_builder_block.py` — `render_fragment()`) : ajout d'un override CSS scopé à `.gb-app.gb-embedded .gb-main` avec spécificité supérieure (3 classes vs 1) :

```css
.gb-app.gb-embedded .gb-main {
  display: flex !important;
  flex: 1 1 auto !important;
  height: 100% !important;
  min-height: 0 !important;
  overflow: hidden !important;
}
```

Ce sélecteur bat `.gb-main` de V3 en spécificité (0,3,0 > 0,1,0) et ne peut pas être contredit par un CSS global non-scopé.

**À retenir** : le CSS de V3 (app standalone) n'est pas scopé à son conteneur `#gb3-embed-{uid}-root`. Si d'autres conflits de classes apparaissent entre V2 et V3 dans un même rapport, la stratégie est la même — ajouter un override scopé à `.gb-app.gb-embedded` dans V2, ou préfixer le CSS V3 lors de l'extraction dans `render_fragment()`.

---

## Pattern zéro-copie store (implémenté juin 2026)

### Principe

Quand un bloc reçoit une **clé string** (ex: `"main"`), son `render()` n'émet **aucune donnée inline** — il émet uniquement un JSON de configuration + du JS qui lit `window.__DATA_STORE__[key]` au moment de l'exécution dans le navigateur.

Les données sont sérialisées **une seule fois** dans le HTML (par `ReportBuilder` via `to_js_injection()`), quelle que soit la quantité de blocs partageant la même clé.

**Règle** : si N blocs utilisent `"main"`, la taille du HTML = taille du store × 1, pas × N.

### Deux chemins dans chaque bloc

```python
if self.has_local_data:
    # DataFrame direct passé à l'instanciation — sérialisation inline (comportement legacy)
    df = self.resolve_df()
    ...sérialise df en JSON dans <script>...
else:
    # Clé store — zéro copie
    key = self._data_arg        # ex: "main"
    df = store.resolve(key)     # lecture Python pour la metadata (colonnes, types) uniquement
    cfg = {"key": key, "cols": [...], ...}
    ...émet var _cfg={cfg_json}; ... = (window.__DATA_STORE__||{})[_cfg.key]||[];...
```

Le chemin store lève `RuntimeError` si `store is None` (oubli de passer `store=report.data`).

### Downsampling

Le downsampling se fait **avant** `register()`, en Python, par l'utilisateur :

```python
df_light = downsample(df, n=500)   # fonction Python existante
report.data.register("main", df_light)
# Tous les blocs travaillent sur df_light — pas de copie supplémentaire
```

Ne jamais downsampler à l'intérieur d'un bloc ou dans le store : cela créerait N copies (une par enregistrement).

### Blocs refactorisés (store path implémenté)

| Bloc | Fichier | Stratégie JS côté store |
|---|---|---|
| `DataTable` | `primitives/base.py` | Config `{key, cols, num, fmt}` → map rows depuis store |
| `RawDataTableBlock` | `tables/raw_data_table.py` | `getRows(key)` lit le store, `COLS` config Python |
| `ScatterLED` | `charts/scatter_led.py` | Normalise `r[col]` → `{x, y, color, ...}` en JS |
| `ScatterSummary` | `charts/summary.py` | Pointe directement sur le store (JS utilise déjà `r[col]`) |
| `SummaryBoxPlots` | `charts/summary.py` | `forEach` groupby JS avec `METRICS` config |
| `WaferMaps` | `wafer/wafer_maps.py` | `forEach` groupby JS → `WDATA[wafer]=[{x,y,scalar...}]` |
| `GraphBuilderV2` | `graph_builder_block.py` | `DATA`/`DATA_FULL` depuis store + slice vector en JS |
| `GraphBuilderV3` | `graph_builder_v3/graph_builder_v3_block.py` | `__GB3_DATA__` remplacé par IIFE lisant le store |

**Non refactorisé (intentionnel) :**
- `StatAnalysis` — sérialise des résultats calculés (Kruskal-Wallis, t-test, RF feature importance), pas des données brutes → pas de duplication à éliminer.

---

## Détection d'outliers scalaires — `add_scalar_outlier_flag`

Fonction dans `core/mock_led_dataset.py`. Détecte les valeurs scalaires aberrantes par la méthode IQR et ajoute une colonne entière **0/1** au DataFrame.

```python
from report_builder.core.mock_led_dataset import add_scalar_outlier_flag

# Outlier global (toutes les LEDs confondues)
df = add_scalar_outlier_flag(df, col="EQE_max", output_col="EQE_max_outlier")

# Outlier intra-wafer (relatif à la distribution de chaque wafer)
df = add_scalar_outlier_flag(df, col="EQE_max", group_col="wafername",
                             output_col="EQE_max_outlier_wafer")
```

**Paramètres :**

| Paramètre | Défaut | Description |
|---|---|---|
| `col` | — | Colonne scalaire à analyser (ex: `"EQE_max"`) |
| `group_col` | `None` | Colonne de regroupement (ex: `"wafername"`) — si fourni, calcul IQR par groupe |
| `k` | `1.5` | Facteur IQR (1.5 = outlier standard, 3.0 = outlier extrême seulement) |
| `output_col` | `"{col}_outlier"` | Nom de la colonne résultat |

**Méthode :** un point est flaggé `1` si `val < Q1 − k×IQR` ou `val > Q3 + k×IQR`, sinon `0`.

**`add_quality_flags` appelle automatiquement** `add_scalar_outlier_flag` pour `EQE_max` (global, k=1.5) → colonne `EQE_max_outlier` disponible dès que `add_quality_flags(df)` est appelé.

**Usage typique dans le Graph Builder :** filtrer `EQE_max_outlier == 1` pour isoler les LEDs suspectes, ou coloriser le scatter par cette colonne pour identifier visuellement les outliers.

---

## Extension Courbes — fonctionnalités du Graph Builder V2/V3

L'extension **Courbes (∿)** dans `graph_builder_v3/static/extensions/curves.js` trace des courbes vectorielles (une courbe par ligne du DataFrame). Elle expose les options suivantes dans son panneau de configuration :

### Grouper par / couleur

Le champ **Grouper par** accepte toutes les colonnes `string` et `number` (ex: `wafername`, `split_str`, `reactor`). Quand une colonne est sélectionnée :
- Une trace Plotly est créée **par valeur unique** du groupBy
- Chaque groupe reçoit une couleur distincte (`COLORS` = palette Plotly par défaut)
- La légende est activée automatiquement
- Les courbes d'un même groupe sont concaténées dans la même trace (séparées par `null` pour des segments distincts)

**Raccourci** : si la colonne est déjà positionnée dans le slot **Couleur** (drag-and-drop), l'extension la reprend automatiquement comme groupBy sans avoir à la re-sélectionner dans le panneau.

### Point pivot scalaire

La section **Point pivot** permet de superposer des **marqueurs scatter** sur les courbes. Cas d'usage : marquer le point de performance clé (ex: le pic EQE) sur chaque courbe LIV.

| Champ config | Valeur typique | Description |
|---|---|---|
| `ptX` | `I_at_EQEmax` | Colonne scalaire pour la position X du point |
| `ptY` | `EQE_max` | Colonne scalaire pour la position Y du point |

**Rendu :** gros marqueurs circulaires (2.5× la taille des points de courbe), couleur identique au groupe ou à la courbe, bordure blanche pour contraste. Le tooltip affiche le nom de la courbe + les valeurs X/Y exactes.

**Exemple :** avec `vX=I`, `vY=EQE`, `ptX=I_at_EQEmax`, `ptY=EQE_max`, chaque courbe EQE(I) affiche son maximum en évidence :

```
Courbes : EQE vs I  →  lignes fines continues
Point pivot : I_at_EQEmax / EQE_max  →  ● gros point sur chaque courbe
```

**Compatibilité groupBy** : quand groupBy est actif, chaque groupe reçoit ses propres marqueurs pivot dans la même couleur que son faisceau de courbes. Les marqueurs partagent le `legendgroup` du groupe → togglables via la légende.

### Colonnes vectorielles dans les autres extensions

Les colonnes de type `vector` (badge ∿) ne sont pas supportées par Scatter, Line, Bar, Boxplot : ces extensions affichent un message d'orientation vers l'extension Courbes au lieu de planter silencieusement.

---

## Tests

```bash
# Tests de contrat (depuis la racine du dépôt lumiere_report)
pytest report_builder/test_blocks_contract.py -v

# Rapport de test complet sur données mock (génère output/test_report_mock.html)
cd report_builder
python test_report_mock.py
```

**`test_blocks_contract.py` vérifie pour chaque bloc :**
- Instanciable avec les paramètres minimaux
- `render()` retourne une string non-vide sans `<html>` / `<body>`
- Si `DataMixin` → `resolve_df(store)` fonctionne avec store mock
- `needs_plotly` et `needs_marked` sont des booleans

**`test_report_mock.py` :** 8 onglets — Vue d'ensemble, Scatter EQE, Résumé wafer, Wafer Maps, Stat Analysis, Graph Builder V2, Graph Builder V3, Données brutes.

---

## Usage type

```python
from report_builder.core import (
    ReportBuilder, Tab, TabView,
    Section, Text, KPIRow, KPI, PlotlyChart, DataTable,
    ScatterLED, WaferMaps, GraphBuilderV2, GraphBuilderV3,
)
from report_builder.core.mock_led_dataset import generate_mock_led_dataset

# 1. Données
df = generate_mock_led_dataset(n_wafers=3, points_per_wafer=200)

# 2. Rapport + registration des données (une seule fois)
report = ReportBuilder(title="Test", subtitle="Mock data")
report.data.register("main", df)

# 3. Blocs
tab = Tab("Analyse")
tab.add(Section("Vue d'ensemble"))
tab.add(KPIRow([KPI("LEDs", len(df)), KPI("Wafers", df["wafername"].nunique())]))
tab.add(ScatterLED(data="main", x_col="EQE_max", y_col="Lambda_peak_at_max_EQE"))
tab.add(GraphBuilderV3(data="main", height=700))

# 4. Export
report.add(TabView([tab]))
report.save("output/rapport.html")
```

---

## Conventions

- Les clés DataStore sont des **identifiants Python valides** (validé dans `DataStore.register()`)
- `needs_plotly` et `needs_marked` sont déclarés **au niveau classe**, pas à l'instance
- Les blocs n'écrivent jamais directement dans le store — seul `ReportBuilder` appelle `to_js_injection()`
- Les transformations lourdes restent côté Python dans des méthodes privées du bloc (ex: `_build_wafer_json`)
- Pour ajouter un nouveau bloc : hériter de `Block` (+ `DataMixin` si DataFrame), le placer dans le bon sous-dossier de `blocks/`, l'ajouter à `blocks/__init__.py` et à `test_blocks_contract.py`

## Conventions GraphBuilder

- V2 = stable, en production. V3 = expérimental, conserver en parallèle
- Toujours utiliser `render()` pour l'intégration dans un rapport, `render_standalone()` pour export standalone
- Le paramètre `height` de V3 est en pixels — ajuster selon la densité du contenu (défaut 700)
- `exclude_cols` : toujours exclure les colonnes vectorielles (spectres, courbes) pour éviter des JSON massifs
