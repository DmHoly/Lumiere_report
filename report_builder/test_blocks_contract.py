"""
test_blocks_contract.py — Contrat de bloc pour le Report Builder.

Vérifie pour chaque bloc exporté :
  1. render() retourne une str non-vide sans <html>/<body>
  2. to_dict() retourne {"type": str, "params": dict}
  3. needs_plotly et needs_marked sont des bool déclarés au niveau classe
  4. Chemin store : render(store=store) fonctionne avec une clé str
  5. Chemin store : render(store=None) lève RuntimeError avec message clair
  6. DataStore : registration, résolution, sérialisation, edge cases
  7. validate_df : détection des problèmes de données avec messages clairs
  8. Layout : Tab, TabView, Row, Col, Grid propagent le store aux blocs imbriqués

Usage :
    cd lumiere_report
    .venv/bin/python -m pytest report_builder/test_blocks_contract.py -v
"""
from __future__ import annotations

import json
import sys
import os
import pytest
import pandas as pd
import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from report_builder.core.blocks import DataStore, DataMixin, validate_df, format_issues, DataIssue
from report_builder.core._helpers import Block
from report_builder.core.blocks.types import DataArg


# ─────────────────────────────────────────────────────────────────────────────
# Fixtures — données mock minimales
# ─────────────────────────────────────────────────────────────────────────────

def _make_mock_df(n: int = 10) -> pd.DataFrame:
    rng = np.random.default_rng(0)
    wafers = ["W1", "W2"]
    return pd.DataFrame({
        "wafername":              [wafers[i % 2] for i in range(n)],
        "Led_Name":               [f"LED_{i:03d}" for i in range(n)],
        "X":                      rng.uniform(-50, 50, n),
        "Y":                      rng.uniform(-50, 50, n),
        "EQE_max":                rng.uniform(10, 30, n),
        "Lambda_peak_at_max_EQE": rng.uniform(450, 530, n),
        "V_at_max_EQE":           rng.uniform(2.5, 3.5, n),
        "EQE_drop_pct":           rng.uniform(0, 20, n),
        "split_str":              ["REF" if i % 2 == 0 else "SPLIT_A" for i in range(n)],
        "reactor":                ["R1" if i % 3 == 0 else "R2" for i in range(n)],
        "temperature_c":          rng.uniform(800, 1000, n),
        "thickness_nm":           rng.uniform(50, 200, n),
        # Colonnes vectorielles
        "I":                      [rng.uniform(0, 10, 15).tolist() for _ in range(n)],
        "V":                      [rng.uniform(2, 4, 15).tolist()  for _ in range(n)],
        "EQE":                    [rng.uniform(5, 30, 15).tolist()  for _ in range(n)],
        "WL":                     [np.linspace(400, 700, 50).tolist() for _ in range(n)],
        "Spectra":                [
            [rng.uniform(0, 1, 50).tolist() for _ in range(5)]
            for _ in range(n)
        ],
    })


@pytest.fixture(scope="module")
def mock_df():
    return _make_mock_df(20)


@pytest.fixture(scope="module")
def mock_store(mock_df):
    store = DataStore()
    store.register("main", mock_df)
    return store


# ─────────────────────────────────────────────────────────────────────────────
# Blocs primitifs — instanciables sans données
# ─────────────────────────────────────────────────────────────────────────────

import plotly.graph_objects as go
from report_builder.core.blocks import (
    Section, Text, KPI, KPIRow, PlotlyChart, DataTable,
    PlotlyChartJSON, EQELambdaBoxplot,
)


class TestSection:
    def test_render(self):
        html = Section("Titre", "sous-titre").render()
        assert html and "Titre" in html

    def test_to_dict(self):
        d = Section("Titre").to_dict()
        assert d["type"] == "Section"
        assert "params" in d

    def test_class_flags(self):
        assert isinstance(Section.needs_plotly, bool)
        assert isinstance(Section.needs_marked, bool)


class TestText:
    def test_render_monolingual(self):
        html = Text("Hello **world**").render()
        assert html and "txt_" in html

    def test_render_bilingual(self):
        html = Text({"en": "Hello", "fr": "Bonjour"}).render()
        assert "EN" in html and "FR" in html

    def test_to_dict(self):
        d = Text("content").to_dict()
        assert d["type"] == "Text"


