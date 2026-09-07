from __future__ import annotations
import pandas as pd
import plotly.express as px
import plotly.graph_objs as go
import plotly.io as pio

from ..._helpers import Block
from ..primitives.base import PlotlyChart


class EQELambdaBoxplot(Block):
    """
    Boxplot dual-axe EQE max / Lambda Dom at MaxEQE groupé par wafer et capteur optique.
    Spécifique au domaine Aledia (colonnes : 'Max EQE', 'Lambda Dom at Max EQE',
    'Optical_Sensor', 'wafername').
    """
    needs_plotly = True

    def __init__(self, store_key: str, height: int = 500):
        self.store_key = store_key
        self.height    = height

    @staticmethod
    def _build_fig(df: pd.DataFrame) -> str:
        plot_df = df.copy()
        plot_df["Optical_Sensor"] = plot_df["Optical_Sensor"].fillna("Unknown").astype(str)

        sensors        = sorted(plot_df["Optical_Sensor"].unique())
        palette_eqe    = px.colors.qualitative.Set2
        palette_lambda = px.colors.qualitative.Dark2
        color_eqe    = {s: palette_eqe[i % len(palette_eqe)]    for i, s in enumerate(sensors)}
        color_lambda = {s: palette_lambda[i % len(palette_lambda)] for i, s in enumerate(sensors)}
        wafers = list(plot_df["wafername"].dropna().unique())

        fig = go.Figure()
        for sensor in sensors:
            d = plot_df[plot_df["Optical_Sensor"] == sensor]
            fig.add_trace(go.Box(
                x=d["wafername"], y=d["Max EQE"],
                name=f"max_EQE - {sensor}",
                legendgroup=sensor, legendgrouptitle_text=sensor,
                marker_color=color_eqe[sensor],
                line=dict(color=color_eqe[sensor], width=1.5),
                yaxis="y", boxpoints=False, offsetgroup=sensor,
            ))
            fig.add_trace(go.Box(
                x=d["wafername"], y=d["Lambda Dom at Max EQE"],
                name=f"λ_Dom - {sensor}",
                legendgroup=sensor,
                marker_color=color_lambda[sensor],
                line=dict(color=color_lambda[sensor], width=1.5),
                fillcolor="rgba(0,0,0,0)",
                yaxis="y2", boxpoints=False, offsetgroup=sensor,
            ))

        fig.update_layout(
            title="Max EQE & Lambda_Dom_at_MaxEQE by Wafer",
            boxmode="group",
            yaxis=dict(title="max_EQE [%]"),
            yaxis2=dict(title="λ_Dom at MaxEQE [nm]", overlaying="y", side="right"),
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
            xaxis=dict(categoryorder="array", categoryarray=wafers),
        )
        for i in range(1, len(wafers)):
            fig.add_shape(
                type="line", x0=i - 0.5, x1=i - 0.5, y0=0, y1=1,
                xref="x", yref="paper",
                line=dict(color="grey", width=1, dash="dashdot"),
            )
        return pio.to_json(fig)

    def render(self, store=None) -> str:
        df = store.resolve(self.store_key)
        fig_json = self._build_fig(df)
        return PlotlyChart(pio.from_json(fig_json), height=self.height).render(store=store)
