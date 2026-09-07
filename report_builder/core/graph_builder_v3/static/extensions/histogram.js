'use strict';
LumiereGraphBuilder.registerExtension({
  id: 'histogram', label: 'Histogram', icon: '▥', category: 'Stats',
  description: 'Histogramme numérique rapide.',
  defaultConfig: {},

  facetTraces({ filtered, xRef, yRef, cfg, colorCol, colorMap, CAT_COLORS }) {
    const x = cfg.x;
    if (!x) return [];
    const groups = colorCol ? [...new Set(filtered.map(r=>r[colorCol]))] : [null];
    return groups.map((g, i) => {
      const rr = g===null ? filtered : filtered.filter(r=>r[colorCol]===g);
      return {
        type:'histogram', name: g===null ? x : String(g),
        x: rr.map(r=>Number(r[x])).filter(Number.isFinite),
        xaxis: xRef, yaxis: yRef,
        opacity: cfg.opacity??0.75,
        marker: { color: colorMap?.[String(g??'')] || CAT_COLORS[i%CAT_COLORS.length] },
        showlegend: false,
      };
    });
  },

  render({ el, data, config, Plotly, GB }) {
    const x = config.x;
    if (!x) { el.innerHTML = '<div class="empty-canvas">Glisse une colonne numérique sur X.</div>'; return; }

    const groups = config.color ? [...new Set(data.map(r => r[config.color]))] : [null];
    const traces = groups.map(g => {
      const rr = g === null ? data : data.filter(r => r[config.color] === g);
      return {
        type: 'histogram',
        name: g === null ? x : String(g),
        x: rr.map(r => Number(r[x])).filter(Number.isFinite),
        opacity: config.opacity ?? 0.75,
      };
    });

    const GB_ = GB || window.LumiereGraphBuilder;
    const base = GB_.PlotlyBridge.makeBaseLayout(config, config.xLabel || x, config.yLabel || 'Count');
    const layout = { ...base, barmode: groups.length > 1 ? 'overlay' : 'relative' };

    Plotly.react(el, traces, layout, { responsive: true });
  },
});
