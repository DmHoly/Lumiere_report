"""
Core — Aledia Report Builder
Import identique à avant, zéro breaking change :
    from .report_builder import ReportBuilder, Tab, TabView, GraphBuilderV2, ...
"""
from ._helpers import Block
from .layout import Row, Col, Grid
from .blocks import (
    Section, Text, KPI, KPIRow, PlotlyChart, DataTable,
    ScatterLED, SummaryBoxPlots, ScatterSummary, ScatterDrillDown, DesignMatrixBlock,
    WaferMaps, CIEDiagram, StatAnalysis, ScatterPoint,
    Imageviewer, ELMatrixBlock, WaferComparator, PLSpectraBlock, LambdaShiftBlock, SEMWafermapBlock, SEM101WafermapBlock,
    BestWaferMapBlock, KPISparkBlock, RawDataTableBlock, TrendlineKPICard, AnomalyBlock, LotSummaryTable, LotInfoCard,
    EasterEggs, LumiereTour, SpiderChart, StatAnalysis, PlotlyChartJSON, EQELambdaBoxplot,
    MergeStoreBlock, WaferELCompareBlock, WaferCurveCompareBlock,
    SimExplorerBlock, SimMapBlock, VLCDesignBlock, VLCCompareBlock, CoreShellULEDBlock,
    AngularFluxBlock,
)
from .graph_builder_block              import GraphBuilderV2
from .graph_builder_v3.graph_builder_v3_block import GraphBuilderV3
from .navigation                       import Tab, TabView, Slide, SlideView, TitleSlide, SectionSlide, SummarySlide
from .report_builder                   import ReportBuilder
from .app_builder                      import AppBuilder, Page

__all__ = [
    "ReportBuilder", "AppBuilder", "Page",
    "Tab", "TabView", "EQELambdaBoxplot",
    "Slide", "SlideView", "TitleSlide", "SectionSlide", "SummarySlide",
    "GraphBuilderV2", "GraphBuilderV3",
    "Row", "Col", "Grid", "PlotlyChartJSON",
    "Section", "Text", "KPI", "KPIRow", "PlotlyChart", "DataTable",
    "ScatterLED", "SummaryBoxPlots", "ScatterSummary", "ScatterDrillDown", "DesignMatrixBlock",
    "WaferMaps", "CIEDiagram", "StatAnalysis", "ScatterPoint",
    "Block", "Imageviewer", "ELMatrixBlock", "WaferComparator", "PLSpectraBlock", "LambdaShiftBlock",
    "SEMWafermapBlock", "SEM101WafermapBlock", "BestWaferMapBlock", "KPISparkBlock",
    "RawDataTableBlock", "TrendlineKPICard", "AnomalyBlock", "LotSummaryTable", "LotInfoCard",
    "SpiderChart", "StatAnalysis",
    "EasterEggs", "LumiereTour", "MergeStoreBlock", "WaferELCompareBlock", "WaferCurveCompareBlock",
    "SimExplorerBlock", "SimMapBlock", "VLCDesignBlock", "VLCCompareBlock", "CoreShellULEDBlock",
    "AngularFluxBlock",
]