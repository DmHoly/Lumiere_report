'use strict';
/**
 * curves.js — Tracé de courbes vectorielles / matricielles
 *
 * Mode vecteur : une courbe par ligne (vX vs vY, tous deux vecteurs)
 * Mode matrice : slider Plotly natif sur la profondeur de la matrice
 *   → nSlices traces groupées, slider = index de tranche
 *   → labels du slider = valeurs d'un vecteur compagnon de même longueur
 *
 * Sélection des axes : glisser-déposer X et Y (colonnes vector/matrix)
 */
(function () {

  const COLORS = [
    '#636efa','#ef553b','#00cc96','#ab63fa','#ffa15a',
    '#19d3f3','#ff6692','#b6e880','#ff97ff','#fecb52',
  ];

  // Coerce array elements to number (handles string-serialized vectors from some data sources).
  function toNum(arr) {
    if (!Array.isArray(arr)) return arr;
    return arr.map(v => {
      if (v == null) return null;
      if (typeof v === 'number') return v;
      const n = Number(v);
      return isNaN(n) ? null : n;
    });
  }

  function fmtVal(v) {
    if (v == null || !isFinite(v)) return String(v ?? '');
    if (Math.abs(v) >= 1e4 || (Math.abs(v) < 1e-2 && v !== 0)) return v.toExponential(3);
    return parseFloat(v.toPrecision(4)).toString();
  }

  /** Longueur de la profondeur d'une matrice (premier élément). */
  function matDepth(val) {
    if (!Array.isArray(val) || !Array.isArray(val[0])) return 0;
    return val.length;
  }

  /** Vecteurs dont la longueur === depth (sur la première ligne valide). */
  function companionVecs(columns, rows, depth) {
    return columns.filter(c => {
      if (c.type !== 'vector' && c.type !== 'matrix') return false;
      const v = rows[0]?.[c.name];
      if (!Array.isArray(v)) return false;
      // vecteur → longueur directe ; matrice → profondeur
      return v.length === depth && !Array.isArray(v[0]);
    });
  }

  LumiereGraphBuilder.registerExtension({
    id: 'curves',
    label: 'Courbes',
    icon: '∿',
    category: 'Vector',
    description: 'Tracé de courbes vectorielles (LIV, spectres…) avec slider matriciel.',

    defaultConfig: {
      groupBy: '', rowLabel: '', mode: 'lines',
      matrixIndex: 0, sliderLabelCol: '',
    },

    configPanel({ columns, config, esc }) {
      const GB   = window.LumiereGraphBuilder;
      const rows = GB.Data?.rows?.() || [];

      const vX = [].concat(config.x||[]).filter(Boolean)[0] || config.vectorX || '';
      const vY = [].concat(config.y||[]).filter(Boolean)[0] || config.vectorY || '';

      const catCols = columns.filter(c => c.type === 'string' || c.type === 'number');
      const scaCols = columns.filter(c => c.type === 'number');

      const selOpts = (list, val) =>
        '<option value="">—</option>' +
        list.map(c => `<option value="${esc(c.name)}" ${c.name===val?'selected':''}>${esc(c.name)} · ${c.type}</option>`).join('');

      const yColDef  = columns.find(c => c.name === vY);
      const isMatrix = yColDef?.type === 'matrix';

      // Profondeur de la matrice (nSlices)
      let depth = 0;
      if (isMatrix && rows.length > 0) {
        const v = rows[0][vY];
        depth = matDepth(v);
      }

      // Vecteurs compagnons de même profondeur
      const companions = isMatrix ? companionVecs(columns, rows, depth) : [];

      return `
        <div class="gbr-cfg-row" style="color:var(--gb-muted,#7a8499);font-size:10px;font-style:italic;padding:4px 0">
          X : <b>${esc(vX || '—')}</b> · Y : <b>${esc(vY || '—')}</b>
          ${isMatrix ? `<span style="margin-left:6px;background:#e0f2fe;color:#0369a1;padding:2px 6px;border-radius:4px;font-size:9px">matrice ${depth} tranches</span>` : ''}
        </div>
        <div class="gbr-cfg-row"><span>Mode</span>
          <select class="gbr-cfg-select" data-cfg="mode">
            <option value="lines"         ${config.mode==='lines'        ?'selected':''}>Lignes</option>
            <option value="markers"       ${config.mode==='markers'      ?'selected':''}>Points</option>
            <option value="lines+markers" ${config.mode==='lines+markers'?'selected':''}>Lignes + Points</option>
          </select>
        </div>
        <div class="gbr-cfg-row"><span>Grouper par</span>
          <select class="gbr-cfg-select" data-cfg="groupBy">
            ${selOpts(catCols, config.groupBy || config.color)}
          </select>
        </div>
        <div class="gbr-cfg-row"><span>Label courbe</span>
          <select class="gbr-cfg-select" data-cfg="rowLabel">
            ${selOpts([...catCols, ...scaCols], config.rowLabel)}
          </select>
        </div>
        <div class="gbr-cfg-row" style="margin-top:6px;border-top:1px solid var(--gb-border,#e5e7eb);padding-top:6px">
          <span style="font-weight:600">Point pivot</span>
        </div>
        <div class="gbr-cfg-row"><span>X scalaire</span>
          <select class="gbr-cfg-select" data-cfg="ptX">
            ${selOpts(scaCols, config.ptX)}
          </select>
        </div>
        <div class="gbr-cfg-row"><span>Y scalaire</span>
          <select class="gbr-cfg-select" data-cfg="ptY">
            ${selOpts(scaCols, config.ptY)}
          </select>
        </div>
        ${isMatrix && companions.length > 0 ? `
        <div class="gbr-cfg-row" style="margin-top:4px">
          <span>Labels slider</span>
          <select class="gbr-cfg-select" data-cfg="sliderLabelCol">
            ${selOpts(companions, config.sliderLabelCol)}
          </select>
        </div>` : ''}
      `;
    },

    render({ el, data, columns, config, Plotly, GB }) {
      const vX = [].concat(config.x||[]).filter(Boolean)[0] || config.vectorX || config._xArr?.[0];
      const vY = [].concat(config.y||[]).filter(Boolean)[0] || config.vectorY || config._yArr?.[0];

      if (!vX || !vY) {
        el.innerHTML = '<div class="empty-canvas">Glisse les colonnes vecteurs sur les axes X et Y.</div>';
        return;
      }

      const yColDef  = columns.find(c => c.name === vY);
      const isMatrix = yColDef?.type === 'matrix';
      const mode     = config.mode || 'lines';
      const groupBy  = config.groupBy || config.color || '';
      const rowLabel = config.rowLabel || '';
      const sliderLabelCol = config.sliderLabelCol || '';

      // Filtrer les lignes valides
      const valid = data.filter(r => {
        const xv = r[vX], yv = r[vY];
        if (!Array.isArray(xv)) return false;
        if (isMatrix) return Array.isArray(yv) && Array.isArray(yv[0]);
        return Array.isArray(yv);
      });

      if (!valid.length) {
        el.innerHTML = `<div class="empty-canvas">Aucune ligne avec des vecteurs valides pour "${GB.esc(vX)}" et "${GB.esc(vY)}".</div>`;
        return;
      }

      const GB_ = GB || window.LumiereGraphBuilder;
      const groups = groupBy
        ? [...new Set(valid.map(r => String(r[groupBy] ?? '')))]
        : [null];
      const colorMap = Object.fromEntries(
        groups.map((g, i) => [g ?? '__all__', COLORS[i % COLORS.length]])
      );

      // ── Mode matrice avec slider Plotly ─────────────────────────────
      if (isMatrix) {
        return _renderMatrix({ el, valid, vX, vY, mode, groups, groupBy, rowLabel,
          colorMap, sliderLabelCol, config, columns, Plotly, GB_ });
      }

      // ── Mode vecteur simple ─────────────────────────────────────────
      const traces = [];
      if (groupBy) {
        for (const g of groups) {
          const gRows = valid.filter(r => String(r[groupBy] ?? '') === g);
          const xData = [], yData = [];
          gRows.forEach(r => { xData.push(...toNum(r[vX]), null); yData.push(...toNum(r[vY]), null); });
          traces.push({
            type: 'scatter', mode, x: xData, y: yData,
            name: String(g), legendgroup: String(g), showlegend: true,
            line: { color: colorMap[g ?? '__all__'], width: 1.5 },
            marker: { color: colorMap[g ?? '__all__'], size: config.pointSize ?? 4 },
            opacity: config.opacity ?? 0.8,
          });
        }
      } else {
        valid.forEach((r, i) => {
          const name = rowLabel && r[rowLabel] != null ? String(r[rowLabel]) : `#${i + 1}`;
          const color = COLORS[i % COLORS.length];
          traces.push({
            type: 'scatter', mode, x: toNum(r[vX]), y: toNum(r[vY]), name,
            showlegend: false,
            line: { color, width: 1.2 }, marker: { color, size: config.pointSize ?? 4 },
            opacity: config.opacity ?? 0.75,
            customdata: [r.__gb_row_id],
            hovertemplate: `${GB.esc(name)}<br>x: %{x:.4g}<br>y: %{y:.4g}<extra></extra>`,
          });
        });
      }

      // ── Point pivot scalaire (ptX / ptY) ──────────────────────────────
      const ptX = config.ptX || '';
      const ptY = config.ptY || '';
      if (ptX && ptY) {
        if (groupBy) {
          for (const g of groups) {
            const gRows = valid.filter(r => String(r[groupBy] ?? '') === g);
            const px = gRows.map(r => { const v = Number(r[ptX]); return isFinite(v) ? v : null; }).filter(v => v !== null);
            const py = gRows.map(r => { const v = Number(r[ptY]); return isFinite(v) ? v : null; }).filter(v => v !== null);
            if (px.length) traces.push({
              type: 'scatter', mode: 'markers',
              x: px, y: py,
              name: String(g), legendgroup: String(g), showlegend: false,
              marker: { color: colorMap[g ?? '__all__'], size: (config.pointSize ?? 4) * 2.5, symbol: 'circle', line: { color: '#fff', width: 1.5 } },
              hovertemplate: `${GB.esc(String(g))}<br>${GB.esc(ptX)}: %{x:.4g}<br>${GB.esc(ptY)}: %{y:.4g}<extra></extra>`,
            });
          }
        } else {
          const px = valid.map(r => { const v = Number(r[ptX]); return isFinite(v) ? v : null; });
          const py = valid.map(r => { const v = Number(r[ptY]); return isFinite(v) ? v : null; });
          const pText = valid.map((r, i) => rowLabel && r[rowLabel] != null ? String(r[rowLabel]) : `#${i + 1}`);
          const pColor = valid.map((_, i) => COLORS[i % COLORS.length]);
          traces.push({
            type: 'scatter', mode: 'markers',
            x: px, y: py,
            name: `${ptY}@${ptX}`, showlegend: false,
            text: pText,
            marker: { color: pColor, size: (config.pointSize ?? 4) * 2.5, symbol: 'circle', line: { color: '#fff', width: 1.5 } },
            hovertemplate: `%{text}<br>${GB.esc(ptX)}: %{x:.4g}<br>${GB.esc(ptY)}: %{y:.4g}<extra></extra>`,
          });
        }
      }

      const autoTitle = `${vY} vs ${vX}`;
      const cfgForLayout = config.title ? config : { ...config, title: autoTitle };
      const base = GB_.PlotlyBridge.makeBaseLayout(cfgForLayout, config.xLabel || vX, config.yLabel || vY,
        { dragmode: 'zoom', showlegend: !!groupBy || config.showLegend === true });
      Plotly.react(el, traces, base, { responsive: true, displayModeBar: false });
    },
  });

  // ── Rendu matriciel avec slider Plotly natif ─────────────────────────
  function _renderMatrix({ el, valid, vX, vY, mode, groups, groupBy, rowLabel,
      colorMap, sliderLabelCol, config, columns, Plotly, GB_ }) {

    const firstRow = valid[0];
    const nSlices  = firstRow[vY].length;  // profondeur (ex: 15 courants)
    const nGroups  = groups.length;

    // Vecteur de labels pour le slider (ex: I[0..14])
    const labelVec = sliderLabelCol && firstRow[sliderLabelCol]
      ? firstRow[sliderLabelCol]
      : null;
    const sliceLabel = k => labelVec
      ? `${sliderLabelCol}=${fmtVal(labelVec[k])}`
      : `[${k}]`;

    // Construire nSlices × nGroups traces
    // trace index = k * nGroups + gi
    const traces = [];

    for (let k = 0; k < nSlices; k++) {
      for (let gi = 0; gi < nGroups; gi++) {
        const g    = groups[gi];
        const gRows = g === null ? valid : valid.filter(r => String(r[groupBy] ?? '') === g);
        const color = colorMap[g ?? '__all__'];

        // Un trace NaN-séparé par groupe (ou "tout") par tranche
        const xData = [], yData = [];
        gRows.forEach(r => {
          const slice = r[vY][k];
          if (!Array.isArray(slice)) return;
          xData.push(...toNum(r[vX]), null);
          yData.push(...toNum(slice), null);
        });
        const traceName = groupBy ? String(g ?? vY) : (rowLabel && gRows[0]?.[rowLabel] != null ? String(gRows[0][rowLabel]) : vY);
        traces.push({
          type: 'scatter', mode,
          x: xData, y: yData,
          name: traceName,
          legendgroup: String(g ?? '__all__'),
          showlegend: k === 0,
          visible: k === 0,
          line:   { color, width: groupBy ? 1.5 : 1.2 },
          marker: { color, size: config.pointSize ?? 4 },
          opacity: config.opacity ?? (groupBy ? 0.8 : 0.7),
        });
      }
    }

    // Nombre de traces par tranche = nGroups
    const tracesPerSlice = nGroups;

    // ── Slider steps ──────────────────────────────────────────────────
    const steps = Array.from({ length: nSlices }, (_, k) => {
      const visible = traces.map((_, ti) => Math.floor(ti / tracesPerSlice) === k);
      return {
        method: 'restyle',
        args: [{ visible }],
        label: sliceLabel(k),
      };
    });

    const sliderPrefix = sliderLabelCol ? `${sliderLabelCol}: ` : 'Index: ';
    const sliders = [{
      active: 0,
      steps,
      x: 0.05, len: 0.90,
      xanchor: 'left',
      y: 0,
      yanchor: 'top',
      pad: { t: 10, b: 10 },
      transition: { duration: 0, easing: 'linear' },
      currentvalue: {
        prefix: sliderPrefix,
        font:   { size: 12, color: '#1e3a5f', family: 'IBM Plex Mono,monospace' },
        xanchor: 'center',
        offset: 20,
      },
      ticklen: 5,
      tickcolor: '#cbd5e1',
      font: { size: 9, color: '#6b7891', family: 'IBM Plex Mono,monospace' },
      bgcolor: 'rgba(238,242,255,0.9)',
      bordercolor: '#c7d2fe',
      borderwidth: 1,
    }];

    const autoTitle = sliderLabelCol
      ? `${vY} vs ${vX}  (slider : ${sliderLabelCol})`
      : `${vY}[k] vs ${vX}`;
    const cfgForLayout = config.title ? config : { ...config, title: autoTitle };
    const base = GB_.PlotlyBridge.makeBaseLayout(
      cfgForLayout,
      config.xLabel || vX,
      config.yLabel || vY,
      { dragmode: 'zoom', showlegend: !!groupBy }
    );

    // Augmenter la marge basse pour laisser de la place au slider
    const layout = {
      ...base,
      margin: { ...base.margin, b: (base.margin.b || 80) + 80 },
      sliders,
    };

    Plotly.react(el, traces, layout, { responsive: true, displayModeBar: false });
  }

})();
