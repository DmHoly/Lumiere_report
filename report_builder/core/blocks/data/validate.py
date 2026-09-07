"""
validate.py — Validation de DataFrame avant enregistrement dans le DataStore.

Usage
-----
    from report_builder.core.blocks.data.validate import validate_df, DataIssue

    issues = validate_df(df, name="main")
    errors   = [i for i in issues if i.level == "error"]
    warnings = [i for i in issues if i.level == "warning"]

    if errors:
        raise ValueError("\\n".join(i.message for i in errors))

Ou, pour afficher un résumé lisible :
    from report_builder.core.blocks.data.validate import format_issues
    print(format_issues(issues))

Niveaux
-------
  "error"   — le DataFrame ne peut pas être rendu correctement (données corrompues,
               types incohérents, colonnes en double…). Le bloc JS produira un
               résultat incorrect ou plantera.
  "warning" — le rendu fonctionnera mais avec des données dégradées ou sous-optimales
               (NaN convertis en null, vecteurs trop longs, colonnes vides…).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

import numpy as np
import pandas as pd


# ─────────────────────────────────────────────────────────────────────────────
#  DataIssue
# ─────────────────────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class DataIssue:
    level:   Literal["error", "warning"]
    column:  str | None   # None = problème global (pas lié à une colonne)
    code:    str          # identifiant machine (ex: "mixed_types", "all_nan")
    message: str          # message lisible pour l'utilisateur

    def __str__(self) -> str:
        tag = "ERROR" if self.level == "error" else "WARN "
        loc = f"[{self.column}] " if self.column else ""
        return f"[{tag}] {loc}{self.message}"


# ─────────────────────────────────────────────────────────────────────────────
#  Helpers internes
# ─────────────────────────────────────────────────────────────────────────────

def _is_vector(v) -> bool:
    return isinstance(v, (list, np.ndarray))


def _col_has_vectors(series: pd.Series) -> bool:
    sample = series.dropna()
    return len(sample) > 0 and _is_vector(sample.iloc[0])


def _col_is_mixed(series: pd.Series) -> bool:
    """Vrai si la colonne mélange scalaires et listes (brise le JS groupby)."""
    sample = series.dropna()
    if len(sample) < 2:
        return False
    types = {_is_vector(v) for v in sample}
    return len(types) > 1   # à la fois True et False dans le set


# ─────────────────────────────────────────────────────────────────────────────
#  Seuils configurables
# ─────────────────────────────────────────────────────────────────────────────

VECTOR_LEN_WARN   = 500    # longueur de vecteur au-delà de laquelle on avertit
VECTOR_COUNT_WARN = 10_000 # nb total de points vectoriels (lignes × longueur moy.)
NAN_RATIO_WARN    = 0.5    # part de NaN dans une colonne scalaire pour avertir


# ─────────────────────────────────────────────────────────────────────────────
#  Fonction principale
# ─────────────────────────────────────────────────────────────────────────────

def validate_df(df: pd.DataFrame, name: str = "df") -> list[DataIssue]:
    """
    Valide un DataFrame avant enregistrement dans le DataStore.

    Parameters
    ----------
    df   : pd.DataFrame à valider
    name : nom du dataset (utilisé dans les messages, ex: "main")

    Returns
    -------
    list[DataIssue] — liste vide si tout est correct.
    Triée : erreurs d'abord, avertissements ensuite.
    """
    issues: list[DataIssue] = []

    # ── 0. Vérifications globales ─────────────────────────────────────────────

    if not isinstance(df, pd.DataFrame):
        issues.append(DataIssue(
            level="error", column=None, code="not_a_dataframe",
            message=f"'{name}' n'est pas un pd.DataFrame (reçu: {type(df).__name__})."
        ))
        return issues   # pas la peine de continuer

    if len(df) == 0:
        issues.append(DataIssue(
            level="warning", column=None, code="empty_df",
            message=f"'{name}' est vide (0 lignes). Le bloc s'affichera sans données."
        ))

    if len(df.columns) == 0:
        issues.append(DataIssue(
            level="error", column=None, code="no_columns",
            message=f"'{name}' n'a aucune colonne."
        ))
        return issues

    # ── 1. Noms de colonnes ───────────────────────────────────────────────────

    # Colonnes en double
    seen: set = set()
    for col in df.columns:
        if col in seen:
            issues.append(DataIssue(
                level="error", column=str(col), code="duplicate_column",
                message=(
                    f"Colonne '{col}' présente plusieurs fois dans '{name}'. "
                    f"Les clés JSON dupliquées écrasent la valeur précédente côté JS."
                )
            ))
        seen.add(col)

    # Noms non-string
    for col in df.columns:
        if not isinstance(col, str):
            issues.append(DataIssue(
                level="error", column=str(col), code="non_string_column_name",
                message=(
                    f"Le nom de colonne {col!r} ({type(col).__name__}) n'est pas une str. "
                    f"Il sera converti en str lors de la sérialisation JSON, "
                    f"ce qui peut casser les références JS (ex: col_name='0' au lieu de 0)."
                )
            ))

    # Noms avec caractères dangereux pour JS/HTML
    import re
    for col in df.columns:
        if isinstance(col, str) and re.search(r'[<>"\'`\\]', col):
            issues.append(DataIssue(
                level="error", column=col, code="unsafe_column_name",
                message=(
                    f"Le nom de colonne '{col}' contient un caractère dangereux "
                    f"(<, >, \", ', `, \\) qui peut casser le JS ou le HTML généré."
                )
            ))

    # ── 2. Vérifications par colonne ──────────────────────────────────────────

    for col in df.columns:
        if not isinstance(col, str):
            continue   # déjà signalé, on évite les erreurs en cascade

        # Pandas retourne un DataFrame si plusieurs colonnes ont le même nom.
        # On ne vérifie que la première occurrence pour éviter les erreurs en cascade.
        raw = df[col]
        series = raw.iloc[:, 0] if isinstance(raw, pd.DataFrame) else raw

        # Mélange scalaire / vecteur dans la même colonne
        if _col_is_mixed(series):
            n_vec = series.dropna().apply(_is_vector).sum()
            n_sca = len(series.dropna()) - n_vec
            issues.append(DataIssue(
                level="error", column=col, code="mixed_types",
                message=(
                    f"'{name}[{col}]' mélange des scalaires ({n_sca} lignes) et des "
                    f"listes/arrays ({n_vec} lignes). Le groupby JS produira des résultats "
                    f"incorrects. Séparez la colonne en deux ou homogénéisez les valeurs."
                )
            ))
            continue   # pas d'autres checks sur cette colonne

        if _col_has_vectors(series):
            # Colonne vectorielle — vérifier la longueur
            sample = series.dropna()
            lengths = [len(v) for v in sample if _is_vector(v)]
            if lengths:
                max_len = max(lengths)
                avg_len = sum(lengths) / len(lengths)
                total_pts = int(avg_len * len(df))

                if max_len > VECTOR_LEN_WARN:
                    issues.append(DataIssue(
                        level="warning", column=col, code="large_vector",
                        message=(
                            f"'{name}[{col}]' contient des vecteurs de longueur max {max_len} "
                            f"(seuil: {VECTOR_LEN_WARN}). Pensez à downsampler avant register() "
                            f"pour réduire la taille du HTML."
                        )
                    ))
                elif total_pts > VECTOR_COUNT_WARN:
                    issues.append(DataIssue(
                        level="warning", column=col, code="large_vector_total",
                        message=(
                            f"'{name}[{col}]' représente ~{total_pts:,} points au total "
                            f"({len(df)} lignes × longueur moy. {avg_len:.0f}). "
                            f"Pensez à downsampler avant register()."
                        )
                    ))

            # Vecteurs avec valeurs non sérialisables à l'intérieur
            bad_rows: list[int] = []
            for idx, v in enumerate(series.dropna()):
                if _is_vector(v):
                    for elem in (v if isinstance(v, list) else v.tolist()):
                        if isinstance(elem, float) and (np.isnan(elem) or np.isinf(elem)):
                            bad_rows.append(idx)
                            break
                        if not isinstance(elem, (int, float, str, bool, type(None),
                                                  np.integer, np.floating)):
                            bad_rows.append(idx)
                            break
            if bad_rows:
                issues.append(DataIssue(
                    level="warning", column=col, code="vector_nan_or_inf",
                    message=(
                        f"'{name}[{col}]' contient des NaN/Inf ou des types non-JSON "
                        f"dans les vecteurs de {len(bad_rows)} ligne(s) "
                        f"(ex: index {bad_rows[:3]}). Ces valeurs seront converties en null."
                    )
                ))

        else:
            # Colonne scalaire

            # Colonne entièrement NaN
            n_null = series.isna().sum()
            if n_null == len(series) and len(series) > 0:
                issues.append(DataIssue(
                    level="warning", column=col, code="all_nan",
                    message=(
                        f"'{name}[{col}]' est entièrement vide (100% NaN/None). "
                        f"La colonne sera sérialisée comme une liste de null."
                    )
                ))
            elif n_null / max(len(series), 1) > NAN_RATIO_WARN:
                ratio_pct = int(n_null / len(series) * 100)
                issues.append(DataIssue(
                    level="warning", column=col, code="high_nan_ratio",
                    message=(
                        f"'{name}[{col}]' contient {ratio_pct}% de valeurs NaN/None "
                        f"({n_null}/{len(series)} lignes)."
                    )
                ))

            # NaN ou Inf scalaires (converties en null par _safe_val, mais on avertit)
            if pd.api.types.is_float_dtype(series):
                n_inf = np.isinf(series.dropna()).sum()
                if n_inf > 0:
                    issues.append(DataIssue(
                        level="warning", column=col, code="inf_values",
                        message=(
                            f"'{name}[{col}]' contient {n_inf} valeur(s) Inf/-Inf. "
                            f"Elles seront converties en null dans le store JS."
                        )
                    ))

            # Types Python non gérés (datetime, timedelta, object complexe)
            if pd.api.types.is_datetime64_any_dtype(series):
                issues.append(DataIssue(
                    level="warning", column=col, code="datetime_column",
                    message=(
                        f"'{name}[{col}]' est de type datetime. "
                        f"Elle sera sérialisée en str ISO 8601 via json.dumps. "
                        f"Convertissez en str avant register() pour contrôler le format : "
                        f"df['{col}'] = df['{col}'].dt.strftime('%Y-%m-%d')."
                    )
                ))

    # ── 3. Taille globale ─────────────────────────────────────────────────────

    # Estimation de la taille JSON (grossière mais rapide)
    n_scalar_cols = sum(1 for c in df.columns if not _col_has_vectors(df[c]))
    estimated_scalar_kb = len(df) * n_scalar_cols * 12 / 1024  # ~12 octets/val
    if estimated_scalar_kb > 5_000:
        issues.append(DataIssue(
            level="warning", column=None, code="large_dataset",
            message=(
                f"'{name}' est grand ({len(df):,} lignes × {n_scalar_cols} colonnes "
                f"scalaires, ~{estimated_scalar_kb/1024:.0f} Mo estimés). "
                f"Pensez à filtrer les colonnes inutiles avant register()."
            )
        ))

    # Tri : erreurs en premier
    issues.sort(key=lambda i: (0 if i.level == "error" else 1, i.column or ""))
    return issues


# ─────────────────────────────────────────────────────────────────────────────
#  Affichage
# ─────────────────────────────────────────────────────────────────────────────

def format_issues(issues: list[DataIssue], name: str = "df") -> str:
    """Retourne un rapport texte lisible pour print() ou logging."""
    if not issues:
        return f"✓ '{name}' — aucun problème détecté."

    errors   = [i for i in issues if i.level == "error"]
    warnings = [i for i in issues if i.level == "warning"]

    lines = [f"Validation '{name}' — {len(errors)} erreur(s), {len(warnings)} avertissement(s):"]
    for issue in issues:
        lines.append(f"  {issue}")
    return "\n".join(lines)
