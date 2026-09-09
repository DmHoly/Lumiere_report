# Lumière Report

Générateur de rapports HTML **standalone** : assemblez des blocs (charts Plotly, tables, KPIs, wafer maps, Graph Builder interactif…) en onglets ou en slides, et exportez un fichier HTML auto-contenu — zéro dépendance serveur, zéro base de données.

Ce dépôt est extrait de [lumiere-suite](https://github.com/DmHoly/lumiere-suite) (ex-module `report_builder/`) pour évoluer de façon autonome.

## Sommaire

- [Installation](#installation)
- [Usage rapide](#usage-rapide)
- [Report Builder — API + interface visuelle](#report-builder--api--interface-visuelle)
- [Concepts clés](#concepts-clés)
- [Catalogue des blocs](#catalogue-des-blocs)
- [Graph Builder V2 / V3](#graph-builder-v2--v3)
- [Structure du dépôt](#structure-du-dépôt)
- [Tests](#tests)
- [Périmètre de ce dépôt](#périmètre-de-ce-dépôt)

## Installation

```bash
pip install -r requirements.txt
# ou, en tant que package installable :
pip install -e .
```

Dépendances optionnelles :
- `psycopg2-binary` — requis uniquement par `VLCDesignBlock` (requête base GOZER)
- `cryptography` — requis uniquement si `ReportBuilderRunner` chiffre ses snapshots

## Usage rapide

```python
from report_builder.core import (
    ReportBuilder, Tab, TabView,
    Section, Text, KPIRow, KPI, ScatterLED, WaferMaps, GraphBuilderV2, GraphBuilderV3,
)
from report_builder.core.mock_led_dataset import generate_mock_led_dataset

df = generate_mock_led_dataset(n_wafers=3, points_per_wafer=200)

report = ReportBuilder(title="Test", subtitle="Mock data")
report.data.register("main", df)   # une seule sérialisation, quel que soit le nombre de blocs qui l'utilisent

tab = Tab("Analyse")
tab.add(Section("Vue d'ensemble"))
tab.add(KPIRow([KPI("LEDs", len(df)), KPI("Wafers", df["wafername"].nunique())]))
tab.add(ScatterLED(data="main", x_col="EQE_max", y_col="Lambda_peak_at_max_EQE"))
tab.add(GraphBuilderV3(data="main", height=700))

report.add(TabView([tab]))
report.save("output/rapport.html")
```

## Report Builder — API + interface visuelle

Au-dessus de la librairie, `app/` expose une API FastAPI et une interface web pour assembler un rapport visuellement, sans écrire de Python :

```bash
uvicorn app.main:app --reload --port 8420
```

**Sous Windows**, double-clique simplement sur `start_report_builder.bat` à la racine du dépôt : il crée l'environnement virtuel au premier lancement, installe les dépendances, démarre le serveur et ouvre le navigateur automatiquement sur `http://127.0.0.1:8420/`. Laisser la fenêtre ouverte pendant l'utilisation ; la fermer (ou Ctrl+C) arrête le serveur.

Puis ouvrir `http://localhost:8420/` :

1. **Uploader ou choisir un dataset** (CSV / Parquet / Excel) dans l'en-tête.
2. **Ajouter des onglets** (= pages du rapport), chacun en mode **Basique** (pile verticale de blocs) ou **Grille** (lignes de 1 à 4 colonnes).
3. **Piocher des blocs dans la bibliothèque** — auto-générée par introspection du catalogue `report_builder.core` (paramètres typés en formulaire : colonnes du dataset, nombres, booléens, listes de KPI…).
4. **Aperçu** en direct (rendu réel via le moteur `report_builder`), **Enregistrer** la config pour la rappeler plus tard, **Exporter** le HTML final.

L'API REST sous-jacente (`/api/datasets`, `/api/blocks`, `/api/reports`) est utilisable indépendamment de l'UI — voir les docstrings dans `app/routers/` et `app/report_compiler.py` (schéma de config détaillé).

## Concepts clés

- **Block** — classe abstraite (`report_builder.core._helpers.Block`) : tout composant visuel implémente `render(store=None) -> str` et retourne un fragment HTML (jamais `<html>`/`<body>`).
- **DataStore** — registre central des DataFrames d'un rapport (`report.data.register("main", df)`). Chaque dataset est sérialisé **une seule fois** dans le HTML final, quel que soit le nombre de blocs qui le consomment (pattern zéro-copie).
- **DataMixin** — tout bloc consommant un DataFrame l'hérite ; accepte soit une clé du DataStore (`"main"`), soit un DataFrame direct passé en override local.
- **Layout** — `Tab` / `TabView` (onglets) ou `Slide` / `SlideView` (slides), plus `Row` / `Col` / `Grid` pour la disposition.

Documentation technique complète (architecture des blocs, DataStore, conventions GraphBuilder V2/V3) : [`report_builder/CLAUDE.md`](report_builder/CLAUDE.md).

## Catalogue des blocs

| Catégorie | Blocs |
|---|---|
| Primitives | `Section`, `Text`, `KPI`, `KPIRow`, `PlotlyChart`, `DataTable`, `PlotlyChartJSON` |
| Charts | `ScatterLED`, `ScatterSummary`, `SummaryBoxPlots`, `ScatterPoint`, `ScatterDrillDown`, `DesignMatrixBlock`, `SpiderChart`, `CIEDiagram` |
| Wafer | `WaferMaps`, `WaferComparator`, `BestWaferMapBlock`, `SEMWafermapBlock`, `SEM101WafermapBlock`, `EQELambdaBoxplot`, `WaferELCompareBlock`, `WaferCurveCompareBlock` |
| Spectres | `PLSpectraBlock`, `LambdaShiftBlock` |
| Stats | `StatAnalysis`, `AnomalyBlock` |
| Tables | `RawDataTableBlock`, `LotSummaryTable`, `LotInfoCard` |
| Images | `Imageviewer`, `ELMatrixBlock` |
| Simulation / VLC | `SimExplorerBlock`, `SimMapBlock`, `VLCDesignBlock`, `VLCCompareBlock`, `CoreShellULEDBlock` |
| Optique | `AngularFluxBlock` |
| Divers | `KPISparkBlock`, `TrendlineKPICard`, `EasterEggs`, `LumiereTour`, `MergeStoreBlock` |

Tous exposés depuis `report_builder.core` ou `report_builder.core.blocks`.

## Graph Builder V2 / V3

Deux moteurs d'exploration de données interactifs, réutilisables comme blocs de rapport ou en app standalone :

- **GraphBuilderV2** (`graph_builder_block.py`) — stable, en production.
- **GraphBuilderV3** (`graph_builder_v3/`) — expérimental, conservé en parallèle. Ses assets JS/CSS (`graph_builder_v3/static/`) sont une copie vendorisée du Graph Builder interactif de lumiere-suite, figée au moment de l'extraction de ce dépôt.

Chaque builder expose `render(store=None)` (fragment embeddable dans un rapport) et `render_standalone()` (page HTML complète, export indépendant).

```python
from report_builder.core import GraphBuilderV2, GraphBuilderV3

tab.add(GraphBuilderV2("main"))
tab.add(GraphBuilderV3(data="main", exclude_cols=["Spectra", "WL"], height=700))
```

## Structure du dépôt

```
lumiere_report/
├── report_builder/
│   ├── core/
│   │   ├── _helpers.py, _assets.py        # Block (ABC), JS/CSS embarqués
│   │   ├── report_builder.py              # ReportBuilder — assembleur principal
│   │   ├── report_builder_runner.py       # Exécution depuis config JSON
│   │   ├── navigation.py, layout.py       # Tab/TabView/Slide, Row/Col/Grid
│   │   ├── mock_led_dataset.py            # Générateur de données de test
│   │   ├── graph_builder_block.py         # GraphBuilderV2
│   │   ├── graph_builder/                 # Code source du builder V2
│   │   ├── graph_builder_v3/              # GraphBuilderV3 + assets vendorisés
│   │   └── blocks/                        # Catalogue des blocs (voir ci-dessus)
│   ├── goniometre/                        # Indexation et analyse de mesures goniomètre (LIV, VLC)
│   ├── test_blocks_contract.py            # Tests de contrat (79 tests)
│   └── test_report_mock.py                # Rapport complet de bout en bout sur données mock
├── app/                                    # API + UI du Report Builder
│   ├── main.py, routers/                  # FastAPI (datasets, blocks, reports)
│   ├── block_registry.py                  # bibliothèque de blocs par introspection
│   ├── dataset_store.py, config_store.py  # persistance datasets / configs (JSON + parquet)
│   ├── report_compiler.py                 # config builder -> ReportBuilder -> HTML
│   └── static/                            # front-end vanilla JS
├── pyproject.toml
├── requirements.txt
└── CLAUDE.md
```

## Tests

```bash
pytest report_builder/test_blocks_contract.py -v

cd report_builder
python test_report_mock.py   # génère output/test_report_mock.html
```

## Périmètre de ce dépôt

Ce dépôt contient le moteur de rendu autonome (`report_builder/core/`, `report_builder/goniometre/`) et sa suite de tests. Les scripts couplés à l'écosystème ETL de lumiere-suite (nodes Aledia, chargement de données métier spécifiques : `QT_report.py`, `full_report_example.py`, `report_from_config.py`…) restent dans le dépôt principal, car ils dépendent de `etl.nodes.aledia_data`.

lumiere-suite garde pour l'instant sa propre copie interne de `report_builder/` ; le faire dépendre de ce dépôt est une étape ultérieure, non réalisée ici.