class TestKPIRow:
    def test_render(self):
        html = KPIRow([KPI("EQE", 25.3, unit="%"), KPI("Lambda", 460, unit="nm")]).render()
        assert "EQE" in html and "Lambda" in html

    def test_to_dict(self):
        d = KPIRow([KPI("EQE", 25)]).to_dict()
        assert d["type"] == "KPIRow"


class TestPlotlyChart:
    def test_render(self):
        fig = go.Figure(go.Scatter(x=[1, 2], y=[3, 4]))
        html = PlotlyChart(fig, height=300).render()
        assert "Plotly.newPlot" in html

    def test_needs_plotly(self):
        assert PlotlyChart.needs_plotly is True


class TestDataTable:
    def test_render_local_df(self, mock_df):
        df = mock_df[["wafername", "EQE_max", "V_at_max_EQE"]].head(5)
        html = DataTable(data=df, title="Test").render()
        assert "rb-table" in html

    def test_render_store_key(self, mock_store):
        html = DataTable(data="main").render(store=mock_store)
        assert "rb-table" in html
        assert "__DATA_STORE__" in html

    def test_missing_store_raises(self):
        block = DataTable(data="main")
        with pytest.raises(RuntimeError, match="DataStore"):
            block.render(store=None)

    def test_to_dict_with_key(self):
        d = DataTable(data="main").to_dict()
        assert d["params"]["data"] == "main"


# ─────────────────────────────────────────────────────────────────────────────
# Blocs domaine — chemins local ET store
# ─────────────────────────────────────────────────────────────────────────────

from report_builder.core.blocks import ScatterLED, ScatterSummary, SummaryBoxPlots, WaferMaps, AngularFluxBlock


class TestScatterLED:
    def _block_store(self):
        return ScatterLED(
            data="main", x_col="EQE_max", y_col="Lambda_peak_at_max_EQE",
            color_col="split_str",
            hover_cols=["Led_Name", "wafername"],
            curve_x="V", curve_y="I",
            spectra_col="Spectra", wavelength_col="WL",
            id_col="Led_Name",
        )

    def _block_local(self, mock_df):
        return ScatterLED(
            data=mock_df, x_col="EQE_max", y_col="Lambda_peak_at_max_EQE",
            color_col="split_str",
        )

    def test_render_store(self, mock_store):
        html = self._block_store().render(store=mock_store)
        assert html and len(html) > 100
        assert "__DATA_STORE__" in html      # chemin store actif
        assert "curveX" in html              # curve_x wired correctement

    def test_render_local(self, mock_df):
        html = self._block_local(mock_df).render()
        assert html and len(html) > 100
        assert "__DATA_STORE__" not in html  # chemin local : données inline

    def test_missing_store_raises(self):
        with pytest.raises(RuntimeError):
            self._block_store().render(store=None)

    def test_to_dict(self):
        d = self._block_store().to_dict()
        assert d["type"] == "ScatterLED"
        assert d["params"]["data"] == "main"

    def test_needs_plotly(self):
        assert ScatterLED.needs_plotly is True

    def test_curve_defs_in_store_path(self, mock_store):
        """curve_x/curve_y doivent être transmis au JS en chemin store."""
        html = self._block_store().render(store=mock_store)
        assert "curveX" in html and "curveY" in html


class TestScatterSummary:
    def _block(self):
        return ScatterSummary(
            data="main", x_col="EQE_max", y_col="Lambda_peak_at_max_EQE",
            color_col="wafername",
        )

    def test_render_store(self, mock_store):
        html = self._block().render(store=mock_store)
        assert html and len(html) > 100
        assert "__DATA_STORE__" in html

    def test_render_local(self, mock_df):
        html = ScatterSummary(
            data=mock_df, x_col="EQE_max", y_col="Lambda_peak_at_max_EQE",
            color_col="wafername",
        ).render()
        assert html and "__DATA_STORE__" not in html

    def test_missing_store_raises(self):
        with pytest.raises(RuntimeError):
            self._block().render(store=None)

    def test_to_dict(self):
        d = self._block().to_dict()
        assert d["type"] == "ScatterSummary"
        assert d["params"]["data"] == "main"


