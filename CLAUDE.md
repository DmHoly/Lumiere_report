# CLAUDE.md

Guidance pour Claude Code sur ce dépôt.

## Projet

**Lumière Report** est le générateur de rapports HTML standalone extrait de [lumiere-suite](https://github.com/DmHoly/lumiere-suite) (ex-module `report_builder/`). Il assemble des blocs (charts Plotly, tables, KPIs, wafer maps, Graph Builder interactif) en un fichier HTML auto-contenu, sans dépendance serveur.

## Structure

```
lumiere_report/
├── report_builder/
│   ├── core/          # Blocs, ReportBuilder, DataStore, GraphBuilder V2/V3 — voir report_builder/CLAUDE.md
│   ├── goniometre/     # Indexation et analyse de mesures goniomètre (LIV, VLC)
│   ├── test_blocks_contract.py
│   └── test_report_mock.py
├── pyproject.toml
├── requirements.txt
└── README.md
```

La documentation technique détaillée (architecture des blocs, DataStore, conventions GraphBuilder V2/V3) est dans `report_builder/CLAUDE.md` — la lire avant toute modification du moteur de rendu.

## Commandes

```bash
pip install -r requirements.txt
pytest report_builder/test_blocks_contract.py -v
cd report_builder && python test_report_mock.py   # génère output/test_report_mock.html
```

## Origine et périmètre

Ce dépôt ne contient que le moteur autonome : `report_builder/core/`, `report_builder/goniometre/` et leurs tests. Les scripts couplés à l'ETL de lumiere-suite (nodes Aledia, chargement de données métier spécifiques : `QT_report.py`, `full_report_example.py`, `report_from_config.py`, etc.) restent dans le dépôt principal, car ils dépendent de `etl.nodes.aledia_data`.

**Point d'attention** : `report_builder/core/graph_builder_v3/static/` contient une copie vendorisée des JS/CSS du Graph Builder interactif de lumiere-suite (`app/pages/graph_builder/static/`), figée au moment de l'extraction. Ce n'est pas dupliqué automatiquement — resynchroniser manuellement si le Graph Builder interactif évolue côté lumiere-suite et que ces changements doivent se refléter dans GraphBuilderV3 ici.

lumiere-suite continue d'utiliser sa propre copie de `report_builder/` en interne pour le moment ; la bascule vers ce dépôt comme dépendance externe est une étape ultérieure, non faite ici.
