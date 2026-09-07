"""
data_mixin.py — Mixin de résolution de données pour les blocs.

Tous les blocs qui acceptent un df (ScatterLED, WaferMaps, etc.) héritent
de DataMixin. Cela leur permet de recevoir soit :
  - une clé str  : "main"  → résolu depuis window.__DATA_STORE__ (côté JS)
                            et depuis DataStore (côté Python au moment du render)
  - un df direct : df_custom  → comportement inchangé, df sérialisé localement

Utilisation dans un bloc :

    class ScatterLED(DataMixin, Block):
        def __init__(self, data: DataArg, ...):
            super().__init__(data)   # DataMixin.__init__
            ...

        def render(self, store=None) -> str:
            df = self.resolve_df(store)
            ...

La méthode resolve_df(store) :
  - Si data est un str  → utilise store.resolve(key) (store obligatoire)
  - Si data est un df   → retourne le df directement (store ignoré)
  - Si store est None et data est un str → lève une erreur explicite

Rétrocompatibilité :
  Les blocs peuvent continuer à accepter df= en premier argument pour ne pas
  casser le code existant. DataMixin accepte les deux via _normalize_data().
"""
from __future__ import annotations

import pandas as pd

from ..types import DataArg


def _normalize_data(data_or_df) -> DataArg:
    """
    Normalise l'argument data :
      - pd.DataFrame → retourné tel quel
      - str          → retourné tel quel
      - None         → retourné tel quel (certains blocs n'ont pas de data)
    """
    if isinstance(data_or_df, (pd.DataFrame, str, type(None))):
        return data_or_df
    raise TypeError(
        f"data must be a str key or a pd.DataFrame, got {type(data_or_df).__name__}"
    )


class DataMixin:
    """
    Mixin à ajouter à chaque bloc qui consomme un DataFrame.

    Fournit :
      self._data_arg  : la valeur brute passée à __init__ (str ou df)
      self.resolve_df(store) : retourne le pd.DataFrame résolu
      self.data_key   : la clé str si data est une référence, sinon None
      self.has_local_data : True si data est un df local
    """

    def _init_data(self, data: DataArg) -> None:
        """À appeler dans __init__ du bloc à la place de self.df = df.copy()."""
        self._data_arg: DataArg = _normalize_data(data)

    def resolve_df(self, store=None) -> pd.DataFrame:
        """
        Retourne le DataFrame résolu.

        Parameters
        ----------
        store : DataStore | None
            Obligatoire si self._data_arg est une clé str.
            Ignoré si self._data_arg est un pd.DataFrame.
        """
        data = self._data_arg

        if isinstance(data, pd.DataFrame):
            return data

        if isinstance(data, str):
            if store is None:
                raise RuntimeError(
                    f"Block references data key {data!r} but no DataStore was provided "
                    f"to resolve_df(). Pass store=report.data when calling render()."
                )
            return store.resolve(data)

        raise TypeError(
            f"_data_arg must be str or pd.DataFrame, got {type(data).__name__}"
        )

    @property
    def data_key(self) -> str | None:
        """Retourne la clé str si data est une référence, sinon None."""
        return self._data_arg if isinstance(self._data_arg, str) else None

    @property
    def has_local_data(self) -> bool:
        """True si le bloc détient un df local (pas une référence au store)."""
        return isinstance(self._data_arg, pd.DataFrame)

    @staticmethod
    def store_js_expr(key: str) -> str:
        """Retourne l'expression JS qui lit une clé depuis window.__DATA_STORE__."""
        import json
        return f'(window.__DATA_STORE__||{{}})[{json.dumps(key)}]||[]'