class TestSummaryBoxPlots:
    def _block(self):
        return SummaryBoxPlots(
            data="main",
            group_col="wafername",
            metrics={"EQE": ("EQE_max", "%"), "Lambda": ("Lambda_peak_at_max_EQE", "nm")},
        )

    def test_render_store(self, mock_store):
        html = self._block().render(store=mock_store)
        assert html and len(html) > 100
        assert "__DATA_STORE__" in html

    def test_render_local(self, mock_df):
        html = SummaryBoxPlots(
            data=mock_df,
            group_col="wafername",
            metrics={"EQE": ("EQE_max", "%")},
        ).render()
        assert html and "__DATA_STORE__" not in html

    def test_missing_store_raises(self):
        with pytest.raises(RuntimeError):
            self._block().render(store=None)

    def test_to_dict(self):
        d = self._block().to_dict()
        assert d["type"] == "SummaryBoxPlots"


class TestWaferMaps:
    def _block(self):
        return WaferMaps(
            data="main",
            x_col="X", y_col="Y", wafer_col="wafername",
            color_col="EQE_max",
            colormap_cols=["EQE_max", "V_at_max_EQE"],
            id_col="Led_Name",
            kpi_cols=["EQE_max"],
            curve_cols={"EQE": {"x": "I", "y": "EQE", "log_y": False, "xlabel": "I", "ylabel": "EQE"}},
            spectra_col="Spectra", wavelength_col="WL",
        )

    def test_render_store(self, mock_store):
        html = self._block().render(store=mock_store)
        assert html and len(html) > 100
        assert "__DATA_STORE__" in html

    def test_render_local(self, mock_df):
        html = WaferMaps(
            data=mock_df,
            x_col="X", y_col="Y", wafer_col="wafername",
            color_col="EQE_max",
            colormap_cols=["EQE_max"],
            id_col="Led_Name",
        ).render()
        assert html and "__DATA_STORE__" not in html

    def test_missing_store_raises(self):
        with pytest.raises(RuntimeError):
            self._block().render(store=None)

    def test_to_dict(self):
        d = self._block().to_dict()
        assert d["type"] == "WaferMaps"


class TestAngularFluxBlock:
    def _mock_cube(self):
        return {
            "theta_ext": [0, 6, 12, 20],
            "intensity_meas_norm": [1.0, 0.9, 0.7, 0.5],
            "intensity_lambertian_norm": [1.0, 0.95, 0.85, 0.7],
            "cumulative_flux": [0.0, 0.4, 0.8, 1.2],
            "cumulative_flux_lambertian": [0.0, 0.5, 1.0, 1.4],
            "theta_band": [0, 6, 12],
            "phi_band": [0, 90],
            "wavelength_band": [450, 460, 470],
            "band_diagram": {
                0: [[1, 2, 3], [1, 2, 2], [0, 1, 1]],
                90: [[1, 1, 2], [1, 1, 1], [0, 0, 1]],
            },
        }

    def _mock_summary_df(self):
        return pd.DataFrame({
            "key": ["m1"],
            "wafername": ["W1"],
            "pos_x": [-2], "pos_y": [-5],
            "current_mA": [4],
            "ratio_12deg": [0.82],
            "lambda_dominant": [480.5],
        })

    def _block(self, data):
        return AngularFluxBlock(data=data, cubes={"m1": self._mock_cube()})

    def test_render_store(self, mock_store):
        mock_store.register("af_summary", self._mock_summary_df())
        html = self._block("af_summary").render(store=mock_store)
        assert html and len(html) > 100
        assert "__DATA_STORE__" in html

    def test_render_local(self):
        html = self._block(self._mock_summary_df()).render()
        assert html and len(html) > 100
        assert "__DATA_STORE__" not in html

    def test_missing_store_raises(self):
        with pytest.raises(RuntimeError):
            self._block("af_summary").render(store=None)

    def test_to_dict(self):
        d = self._block(self._mock_summary_df()).to_dict()
        assert d["type"] == "AngularFluxBlock"

    def test_needs_plotly(self):
        assert AngularFluxBlock.needs_plotly is True


# ─────────────────────────────────────────────────────────────────────────────
# Contrat ABC
# ─────────────────────────────────────────────────────────────────────────────

class TestBlockABC:
    def test_cannot_instantiate_block_directly(self):
        with pytest.raises(TypeError):
            Block()

    def test_subclass_without_render_is_rejected(self):
        class Incomplete(Block):
            pass
        with pytest.raises(TypeError):
            Incomplete()

    def test_subclass_with_render_works(self):
        class Valid(Block):
            def render(self, store=None) -> str:
                return "<div>ok</div>"
        assert Valid().render() == "<div>ok</div>"


