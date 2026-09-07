'use strict';
/**
 * linked_views.js — Deux projections 2D d'un même dataset avec brushing bidirectionnel.
 *
 * Principe : chaque ligne du dataset est un point dans les deux graphes.
 * Sélectionner des points dans un graphe les met en évidence dans l'autre.
 * Permet d'explorer un espace 4D comme deux coupes 2D couplées.
 *
 * Axes :
 *   X1 / Y1  → zone DnD principale (X et Y)
 *   X2 / Y2  → config panel (dropdowns)
 *
 * Brushing : plotly_selected / plotly_deselect + Plotly.restyle selectedpoints
 */
(function () {

  const CAT_COLORS = [
    '#636efa','#ef553b','#00cc96','#ab63fa','#ffa15a',
    '#19d3f3','#ff6692','#b6e880','#ff97ff','#fecb52',
  ];

  LumiereGraphBuilder.registerExtension({
    id: 'linked_views',
    label: 'Linked views',
    icon: '⛓',
    category: 'Advanced',
    description: 'Deux projections 2D couplées — brushing bidirectionnel pour explorer un espace 4D.',
    defaultConfig: { x2: '', y2: '' },

    configPanel({ columns, config, esc }) {
      const x1 = [].concat(config.x||[]).filter(Boolean)[0] || '';
      const y1 = [].concat(config.y||[]).filter(Boolean)[0] || '';
      const selOpts = (val) =>
        '<option value="">—</option>' +
        columns
          .filter(c => c.type !== 'vector' && c.type !== 'matrix')
          .map(c => `<option value="${esc(c.name)}" ${c.name===val?'selected':''}>${esc(c.name)} · ${c.type}</option>`)
          .join('');
      return `
        <div style="font-size:10px;color:#6b7891;margin-bottom:8px;line-height:1.6">
          <b>Vue 1</b> · X=<code style="background:#f1f5f9;padding:0 3px;border-radius:3px">${esc(x1||'—')}</code>
          Y=<code style="background:#f1f5f9;padding:0 3px;border-radius:3px">${esc(y1||'—')}</code><br>
          <span style="font-style:italic">Glisse les colonnes sur les axes X / Y principaux</span>
        </div>
        <div class="gbr-cfg-row"><span>Vue 2 · X2</span>
          <select class="gbr-cfg-select" data-cfg="x2">${selOpts(config.x2||'')}</select>
        </div>
        <div class="gbr-cfg-row"><span>Vue 2 · Y2</span>
          <select class="gbr-cfg-select" data-cfg="y2">${selOpts(config.y2||'')}</select>
        </div>
        <div style="margin-top:10px;font-size:9px;color:#6b7891;line-height:1.6;font-style:italic">
          💡 Sélectionne des points (outil □ ou ◌) dans l'une des vues
          pour les mettre en évidence dans l'autre.
        </div>`;
    },

    render({ el, data, columns, config, Plotly, GB }) {
      const x1 = config.x, y1 = config.y;
      const x2 = config.x2 || '', y2 = config.y2 || '';

      if (!x1 || !y1) {
        el.innerHTML = '<div class="empty-canvas">Glisse des colonnes sur les axes X et Y (vue 1).</div>';
        return;
      }
      if (!x2 || !y2) {
        el.innerHTML = '<div class="empty-canvas">Configure X2 et Y2 dans ⚙ Config pour la vue 2.</div>';
        return;
      }

      const GB_ = GB || window.LumiereGraphBuilder;
      const esc  = GB_.esc.bind(GB_);

      // ── Conteneur ─────────────────────────────────────────────────────
      el.innerHTML = `
        <div class="lv-root">
          <div class="lv-pane">
            <div class="lv-header">
              <span class="lv-axis-tag">X</span>${esc(x1)}
              <span class="lv-axis-tag" style="margin-left:6px">Y</span>${esc(y1)}
              <span class="lv-hint" id="lv-hint1"></span>
            </div>
            <div class="lv-plot" id="lv-p1"></div>
          </div>
          <div class="lv-sep"></div>
          <div class="lv-pane">
            <div class="lv-header">
              <span class="lv-axis-tag">X</span>${esc(x2)}
              <span class="lv-axis-tag" style="margin-left:6px">Y</span>${esc(y2)}
              <span class="lv-hint" id="lv-hint2"></span>
            </div>
            <div class="lv-plot" id="lv-p2"></div>
          </div>
        </div>`;

      const p1 = el.querySelector('#lv-p1');
      const p2 = el.querySelector('#lv-p2');
      const hint1 = el.querySelector('#lv-hint1');
      const hint2 = el.querySelector('#lv-hint2');

      // ── Couleurs ──────────────────────────────────────────────────────
      const colorCol = config.color;
      let markerColors = '#636efa';
      if (colorCol) {
        const uniq = [...new Set(data.map(r => String(r[colorCol] ?? '')))];
        const cmap = Object.fromEntries(uniq.map((v, i) => [v, i]));
        markerColors = data.map(r => CAT_COLORS[cmap[String(r[colorCol]??'')] % CAT_COLORS.length]);
      }

      // ── Tooltip commun aux deux vues ──────────────────────────────────
      const tooltipCols = [].concat(config.tooltip || []).filter(Boolean);
      const makeText = r => {
        const lines = [
          `<b>${x1}</b>: ${r[x1] ?? ''}`, `<b>${y1}</b>: ${r[y1] ?? ''}`,
          x2!==x1 ? `<b>${x2}</b>: ${r[x2] ?? ''}` : null,
          y2!==y1 ? `<b>${y2}</b>: ${r[y2] ?? ''}` : null,
          ...tooltipCols.filter(c => ![x1,y1,x2,y2].includes(c)).map(c => `${c}: ${r[c] ?? ''}`),
        ].filter(Boolean);
        return lines.join('<br>');
      };
      const hoverText = data.map(makeText);

      // ── Construction des traces (1 trace par vue pour mapping propre) ──
      const mkTrace = (xCol, yCol) => ({
        type: 'scattergl', mode: 'markers',
        x: data.map(r => r[xCol]),
        y: data.map(r => r[yCol]),
        customdata: data.map((_, i) => i),   // indice global = clé de liaison
        text: hoverText,
        hovertemplate: '%{text}<extra></extra>',
        marker: {
          size:    config.pointSize ?? 5,
          opacity: config.opacity ?? 0.75,
          color:   markerColors,
          symbol:  config.markerSymbol || 'circle',
        },
        // Styles sélectionné / non-sélectionné (brushing)
        selected:   { marker: { color: '#ef4444', size: (config.pointSize ?? 5) * 2, opacity: 1 } },
        unselected: { marker: { opacity: 0.08 } },
        showlegend: false,
      });

      const mkLayout = (xCol, yCol, xLbl, yLbl) =>
        GB_.PlotlyBridge.makeBaseLayout(
          config, xLbl || xCol, yLbl || yCol,
          { dragmode: 'select', showlegend: false }
        );

      const cfg1 = { responsive: true, displayModeBar: true,
        modeBarButtonsToRemove: ['toImage','sendDataToCloud','autoScale2d','hoverClosestCartesian','hoverCompareCartesian'] };

      Plotly.react(p1, [mkTrace(x1, y1)], mkLayout(x1, y1, config.xLabel, config.yLabel),  cfg1);
      Plotly.react(p2, [mkTrace(x2, y2)], mkLayout(x2, y2, config.x2Label, config.y2Label), cfg1);

      // ── Brushing bidirectionnel ───────────────────────────────────────
      let _brushLock = false;  // évite les boucles infinies

      const link = (src, tgt, hintSrc, hintTgt) => {
        src.on('plotly_selected', ev => {
          if (_brushLock) return;
          const pts = ev?.points || [];
          if (!pts.length) return;
          const idxs = pts.map(p => p.customdata);
          _brushLock = true;
          Plotly.restyle(tgt, { selectedpoints: [idxs] }, [0]);
          _brushLock = false;
          const n = idxs.length;
          if (hintSrc) hintSrc.textContent = `${n} pt${n>1?'s':''} sélectionné${n>1?'s':''}`;
          if (hintTgt) hintTgt.textContent = `${n} pt${n>1?'s':''} en surbrillance`;
        });

        src.on('plotly_deselect', () => {
          if (_brushLock) return;
          _brushLock = true;
          Plotly.restyle(tgt, { selectedpoints: [null] }, [0]);
          _brushLock = false;
          if (hintSrc) hintSrc.textContent = '';
          if (hintTgt) hintTgt.textContent = '';
        });
      };

      link(p1, p2, hint1, hint2);
      link(p2, p1, hint2, hint1);
    },
  });

})();
