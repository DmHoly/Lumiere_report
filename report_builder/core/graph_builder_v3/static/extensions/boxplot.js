'use strict';
LumiereGraphBuilder.registerExtension({
  id: 'boxplot', label: 'Box plot', icon: '▣', category: 'Stats',
  description: 'Distribution par split / catégorie.',
  defaultConfig: {},

  facetTraces({ filtered, xRef, yRef, cfg }) {
    const x = cfg.x, y = cfg.y;
    if (!x || !y) return [];
    const groups = [...new Set(filtered.map(r => r[x]))];
    return groups.map(g => ({
      type: 'box', name: String(g),
      y: filtered.filter(r=>r[x]===g).map(r=>Number(r[y])).filter(Number.isFinite),
      xaxis: xRef, yaxis: yRef,
      boxpoints: 'outliers',
      marker: { opacity: cfg.opacity??0.85 },
      showlegend: false,
    }));
  },

  render({ el, data, config, Plotly, GB }) {
    const x = config.x, y = config.y;
    if (!x || !y) { el.innerHTML = '<div class="empty-canvas">Glisse catégorie → X et valeur → Y.</div>'; return; }

    const GB_  = GB || window.LumiereGraphBuilder;
    const cols = GB_?.columns || [];
    const yDef = cols.find(c => c.name === y);
    if (yDef?.type === 'vector' || yDef?.type === 'matrix') {
      el.innerHTML = '<div class="empty-canvas">Les colonnes vectorielles (∿) ne sont pas supportées ici.<br>Utilise l\'extension <b>Courbes (∿)</b>.</div>';
      return;
    }

    const groups = [...new Set(data.map(r => r[x]))];
    const traces = groups.map(g => ({
      type: 'box', name: String(g),
      y: data.filter(r => r[x] === g).map(r => Number(r[y])).filter(Number.isFinite),
      boxpoints: 'outliers',
      marker: { opacity: config.opacity ?? 0.85 },
    }));

    const base = GB_.PlotlyBridge.makeBaseLayout(config, config.xLabel || x, config.yLabel || y, { showlegend: false });
    Plotly.react(el, traces, base, { responsive: true, displayModeBar: false });
  },
});
