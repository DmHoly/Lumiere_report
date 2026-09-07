from __future__ import annotations
import json
import html as _h
from ..._helpers import Block


class PlotlyChartJSON(Block):
    """
    Bloc Plotly qui charge une figure depuis un JSON template,
    puis injecte les données depuis le DataStore au moment du render.

    Note : la logique de mapping colonnes (wafername, Lambda_Dom_at_MaxEQE, etc.)
    est spécifique au domaine Aledia EQE. Pour un usage générique, préférer PlotlyChart.
    """
    needs_plotly = True

    def __init__(self, fig_json: str, store_key: str = "main", height: int = 420,
                 caption: str = "", config: dict | None = None):
        self.fig_json  = fig_json
        self.store_key = store_key
        self.height    = height
        self.caption   = caption
        self.config    = config or {"responsive": True, "displaylogo": False}
        self._id       = f"chart_{id(self)}"

    def render(self, store=None) -> str:
        import plotly.io as pio

        fig = pio.from_json(self.fig_json)

        if store is not None:
            df = store.resolve(self.store_key)
            if df is not None:
                wafers = df["wafername"].unique().tolist()
                for trace in fig.data:
                    if trace.yaxis == "y2":
                        trace.x = df["wafername"].tolist()
                        trace.y = df["Lambda_Dom_at_MaxEQE"].tolist()
                    else:
                        trace.x = df["wafername"].tolist()
                        trace.y = df["max_EQE"].tolist()
                fig.layout.shapes = []
                for i in range(len(wafers)):
                    fig.add_shape(
                        type="line",
                        x0=i - 0.5, y0=0, x1=i - 0.5, y1=1,
                        xref="x", yref="paper",
                        line=dict(color="grey", width=2, dash="dashdot"),
                    )

        final_json = pio.to_json(fig)
        cfg_json   = json.dumps(self.config)
        cap        = f'<div class="rb-chart-caption">{_h.escape(self.caption)}</div>' if self.caption else ""
        return (
            f'<div class="rb-chart-wrap"><div id="{self._id}" style="height:{self.height}px;"></div>{cap}</div>'
            f'<script>(function(){{var s={final_json};'
            f'var l=Object.assign({{paper_bgcolor:"transparent",plot_bgcolor:"transparent",'
            f'margin:{{t:40,r:20,b:40,l:50}},font:{{family:"IBM Plex Mono,monospace",size:11,color:"#4A5580"}},'
            f'colorway:["#0A2463","#D4AF37","#3e92cc","#e85d4a","#2dc653","#9b5de5"]}},s.layout);'
            f'Plotly.newPlot("{self._id}",s.data,l,{cfg_json});}})();</script>'
        )
