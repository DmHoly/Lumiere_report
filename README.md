# Lumière Report

Générateur de rapports HTML standalone : assemblez des blocs (charts Plotly, tables, KPIs, wafer maps, Graph Builder interactif…) en onglets ou en slides, et exportez un fichier HTML auto-contenu (zéro dépendance serveur).

Ce dépôt est extrait de [lumiere-suite](https://github.com/DmHoly/lumiere-suite) (module `report_builder/`) pour évoluer de façon autonome.

## Installation

```bash
pip install -r requirements.txt
# ou, en tant que package :
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
report.data.register("main", df)

tab = Tab("Analyse")
tab.add(Section("Vue d'ensemble"))
tab.add(KPIRow([KPI("LEDs", len(df)), KPI("Wafers", df["wafername"].nunique())]))
tab.add(ScatterLED(data="main", x_col="EQE_max", y_col="Lambda_peak_at_max_EQE"))
tab.add(GraphBuilderV3(data="main", height=700))

report.add(TabView([tab]))
report.save("output/rapport.html")
```

Voir `report_builder/CLAUDE.md` pour la documentation technique complète (architecture des blocs, DataStore, GraphBuilder V2/V3, conventions).

## Tests

```bash
pytest report_builder/test_blocks_contract.py -v

cd report_builder
python test_report_mock.py   # génère output/test_report_mock.html
```

## Périmètre de ce dépôt

Ce dépôt contient le moteur de rendu autonome (`report_builder/core/`, `report_builder/goniometre/`) et sa suite de tests. Les scripts couplés à l'écosystème ETL de lumiere-suite (nodes Aledia, chargement de données spécifiques métier) restent dans le dépôt principal.
