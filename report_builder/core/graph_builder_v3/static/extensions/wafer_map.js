'use strict';
LumiereGraphBuilder.registerExtension({
  id: 'wafer_map', label: 'Wafer Map', icon: '◎', category: 'Specialized',
  description: 'Explorateur wafer map pour datasets avec X/Y.',
  defaultConfig: {},

  render({ el, data, config, Plotly, GB }) {
    const x = config.x || 'X', y = config.y || 'Y', color = config.color;
    if (!x || !y) { el.innerHTML = '<div class="empty-canvas">Glisse X et Y (coordonnées wafer).</div>'; return; }

    const GB_ = GB || window.LumiereGraphBuilder;
    const colorArr = color ? data.map(r => Number(r[color])) : undefined;
    const trace = {
      type: 'scattergl', mode: 'markers',
      x: data.map(r => r[x]),
      y: data.map(r => r[y]),
      customdata: data.map(r => r.__gb_row_id),
      marker: {
        size: config.pointSize ?? 12,
        opacity: config.opacity ?? 0.85,
        color: colorArr,
        colorscale: config.contScale || 'Viridis',
        showscale: !!color,
        colorbar: color ? { title: { text: color }, thickness: 14, len: 0.8 } : undefined,
        line: { width: 1 },
      },
      text: data.map(r => Object.entries(r).filter(([k]) => k !== '__gb_row_id').slice(0, 10).map(([k, v]) => `${k}: ${v}`).join('<br>')),
      hovertemplate: '%{text}<extra></extra>',
    };

    const base = GB_.PlotlyBridge.makeBaseLayout(config, config.xLabel || x, config.yLabel || y,
      { dragmode: 'select', marginR: color ? 80 : 24, showlegend: false });
    const layout = {
      ...base,
      xaxis: { ...base.xaxis, scaleanchor: 'y', scaleratio: 1 },
    };

    Plotly.react(el, [trace], layout, { responsive: true, displayModeBar: false });
  },
});