# ─────────────────────────────────────────────────────────────────────────────
# DataStore — contrat complet
# ─────────────────────────────────────────────────────────────────────────────

class TestDataStore:
    def test_register_and_resolve(self, mock_df):
        store = DataStore()
        store.register("main", mock_df)
        df = store.resolve("main")
        assert len(df) == len(mock_df)

    def test_resolve_direct_df(self, mock_df):
        store = DataStore()
        df = store.resolve(mock_df)
        assert df is mock_df

    def test_missing_key_raises(self):
        store = DataStore()
        with pytest.raises(KeyError, match="not found"):
            store.resolve("missing")

    def test_invalid_key_raises(self):
        store = DataStore()
        with pytest.raises(ValueError):
            store.register("123bad", pd.DataFrame())   # commence par un chiffre
        with pytest.raises(ValueError):
            store.register("has space", pd.DataFrame())  # espace interdit
        # tirets et points sont désormais autorisés
        store.register("led-data", pd.DataFrame())
        store.register("eqe.v2", pd.DataFrame())

    def test_chaining(self, mock_df):
        store = DataStore().register("a", mock_df).register("b", mock_df)
        assert "a" in store and "b" in store

    def test_contains_and_len(self, mock_df):
        store = DataStore()
        store.register("main", mock_df)
        assert "main" in store
        assert "other" not in store
        assert len(store) == 1

    def test_js_injection_contains_key(self, mock_df):
        store = DataStore()
        store.register("main", mock_df)
        js = store.to_js_injection()
        assert '"main"' in js
        assert "window.__DATA_STORE__" in js

    def test_js_injection_valid_json(self, mock_df):
        """Le JSON injecté doit être parseable — pas de NaN, pas d'Infinity."""
        store = DataStore()
        store.register("main", mock_df)
        js = store.to_js_injection()
        # Extraire le JSON du tableau pour la clé "main" : entre le premier [ après = et le ; suivant
        marker = 'window.__DATA_STORE__["main"] = '
        start = js.index(marker) + len(marker)
        end   = js.index(";", start)
        parsed = json.loads(js[start:end])
        assert isinstance(parsed, list)
        assert len(parsed) == len(mock_df)

    def test_nan_inf_converted_to_null(self):
        """NaN et Inf doivent devenir null dans le JSON, pas planter."""
        df = pd.DataFrame({
            "a": [1.0, float("nan"), float("inf"), float("-inf")],
            "b": ["x", "y", "z", "w"],
        })
        store = DataStore()
        store.register("test", df)
        js = store.to_js_injection()
        assert "NaN" not in js
        assert "Infinity" not in js
        # null doit être présent pour les 3 valeurs invalides
        assert js.count("null") >= 3

    def test_numpy_types_serialized(self):
        """numpy.int64, numpy.float32 etc. doivent être sérialisables."""
        df = pd.DataFrame({
            "int_col":   np.array([1, 2, 3], dtype=np.int64),
            "float_col": np.array([1.1, 2.2, 3.3], dtype=np.float32),
            "bool_col":  np.array([True, False, True], dtype=np.bool_),
        })
        store = DataStore()
        store.register("numpy", df)
        js = store.to_js_injection()   # ne doit pas lever TypeError
        assert '"numpy"' in js

    def test_empty_store_injection(self):
        js = DataStore().to_js_injection()
        assert "window.__DATA_STORE__" in js

    def test_types_centralised(self):
        from report_builder.core.blocks.types import DataArg
        from report_builder.core.blocks.data.data_mixin import DataArg as DA_mixin
        from report_builder.core.blocks.data.data_store import DataArg as DA_store
        assert DA_mixin is DataArg
        assert DA_store is DataArg

    def test_store_js_expr(self):
        expr = DataMixin.store_js_expr("my-key")
        assert '"my-key"' in expr
        assert "window.__DATA_STORE__" in expr
        assert "||[]" in expr


# ─────────────────────────────────────────────────────────────────────────────
# validate_df — détection des problèmes de données
# ─────────────────────────────────────────────────────────────────────────────

