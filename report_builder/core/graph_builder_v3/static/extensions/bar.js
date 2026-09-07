'use strict';
LumiereGraphBuilder.registerExtension({
  id: 'bar', label: 'Bar mean', icon: '▮', category: 'Basic',
  description: 'Barres agrégées par catégorie (moyenne).',
  defaultConfig: {},

  facetTraces({ filtered, xRef, yRef, cfg }) {
    const x = cfg.x, y = cfg.y;
    if (!x || !y) return [];
    const map = new Map();
    filtered.forEach(r => {
      const k=String(r[x]), v=Number(r[y]);
      if (!Number.isFinite(v)) return;
      if (!map.has(k)) map.set(k,[]);
      map.get(k).push(v);
    });
    const keys=[...map.keys()];
    const vals=keys.map(k=>map.get(k).reduce((a,b)=>a+b,0)/map.get(k).length);
    return [{ type:'bar', x:keys, y:vals,
      xaxis:xRef, yaxis:yRef,
      marker:{ opacity:cfg.opacity??0.85 },
      showlegend:false }];
  },

  render({ el, data, config, Plotly, GB }) {
    const x = config.x, y = config.y;
    if (!x || !y) { el.innerHTML = '<div class="empty-canvas">Glisse catégorie → X et valeur numérique → Y.</div>'; return; }

    const GB_  = GB || window.LumiereGraphBuilder;
    const cols = GB_?.columns || [];
    const xDef = cols.find(c => c.name === x), yDef = cols.find(c => c.name === y);
    if (xDef?.type === 'vector' || xDef?.type === 'matrix' || yDef?.type === 'vector' || yDef?.type === 'matrix') {
      el.innerHTML = '<div class="empty-canvas">Les colonnes vectorielles (∿) ne sont pas supportées ici.<br>Utilise l\'extension <b>Courbes (∿)</b>.</div>';
      return;
    }

    const map = new Map();
    data.forEach(r => {
      const k = String(r[x]); const v = Number(r[y]);
      if (!Number.isFinite(v)) return;
      if (!map.has(k)) map.set(k, []);
      map.get(k).push(v);
    });
    const keys = [...map.keys()];
    const vals = keys.map(k => map.get(k).reduce((a, b) => a + b, 0) / map.get(k).length);

    const base = GB_.PlotlyBridge.makeBaseLayout(config, config.xLabel || x, config.yLabel || `Mean(${y})`, { showlegend: false });
    const layout = { ...base, yaxis: { ...base.yaxis } };

    Plotly.react(el, [{ type: 'bar', x: keys, y: vals, name: 'mean',
      marker: { opacity: config.opacity ?? 0.85 } }],
      layout, { responsive: true, displayModeBar: false });
  },
});
