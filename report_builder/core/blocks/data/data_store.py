"""
data_store.py — DataStore partagé pour ReportBuilder.

Principe :
  - Les DataFrames sont enregistrés une seule fois dans le store par une clé str.
  - Chaque bloc accepte soit une clé str (référence au store) soit un df direct (override local).
  - À la sérialisation HTML, chaque dataset n'est injecté qu'une seule fois dans
    window.__DATA_STORE__[key], quelle que soit le nombre de blocs qui le partagent.

Usage :
    # Côté Python (dans demo_led_report.py)
    report = ReportBuilder(...)
    report.data.register("main", df)
    report.data.register("yield", df_yield)   # dataset plus petit, optionnel

    tab_report.add(ScatterLED(data="main", ...))   # clé → 0 octets de plus
    tab_report.add(WaferMaps( data="main", ...))   # même dataset, toujours 0 octets
    tab_report.add(KPIRow([...]))                   # pas de data → inchangé

    # Override local : un bloc reçoit un df complètement différent
    tab_report.add(SummaryBoxPlots(data=df_external, ...))

    # Dans ReportBuilder.save() :
    store_json = report.data.to_js_injection()   # → injecté une fois dans le HTML
"""
from __future__ import annotations

import json

import numpy as np
import pandas as pd

from ..types import DataArg


# ─────────────────────────────────────────────────────────────────────────────
#  Helpers de sérialisation
# ─────────────────────────────────────────────────────────────────────────────

def _safe_val(v):
    """Convertit une valeur en type JSON-sérialisable."""
    if isinstance(v, float):
        if np.isnan(v) or np.isinf(v):
            return None
        return v
    if isinstance(v, (np.integer,)):
        return int(v)
    if isinstance(v, (np.floating,)):
        f = float(v)
        return None if (np.isnan(f) or np.isinf(f)) else f
    if isinstance(v, (np.ndarray, list)):
        return [_safe_val(x) for x in v]
    return v


def _df_to_records(df: pd.DataFrame) -> list[dict]:
    """Convertit un DataFrame en liste de dicts JSON-safe."""
    records = []
    for _, row in df.iterrows():
        rec = {}
        for col, val in row.items():
            rec[col] = _safe_val(val)
        records.append(rec)
    return records


# ─────────────────────────────────────────────────────────────────────────────
#  DataStore
# ─────────────────────────────────────────────────────────────────────────────

class DataStore:
    """
    Registre de DataFrames partagés entre les blocs d'un rapport.

    Règles :
      - register(key, df)    → enregistre un dataset sous une clé str
      - resolve(data)        → retourne le df correspondant (clé ou df direct)
      - to_js_injection()    → retourne le bloc <script> à insérer une fois dans le HTML

    Les blocs qui stockaient self.df = df.copy() doivent désormais stocker
    self._data_arg = data (clé ou df) et appeler store.resolve(self._data_arg)
    au moment du render(), ou bien continuer à stocker le df résolu si le bloc
    est construit sans store (rétrocompatibilité).
    """

    def __init__(self):
        self._store: dict[str, pd.DataFrame] = {}

    # ── API publique ──────────────────────────────────────────────────────────

    def register(self, key: str, df: pd.DataFrame) -> "DataStore":
        """Enregistre un DataFrame. Retourne self pour le chaînage."""
        import re
        if not isinstance(key, str) or not re.match(r'^[A-Za-z_][A-Za-z0-9_\-\.]*$', key):
            raise ValueError(
                f"DataStore key must start with a letter or underscore and contain only "
                f"letters, digits, hyphens, underscores or dots, got: {key!r}"
            )
        self._store[key] = df
        return self

    def resolve(self, data: DataArg) -> pd.DataFrame:
        """
        Résout un argument data :
          - str  → cherche dans le store (KeyError si absent)
          - DataFrame → retourné tel quel (override local)
        """
        if isinstance(data, str):
            if data not in self._store:
                available = list(self._store.keys())
                raise KeyError(
                    f"DataStore key {data!r} not found. "
                    f"Available keys: {available}. "
                    f"Did you forget report.data.register('{data}', df) ?"
                )
            return self._store[data]
        if isinstance(data, pd.DataFrame):
            return data
        raise TypeError(
            f"data must be a str key or a pd.DataFrame, got {type(data).__name__}"
        )

    def keys(self) -> list[str]:
        """Liste des clés enregistrées."""
        return list(self._store.keys())

    def __contains__(self, key: str) -> bool:
        return key in self._store

    def __len__(self) -> int:
        return len(self._store)

    # ── Sérialisation HTML ────────────────────────────────────────────────────

    def to_js_injection(self) -> str:
        """
        Retourne un bloc <script> qui expose tous les datasets enregistrés
        dans window.__DATA_STORE__[key].

        À insérer UNE SEULE FOIS dans le HTML généré par ReportBuilder.save().

        Exemple d'output :
            <script>
            window.__DATA_STORE__ = window.__DATA_STORE__ || {};
            window.__DATA_STORE__["main"] = [...];
            window.__DATA_STORE__["yield"] = [...];
            </script>
        """
        if not self._store:
            return '<script>window.__DATA_STORE__ = window.__DATA_STORE__ || {};</script>'

        lines = ['<script>', 'window.__DATA_STORE__ = window.__DATA_STORE__ || {};']
        for key, df in self._store.items():
            records = _df_to_records(df)
            # Escape </ pour éviter que le parser HTML coupe le tag <script>
            # si une valeur string contient "</script>" ou similaire.
            safe = json.dumps(records).replace('</', '<\\/')
            lines.append(
                f'window.__DATA_STORE__[{json.dumps(key)}] = {safe};'
            )
        lines.append('</script>')
        return '\n'.join(lines)

    def to_json_dict(self) -> dict[str, list[dict]]:
        """
        Version dict Python (utile pour les tests ou pour passer à un template Jinja).
        """
        return {key: _df_to_records(df) for key, df in self._store.items()}

    # ── Introspection ─────────────────────────────────────────────────────────

    def __repr__(self) -> str:
        summaries = []
        for key, df in self._store.items():
            summaries.append(f"  {key!r}: {len(df)} rows × {len(df.columns)} cols")
        body = "\n".join(summaries) if summaries else "  (empty)"
        return f"DataStore(\n{body}\n)"