class TestValidateDf:

    # ── Cas sains ────────────────────────────────────────────────────────────

    def test_clean_df_no_issues(self, mock_df):
        issues = validate_df(mock_df, name="main")
        errors = [i for i in issues if i.level == "error"]
        assert errors == [], f"Erreurs inattendues sur un df propre : {errors}"

    # ── Vérifications globales ────────────────────────────────────────────────

    def test_not_a_dataframe(self):
        issues = validate_df([1, 2, 3], name="bad")
        assert any(i.code == "not_a_dataframe" for i in issues)
        assert all(i.level == "error" for i in issues)

    def test_empty_df_warns(self):
        issues = validate_df(pd.DataFrame({"a": []}), name="empty")
        assert any(i.code == "empty_df" for i in issues)
        assert all(i.level == "warning" for i in issues if i.code == "empty_df")

    def test_no_columns_errors(self):
        issues = validate_df(pd.DataFrame(), name="nocols")
        assert any(i.code == "no_columns" for i in issues)
        assert any(i.level == "error" for i in issues)

    # ── Noms de colonnes ─────────────────────────────────────────────────────

    def test_duplicate_columns_error(self):
        df = pd.DataFrame([[1, 2]], columns=["a", "a"])
        issues = validate_df(df, name="dup")
        assert any(i.code == "duplicate_column" for i in issues)
        assert any(i.level == "error" for i in issues)

    def test_non_string_column_name_error(self):
        df = pd.DataFrame({0: [1, 2], "b": [3, 4]})
        issues = validate_df(df, name="intcol")
        assert any(i.code == "non_string_column_name" for i in issues)

    def test_unsafe_column_name_error(self):
        df = pd.DataFrame({'val<ue': [1, 2], 'ok': [3, 4]})
        issues = validate_df(df, name="unsafe")
        assert any(i.code == "unsafe_column_name" for i in issues)

    # ── Types mixtes ──────────────────────────────────────────────────────────

    def test_mixed_types_error(self):
        """Colonne avec scalaires ET listes dans les mêmes lignes → erreur."""
        df = pd.DataFrame({
            "mixed": [1.0, [1.0, 2.0], 3.0, [4.0]],
            "ok": [1, 2, 3, 4],
        })
        issues = validate_df(df, name="mixed")
        assert any(i.code == "mixed_types" and i.column == "mixed" for i in issues)
        assert any(i.level == "error" for i in issues if i.code == "mixed_types")

    def test_pure_vector_column_ok(self, mock_df):
        """Colonne entièrement vectorielle → pas d'erreur mixed_types."""
        issues = validate_df(mock_df, name="main")
        assert not any(i.code == "mixed_types" for i in issues)

    # ── NaN / Inf scalaires ───────────────────────────────────────────────────

    def test_all_nan_column_warns(self):
        df = pd.DataFrame({"empty_col": [np.nan, np.nan, np.nan], "ok": [1, 2, 3]})
        issues = validate_df(df, name="nan")
        assert any(i.code == "all_nan" and i.column == "empty_col" for i in issues)
        assert all(i.level == "warning" for i in issues if i.code == "all_nan")

    def test_inf_values_warn(self):
        df = pd.DataFrame({"x": [1.0, float("inf"), 3.0]})
        issues = validate_df(df, name="inf")
        assert any(i.code == "inf_values" for i in issues)
        assert all(i.level == "warning" for i in issues if i.code == "inf_values")

    def test_high_nan_ratio_warns(self):
        vals = [np.nan] * 8 + [1.0, 2.0]
        df = pd.DataFrame({"sparse": vals})
        issues = validate_df(df, name="sparse")
        assert any(i.code in ("high_nan_ratio", "all_nan") for i in issues)

    # ── NaN dans les vecteurs ─────────────────────────────────────────────────

    def test_vector_nan_warns(self):
        df = pd.DataFrame({
            "spectra": [[1.0, float("nan"), 3.0], [4.0, 5.0, 6.0]],
        })
        issues = validate_df(df, name="vecnan")
        assert any(i.code == "vector_nan_or_inf" for i in issues)
        assert all(i.level == "warning" for i in issues if i.code == "vector_nan_or_inf")

    # ── Datetime ─────────────────────────────────────────────────────────────

    def test_datetime_column_warns(self):
        df = pd.DataFrame({"ts": pd.to_datetime(["2024-01-01", "2024-01-02"])})
        issues = validate_df(df, name="dates")
        assert any(i.code == "datetime_column" for i in issues)

    # ── Vecteurs trop longs ───────────────────────────────────────────────────

    def test_large_vector_warns(self):
        df = pd.DataFrame({
            "big": [list(range(1000)) for _ in range(5)],
        })
        issues = validate_df(df, name="bigvec")
        assert any(i.code == "large_vector" for i in issues)

    # ── format_issues ─────────────────────────────────────────────────────────

    def test_format_issues_no_issues(self, mock_df):
        issues = validate_df(mock_df, name="main")
        # On filtre les warnings de vecteurs longs (données mock volontairement grandes)
        errors = [i for i in issues if i.level == "error"]
        txt = format_issues(errors, name="main")
        assert "0 erreur" in txt or "✓" in txt

    def test_format_issues_with_errors(self):
        df = pd.DataFrame([[1, 2]], columns=["a", "a"])
        issues = validate_df(df, name="dup")
        txt = format_issues(issues, name="dup")
        assert "ERROR" in txt
        assert "dup" in txt

    def test_dataissue_str(self):
        issue = DataIssue(level="error", column="col", code="test", message="msg test")
        assert "ERROR" in str(issue)
        assert "col" in str(issue)
        assert "msg test" in str(issue)

    def test_issues_sorted_errors_first(self):
        df = pd.DataFrame({
            "empty": [np.nan, np.nan],
            "mixed": [1.0, [1.0, 2.0]],
        })
        issues = validate_df(df, name="order")
        levels = [i.level for i in issues]
        # Toutes les erreurs doivent précéder tous les warnings
        if "warning" in levels and "error" in levels:
            last_error  = max(i for i, l in enumerate(levels) if l == "error")
            first_warn  = min(i for i, l in enumerate(levels) if l == "warning")
            assert last_error < first_warn


