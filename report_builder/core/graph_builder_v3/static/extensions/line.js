'use strict';
LumiereGraphBuilder.registerExtension({
  id: 'line', label: 'Line', icon: '⌁', category: 'Basic',
  description: 'Courbes XY — tendances et séries temporelles.',
  defaultConfig: {},

  facetTraces({ filtered, xRef, yRef, cfg, colorCol, colorMap, CAT_COLORS }) {
    const x = cfg.x, y = cfg.y;
    if (!x || !y) return [];
    const sorted = [...filtered].sort((a,b)=>String(a[x]).localeCompare(String(b[x])));
    const groups = colorCol ? [...new Set(sorted.map(r=>r[colorCol]))] : [null];
    return groups.map((g, i) => {
      const rr = g===null ? sorted : sorted.filter(r=>r[colorCol]===g);
      const color = colorMap?.[String(g??'')] || CAT_COLORS[i%CAT_COLORS.length];
      return {
        type:'scatter', mode:'lines+markers',
        name: g===null ? y : String(g),
        x: rr.map(r=>r[x]), y: rr.map(r=>r[y]),
        xaxis: xRef, yaxis: yRef,
        line: { color, width:1.5 },
        marker: { color, size:cfg.pointSize??4, opacity:cfg.opacity??0.9, symbol:cfg.markerSymbol||'circle' },
        showlegend: false,
      };
    });
  },

  render({ el, data, config, Plotly, GB }) {
    const x = config.x, y = config.y;
    if (!x || !y) { el.innerHTML = '<div class="empty-canvas">Glisse une colonne sur X et une sur Y.</div>'; return; }

    const GB_  = GB || window.LumiereGraphBuilder;
    const cols = GB_?.columns || [];
    const xDef = cols.find(c => c.name === x), yDef = cols.find(c => c.name === y);
    if (xDef?.type === 'vector' || xDef?.type === 'matrix' || yDef?.type === 'vector' || yDef?.type === 'matrix') {
      el.innerHTML = '<div class="empty-canvas">Les colonnes vectorielles (∿) ne sont pas supportées ici.<br>Utilise l\'extension <b>Courbes (∿)</b>.</div>';
      return;
    }

    const rows   = [...data].sort((a, b) => String(a[x]).localeCompare(String(b[x])));
    const groups = config.color ? [...new Set(rows.map(r => r[config.color]))] : [null];
    const tooltipCols = [].concat(config.tooltip || []).filter(Boolean);
    const makeHover = r => tooltipCols.length
      ? tooltipCols.map(col => `${col}: ${r[col] ?? ''}`).join('<br>')
      : `${x}: ${r[x]}<br>${y}: ${r[y]}`;

    const traces = groups.map(g => {
      const rr = g === null ? rows : rows.filter(r => r[config.color] === g);
      return {
        type: 'scatter', mode: 'lines+markers',
        name: g === null ? y : String(g),
        x: rr.map(r => r[x]),
        y: rr.map(r => r[y]),
        text: rr.map(r => makeHover(r)),
        hovertemplate: '%{text}<extra></extra>',
        customdata: rr.map(r => r.__gb_row_id),
        marker: { size: config.pointSize ?? 5, opacity: config.opacity ?? 0.9, symbol: config.markerSymbol || 'circle' },
      };
    });

    const layout = GB_.PlotlyBridge.makeBaseLayout(config, config.xLabel || x, config.yLabel || y);
    Plotly.react(el, traces, layout, { responsive: true, displayModeBar: false });
  },
});
