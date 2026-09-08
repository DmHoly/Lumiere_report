"""
report_compiler.py — Compile la config JSON du builder en un ReportBuilder
réel (report_builder.core), puis en HTML.

Schéma de config attendu (voir aussi app/static/js/builder.js) :

{
  "meta": {"title": "...", "subtitle": "...", "author": "..."},
  "main_dataset": "mon_dataset",              # clé DatasetStore
  "pages": [
    {
      "name": "Vue d'ensemble",
      "layout": "basic",                      # pile verticale
      "blocks": [ {"type": "Section", "params": {...}}, ... ]
    },
    {
      "name": "Grille",
      "layout": "grid",                       # lignes de 1 à 4 cellules
      "rows": [
        {"ncols": 2, "cells": [ {"type": "ScatterLED", "params": {...}}, null ]}
      ]
    }
  ]
}

Une cellule de grille à null reste vide (espace réservé). Tout paramètre de
bloc dont la valeur est une chaîne correspondant à une clé de dataset connue
est traité comme une référence de dataset secondaire (ex: WaferELCompareBlock
.el_data) et ce dataset est enregistré dans le DataStore du rapport en plus
du dataset principal.

Contrairement à ReportBuilderRunner.generate() (tolérant : les blocs en
erreur sont listés dans "skipped" et le rapport se génère quand même), ce
compilateur échoue au premier bloc en erreur — dans un contexte d'édition
interactive, l'utilisateur doit savoir immédiatement quel bloc casse et
pourquoi plutôt que de deviner face à un aperçu incomplet.
"""
from __future__ import annotations

from typing import Any, Iterator

from report_builder import core as C
from report_builder.core.report_builder_runner import build_block

from .dataset_store import store as dataset_store


class BlockBuildError(Exception):
    def __init__(self, page: str, block_type: str, original: Exception):
        self.page = page
        self.block_type = block_type
        self.original = original
        super().__init__(f"[{page}] {block_type}: {original}")


class ConfigError(Exception):
    pass


def _iter_block_configs(page: dict) -> Iterator[dict]:
    if page.get("layout") == "grid":
        for row in page.get("rows", []) or []:
            for cell in row.get("cells", []) or []:
                if cell:
                    yield cell
    else:
        yield from page.get("blocks", []) or []


def _collect_dataset_keys(config: dict, main_key: str) -> set[str]:
    keys = {main_key}
    for page in config.get("pages", []) or []:
        for block_cfg in _iter_block_configs(page):
            for v in (block_cfg.get("params") or {}).values():
                if isinstance(v, str) and dataset_store.exists(v):
                    keys.add(v)
    return keys


def compile_report(config: dict):
    """Construit un objet report_builder.core.ReportBuilder depuis la config."""
    meta = config.get("meta") or {}
    main_key = config.get("main_dataset")
    if not main_key:
        raise ConfigError("main_dataset manquant dans la config")
    if not dataset_store.exists(main_key):
        raise ConfigError(f"Dataset introuvable : {main_key!r}")

    pages = config.get("pages") or []
    if not pages:
        raise ConfigError("La config ne contient aucune page")

    report = C.ReportBuilder(
        title=meta.get("title") or "Rapport",
        subtitle=meta.get("subtitle") or "",
        author=meta.get("author") or "Lumière Report",
    )

    for key in _collect_dataset_keys(config, main_key):
        report.data.register(key, dataset_store.get(key))

    tabs = []
    for page in pages:
        page_name = page.get("name") or "Page"
        tab = C.Tab(page_name)
        layout = page.get("layout", "basic")

        if layout == "grid":
            for row_cfg in page.get("rows", []) or []:
                cells: list[dict | None] = row_cfg.get("cells") or []
                ncols = row_cfg.get("ncols") or max(len(cells), 1)
                row = C.Row(ncols=ncols)
                for i, cell in enumerate(cells[:ncols]):
                    if not cell:
                        continue
                    try:
                        blk = build_block(cell["type"], cell.get("params", {}), C, main_key)
                    except Exception as exc:
                        raise BlockBuildError(page_name, cell.get("type", "?"), exc) from exc
                    row[i].add(blk)
                tab.add(row)
        else:
            for block_cfg in page.get("blocks", []) or []:
                try:
                    blk = build_block(block_cfg["type"], block_cfg.get("params", {}), C, main_key)
                except Exception as exc:
                    raise BlockBuildError(page_name, block_cfg.get("type", "?"), exc) from exc
                tab.add(blk)

        tabs.append(tab)

    report.add(C.TabView(tabs))
    return report


def render_html(config: dict) -> str:
    return compile_report(config).render()
