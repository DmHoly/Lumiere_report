"""
stat_analysis.py — Bloc StatAnalysis v2 pour LUMIÈRE / Aledia Report Builder
==============================================================================

Corrections fondamentales :
  • Agrégation WAFER-LEVEL avant toute stat : médiane par wafer par target,
    puis test inter-splits sur les médianes wafer (N = n_wafers, pas n_LEDs)
  • Layout repensé : 2 colonnes max, charts 380-500px, table héro "vs Réf"
  • Tests de normalité → choix automatique Welch / Kruskal
  • Ref split identifié par mot-clé, comparaison vs ref en premier
  • Facteur confondant visible sur tous les scatters (colormap)
  • 5 onglets lisibles : Résultats · Distributions · ML · Corrélations · Uniformité
"""
from __future__ import annotations

import html as _h
import json
import re
import uuid
import warnings
from itertools import combinations

import numpy as np
import pandas as pd

try:
    from scipy import stats as _scipy_stats
    _HAS_SCIPY = True
except ImportError:
    _HAS_SCIPY = False

try:
    from sklearn.ensemble import RandomForestRegressor
    from sklearn.model_selection import cross_val_score, train_test_split
    from sklearn.preprocessing import LabelEncoder
    _HAS_SKLEARN = True
except ImportError:
    _HAS_SKLEARN = False

from ..._helpers import Block
from ..data.data_mixin import DataMixin, DataArg


# ─────────────────────────────────────────────────────────────────────────────
#  JSON helper
# ─────────────────────────────────────────────────────────────────────────────
def _j(obj) -> str:
    def _enc(x):
        if isinstance(x, (np.floating,)) and (np.isnan(x) or np.isinf(x)):
            return None
        if isinstance(x, (np.floating,)):  return float(x)
        if isinstance(x, (np.integer,)):   return int(x)
        if isinstance(x, np.ndarray):      return x.tolist()
        return x
    s = json.dumps(obj, default=_enc)
    s = re.sub(r'(?<!["\w])(NaN|-?Infinity)(?!["\w])', 'null', s)
    s = s.replace('</', r'<\/')
    return s


# ─────────────────────────────────────────────────────────────────────────────
#  Helpers statistiques
# ─────────────────────────────────────────────────────────────────────────────
def _pearson(a: np.ndarray, b: np.ndarray):
    mask = ~(np.isnan(a) | np.isnan(b))
    a, b = a[mask], b[mask]
    if len(a) < 3:
        return None, None
    if _HAS_SCIPY:
        r, p = _scipy_stats.pearsonr(a, b)
        return float(r), float(p)
    ma, mb = a.mean(), b.mean()
    num = ((a - ma) * (b - mb)).sum()
    den = np.sqrt(((a - ma) ** 2).sum() * ((b - mb) ** 2).sum())
    r = float(num / den) if den else 0.0
    return r, None


def _wafer_stats(vals: np.ndarray) -> dict:
    v = vals[~np.isnan(vals)]
    if not len(v):
        return dict(n=0, median=None, mean=None, std=None,
                    q25=None, q75=None, min=None, max=None, cv=None)
    med = float(np.median(v))
    std = float(v.std())
    q25 = float(np.percentile(v, 25))
    q75 = float(np.percentile(v, 75))
    cv  = round(abs(std / med * 100), 2) if med != 0 else None
    return dict(n=int(len(v)), median=round(med, 6), mean=round(float(v.mean()), 6),
                std=round(std, 6), q25=round(q25, 6), q75=round(q75, 6),
                min=round(float(v.min()), 6), max=round(float(v.max()), 6), cv=cv)


def _fit_rf(X_df: pd.DataFrame, y: np.ndarray, n_estimators: int, feat_names: list):
    if not _HAS_SKLEARN or len(y) < 6 or not feat_names or X_df.empty:
        return None
    Xc = X_df.copy()
    for col in Xc.select_dtypes(include="object").columns:
        le = LabelEncoder()
        Xc[col] = le.fit_transform(Xc[col].fillna("__na__").astype(str))
    Xc = Xc.fillna(Xc.median(numeric_only=True))
    X = Xc.values
    mask = ~np.isnan(y)
    X, y = X[mask], y[mask]
    if len(y) < 6:
        return None
    test_size = 0.25 if len(y) >= 8 else 0
    if test_size > 0:
        Xtr, Xte, ytr, yte = train_test_split(X, y, test_size=test_size, random_state=42)
    else:
        Xtr, Xte, ytr, yte = X, X, y, y
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        rf = RandomForestRegressor(n_estimators=n_estimators, random_state=42, n_jobs=-1)
        rf.fit(Xtr, ytr)
        cv_k = min(5, len(y))
        cv = cross_val_score(rf, X, y, cv=cv_k, scoring="r2") if cv_k >= 3 else np.array([rf.score(X, y)])
    imp_raw  = rf.feature_importances_
    imp_norm = (imp_raw / imp_raw.sum() * 100).tolist() if imp_raw.sum() > 0 else imp_raw.tolist()
    return dict(
        importance=[{"feature": f, "importance": round(float(v), 2)}
                    for f, v in sorted(zip(feat_names, imp_norm), key=lambda x: x[1], reverse=True)],
        r2_train=round(float(rf.score(Xtr, ytr)), 4),
        r2_test =round(float(rf.score(Xte, yte)),  4),
        cv_mean =round(float(cv.mean()), 4),
        cv_std  =round(float(cv.std()),  4),
    )


