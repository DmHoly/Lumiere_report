# CLAUDE.md

Guidance pour Claude Code sur ce dépôt.

## Projet

**Lumière Report** est le générateur de rapports HTML standalone extrait de [lumiere-suite](https://github.com/DmHoly/lumiere-suite) (ex-module `report_builder/`). Il assemble des blocs (charts Plotly, tables, KPIs, wafer maps, Graph Builder interactif) en un fichier HTML auto-contenu, sans dépendance serveur.

Deux parties dans ce dépôt :
1. **`report_builder/`** — la librairie pure Python (zéro dépendance serveur), le moteur de rendu.
2. **`app/`** — une API FastAPI + un front-end (le "Report Builder") qui expose la librairie : upload de dataset, bibliothèque de blocs, assemblage visuel (mode basique ou grille), sauvegarde/rappel de configs, export HTML.

`report_builder/` ne dépend jamais de `app/` (sens unique) — la librairie reste utilisable seule en script Python.

## Structure

```
lumiere_report/
├── report_builder/
│   ├── core/          # Blocs, ReportBuilder, DataStore, GraphBuilder V2/V3 — voir report_builder/CLAUDE.md
│   ├── goniometre/     # Indexation et analyse de mesures goniomètre (LIV, VLC)
│   ├── test_blocks_contract.py
│   └── test_report_mock.py
├── app/                        # API + front-end du Report Builder — voir app/CLAUDE.md
│   ├── main.py                 # FastAPI app (uvicorn app.main:app)
│   ├── block_registry.py       # introspecte report_builder.core -> bibliothèque de blocs pour l'UI
│   ├── dataset_store.py        # datasets uploadés/pré-enregistrés (cache parquet sous app/data/datasets/)
│   ├── config_store.py         # configs de rapport sauvegardées (JSON sous app/data/configs/)
│   ├── report_compiler.py      # config JSON du builder -> ReportBuilder réel -> HTML
│   ├── routers/                # datasets.py, blocks.py, reports.py
│   ├── static/                 # front-end vanilla JS (index.html, css/, js/)
│   └── data/                   # stockage runtime, gitignored (sauf .gitkeep)
├── pyproject.toml
├── requirements.txt
└── README.md
```

La documentation technique détaillée du moteur de rendu (architecture des blocs, DataStore, conventions GraphBuilder V2/V3) est dans `report_builder/CLAUDE.md` — la lire avant toute modification de `report_builder/core/`.

## Commandes

```bash
pip install -r requirements.txt

# Librairie seule — tests + rapport de démo
pytest report_builder/test_blocks_contract.py -v
cd report_builder && python test_report_mock.py   # génère output/test_report_mock.html

# App builder (API + front-end)
uvicorn app.main:app --reload --port 8420
# UI  : http://localhost:8420/
# API : http://localhost:8420/api/...
```

## Origine et périmètre

Ce dépôt ne contient que le moteur autonome : `report_builder/core/`, `report_builder/goniometre/` et leurs tests. Les scripts couplés à l'ETL de lumiere-suite (nodes Aledia, chargement de données métier spécifiques : `QT_report.py`, `full_report_example.py`, `report_from_config.py`, etc.) restent dans le dépôt principal, car ils dépendent de `etl.nodes.aledia_data`.

**Point d'attention** : `report_builder/core/graph_builder_v3/static/` contient une copie vendorisée des JS/CSS du Graph Builder interactif de lumiere-suite (dans ce dépôt-là, sous `app/pages/graph_builder/static/` — un `app/` différent du `app/` FastAPI de ce dépôt, ne pas confondre), figée au moment de l'extraction. Ce n'est pas dupliqué automatiquement — resynchroniser manuellement si le Graph Builder interactif évolue côté lumiere-suite et que ces changements doivent se refléter dans GraphBuilderV3 ici.

lumiere-suite continue d'utiliser sa propre copie de `report_builder/` en interne pour le moment ; la bascule vers ce dépôt comme dépendance externe est une étape ultérieure, non faite ici.

## Le Report Builder (`app/`)

Bibliothèque de blocs auto-générée par introspection (`app/block_registry.py`) : chaque bloc placable dans le builder est découvert depuis `report_builder.core.__all__`, avec ses paramètres de constructeur classés par "kind" (colonne, texte, nombre, référence de dataset…) pour générer les formulaires côté front sans code dupliqué par bloc. Ajouter un nouveau bloc dans `report_builder/core/` le fait apparaître automatiquement dans le builder — sauf s'il nécessite un DataFrame Python direct (non passable en JSON), auquel cas il est marqué `usable: false`.

La config d'un rapport (pages, blocs, params) suit le même schéma `{meta, pages:[...]}` que `ReportBuilder.to_config()` / `ReportBuilderRunner`, étendu avec `layout: "basic"|"grid"` par page et `main_dataset` au niveau racine. Voir la docstring de `app/report_compiler.py` pour le schéma complet.
