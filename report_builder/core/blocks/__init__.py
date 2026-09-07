"""
blocks/ — Catalogue public des blocs du Report Builder.

Tous les blocs sont importés ici depuis leurs sous-dossiers respectifs.
L'API publique est inchangée : `from report_builder.core.blocks import ScatterLED` fonctionne.

Structure :
  data/        — DataStore, DataMixin, DataArg (couche données)
  primitives/  — Section, Text, KPI, KPIRow, PlotlyChart, DataTable, PlotlyChartJSON
  charts/      — ScatterLED, ScatterSummary, SummaryBoxPlots, ScatterPoint, SpiderChart, CIEDiagram
  wafer/       — WaferMaps, WaferComparator, BestWaferMapBlock, SEMWafermapBlock, EQELambdaBoxplot
  spectra/     — PLSpectraBlock, LambdaShiftBlock
  stats/       — StatAnalysis, AnomalyBlock
  tables/      — RawDataTableBlock, LotSummaryTable, LotInfoCard
  images/      — Imageviewer
  misc/        — KPISparkBlock, TrendlineKPICard, EasterEggs, LumiereTour
"""

# ── Type partagé ──────────────────────────────────────────────────────────────
from .types import DataArg

# ── Couche données ────────────────────────────────────────────────────────────
from .data.data_store import DataStore
from .data.data_mixin import DataMixin
from .data.validate   import validate_df, format_issues, DataIssue

# ── Primitives ────────────────────────────────────────────────────────────────
from .primitives.base import Section, Text, KPI, KPIRow, PlotlyChart, DataTable
from .primitives.plotly_chart_json import PlotlyChartJSON

# ── Charts ────────────────────────────────────────────────────────────────────
from .charts.scatter_led import ScatterLED
from .charts.summary import SummaryBoxPlots, ScatterSummary
from .charts.scatter_point import ScatterPoint
from .charts.scatter_drilldown import ScatterDrillDown
from .charts.design_matrix import DesignMatrixBlock
from .charts.spider_chart import SpiderChart
from .charts.cie_diagram import CIEDiagram

# ── Wafer ─────────────────────────────────────────────────────────────────────
from .wafer.wafer_maps import WaferMaps
from .wafer.wafer_comparator import WaferComparator
from .wafer.best_wafer_map import BestWaferMapBlock
from .wafer.sem_wafermap import SEMWafermapBlock
from .wafer.sem101_wafermap import SEM101WafermapBlock
from .wafer.eqe_lambda_boxplot import EQELambdaBoxplot
from .wafer.wafer_el_compare import WaferELCompareBlock
from .wafer.wafer_curve_compare import WaferCurveCompareBlock

# ── Spectres ──────────────────────────────────────────────────────────────────
from .spectra.pl_spectra import PLSpectraBlock
from .spectra.lambda_shift import LambdaShiftBlock

# ── Stats ─────────────────────────────────────────────────────────────────────
from .stats.stat_analysis import StatAnalysis
from .stats.anomaly import AnomalyBlock

# ── Tables ───────────────────────────────────────────────────────────────────
from .tables.raw_data_table import RawDataTableBlock
from .tables.lot_summary_table import LotSummaryTable
from .tables.lot_info_card import LotInfoCard

# ── Images ───────────────────────────────────────────────────────────────────
from .images.imageviewer import Imageviewer
from .images.el_matrix import ELMatrixBlock

# ── Misc ─────────────────────────────────────────────────────────────────────
from .misc.kpi_spark import KPISparkBlock
from .misc.trendline_kpi import TrendlineKPICard
from .misc.easter_eggs import EasterEggs
from .misc.lumiere_tour import LumiereTour
from .misc.merge_store import MergeStoreBlock

# ── Simulation / VLC ─────────────────────────────────────────────────────────
from .simu_explorer.SimExplorerBlock import SimExplorerBlock, SimMapBlock
from .simu_explorer.vlc_block.vlc_design import VLCDesignBlock
from .simu_explorer.vlc_block.vlc_compare import VLCCompareBlock
from .simu_explorer.core_shell_uled_block import CoreShellULEDBlock

# ── Optique ──────────────────────────────────────────────────────────────────
from .optics.angular_flux import AngularFluxBlock

__all__ = [
    # Type
    "DataArg",
    # Data layer
    "DataStore", "DataMixin", "validate_df", "format_issues", "DataIssue",
    # Primitives
    "Section", "Text", "KPI", "KPIRow", "PlotlyChart", "DataTable", "PlotlyChartJSON",
    # Charts
    "ScatterLED", "SummaryBoxPlots", "ScatterSummary", "ScatterPoint", "ScatterDrillDown", "DesignMatrixBlock", "SpiderChart", "CIEDiagram",
    # Wafer
    "WaferMaps", "WaferComparator", "BestWaferMapBlock", "SEMWafermapBlock", "SEM101WafermapBlock", "EQELambdaBoxplot", "WaferELCompareBlock", "WaferCurveCompareBlock",
    # Spectra
    "PLSpectraBlock", "LambdaShiftBlock",
    # Stats
    "StatAnalysis", "AnomalyBlock",
    # Tables
    "RawDataTableBlock", "LotSummaryTable", "LotInfoCard",
    # Images
    "Imageviewer", "ELMatrixBlock",
    # Misc
    "KPISparkBlock", "TrendlineKPICard", "EasterEggs", "LumiereTour", "MergeStoreBlock",
    # Simulation / VLC
    "SimExplorerBlock", "SimMapBlock", "VLCDesignBlock", "VLCCompareBlock", "CoreShellULEDBlock",
    # Optique
    "AngularFluxBlock",
]