# ─────────────────────────────────────────────────────────────────────────────
#  StatAnalysis Block
# ─────────────────────────────────────────────────────────────────────────────
class StatAnalysis(DataMixin, Block):
    """
    Analyse statistique + ML d'un DOE LED sur données wafer-level.
    Agrège par wafer (médiane) avant toute analyse statistique.
    """
    needs_plotly = True

    def __init__(
        self,
        data: DataArg,
        targets: list,
        features: list | None = None,
        split_col: str = "split",
        wafer_col: str | None = "wafername",
        site_col:  str | None = None,
        target_labels:  dict | None = None,
        feature_labels: dict | None = None,
        alpha: float = 0.05,
        corr_threshold: float = 0.4,
        n_estimators: int = 100,
        confound_col: str | None = None,
        ref_keyword: str = "ref",
        num: str = "05",
        title: str = "Analyse Split",
        subtitle: str = "agrégation wafer · normalité · tests vs réf · ML · uniformité",
    ):
        self._init_data(data)
        self.targets        = targets
        self._features_arg  = features
        self.split_col      = split_col
        self.wafer_col      = wafer_col
        self.site_col       = site_col
        self.confound_col   = confound_col
        self.ref_keyword    = ref_keyword.lower()
        if isinstance(target_labels, list):
            target_labels = dict(zip(targets, target_labels))
        if isinstance(feature_labels, list):
            feature_labels = dict(zip(features or [], feature_labels))
        self.target_labels  = target_labels  or {}
        self.feature_labels = feature_labels or {}
        self.alpha          = alpha
        self.corr_threshold = corr_threshold
        self.n_estimators   = n_estimators
        self.num            = num
        self.title          = title
        self.subtitle       = subtitle
        self._id            = f"sa_{uuid.uuid4().hex[:8]}"

    def _tlabel(self, c): return self.target_labels.get(c, c)
    def _flabel(self, c): return self.feature_labels.get(c, c)

    def _resolve_features(self, df: pd.DataFrame) -> list:
        if self._features_arg is not None:
            return [c for c in self._features_arg if c in df.columns]
        exclude = set(self.targets) | {self.split_col, self.wafer_col, self.site_col} - {None}
        num_cols = df.select_dtypes(include=[np.number]).columns.tolist()
        # Exclure colonnes avec valeurs liste/array
        clean = []
        for c in num_cols:
            if c in exclude:
                continue
            sample = df[c].dropna().head(3)
            if len(sample) == 0:
                continue
            if isinstance(sample.iloc[0], (list, np.ndarray)):
                continue
            if df[c].var() > 0:
                clean.append(c)
        return clean

    def _aggregate_by_wafer(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Réduit les données LED→wafer en calculant la médiane par wafer.
        C'est le niveau d'analyse correct pour comparer des splits de DOE.
        """
        if not self.wafer_col or self.wafer_col not in df.columns:
            return df

        # Colonnes numériques scalaires uniquement
        num_cols = []
        for c in df.select_dtypes(include=[np.number]).columns:
            sample = df[c].dropna().head(3)
            if len(sample) == 0:
                continue
            if isinstance(sample.iloc[0], (list, np.ndarray)):
                continue
            num_cols.append(c)

        grp = df.groupby(self.wafer_col)
        df_agg = grp[num_cols].median()

        # Split : mode par wafer
        if self.split_col in df.columns:
            df_agg[self.split_col] = grp[self.split_col].agg(
                lambda x: x.mode().iloc[0] if len(x.mode()) else "—"
            )

        return df_agg.reset_index()

    def _build_payload(self, df: pd.DataFrame) -> dict:
        targets  = [t for t in self.targets if t in df.columns]
        features = self._resolve_features(df)

        # ── Normaliser split ────────────────────────────────────────────────
        if self.split_col in df.columns:
            df = df.copy()
            df[self.split_col] = df[self.split_col].fillna("—").astype(str)

        splits_all = sorted(df[self.split_col].unique().tolist()) \
                     if self.split_col in df.columns else ["—"]

        # ── Réf ─────────────────────────────────────────────────────────────
        ref_split = None
        for s in splits_all:
            if self.ref_keyword in str(s).lower():
                ref_split = str(s)
                break

        tgt_labels  = {t: self._tlabel(t)  for t in targets}
        feat_labels = {f: self._flabel(f)  for f in features}

        # ── AGRÉGATION WAFER-LEVEL ────────────────────────────────────────
        # Pour la stat, on travaille sur les médianes wafer (unité indépendante)
        df_w = self._aggregate_by_wafer(df)
        n_wafers_total = len(df_w)

        # ── Balance des splits ──────────────────────────────────────────────
        split_balance = {}
        for s in splits_all:
            mask_led = (df[self.split_col] == s).values \
                       if self.split_col in df.columns else np.ones(len(df), bool)
            mask_w   = (df_w[self.split_col] == s).values \
                       if self.split_col in df_w.columns else np.ones(len(df_w), bool)
            split_balance[s] = {
                "n_leds":   int(mask_led.sum()),
                "n_wafers": int(mask_w.sum()),
                "is_ref":   s == ref_split,
            }

        # ── Normalité (Shapiro sur médianes wafer par split × target) ──────
        normality = {}
        for t in targets:
            normality[t] = {}
            for s in splits_all:
                if self.split_col in df_w.columns:
                    mask = (df_w[self.split_col] == s).values
                else:
                    mask = np.ones(len(df_w), bool)
                vals = pd.to_numeric(df_w.loc[mask, t], errors="coerce").dropna().values \
                       if t in df_w.columns else np.array([])
                n = len(vals)
                if _HAS_SCIPY and 3 <= n <= 5000:
                    try:
                        stat, p = _scipy_stats.shapiro(vals)
                        normality[t][s] = {"stat": round(float(stat), 4),
                                           "p": round(float(p), 4),
                                           "is_normal": float(p) > 0.05, "n": n}
                    except Exception:
                        normality[t][s] = {"stat": None, "p": None, "is_normal": None, "n": n}
                else:
                    normality[t][s] = {"stat": None, "p": None,
                                       "is_normal": True if n < 3 else None, "n": n}

        # ── Stats par split × target (sur médianes wafer) ──────────────────
        dist_data = {}
        for t in targets:
            dist_data[t] = {}
            for s in splits_all:
                if self.split_col in df_w.columns:
                    mask = (df_w[self.split_col] == s).values
                else:
                    mask = np.ones(len(df_w), bool)
                col_data = df_w[t] if t in df_w.columns else pd.Series(dtype=float)
                vals = pd.to_numeric(col_data.loc[mask], errors="coerce").dropna().values
                dist_data[t][s] = {"values": vals.tolist(), **_wafer_stats(vals)}

        # ── Tests statistiques pairwise (sur médianes wafer) ────────────────
        tests = {}
        for t in targets:
            pairwise = []
            test_used = "kruskal"

            # Choix du test : Welch si TOUS les groupes sont normaux
            all_normal = all(
                normality[t].get(s, {}).get("is_normal") is True
                for s in splits_all
                if split_balance[s]["n_wafers"] >= 3
            )
            test_used = "welch_t" if all_normal else "kruskal"

            # KW global
            kw = None
            if _HAS_SCIPY and len(splits_all) >= 2:
                groups_w = []
                for s in splits_all:
                    if self.split_col in df_w.columns:
                        mask = (df_w[self.split_col] == s).values
                    else:
                        mask = np.ones(len(df_w), bool)
                    col_data = df_w[t] if t in df_w.columns else pd.Series(dtype=float)
                    g = pd.to_numeric(col_data.loc[mask], errors="coerce").dropna().values
                    if len(g) >= 2:
                        groups_w.append(g)
                if len(groups_w) >= 2:
                    try:
                        H, pkw = _scipy_stats.kruskal(*groups_w)
                        kw = {"H": round(float(H), 3), "p": round(float(pkw), 4)}
                    except Exception:
                        pass

            # Paires : vs-ref en premier, puis autres
            pairs = []
            if ref_split:
                for s in splits_all:
                    if s != ref_split:
                        pairs.append((ref_split, s))
            for a_s, b_s in combinations(splits_all, 2):
                if not any(set([a_s, b_s]) == set([p[0], p[1]]) for p in pairs):
                    pairs.append((a_s, b_s))

            n_pairs = len(pairs)
            for a_s, b_s in pairs:
                if self.split_col in df_w.columns:
                    ga = pd.to_numeric(df_w.loc[df_w[self.split_col] == a_s, t]
                                       if t in df_w.columns else pd.Series(dtype=float),
                                       errors="coerce").dropna().values
                    gb = pd.to_numeric(df_w.loc[df_w[self.split_col] == b_s, t]
                                       if t in df_w.columns else pd.Series(dtype=float),
                                       errors="coerce").dropna().values
                else:
                    continue
                if len(ga) < 2 or len(gb) < 2:
                    continue
                try:
                    if _HAS_SCIPY:
                        _, p_raw = _scipy_stats.ttest_ind(ga, gb, equal_var=False)
                        p_bonf = min(float(p_raw) * max(n_pairs, 1), 1.0)
                        pooled = np.sqrt((ga.std() ** 2 + gb.std() ** 2) / 2)
                        d_cohen = float((ga.mean() - gb.mean()) / pooled) if pooled else 0.0
                        # delta vs ref : b - a si a est la ref
                        delta = float(gb.mean() - ga.mean()) if a_s == ref_split \
                                else float(ga.mean() - gb.mean())
                        delta_pct = delta / abs(ga.mean()) * 100 if ga.mean() != 0 else 0.0
                        pairwise.append(dict(
                            a=str(a_s), b=str(b_s),
                            p_raw=round(float(p_raw), 4),
                            p_bonf=round(p_bonf, 4),
                            delta=round(delta, 6),
                            delta_pct=round(delta_pct, 2),
                            cohens_d=round(d_cohen, 3),
                            significant=p_bonf < self.alpha,
                            vs_ref=a_s == ref_split or b_s == ref_split,
                            na=int(len(ga)), nb=int(len(gb)),
                        ))
                except Exception:
                    pass

            tests[t] = {
                "kw": kw, "pairwise": pairwise,
                "n_significant": sum(1 for p in pairwise if p["significant"]),
                "test_used": test_used,
            }

        # ── Table résumé vs réf ─────────────────────────────────────────────
        # {split: {target: {median, delta, delta_pct, p_bonf, significant}}}
        summary_table = {}
        for s in splits_all:
            summary_table[s] = {}
            for t in targets:
                med = dist_data[t][s].get("median")
                pw_entry = None
                if ref_split and ref_split != s:
                    for pw in tests[t]["pairwise"]:
                        a, b = pw["a"], pw["b"]
                        if (a == ref_split and b == s) or (b == ref_split and a == s):
                            pw_entry = pw
                            break
                ref_med = dist_data[t][ref_split].get("median") if ref_split else None
                delta     = (med - ref_med) if med is not None and ref_med is not None else None
                delta_pct = (delta / abs(ref_med) * 100) if delta is not None and ref_med else None
                summary_table[s][t] = {
                    "median":    round(med, 4) if med is not None else None,
                    "delta":     round(delta, 4) if delta is not None else None,
                    "delta_pct": round(delta_pct, 2) if delta_pct is not None else None,
                    "p_bonf":    pw_entry["p_bonf"] if pw_entry else None,
                    "significant": pw_entry["significant"] if pw_entry else None,
                    "cohens_d":  pw_entry["cohens_d"] if pw_entry else None,
                    "is_ref":    s == ref_split,
                }

        # ── ML sur médianes wafer ────────────────────────────────────────────
        feats_in_w = [f for f in features if f in df_w.columns]
        X_df_w = df_w[feats_in_w].copy() if feats_in_w else pd.DataFrame()
        ml = {}
        for t in targets:
            if t not in df_w.columns:
                ml[t] = None
                continue
            y = pd.to_numeric(df_w[t], errors="coerce").values
            ml[t] = _fit_rf(X_df_w, y, self.n_estimators, feats_in_w)

        # ── Corrélations features × targets (wafer level) ──────────────────
        t0 = targets[0]
        feat_arr_w = {}
        tgt_arr_w  = {}
        for f in feats_in_w:
            feat_arr_w[f] = pd.to_numeric(df_w[f], errors="coerce").values
        for t in targets:
            tgt_arr_w[t] = pd.to_numeric(df_w[t], errors="coerce").values \
                           if t in df_w.columns else np.full(len(df_w), np.nan)

        corr_matrix, pval_matrix = [], []
        for f in feats_in_w:
            row_r, row_p = [], []
            for t in targets:
                r, p = _pearson(feat_arr_w[f], tgt_arr_w[t])
                row_r.append(round(r, 3) if r is not None else None)
                row_p.append(round(p, 4) if p is not None else None)
            corr_matrix.append(row_r)
            pval_matrix.append(row_p)

        top_pairs = []
        for i, f in enumerate(feats_in_w):
            for j, t in enumerate(targets):
                r = corr_matrix[i][j] if corr_matrix else None
                if r is not None and abs(r) >= self.corr_threshold:
                    top_pairs.append({"feature": f, "target": t, "r": r})
        top_pairs.sort(key=lambda x: abs(x["r"]), reverse=True)

        # ── Feature–feature parmi top RF ─────────────────────────────────────
        top_feats_rf = []
        if ml.get(t0):
            top_feats_rf = [d["feature"] for d in ml[t0]["importance"][:8]]
        feat_feat_corr = []
        for f1, f2 in combinations(top_feats_rf, 2):
            if f1 in feat_arr_w and f2 in feat_arr_w:
                r, _ = _pearson(feat_arr_w[f1], feat_arr_w[f2])
                if r is not None:
                    feat_feat_corr.append({"f1": f1, "f2": f2, "r": round(r, 3)})
        feat_feat_corr.sort(key=lambda x: abs(x["r"]), reverse=True)

        # ── Scatter données (LED-level pour richesse, wafer-level pour stat) ─
        all_scatter = {}
        for f in feats_in_w:
            for t in targets:
                xs_w = feat_arr_w[f].tolist()
                ys_w = tgt_arr_w[t].tolist()
                sp_w = df_w[self.split_col].astype(str).tolist() \
                       if self.split_col in df_w.columns else ["—"] * len(df_w)
                wf_w = df_w[self.wafer_col].astype(str).tolist() \
                       if self.wafer_col in df_w.columns else [None] * len(df_w)
                conf_w = pd.to_numeric(df_w[self.confound_col], errors="coerce").tolist() \
                         if self.confound_col and self.confound_col in df_w.columns else None
                all_scatter[f"{f}||{t}"] = {
                    "x": xs_w, "y": ys_w, "split": sp_w, "wafer": wf_w, "conf": conf_w
                }

        # ── Uniformité (CV par wafer par target, LED-level) ──────────────────
        uniformity = {}
        if self.wafer_col and self.wafer_col in df.columns:
            for t in targets:
                if t not in df.columns:
                    continue
                rows = []
                for w, grp in df.groupby(self.wafer_col):
                    vals = pd.to_numeric(grp[t], errors="coerce").dropna().values
                    if len(vals) < 2:
                        continue
                    st = _wafer_stats(vals)
                    split_val = "—"
                    if self.split_col in df.columns:
                        sv = grp[self.split_col].dropna().unique()
                        split_val = str(sv[0]) if len(sv) == 1 else "mixed"
                    rows.append({"wafer": str(w), **st, "split": split_val,
                                 "is_ref": split_val == ref_split})
                uniformity[t] = rows

        # ── Confound scatter (LED-level) ─────────────────────────────────────
        confound_scatter = {}
        if self.confound_col and self.confound_col in df.columns:
            conf_v = pd.to_numeric(df[self.confound_col], errors="coerce").tolist()
            for t in targets:
                if t not in df.columns:
                    continue
                sp = df[self.split_col].astype(str).tolist() \
                     if self.split_col in df.columns else ["—"] * len(df)
                confound_scatter[t] = {
                    "x": conf_v,
                    "y": pd.to_numeric(df[t], errors="coerce").tolist(),
                    "split": sp,
                }

        # ── Résumé ───────────────────────────────────────────────────────────
        auto_summary = []
        test_name = "Welch t-test" if tests[t0]["test_used"] == "welch_t" else "Kruskal-Wallis"
        n_sig = tests[t0]["n_significant"]
        if n_sig:
            auto_summary.append(
                f"{n_sig} paire(s) significatives sur <strong>{_h.escape(tgt_labels[t0])}</strong> "
                f"({test_name} sur {n_wafers_total} wafers, α = {self.alpha}, Bonferroni)."
            )
        else:
            auto_summary.append(
                f"Aucun écart significatif sur <strong>{_h.escape(tgt_labels[t0])}</strong> "
                f"({test_name} sur {n_wafers_total} wafers, α = {self.alpha})."
            )
        if ml.get(t0):
            top2 = [d["feature"] for d in ml[t0]["importance"][:2]]
            auto_summary.append(
                "Drivers RF (<strong>" + tgt_labels[t0] + "</strong>) : " +
                " · ".join(f"<em>{_h.escape(self._flabel(f))}</em>" for f in top2) + "."
            )
        if self.confound_col and self.confound_col in df.columns:
            conf_arr = pd.to_numeric(df[self.confound_col], errors="coerce").values
            r_conf, _ = _pearson(conf_arr, pd.to_numeric(df[t0], errors="coerce").values)
            if r_conf is not None:
                auto_summary.append(
                    f"Facteur confondant <strong>{_h.escape(self.confound_col)}</strong> : "
                    f"r = {r_conf:+.2f} avec {_h.escape(tgt_labels[t0])}."
                )
        ns = [split_balance[s]["n_wafers"] for s in splits_all]
        if len(ns) >= 2 and max(ns) > 0 and min(ns) / max(ns) < 0.5:
            auto_summary.append(
                f"⚠ Déséquilibre : {min(ns)}–{max(ns)} wafers par split "
                "— interpréter les tests avec précaution."
            )

        return dict(
            targets        = targets,
            features       = feats_in_w,
            splits         = [str(s) for s in splits_all],
            ref_split      = ref_split,
            target_labels  = tgt_labels,
            feature_labels = feat_labels,
            confound_col   = self.confound_col,
            alpha          = self.alpha,
            corr_threshold = self.corr_threshold,
            has_sklearn    = _HAS_SKLEARN,
            has_scipy      = _HAS_SCIPY,
            n_wafers       = n_wafers_total,
            kpis = dict(
                n_splits    = len(splits_all),
                n_targets   = len(targets),
                n_features  = len(feats_in_w),
                n_wafers    = n_wafers_total,
                n_leds      = len(df),
                n_sig       = sum(tests[t]["n_significant"] for t in targets),
            ),
            split_balance  = split_balance,
            normality      = normality,
            dist_data      = dist_data,
            tests          = tests,
            summary_table  = summary_table,
            ml             = ml,
            corr_matrix    = corr_matrix,
            pval_matrix    = pval_matrix,
            top_pairs      = top_pairs[:10],
            all_scatter    = all_scatter,
            uniformity     = uniformity,
            confound_scatter = confound_scatter,
            feat_feat_corr = feat_feat_corr[:8],
            top_feats_rf   = top_feats_rf,
            auto_summary   = auto_summary,
        )

    # ─────────────────────────────────────────────────────────────────────────
    #  RENDER
    # ─────────────────────────────────────────────────────────────────────────
    def render(self, store=None) -> str:
        cid = self._id
        try:
            df = self.resolve_df(store)
        except Exception as e:
            return self._error_html(str(e))
        missing = [t for t in self.targets if t not in df.columns]
        if missing:
            return self._error_html(f"Colonnes targets introuvables : {', '.join(missing)}")
        try:
            payload = self._build_payload(df)
        except Exception as e:
            import traceback
            return self._error_html(f"Erreur : {e}\n\n{traceback.format_exc()}")

        js = _j(payload)
        return f"""
<!-- StatAnalysis {cid} -->
<div class="led-block" id="{cid}_wrap">

<div class="led-block-header">
  <span class="led-block-num">{_h.escape(self.num)}</span>
  <span class="led-block-title">{_h.escape(self.title)}</span>
  <span class="led-block-sub">{_h.escape(self.subtitle)}</span>
</div>

<!-- KPI strip -->
<div id="{cid}_kpi_strip" style="display:grid;grid-template-columns:repeat(6,1fr);
  border-bottom:1px solid var(--border);background:#F8F9FD;"></div>

<!-- Toolbar : targets · tabs · splits -->
<div style="display:flex;align-items:stretch;border-bottom:1px solid var(--border);
  background:#F8F9FD;flex-wrap:wrap;min-height:42px;">
  <div style="padding:8px 14px;border-right:1px solid var(--border);
    display:flex;align-items:center;gap:6px;flex-wrap:wrap;">
    <span class="{cid}-label">TARGET</span>
    <div id="{cid}_tpills" style="display:flex;gap:5px;flex-wrap:wrap;"></div>
  </div>
  <div style="display:flex;align-items:center;gap:2px;padding:6px 10px;flex-wrap:wrap;">
    <button class="{cid}-tab active" onclick="{cid}_sw('results',this)">Résultats vs Réf</button>
    <button class="{cid}-tab"        onclick="{cid}_sw('dist',this)">Distributions</button>
    <button class="{cid}-tab"        onclick="{cid}_sw('ml',this)">Machine Learning</button>
    <button class="{cid}-tab"        onclick="{cid}_sw('corr',this)">Corrélations</button>
    <button class="{cid}-tab"        onclick="{cid}_sw('unif',this)">Uniformité</button>
  </div>
  <div style="margin-left:auto;padding:8px 14px;border-left:1px solid var(--border);
    display:flex;align-items:center;gap:6px;flex-wrap:wrap;">
    <span class="{cid}-label">SPLITS</span>
    <div id="{cid}_spills" style="display:flex;gap:4px;flex-wrap:wrap;"></div>
  </div>
</div>

<!-- Résumé auto -->
<div style="padding:10px 16px;border-bottom:1px solid var(--border);background:#FFFBF0;
  display:flex;align-items:flex-start;gap:10px;">
  <span style="font-size:16px;flex-shrink:0;margin-top:1px;">📋</span>
  <div id="{cid}_summary" style="font-family:'DM Sans',sans-serif;font-size:12px;
    color:#4A5580;line-height:1.7;"></div>
</div>

<!-- ═══ TAB : Résultats vs Réf ═══════════════════════════════════════════════ -->
<div id="{cid}_T_results">
  <!-- Table héro -->
  <div style="padding:16px 20px;border-bottom:1px solid var(--border);">
    <div class="{cid}-section-title">RÉSULTATS PAR SPLIT vs RÉFÉRENCE — médiane sur wafers</div>
    <div id="{cid}_res_table" style="overflow-x:auto;margin-top:8px;"></div>
  </div>
  <!-- Forest plot delta% -->
  <div style="padding:4px 0 0 0;">
    <div class="{cid}-section-title" style="padding:8px 20px;">
      DELTA% vs RÉFÉRENCE — <span id="{cid}_forest_tgt"></span>
    </div>
    <div id="{cid}_forest" style="height:360px;"></div>
  </div>
</div>

<!-- ═══ TAB : Distributions ═══════════════════════════════════════════════════ -->
<div id="{cid}_T_dist" style="display:none;">
  <div style="display:grid;grid-template-columns:1fr 1fr;border-bottom:1px solid var(--border);">
    <!-- Violin / box par split -->
    <div style="border-right:1px solid var(--border);">
      <div class="{cid}-section-title" id="{cid}_dist_title">DISTRIBUTION PAR SPLIT — médiane wafer</div>
      <div id="{cid}_violin" style="height:420px;"></div>
    </div>
    <!-- Stats panel -->
    <div>
      <div class="{cid}-section-title" id="{cid}_test_title">TESTS STATISTIQUES</div>
      <div id="{cid}_tests" style="padding:12px 16px;overflow-y:auto;height:380px;"></div>
    </div>
  </div>
  <!-- Confound scatter -->
  <div id="{cid}_conf_wrap" style="display:none;border-top:1px solid var(--border);">
    <div class="{cid}-section-title" id="{cid}_conf_title">FACTEUR CONFONDANT</div>
    <div id="{cid}_conf_scatter" style="height:340px;"></div>
  </div>
</div>

<!-- ═══ TAB : Machine Learning ════════════════════════════════════════════════ -->
<div id="{cid}_T_ml" style="display:none;">
  <div style="display:grid;grid-template-columns:3fr 2fr;border-bottom:1px solid var(--border);">
    <!-- Importance RF -->
    <div style="border-right:1px solid var(--border);">
      <div class="{cid}-section-title">IMPORTANCE DES VARIABLES — Random Forest sur médianes wafer</div>
      <div id="{cid}_imp" style="height:420px;"></div>
    </div>
    <!-- R² + scatter top feature -->
    <div>
      <div class="{cid}-section-title" id="{cid}_pdp_title">TOP FEATURE vs TARGET</div>
      <div id="{cid}_pdp" style="height:280px;"></div>
      <div id="{cid}_r2" style="padding:14px 18px;border-top:1px solid var(--border);"></div>
    </div>
  </div>
  <!-- Feature-feature corr -->
  <div style="padding:12px 20px;">
    <div class="{cid}-section-title" style="padding:0 0 8px 0;">
      COLINÉARITÉS ENTRE TOP FEATURES RF (potentiels facteurs confondants)
    </div>
    <div id="{cid}_ff_corr" style="display:flex;gap:8px;flex-wrap:wrap;"></div>
  </div>
  <div id="{cid}_no_sk" style="display:none;padding:10px 16px;font-family:'IBM Plex Mono',monospace;
    font-size:10px;color:#92400E;background:#FEF3C7;">⚠ scikit-learn non disponible</div>
</div>

<!-- ═══ TAB : Corrélations ════════════════════════════════════════════════════ -->
<div id="{cid}_T_corr" style="display:none;">
  <!-- Heatmap pleine largeur -->
  <div style="border-bottom:1px solid var(--border);">
    <div class="{cid}-section-title">CORRÉLATIONS FEATURES × TARGETS — Pearson r · niveau wafer</div>
    <div id="{cid}_heatmap" style="height:420px;"></div>
  </div>
  <!-- Top scatters -->
  <div style="padding:12px 20px;border-bottom:1px solid var(--border);">
    <div class="{cid}-section-title" style="padding:0 0 10px 0;">
      TOP CORRÉLATIONS |r| ≥ <span id="{cid}_thr_lbl"></span>
    </div>
    <div id="{cid}_top_sc" style="display:flex;gap:12px;flex-wrap:wrap;"></div>
  </div>
  <!-- Détail cellule + modal -->
  <div id="{cid}_cell_detail" style="display:none;padding:14px 20px;background:#F8F9FD;
    border-bottom:1px solid var(--border);">
    <div id="{cid}_cell_inner" style="display:flex;gap:20px;align-items:flex-start;flex-wrap:wrap;"></div>
  </div>
</div>

<!-- ═══ TAB : Uniformité ══════════════════════════════════════════════════════ -->
<div id="{cid}_T_unif" style="display:none;">
  <div style="padding:10px 20px;border-bottom:1px solid var(--border);
    font-family:'IBM Plex Mono',monospace;font-size:9px;color:#8B97BF;background:#F8F9FD;">
    💡 Analyse LED→wafer : chaque point = 1 wafer (médiane et dispersion des LEDs sur ce wafer).
    Si les wafers avec CV% élevé ont aussi une meilleure médiane → hétérogénéité procédé à investiguer.
  </div>
  <div style="display:grid;grid-template-columns:1fr 1fr;">
    <div style="border-right:1px solid var(--border);">
      <div class="{cid}-section-title" id="{cid}_unif_sc_title">MÉDIANE vs CV% — par wafer</div>
      <div id="{cid}_unif_sc" style="height:400px;"></div>
    </div>
    <div>
      <div class="{cid}-section-title">BALANCE DES SPLITS — n wafers · n LEDs</div>
      <div id="{cid}_bal_bar" style="height:280px;"></div>
      <div style="padding:10px 16px;border-top:1px solid var(--border);">
        <div class="{cid}-section-title" style="padding:0 0 6px 0;">NORMALITÉ SHAPIRO-WILK</div>
        <div id="{cid}_norm_tbl" style="overflow-y:auto;max-height:140px;"></div>
      </div>
    </div>
  </div>
</div>

</div><!-- /led-block -->

<!-- Modal scatter -->
<div id="{cid}_modal" style="display:none;position:fixed;inset:0;z-index:9999;
  background:rgba(10,36,99,.5);backdrop-filter:blur(4px);align-items:center;justify-content:center;">
  <div style="background:#fff;border-radius:8px;overflow:hidden;width:660px;max-width:95vw;
    box-shadow:0 24px 80px rgba(10,36,99,.3);">
    <div style="display:flex;align-items:center;justify-content:space-between;
      padding:12px 18px;border-bottom:1px solid #E4E8F4;background:#F8F9FD;">
      <div id="{cid}_mtitle" style="font-family:'Syne',sans-serif;font-weight:700;font-size:13px;color:#0A2463;"></div>
      <button onclick="{cid}_closeM()" style="border:none;background:none;cursor:pointer;
        color:#8B97BF;font-size:18px;padding:2px 8px;">✕</button>
    </div>
    <div id="{cid}_mstats" style="padding:6px 18px;font-family:'IBM Plex Mono',monospace;
      font-size:9px;color:#8B97BF;border-bottom:1px solid #E4E8F4;"></div>
    <div id="{cid}_mplot" style="height:400px;"></div>
  </div>
</div>

<style>
.{cid}-tab {{
  font-family:'IBM Plex Mono',monospace;font-size:8px;letter-spacing:.08em;
  text-transform:uppercase;padding:5px 12px;border:1px solid #E4E8F4;
  background:#fff;color:#8B97BF;cursor:pointer;border-radius:3px;transition:all .15s;
}}
.{cid}-tab:hover  {{ color:#0A2463;border-color:#8B97BF; }}
.{cid}-tab.active {{ background:#0A2463;color:#E5C76B;border-color:#0A2463;font-weight:600; }}
.{cid}-label {{
  font-family:'IBM Plex Mono',monospace;font-size:8px;color:#8B97BF;
  letter-spacing:.08em;text-transform:uppercase;white-space:nowrap;
}}
.{cid}-section-title {{
  padding:7px 20px;font-family:'IBM Plex Mono',monospace;font-size:9px;
  letter-spacing:.08em;text-transform:uppercase;color:#8B97BF;
  border-bottom:1px solid #E4E8F4;
}}
.{cid}-kpi-cell {{
  padding:8px 10px;font-family:'IBM Plex Mono',monospace;font-size:8px;
  text-align:center;border-right:1px solid #E4E8F4;
}}
</style>

<script id="{cid}_d" type="application/json">{js}</script>
<script>
(function(){{
"use strict";
var CID="{cid}";
var D=JSON.parse(document.getElementById(CID+"_d").textContent);

/* ── Palette ── */
var NAVY="#0A2463",GOLD="#D4AF37",S4="#8B97BF",S6="#4A5580";
var BG="#F8F9FD",SURF="#FFFFFF";
var GREEN="#10B981",RED="#EF4444",AMBER="#F59E0B";
var SPLIT_PAL=["#D4AF37","#0A2463","#2A7FD4","#8B5CF6","#10B981","#F59E0B","#EF4444","#EC4899","#14B8A6","#F97316"];
var TGT_PAL  =["#D4AF37","#8B5CF6","#10B981","#EF4444","#2A7FD4"];
var FM="'IBM Plex Mono',monospace",FD="'Syne',sans-serif",FB="'DM Sans',sans-serif";

var PLY={{responsive:true,displaylogo:false,
  modeBarButtonsToRemove:["autoScale2d","toggleSpikelines","sendDataToCloud"]}};
var BL ={{paper_bgcolor:"rgba(0,0,0,0)",plot_bgcolor:BG,
  font:{{family:FM,color:S4,size:10}},margin:{{t:16,r:16,b:40,l:40}}}};

var ST={{target:D.targets[0],splits:D.splits.slice(),tab:"results"}};

function $$(id){{return document.getElementById(CID+"_"+id);}}
function tl(t){{return D.target_labels[t]||t;}}
function fl(f){{return D.feature_labels[f]||f;}}
function esc(s){{return String(s).replace(/&/g,"&amp;").replace(/</g,"&lt;");}}
function scol(s){{
  if(s===D.ref_split) return GOLD;
  return SPLIT_PAL[D.splits.indexOf(s)%SPLIT_PAL.length];
}}
function hexRgb(h){{return [parseInt(h.slice(1,3),16),parseInt(h.slice(3,5),16),parseInt(h.slice(5,7),16)];}}
function rgba(h,a){{var c=hexRgb(h);return"rgba("+c[0]+","+c[1]+","+c[2]+","+a+")";}}
function lr(xs,ys){{
  var n=xs.length,mx=0,my=0,i,num=0,den=0;
  for(i=0;i<n;i++){{mx+=xs[i];my+=ys[i];}} mx/=n;my/=n;
  for(i=0;i<n;i++){{num+=(xs[i]-mx)*(ys[i]-my);den+=(xs[i]-mx)*(xs[i]-mx);}}
  var a=den?num/den:0;return{{a:a,b:my-a*mx}};
}}
function pearson(xs,ys){{
  var n=xs.length,mx=0,my=0,i,num=0,dx=0,dy=0;
  for(i=0;i<n;i++){{mx+=xs[i];my+=ys[i];}} mx/=n;my/=n;
  for(i=0;i<n;i++){{num+=(xs[i]-mx)*(ys[i]-my);dx+=(xs[i]-mx)*(xs[i]-mx);dy+=(ys[i]-my)*(ys[i]-my);}}
  return Math.sqrt(dx*dy)?num/Math.sqrt(dx*dy):0;
}}

/* ── KPI strip ── */
function renderKPIs(){{
  var items=[
    {{l:"WAFERS",v:D.kpis.n_wafers}},
    {{l:"LEDs",v:D.kpis.n_leds}},
    {{l:"SPLITS",v:D.kpis.n_splits}},
    {{l:"TARGETS",v:D.kpis.n_targets}},
    {{l:"FEATURES",v:D.kpis.n_features}},
    {{l:"ÉCARTS SIG.",v:D.kpis.n_sig}},
  ];
  $$("kpi_strip").innerHTML=items.map(function(d){{
    return '<div class="{cid}-kpi-cell">'+
      '<div style="color:'+S4+';letter-spacing:.08em;margin-bottom:4px;">'+d.l+'</div>'+
      '<div style="font-family:'+FD+';font-weight:800;font-size:24px;color:'+NAVY+';line-height:1;">'+d.v+'</div>'+
      '</div>';
  }}).join("");
  // Résumé
  $$("summary").innerHTML=(D.auto_summary||[]).join(" &nbsp;·&nbsp; ");
}}

/* ── Target pills ── */
function renderTPills(){{
  $$("tpills").innerHTML=D.targets.map(function(t,i){{
    var on=t===ST.target,c=TGT_PAL[i%TGT_PAL.length];
    return '<button onclick="'+CID+'_setT('+i+')" style="font-family:'+FM+';font-size:8px;'+
      'padding:3px 10px;border-radius:20px;cursor:pointer;border:1.5px solid '+c+';'+
      'background:'+(on?c:"transparent")+';color:'+(on?"white":c)+';transition:all .15s;">'+
      esc(tl(t).replace(/ \(.*\)/,""))+'</button>';
  }}).join("");
}}
window[CID+"_setT"]=function(i){{ST.target=D.targets[i];renderTPills();renderActive();}};

/* ── Split pills ── */
function renderSPills(){{
  $$("spills").innerHTML=D.splits.map(function(s,i){{
    var on=ST.splits.indexOf(s)>=0,c=scol(s),isRef=s===D.ref_split;
    return '<button onclick="'+CID+'_togS('+i+')" style="font-family:'+FM+';font-size:8px;'+
      'padding:3px 10px;border-radius:20px;cursor:pointer;'+
      'border:'+(isRef?"2px":"1.5px")+' solid '+c+';'+
      (isRef?'font-weight:700;':'')+
      'background:'+(on?c:"transparent")+';color:'+(on?"white":c)+';transition:all .15s;">'+
      esc(s)+(isRef?" ★":"")+'</button>';
  }}).join("");
}}
window[CID+"_togS"]=function(i){{
  var s=D.splits[i],idx=ST.splits.indexOf(s);
  if(idx>=0&&ST.splits.length>1)ST.splits.splice(idx,1);
  else if(idx<0)ST.splits.push(s);
  renderSPills();renderActive();
}};

/* ══════════════════════════════════════════════════════════════════════════
   TAB 1 — RÉSULTATS vs RÉF
══════════════════════════════════════════════════════════════════════════ */
function renderResults(){{
  renderResultsTable();
  renderForest();
}}

function renderResultsTable(){{
  var t=ST.target;
  var ss=D.splits.filter(function(s){{return ST.splits.indexOf(s)>=0;}});
  var tgts=D.targets;

  // Construire table HTML
  var html='<table style="width:100%;border-collapse:collapse;font-family:'+FM+';font-size:9px;">';
  // Header
  html+='<thead><tr style="background:#F0F3FC;">';
  html+='<th style="padding:8px 12px;text-align:left;color:'+S4+';border-bottom:2px solid #E4E8F4;'+
        'letter-spacing:.06em;min-width:140px;">SPLIT</th>';
  tgts.forEach(function(t2){{
    html+='<th style="padding:8px 12px;text-align:center;color:'+S4+';border-bottom:2px solid #E4E8F4;'+
          'letter-spacing:.06em;white-space:nowrap;border-left:1px solid #E4E8F4;">'+
          esc(tl(t2).replace(/ \(.*\)/,""))+'</th>';
  }});
  html+='</tr></thead><tbody>';

  ss.forEach(function(s){{
    var isRef=s===D.ref_split;
    var rowBg=isRef?rgba(GOLD,.07):"white";
    html+='<tr style="border-bottom:1px solid #E4E8F4;background:'+rowBg+';">';
    html+='<td style="padding:8px 12px;font-weight:'+(isRef?700:500)+';color:'+(isRef?GOLD:NAVY)+
          ';white-space:nowrap;">'+(isRef?"★ ":"")+esc(s)+
          (isRef?' <span style="font-size:7px;background:'+GOLD+';color:white;padding:1px 5px;'+
            'border-radius:2px;margin-left:4px;">RÉF</span>':'')+
          '<br><span style="font-size:7.5px;color:'+S4+';font-weight:400;">'+
          (D.split_balance[s]?D.split_balance[s].n_wafers+" wafers":"")+'</span></td>';

    tgts.forEach(function(t2){{
      var cell=D.summary_table[s]&&D.summary_table[s][t2];
      if(!cell){{ html+='<td style="border-left:1px solid #E4E8F4;"></td>'; return; }}
      var med=cell.median!=null?cell.median.toPrecision(4):"—";
      var dPct=cell.delta_pct;
      var sig=cell.significant;
      var pval=cell.p_bonf;
      var col=sig===true?(dPct>0?GREEN:RED):S4;
      var arrow=dPct!=null?(dPct>0?"▲":"▼"):"";
      var bg=sig===true?rgba(col,.07):"transparent";

      html+='<td style="padding:8px 10px;text-align:center;border-left:1px solid #E4E8F4;background:'+bg+'">';
      if(isRef){{
        html+='<div style="font-family:'+FD+';font-weight:700;font-size:12px;color:'+NAVY+';">'+esc(String(med))+'</div>';
      }} else {{
        html+='<div style="font-family:'+FD+';font-weight:600;font-size:11px;color:'+NAVY+';">'+esc(String(med))+'</div>';
        if(dPct!=null){{
          html+='<div style="font-size:9px;color:'+col+';font-weight:600;">'+
            arrow+(dPct>0?"+":"")+dPct.toFixed(1)+'%</div>';
        }}
        if(pval!=null){{
          var pvl=pval<0.001?"<0.001":pval.toFixed(3);
          html+='<div style="font-size:7.5px;padding:1px 5px;border-radius:8px;margin-top:2px;display:inline-block;'+
            'background:'+(sig?rgba(col,.15):"#F0F3FC")+';color:'+(sig?col:S4)+
            ';border:1px solid '+(sig?rgba(col,.3):"#E4E8F4")+';">'+
            'p='+pvl+(sig?" ✓":" n.s.")+'</div>';
        }}
      }}
      html+='</td>';
    }});
    html+='</tr>';
  }});
  html+='</tbody></table>';
  $$("res_table").innerHTML=html;
}}

function renderForest(){{
  var t=ST.target;
  $$("forest_tgt").textContent=tl(t);
  var ss=D.splits.filter(function(s){{
    return ST.splits.indexOf(s)>=0&&s!==D.ref_split;
  }});
  if(!ss.length){{ Plotly.react(CID+"_forest",[],BL,PLY); return; }}

  var vals=ss.map(function(s){{
    var c=D.summary_table[s]&&D.summary_table[s][t];
    return c?c.delta_pct:null;
  }});
  var sigs=ss.map(function(s){{
    var c=D.summary_table[s]&&D.summary_table[s][t];
    return c&&c.significant;
  }});
  var ns=ss.map(function(s){{return D.split_balance[s]?D.split_balance[s].n_wafers:1;}});
  var colors=ss.map(function(s,i){{
    return sigs[i]?(vals[i]>0?GREEN:RED):S4;
  }});

  Plotly.react(CID+"_forest",[
    {{type:"bar",orientation:"h",
      y:ss,x:vals,
      marker:{{color:colors,opacity:.85,line:{{width:0}}}},
      error_x:{{type:"data",array:ns.map(function(n){{return n>0?Math.abs(vals[ss.indexOf(ss[ns.indexOf(n)])]||0)/Math.sqrt(n)*1.96:0}}),visible:false}},
      text:vals.map(function(v,i){{return v!=null?((v>0?"+":"")+v.toFixed(1)+"%"):"n.d."}}),
      textposition:"outside",textfont:{{family:FM,size:10,color:NAVY}},
      hovertemplate:"<b>%{{y}}</b><br>Δ% = %{{x:.2f}}%<extra></extra>",
    }},
    {{type:"scatter",mode:"lines",x:[0,0],y:[-0.5,ss.length-0.5],
      line:{{color:GOLD,width:2,dash:"dot"}},showlegend:false,hoverinfo:"skip"}},
  ],Object.assign({{}},BL,{{
    margin:{{t:16,r:80,b:40,l:140}},
    xaxis:{{title:{{text:"Δ% vs référence",font:{{family:FM,size:9}}}},tickfont:{{family:FM,size:9}},
      gridcolor:"#E4E8F4",zeroline:false}},
    yaxis:{{tickfont:{{family:FM,size:11,color:NAVY}},gridcolor:"transparent",autorange:"reversed"}},
    shapes:[{{type:"line",x0:0,x1:0,y0:-0.5,y1:ss.length-0.5,
      line:{{color:GOLD,width:2,dash:"dot"}}}}],
  }}),PLY);
}}

/* ══════════════════════════════════════════════════════════════════════════
   TAB 2 — DISTRIBUTIONS
══════════════════════════════════════════════════════════════════════════ */
function renderDist(){{
  var t=ST.target;
  var dist=D.dist_data[t]||{{}};
  var ss=D.splits.filter(function(s){{return ST.splits.indexOf(s)>=0;}});

  $$("dist_title").textContent=tl(t).toUpperCase()+" — DISTRIBUTION DES MÉDIANES WAFER PAR SPLIT";

  var violins=ss.map(function(s){{
    var vals=(dist[s]&&dist[s].values)||[];
    var hex=scol(s);
    var c=hexRgb(hex);
    var isRef=s===D.ref_split;
    return{{type:"violin",y:vals,x:vals.map(function(){{return s;}}),name:s,
      box:{{visible:true,width:.35}},meanline:{{visible:false}},
      line:{{color:hex,width:isRef?2.5:1.5}},
      fillcolor:"rgba("+c[0]+","+c[1]+","+c[2]+",.2)",
      marker:{{color:hex,size:5,opacity:.7,
        symbol:isRef?"diamond":"circle",
        line:{{color:"white",width:1}}}},
      points:"all",jitter:.25,spanmode:"soft",
      showlegend:true,legendrank:isRef?0:1}};
  }});
  Plotly.react(CID+"_violin",violins,Object.assign({{}},BL,{{
    margin:{{t:16,r:16,b:50,l:60}},
    xaxis:{{tickfont:{{family:FM,size:11,color:NAVY}},gridcolor:"transparent"}},
    yaxis:{{title:{{text:esc(tl(t)),font:{{family:FM,size:9}},standoff:6}},
      tickfont:{{family:FM,size:9}},gridcolor:"#E4E8F4"}},
    violingap:.08,
    legend:{{font:{{family:FM,size:9}},orientation:"h",y:-.12,x:.2}},
  }}),PLY);

  /* Tests panel */
  var tests=D.tests[t]||{{}};
  var pw=tests.pairwise||[];
  var used=tests.test_used==="welch_t"?"Welch t-test":"Kruskal-Wallis";
  $$("test_title").textContent="TESTS STATISTIQUES — "+used.toUpperCase();

  var kw=tests.kw;
  var html='<div style="margin-bottom:12px;padding:8px 10px;border-radius:4px;'+
    'background:'+BG+';border-left:3px solid '+GOLD+';">'+
    '<div style="font-family:'+FM+';font-size:8px;color:'+S4+';margin-bottom:2px;letter-spacing:.06em;">'+
      'TEST GLOBAL (Kruskal-Wallis)</div>'+
    '<div style="font-family:'+FD+';font-weight:800;font-size:14px;color:'+NAVY+';">'+
      (kw?"H = "+kw.H+"  ·  p = "+kw.p:"n.d.")+'</div>'+
    '<div style="font-family:'+FM+';font-size:8px;color:'+S4+';margin-top:3px;">'+
      'Pairwise : '+used+' · Bonferroni · α = '+D.alpha+
      ' · N = médianes wafer</div></div>';

  if(pw.length){{
    pw.forEach(function(p){{
      var sig=p.significant, isRef=p.vs_ref;
      var d=Math.abs(p.cohens_d);
      var col=sig?(d>0.8?RED:d>0.5?AMBER:GREEN):S4;
      var border=isRef?"2px solid "+GOLD:"1px solid "+(sig?rgba(col,.4):"#E4E8F4");
      var dPct=p.delta_pct!=null?((p.delta_pct>0?"+":"")+p.delta_pct.toFixed(1)+"%"):"";
      html+='<div style="padding:7px 10px;border-radius:4px;border:'+border+';'+
        'background:'+(sig?rgba(col,.06):BG)+';margin-bottom:6px;">'+
        '<div style="display:flex;align-items:center;justify-content:space-between;gap:6px;">'+
          '<span style="font-family:'+FD+';font-weight:600;font-size:10px;color:'+NAVY+';">'+
            (isRef?'<span style="color:'+GOLD+'">★</span> ':'')+esc(p.a)+' vs '+esc(p.b)+'</span>'+
          '<span style="font-family:'+FM+';font-size:8px;color:'+(sig?col:S4)+';">'+
            'p='+(p.p_bonf<0.001?"<0.001":p.p_bonf.toFixed(3))+'</span>'+
        '</div>'+
        '<div style="display:flex;gap:8px;margin-top:4px;align-items:center;">'+
          '<span style="font-family:'+FM+';font-size:8px;color:'+S4+';">d='+p.cohens_d.toFixed(2)+'</span>'+
          (dPct?'<span style="font-family:'+FM+';font-size:8px;color:'+col+';font-weight:600;">'+esc(dPct)+'</span>':'')+
          '<span style="margin-left:auto;font-family:'+FM+';font-size:7.5px;padding:1px 6px;border-radius:10px;'+
            'background:'+(sig?col:S4)+';color:white;">'+(sig?"✓ SIG":"n.s.")+'</span>'+
        '</div></div>';
    }});
  }}
  $$("tests").innerHTML=html;

  /* Confound scatter */
  renderConfound(t);
}}

function renderConfound(t){{
  var wrap=$$("conf_wrap");
  if(!D.confound_col||!D.confound_scatter[t]){{wrap.style.display="none";return;}}
  wrap.style.display="block";
  $$("conf_title").textContent="FACTEUR CONFONDANT : "+D.confound_col.toUpperCase()+" vs "+tl(t).toUpperCase()+" — données LED";
  var src=D.confound_scatter[t];
  var ss=D.splits.filter(function(s){{return ST.splits.indexOf(s)>=0;}});
  var bySplit={{}};
  src.x.forEach(function(x,i){{
    var s=src.split[i];
    if(ss.indexOf(s)<0||x==null||src.y[i]==null)return;
    if(!bySplit[s])bySplit[s]={{x:[],y:[]}};
    bySplit[s].x.push(x);bySplit[s].y.push(src.y[i]);
  }});
  var traces=[];
  Object.keys(bySplit).forEach(function(s){{
    var d=bySplit[s],c=scol(s);
    var reg=lr(d.x,d.y);
    var xmn=Math.min.apply(null,d.x),xmx=Math.max.apply(null,d.x);
    var r=pearson(d.x,d.y);
    traces.push({{type:"scatter",mode:"markers",name:s,x:d.x,y:d.y,
      marker:{{color:c,size:3,opacity:.45,line:{{color:"white",width:.3}}}},
      hovertemplate:"<b>"+esc(s)+"</b><br>"+esc(D.confound_col)+": %{{x:.1f}}<br>"+esc(tl(t))+": %{{y:.4f}}<extra></extra>"}});
    traces.push({{type:"scatter",mode:"lines",showlegend:false,
      x:[xmn,xmx],y:[reg.a*xmn+reg.b,reg.a*xmx+reg.b],
      line:{{color:c,width:2}},hoverinfo:"skip",
      name:"r="+r.toFixed(2)+" ("+s+")"}});
  }});
  Plotly.react(CID+"_conf_scatter",traces,Object.assign({{}},BL,{{
    margin:{{t:10,r:16,b:50,l:60}},
    xaxis:{{title:{{text:esc(D.confound_col),font:{{family:FM,size:9}}}},tickfont:{{family:FM,size:8}},gridcolor:"#E4E8F4"}},
    yaxis:{{title:{{text:esc(tl(t)),font:{{family:FM,size:9}},standoff:4}},tickfont:{{family:FM,size:8}},gridcolor:"#E4E8F4"}},
    legend:{{font:{{family:FM,size:9}},orientation:"h",y:-.15}},
  }}),PLY);
}}

/* ══════════════════════════════════════════════════════════════════════════
   TAB 3 — MACHINE LEARNING
══════════════════════════════════════════════════════════════════════════ */
function renderML(){{
  var t=ST.target,ml=D.ml[t];
  var tcol=TGT_PAL[D.targets.indexOf(t)%TGT_PAL.length];
  if(!D.has_sklearn||!ml){{
    $$("no_sk").style.display="block";
    $$("imp").innerHTML='<div style="display:flex;align-items:center;justify-content:center;height:100%;'+
      'font-family:'+FM+';font-size:10px;color:'+S4+';">sklearn non disponible</div>';
    return;
  }}
  $$("no_sk").style.display="none";

  /* Importance RF — barres horizontales */
  var imp=ml.importance.slice().reverse();
  var maxImp=Math.max.apply(null,imp.map(function(d){{return d.importance;}}));
  Plotly.react(CID+"_imp",[{{
    type:"bar",orientation:"h",
    x:imp.map(function(d){{return d.importance;}}),
    y:imp.map(function(d){{return fl(d.feature);}}),
    marker:{{
      color:imp.map(function(d){{return d.importance;}}),
      colorscale:[[0,S4],[0.5,tcol],[1,NAVY]],
      showscale:false,line:{{width:0}},
    }},
    text:imp.map(function(d){{return d.importance.toFixed(1)+"%";}}),
    textposition:"outside",textfont:{{family:FM,size:9,color:NAVY}},
    hovertemplate:"<b>%{{y}}</b><br>Importance RF : %{{x:.1f}}%<extra></extra>",
  }}],Object.assign({{}},BL,{{
    margin:{{t:16,r:55,b:40,l:160}},
    xaxis:{{title:{{text:"Importance (%)",font:{{family:FM,size:9}}}},
      tickfont:{{family:FM,size:9}},gridcolor:"#E4E8F4",range:[0,maxImp*1.25]}},
    yaxis:{{tickfont:{{family:FM,size:9,color:S6}},gridcolor:"transparent",autorange:"reversed"}},
  }}),PLY);

  /* Scatter top feature vs target, coloré par confound ou split */
  var topF=ml.importance[0]&&ml.importance[0].feature;
  if(topF){{
    $$("pdp_title").textContent=fl(topF).toUpperCase()+" → "+tl(t).toUpperCase();
    var key=topF+"||"+t;
    var src=D.all_scatter[key];
    if(src){{
      var ss2=D.splits.filter(function(s){{return ST.splits.indexOf(s)>=0;}});
      var xs=[],ys=[],cs=[],hov=[],cof=[];
      var useConf=!!(D.confound_col&&src.conf&&src.conf.some(function(v){{return v!=null;}}));
      src.x.forEach(function(x,i){{
        if(ss2.indexOf(src.split[i])<0||x==null||src.y[i]==null)return;
        xs.push(x);ys.push(src.y[i]);
        cs.push(scol(src.split[i]));
        hov.push((src.wafer&&src.wafer[i])||src.split[i]);
        if(useConf)cof.push(src.conf[i]);
      }});
      var reg=lr(xs,ys);
      var xmn=Math.min.apply(null,xs),xmx=Math.max.apply(null,xs);
      var r=pearson(xs,ys);
      var mker=useConf?{{color:cof,colorscale:"RdBu",reversescale:true,showscale:true,size:5,opacity:.8,
        line:{{color:"white",width:.4}},
        colorbar:{{thickness:8,len:.7,title:{{text:(D.confound_col||"").split(" ").slice(-1)[0],font:{{family:FM,size:7}}}},tickfont:{{family:FM,size:7}}}}}}:
        {{color:cs,size:5,opacity:.75,line:{{color:"white",width:.4}}}};
      Plotly.react(CID+"_pdp",[
        {{type:"scatter",mode:"markers",x:xs,y:ys,text:hov,showlegend:false,marker:mker,
          hovertemplate:"<b>%{{text}}</b><br>"+esc(fl(topF))+": %{{x:.3f}}<br>"+esc(tl(t))+": %{{y:.4f}}<extra></extra>"}},
        {{type:"scatter",mode:"lines",x:[xmn,xmx],y:[reg.a*xmn+reg.b,reg.a*xmx+reg.b],
          line:{{color:NAVY,width:2,dash:"dash"}},showlegend:false,hoverinfo:"skip"}},
      ],Object.assign({{}},BL,{{
        margin:{{t:10,r:useConf?75:16,b:45,l:55}},
        xaxis:{{title:{{text:esc(fl(topF)),font:{{family:FM,size:9}}}},tickfont:{{family:FM,size:8}},gridcolor:"#E4E8F4"}},
        yaxis:{{title:{{text:esc(tl(t)),font:{{family:FM,size:9}},standoff:4}},tickfont:{{family:FM,size:8}},gridcolor:"#E4E8F4"}},
        annotations:[{{x:(xmn+xmx)/2,y:reg.a*(xmn+xmx)/2+reg.b,
          text:"r="+(r>0?"+":"")+r.toFixed(2),showarrow:false,yshift:14,
          font:{{family:FM,size:9,color:NAVY}},bgcolor:"white",bordercolor:GOLD,borderwidth:1,borderpad:3}}],
      }}),PLY);
    }}
  }}

  /* R² */
  function rbar(l,v,c,n){{
    return '<div style="margin-bottom:10px;">'+
      '<div style="display:flex;justify-content:space-between;margin-bottom:4px;">'+
        '<span style="font-family:'+FM+';font-size:8px;color:'+S6+';text-transform:uppercase;letter-spacing:.06em;">'+l+'</span>'+
        '<span style="font-family:'+FD+';font-weight:800;font-size:14px;color:'+c+';">'+v.toFixed(3)+'</span></div>'+
      '<div style="background:#E4E8F4;border-radius:2px;height:6px;overflow:hidden;">'+
        '<div style="width:'+Math.max(0,Math.min(1,v))*100+'%;height:100%;background:'+c+
          ';border-radius:2px;"></div></div>'+(n?'<div style="font-family:'+FM+';font-size:7.5px;color:'+S4+';margin-top:2px;">'+n+'</div>':"");
  }}
  var dlt=ml.r2_train-ml.r2_test,dc=dlt>0.15?RED:dlt>0.08?AMBER:GREEN;
  $$("r2").innerHTML=
    '<div style="font-family:'+FM+';font-size:8px;color:'+S4+';letter-spacing:.08em;margin-bottom:10px;">'+
      'MODÈLE RF — '+esc(tl(t))+'</div>'+
    rbar("R² Train",ml.r2_train,NAVY,"Entraînement (75%)")+
    rbar("R² Test",ml.r2_test,tcol,"Test (25%)")+
    rbar("R² CV",ml.cv_mean,GREEN,"CV "+ml.cv_mean.toFixed(3)+" ± "+ml.cv_std.toFixed(3))+
    '<div style="display:flex;justify-content:space-between;margin-top:8px;padding:6px 8px;background:'+BG+';border-radius:3px;">'+
      '<span style="font-family:'+FM+';font-size:8px;color:'+S6+';">Surapprentissage Δ</span>'+
      '<span style="font-family:'+FD+';font-weight:700;font-size:13px;color:'+dc+';">'+dlt.toFixed(3)+'</span></div>';

  /* Feature–feature */
  var el=$$("ff_corr");
  var ffc=D.feat_feat_corr||[];
  if(!ffc.length){{el.innerHTML='<span style="font-family:'+FM+';font-size:9px;color:'+S4+';">Aucune colinéarité entre top features.</span>';return;}}
  el.innerHTML=ffc.map(function(p){{
    var col=Math.abs(p.r)>0.7?RED:Math.abs(p.r)>0.5?AMBER:S4;
    return '<div style="padding:5px 10px;border-radius:4px;background:'+rgba(col,.07)+';'+
      'border:1px solid '+rgba(col,.25)+';display:flex;align-items:center;gap:8px;">'+
      '<span style="font-family:'+FM+';font-size:8px;color:'+S6+';">'+esc(fl(p.f1))+' ↔ '+esc(fl(p.f2))+'</span>'+
      '<span style="font-family:'+FD+';font-weight:700;font-size:11px;color:'+col+';">'+(p.r>0?"+":"")+p.r.toFixed(2)+'</span>'+
      '</div>';
  }}).join("");
}}

/* ══════════════════════════════════════════════════════════════════════════
   TAB 4 — CORRÉLATIONS
══════════════════════════════════════════════════════════════════════════ */
function renderCorr(){{
  var feats=D.features, tgts=D.targets, Z=D.corr_matrix;
  if(!Z||!Z.length){{
    $$("heatmap").innerHTML='<div style="padding:20px;font-family:'+FM+';font-size:10px;color:'+S4+';">Aucune donnée de corrélation.</div>';
    return;
  }}
  var annots=[];
  feats.forEach(function(f,i){{
    tgts.forEach(function(t2,j){{
      var v=Z[i]&&Z[i][j]!=null?Z[i][j]:null;
      if(v===null)return;
      annots.push({{x:tl(t2),y:fl(f),text:v.toFixed(2),showarrow:false,
        font:{{family:FM,size:9,color:Math.abs(v)>0.45?(v>0?"#fff":SURF):NAVY}}}});
    }});
  }});
  Plotly.react(CID+"_heatmap",[{{
    type:"heatmap",z:Z,x:tgts.map(tl),y:feats.map(fl),
    colorscale:[[0,"#1D6FA8"],[0.5,BG],[1,GOLD]],
    zmin:-1,zmax:1,showscale:true,
    colorbar:{{thickness:12,len:.9,tickfont:{{family:FM,size:8}},
      title:{{text:"r",font:{{family:FM,size:9}}}},tickvals:[-1,-.5,0,.5,1]}},
    xgap:3,ygap:3,
    hovertemplate:"<b>%{{y}}</b> → <b>%{{x}}</b><br>r = %{{z:.3f}}<extra></extra>",
  }}],Object.assign({{}},BL,{{
    margin:{{t:16,r:80,b:80,l:140}},annotations:annots,
    xaxis:{{tickfont:{{family:FM,size:10,color:NAVY}},side:"top",tickangle:-30,gridcolor:"transparent"}},
    yaxis:{{tickfont:{{family:FM,size:9,color:S6}},gridcolor:"transparent",autorange:"reversed"}},
  }}),PLY);

  var el_hm=document.getElementById(CID+"_heatmap");
  if(el_hm._saL)el_hm.removeListener("plotly_click",el_hm._saL);
  el_hm._saL=function(ev){{
    if(!ev.points||!ev.points[0])return;
    var pt=ev.points[0];
    var fi=feats.map(fl).indexOf(pt.y),ti=tgts.map(tl).indexOf(pt.x);
    if(fi<0||ti<0)return;
    showCellDetail(feats[fi],tgts[ti],pt.z,fi,ti);
  }};
  el_hm.on("plotly_click",el_hm._saL);

  $$("thr_lbl").textContent=D.corr_threshold.toFixed(2);
  renderTopScatter();
}}

function showCellDetail(f,t2,r,fi,ti){{
  var det=$$("cell_detail"); det.style.display="block";
  var pv=D.pval_matrix[fi]&&D.pval_matrix[fi][ti];
  var pvl=pv!=null?(pv<0.001?"<0.001":pv.toFixed(3)):"n.d.";
  var col=Math.abs(r)>0.6?GOLD:Math.abs(r)>0.35?AMBER:S4;
  $$("cell_inner").innerHTML=
    '<div style="display:flex;align-items:flex-end;gap:8px;">'+
      '<div style="font-family:'+FD+';font-weight:800;font-size:40px;color:'+col+';line-height:1;">'+
        (r>0?"+":"")+r.toFixed(2)+'</div>'+
      '<div style="display:flex;flex-direction:column;gap:4px;padding-bottom:6px;">'+
        '<span style="font-family:'+FM+';font-size:9px;color:'+S4+';">R² = '+(r*r).toFixed(3)+'</span>'+
        '<span style="font-family:'+FM+';font-size:9px;color:'+S4+';">p = '+pvl+'</span>'+
      '</div></div>'+
    '<div style="font-family:'+FM+';font-size:9px;color:'+S6+';margin-bottom:8px;">'+
      esc(fl(f))+' → '+esc(tl(t2))+'</div>'+
    '<div style="background:#E4E8F4;border-radius:3px;height:5px;width:200px;overflow:hidden;margin-bottom:10px;">'+
      '<div style="width:'+Math.abs(r)*100+'%;height:100%;background:'+col+';border-radius:3px;"></div></div>'+
    '<button onclick="'+CID+'_openM('+fi+','+ti+')" style="font-family:'+FM+';font-size:8px;'+
      'padding:6px 14px;border:1.5px solid '+NAVY+';background:transparent;color:'+NAVY+';'+
      'border-radius:3px;cursor:pointer;letter-spacing:.06em;text-transform:uppercase;">↗ Voir scatter</button>';
}}

function renderTopScatter(){{
  var pairs=D.top_pairs.slice(0,8);
  var el=$$("top_sc");
  if(!pairs.length){{
    el.innerHTML='<div style="font-family:'+FM+';font-size:10px;color:'+S4+';">Aucune corrélation ≥ '+D.corr_threshold+'.</div>';
    return;
  }}
  el.innerHTML=pairs.map(function(p,idx){{
    var col=Math.abs(p.r)>0.6?GOLD:AMBER;
    return '<div style="background:white;border:1px solid #E4E8F4;border-radius:4px;overflow:hidden;'+
      'flex:1;min-width:140px;max-width:200px;cursor:pointer;" onclick="'+CID+'_openM_idx('+idx+')">'+
      '<div style="padding:5px 8px;border-bottom:1px solid #E4E8F4;display:flex;justify-content:space-between;align-items:center;">'+
        '<span style="font-family:'+FM+';font-size:7px;color:'+S6+';overflow:hidden;text-overflow:ellipsis;white-space:nowrap;max-width:110px;">'+
          esc(fl(p.feature))+'→'+esc(tl(p.target))+'</span>'+
        '<span style="font-family:'+FD+';font-weight:800;font-size:10px;color:'+col+';flex-shrink:0;margin-left:4px;">'+
          (p.r>0?"+":"")+p.r.toFixed(2)+'</span>'+
      '</div>'+
      '<div id="'+CID+'_tsc_'+idx+'" style="height:80px;"></div></div>';
  }}).join("");
  pairs.forEach(function(p,idx){{
    var src=D.all_scatter[p.feature+"||"+p.target];
    if(!src)return;
    var xs=[],ys=[],cs=[];
    src.x.forEach(function(x,i){{
      if(ST.splits.indexOf(src.split[i])<0||x==null||src.y[i]==null)return;
      xs.push(x);ys.push(src.y[i]);cs.push(scol(src.split[i]));
    }});
    if(!xs.length)return;
    var reg=lr(xs,ys);
    var xmn=Math.min.apply(null,xs),xmx=Math.max.apply(null,xs);
    Plotly.newPlot(CID+"_tsc_"+idx,[
      {{type:"scatter",mode:"markers",x:xs,y:ys,marker:{{color:cs,size:3,opacity:.6}},showlegend:false,hoverinfo:"skip"}},
      {{type:"scatter",mode:"lines",x:[xmn,xmx],y:[reg.a*xmn+reg.b,reg.a*xmx+reg.b],
        line:{{color:NAVY,width:1.5,dash:"dot"}},showlegend:false,hoverinfo:"skip"}},
    ],{{paper_bgcolor:"rgba(0,0,0,0)",plot_bgcolor:BG,
      margin:{{t:2,r:4,b:16,l:26}},showlegend:false,
      xaxis:{{tickfont:{{family:FM,size:6}},gridcolor:"#E4E8F4",nticks:4}},
      yaxis:{{tickfont:{{family:FM,size:6}},gridcolor:"#E4E8F4",nticks:4}},
    }},{{staticPlot:true,responsive:true}});
  }});
}}

/* ══════════════════════════════════════════════════════════════════════════
   TAB 5 — UNIFORMITÉ
══════════════════════════════════════════════════════════════════════════ */
function renderUnif(){{
  var t=ST.target;
  var rows=(D.uniformity&&D.uniformity[t])||[];
  var ss=D.splits.filter(function(s){{return ST.splits.indexOf(s)>=0;}});

  $$("unif_sc_title").textContent="MÉDIANE vs CV% — "+tl(t).toUpperCase()+" — chaque point = 1 wafer";

  if(!rows.length){{
    $$("unif_sc").innerHTML='<div style="padding:20px;font-family:'+FM+';font-size:10px;color:'+S4+';">'+
      'Pas de données par wafer (définir wafer_col).</div>';
    $$("bal_bar").innerHTML="";
    $$("norm_tbl").innerHTML="";
    return;
  }}

  /* Scatter médiane vs CV */
  var bySplit={{}};
  rows.filter(function(r){{return ss.indexOf(r.split)>=0;}}).forEach(function(r){{
    if(!bySplit[r.split])bySplit[r.split]={{x:[],y:[],w:[]}};
    bySplit[r.split].x.push(r.median);
    bySplit[r.split].y.push(r.cv);
    bySplit[r.split].w.push(r.wafer+" (n="+r.n+")");
  }});

  var scTraces=Object.keys(bySplit).map(function(s){{
    var d=bySplit[s],c=scol(s),isRef=s===D.ref_split;
    return {{type:"scatter",mode:"markers+text",name:s+(isRef?" ★":""),
      x:d.x,y:d.y,text:d.w,
      textposition:"top center",textfont:{{family:FM,size:7,color:S4}},
      marker:{{color:c,size:isRef?11:9,opacity:.85,
        symbol:isRef?"diamond":"circle",
        line:{{color:"white",width:1.5}}}},
      hovertemplate:"<b>%{{text}}</b><br>Médiane: %{{x:.4f}}<br>CV%: %{{y:.1f}}<extra>"+esc(s)+"</extra>"}};
  }});
  Plotly.react(CID+"_unif_sc",scTraces,Object.assign({{}},BL,{{
    margin:{{t:16,r:16,b:50,l:70}},
    xaxis:{{title:{{text:"Médiane "+esc(tl(t)),font:{{family:FM,size:9}}}},tickfont:{{family:FM,size:9}},gridcolor:"#E4E8F4"}},
    yaxis:{{title:{{text:"CV% (dispersion intra-wafer)",font:{{family:FM,size:9}},standoff:4}},tickfont:{{family:FM,size:9}},gridcolor:"#E4E8F4"}},
    legend:{{font:{{family:FM,size:9}},orientation:"h",y:-.12}},
  }}),PLY);

  /* Balance bar */
  var splits2=D.splits.filter(function(s){{return ss.indexOf(s)>=0;}});
  Plotly.react(CID+"_bal_bar",[
    {{type:"bar",name:"Wafers",x:splits2,
      y:splits2.map(function(s){{return D.split_balance[s]?D.split_balance[s].n_wafers:0;}}),
      marker:{{color:splits2.map(scol),opacity:.8,line:{{width:0}}}},
      text:splits2.map(function(s){{return D.split_balance[s]?D.split_balance[s].n_wafers+"":" "}}),
      textposition:"outside",textfont:{{family:FM,size:10,color:NAVY}},
      hovertemplate:"<b>%{{x}}</b><br>Wafers : %{{y}}<extra></extra>"}},
    {{type:"bar",name:"LEDs",x:splits2,
      y:splits2.map(function(s){{return D.split_balance[s]?D.split_balance[s].n_leds:0;}}),
      marker:{{color:splits2.map(function(s){{return rgba(scol(s),.35);}}),line:{{width:0}}}},
      hovertemplate:"<b>%{{x}}</b><br>LEDs : %{{y}}<extra></extra>",
      visible:"legendonly"}},
  ],Object.assign({{}},BL,{{
    margin:{{t:16,r:16,b:50,l:40}},
    barmode:"group",
    xaxis:{{tickfont:{{family:FM,size:10,color:NAVY}},gridcolor:"transparent"}},
    yaxis:{{title:{{text:"Count",font:{{family:FM,size:9}}}},tickfont:{{family:FM,size:9}},gridcolor:"#E4E8F4"}},
    legend:{{font:{{family:FM,size:9}},orientation:"h",y:-.15}},
  }}),PLY);

  /* Table normalité */
  var norm=D.normality[t]||{{}};
  var html='<table style="width:100%;border-collapse:collapse;font-family:'+FM+';font-size:8px;">';
  html+='<tr style="background:#F0F3FC;"><th style="padding:5px 8px;text-align:left;color:'+S4+';">Split</th>'+
    '<th style="padding:5px 8px;text-align:center;color:'+S4+';">N wafers</th>'+
    '<th style="padding:5px 8px;text-align:center;color:'+S4+';">W</th>'+
    '<th style="padding:5px 8px;text-align:center;color:'+S4+';">p</th>'+
    '<th style="padding:5px 8px;text-align:center;color:'+S4+';">Normalité</th></tr>';
  splits2.forEach(function(s){{
    var nr=norm[s]||{{}};
    var isN=nr.is_normal;
    var c=isN===true?GREEN:isN===false?AMBER:S4;
    var lbl=isN===true?"✓ Normal":isN===false?"~ Non-normal":"n.d.";
    var isRef=s===D.ref_split;
    html+='<tr style="border-bottom:1px solid #E4E8F4;background:'+(isRef?rgba(GOLD,.05):"white")+'">'+
      '<td style="padding:5px 8px;color:'+(isRef?GOLD:NAVY)+';font-weight:'+(isRef?700:400)+
        ';">'+(isRef?"★ ":"")+esc(s)+'</td>'+
      '<td style="padding:5px 8px;text-align:center;color:'+S6+';">'+(nr.n||"—")+'</td>'+
      '<td style="padding:5px 8px;text-align:center;color:'+S6+';">'+(nr.stat!=null?nr.stat.toFixed(3):"—")+'</td>'+
      '<td style="padding:5px 8px;text-align:center;color:'+S6+';">'+(nr.p!=null?(nr.p<0.001?"<0.001":nr.p.toFixed(3)):"—")+'</td>'+
      '<td style="padding:5px 8px;text-align:center;"><span style="padding:1px 6px;border-radius:8px;'+
        'background:'+rgba(c,.12)+';color:'+c+';border:1px solid '+rgba(c,.3)+';">'+lbl+'</span></td>'+
      '</tr>';
  }});
  html+='</table>';
  $$("norm_tbl").innerHTML=html;
}}

/* ══════════════════════════════════════════════════════════════════════════
   Modal
══════════════════════════════════════════════════════════════════════════ */
window[CID+"_openM"]=function(feat,tgt){{
  if(typeof feat==="number")feat=D.features[feat];
  if(typeof tgt==="number")tgt=D.targets[tgt];
  var modal=$$("modal");modal.style.display="flex";
  var src=D.all_scatter[feat+"||"+tgt];
  if(!src){{$$("mtitle").textContent="Données indisponibles";return;}}
  var ss=D.splits.filter(function(s){{return ST.splits.indexOf(s)>=0;}});
  var bySplit={{}};
  src.x.forEach(function(x,i){{
    var s=src.split[i];
    if(ss.indexOf(s)<0||x==null||src.y[i]==null)return;
    if(!bySplit[s])bySplit[s]={{x:[],y:[],w:[]}};
    bySplit[s].x.push(x);bySplit[s].y.push(src.y[i]);
    bySplit[s].w.push((src.wafer&&src.wafer[i])||s);
  }});
  var allX=[],allY=[];
  Object.values(bySplit).forEach(function(d){{allX=allX.concat(d.x);allY=allY.concat(d.y);}});
  var r=pearson(allX,allY),reg=lr(allX,allY);
  var xmn=Math.min.apply(null,allX),xmx=Math.max.apply(null,allX);
  $$("mtitle").textContent=tl(tgt)+" vs "+fl(feat);
  $$("mstats").textContent="r = "+(r>0?"+":"")+r.toFixed(3)+"  ·  R² = "+(r*r).toFixed(3)+"  ·  n = "+allX.length+" wafers";
  var traces=Object.keys(bySplit).map(function(s){{
    var d=bySplit[s],c=scol(s),isRef=s===D.ref_split;
    return{{type:"scatter",mode:"markers",name:s+(isRef?" ★":""),x:d.x,y:d.y,text:d.w,
      marker:{{color:c,size:isRef?8:6,opacity:.8,symbol:isRef?"diamond":"circle",
        line:{{color:"white",width:1}}}},
      hovertemplate:"<b>%{{text}}</b><br>"+esc(fl(feat))+": %{{x:.3f}}<br>"+esc(tl(tgt))+": %{{y:.4f}}<extra>"+esc(s)+"</extra>"}};
  }});
  traces.push({{type:"scatter",mode:"lines",name:"Régression",
    x:[xmn,xmx],y:[reg.a*xmn+reg.b,reg.a*xmx+reg.b],
    line:{{color:NAVY,width:2,dash:"dash"}},showlegend:true,hoverinfo:"skip"}});
  Plotly.react(CID+"_mplot",traces,{{
    paper_bgcolor:"rgba(0,0,0,0)",plot_bgcolor:BG,
    font:{{family:FM,color:S4,size:10}},margin:{{t:16,r:20,b:55,l:65}},
    xaxis:{{title:{{text:esc(fl(feat)),font:{{family:FM,size:10}}}},tickfont:{{family:FM,size:9}},gridcolor:"#E4E8F4"}},
    yaxis:{{title:{{text:esc(tl(tgt)),font:{{family:FM,size:10}},standoff:6}},tickfont:{{family:FM,size:9}},gridcolor:"#E4E8F4"}},
    legend:{{font:{{family:FM,size:9}},orientation:"h",y:-.15}},
    annotations:[{{x:(xmn+xmx)/2,y:reg.a*(xmn+xmx)/2+reg.b,yshift:14,
      text:"r="+(r>0?"+":"")+r.toFixed(3)+" | R²="+(r*r).toFixed(3),
      showarrow:false,font:{{family:FM,size:9,color:NAVY}},
      bgcolor:"white",bordercolor:GOLD,borderwidth:1,borderpad:4}}],
  }},PLY);
}};
window[CID+"_openM_idx"]=function(i){{
  var p=D.top_pairs[i];if(!p)return;
  window[CID+"_openM"](p.feature,p.target);
}};
window[CID+"_closeM"]=function(){{$$("modal").style.display="none";}};
$$("modal").addEventListener("click",function(e){{if(e.target===this)window[CID+"_closeM"]();}});
document.addEventListener("keydown",function(e){{if(e.key==="Escape")window[CID+"_closeM"]();}});

/* ── Switch tabs ── */
var TABS=["results","dist","ml","corr","unif"];
window[CID+"_sw"]=function(tab,btn){{
  TABS.forEach(function(x){{
    var el=$$("T_"+x);if(el)el.style.display=x===tab?"block":"none";
  }});
  document.querySelectorAll(".{cid}-tab").forEach(function(b){{b.classList.remove("active");}});
  btn.classList.add("active");
  ST.tab=tab;
  renderActive();
}};

function renderActive(){{
  if(ST.tab==="results") renderResults();
  if(ST.tab==="dist")    renderDist();
  if(ST.tab==="ml")      renderML();
  if(ST.tab==="corr")    renderCorr();
  if(ST.tab==="unif")    renderUnif();
}}

/* ── Init ── */
renderKPIs();
renderTPills();
renderSPills();
renderResults();

}})();
</script>
"""

    def _error_html(self, msg: str) -> str:
        import html as hh
        return f"""
<div class="led-block">
  <div class="led-block-header">
    <span class="led-block-num">{_h.escape(self.num)}</span>
    <span class="led-block-title">{_h.escape(self.title)}</span>
  </div>
  <div style="padding:20px 24px;font-family:'IBM Plex Mono',monospace;font-size:11px;
    color:#EF4444;white-space:pre-wrap;background:#FEF2F2;border-top:1px solid #FECACA;">
    ⚠️ {hh.escape(msg)}
  </div>
</div>
"""
