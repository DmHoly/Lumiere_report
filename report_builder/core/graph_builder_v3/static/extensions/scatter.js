'use strict';

const _CONT_SCALES = ['Viridis','Plasma','Inferno','Magma','Cividis','Blues','Reds','Greens','YlOrRd','RdBu'];

LumiereGraphBuilder.registerExtension({
  id: 'scatter',
  label: 'Scatter',
  icon: '•',
  category: 'Basic',
  description: 'Nuage de points Plotly standard.',
  defaultConfig: { colorMode:'auto', contScale:'Viridis' },

  configPanel({ columns, config, esc }) {
    return `
      <div class="gbr-cfg-row">
        <span>Mode couleur</span>
        <select class="gbr-cfg-select" data-cfg="colorMode">
          <option value="auto"        ${config.colorMode==='auto'       ?'selected':''}>Auto (numérique→continu)</option>
          <option value="continuous"  ${config.colorMode==='continuous' ?'selected':''}>Continu (colorscale)</option>
          <option value="categorical" ${config.colorMode==='categorical'?'selected':''}>Catégoriel (discret)</option>
        </select>
      </div>
      <div class="gbr-cfg-row">
        <span>Échelle continue</span>
        <select class="gbr-cfg-select" data-cfg="contScale">
          ${_CONT_SCALES.map(s => `<option value="${s}" ${config.contScale===s?'selected':''}>${s}</option>`).join('')}
        </select>
      </div>`;
  },

  facetTraces({ filtered, xRef, yRef, cfg, colorCol, isCont, colorMap, CAT_COLORS, isFirstCell }) {
    let markerColor = '#636efa', markerExtra = {};
    if (colorCol && isCont) {
      markerColor = filtered.map(r => parseFloat(r[colorCol]));
      markerExtra = {
        colorscale: cfg.contScale||'Viridis', showscale: isFirstCell,
        colorbar: isFirstCell ? { title:{text:colorCol}, thickness:12, len:0.8 } : undefined,
      };
    } else if (colorMap && colorCol) {
      markerColor = filtered.map(r => colorMap[String(r[colorCol]??'')] || '#636efa');
    }
    const tooltipCols = [].concat(cfg.tooltip||[]).filter(Boolean);
    const hoverExtra = tooltipCols.length ? {
      text: filtered.map(r => tooltipCols.map(c=>`${c}: ${r[c]??''}`).join('<br>')),
      hovertemplate: '%{text}<extra></extra>',
    } : {};
    return [{
      type:'scattergl', mode:'markers',
      x: filtered.map(r=>r[cfg.x]), y: filtered.map(r=>r[cfg.y]),
      xaxis: xRef, yaxis: yRef,
      marker: { size:cfg.pointSize??6, opacity:cfg.opacity??0.85,
                symbol:cfg.markerSymbol||'circle', color:markerColor, ...markerExtra },
      customdata: filtered.map(r=>r.__gb_row_id),
      showlegend: false, ...hoverExtra,
    }];
  },

  render({ el, data, config, Plotly, GB }) {
    const x = config.x, y = config.y;
    if (!x || !y) { el.innerHTML = '<div class="empty-canvas">Glisse une colonne sur X et une sur Y.</div>'; return; }

    const GB_      = GB || window.LumiereGraphBuilder;
    const cols     = GB_?.columns || [];
    const xDef     = cols.find(c => c.name === x);
    const yDef     = cols.find(c => c.name === y);
    if (xDef?.type === 'vector' || xDef?.type === 'matrix' || yDef?.type === 'vector' || yDef?.type === 'matrix') {
      el.innerHTML = '<div class="empty-canvas">Les colonnes vectorielles (∿) ne sont pas supportées par le Scatter.<br>Utilise l\'extension <b>Courbes (∿)</b> pour tracer L, I, V, EQE…</div>';
      return;
    }

    const colorCol = config.color;
    const colDef   = colorCol ? cols.find(c => c.name === colorCol) : null;
    const mode     = config.colorMode || 'auto';
    const isCont   = colorCol && (mode === 'continuous' || (mode === 'auto' && colDef?.type === 'number'));

    // Size mapping
    const sizeCol = config.size;
    let sizeArr = null;
    if (sizeCol) {
      const vals = data.map(r => parseFloat(r[sizeCol]));
      const fin  = vals.filter(v => isFinite(v));
      if (fin.length) {
        const mn = Math.min(...fin), mx = Math.max(...fin), rng = mx - mn || 1;
        sizeArr = vals.map(v => isFinite(v) ? 4 + ((v - mn) / rng) * 20 : 4);
      }
    }

    // Tooltip
    const tooltipCols = [].concat(config.tooltip || []).filter(Boolean);
    const makeHover = r => tooltipCols.length
      ? tooltipCols.map(col => `${col}: ${r[col] ?? ''}`).join('<br>')
      : null;
    const traceHover = (textArr) => tooltipCols.length
      ? { text: textArr, hovertemplate: '%{text}<extra></extra>' }
      : {};

    const baseMarker = { opacity: config.opacity ?? 0.85, symbol: config.markerSymbol || 'circle' };

    let traces;

    if (isCont) {
      traces = [{
        type: 'scattergl', mode: 'markers', name: y,
        x: data.map(r => r[x]),
        y: data.map(r => r[y]),
        customdata: data.map(r => r.__gb_row_id),
        ...traceHover(data.map(r => makeHover(r))),
        marker: {
          ...baseMarker,
          size:       sizeArr || (config.pointSize ?? 6),
          color:      data.map(r => parseFloat(r[colorCol])),
          colorscale: config.contScale || 'Viridis',
          showscale:  true,
          colorbar:   { title: { text: colorCol }, thickness: 14, len: 0.8 },
        },
      }];
    } else {
      const groups = colorCol ? [...new Set(data.map(r => r[colorCol]))] : [null];
      traces = groups.map(g => {
        const rows     = g === null ? data : data.filter(r => r[colorCol] === g);
        const rowSizes = sizeArr ? rows.map(r => sizeArr[data.indexOf(r)]) : null;
        return {
          type: 'scattergl', mode: 'markers',
          name: g === null ? y : String(g),
          x: rows.map(r => r[x]),
          y: rows.map(r => r[y]),
          customdata: rows.map(r => r.__gb_row_id),
          ...traceHover(rows.map(r => makeHover(r))),
          marker: { ...baseMarker, size: rowSizes || (config.pointSize ?? 6) },
        };
      });
    }

    const base = (GB_ || window.LumiereGraphBuilder).PlotlyBridge.makeBaseLayout(
      config,
      config.xLabel || x,
      config.yLabel || y,
      { marginR: isCont ? 80 : 24, showlegend: !isCont && config.showLegend !== false }
    );

    const layout = { ...base };

    Plotly.react(el, traces, layout, { responsive: true, displayModeBar: false });
  },
});