# ─────────────────────────────────────────────────────────────────────────────
# Layout — Tab, TabView, Row, Col, Grid propagent le store
# ─────────────────────────────────────────────────────────────────────────────

from report_builder.core.navigation import Tab, TabView
from report_builder.core.layout import Row, Col, Grid


class TestLayout:

    def test_tab_render_content_propagates_store(self, mock_store):
        """Tab.render_content() doit passer le store à ses blocs enfants."""
        tab = Tab("Test")
        tab.add(DataTable(data="main"))
        html = tab.render_content(store=mock_store)
        assert "__DATA_STORE__" in html

    def test_tabview_render_propagates_store(self, mock_store):
        """TabView.render() doit passer le store à tous ses onglets."""
        tab1 = Tab("A")
        tab1.add(DataTable(data="main"))
        tab2 = Tab("B")
        tab2.add(Section("Titre"))
        tv = TabView([tab1, tab2])
        html = tv.render(store=mock_store)
        assert "__DATA_STORE__" in html
        assert "Titre" in html

    def test_row_render_propagates_store(self, mock_store):
        """Row.render() doit propager le store à chaque Col."""
        row = Row(ncols=2)
        row[0].add(DataTable(data="main"))
        row[1].add(Section("X"))
        html = row.render(store=mock_store)
        assert "__DATA_STORE__" in html

    def test_col_render_propagates_store(self, mock_store):
        """Col.render() doit passer le store à ses blocs."""
        col = Col()
        col.add(DataTable(data="main"))
        html = col.render(store=mock_store)
        assert "__DATA_STORE__" in html

    def test_grid_render_propagates_store(self, mock_store):
        """Grid.render() doit propager le store à chaque cellule."""
        grid = Grid(nrows=1, ncols=2)
        grid[0, 0].add(DataTable(data="main"))
        grid[0, 1].add(Section("Y"))
        html = grid.render(store=mock_store)
        assert "__DATA_STORE__" in html

    def test_tab_without_store_raises_if_bloc_needs_it(self):
        """render_content sans store doit propager le RuntimeError du bloc enfant."""
        tab = Tab("Err")
        tab.add(DataTable(data="main"))
        with pytest.raises(RuntimeError):
            tab.render_content(store=None)

    def test_tab_with_local_df_no_store_needed(self, mock_df):
        """Tab avec df locaux ne nécessite pas de store."""
        tab = Tab("Local")
        tab.add(DataTable(data=mock_df[["wafername", "EQE_max"]].head(5)))
        html = tab.render_content()
        assert "rb-table" in html
