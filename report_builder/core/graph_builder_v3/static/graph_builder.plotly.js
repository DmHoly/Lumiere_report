'use strict';
(function(){
  const GB = window.LumiereGraphBuilder;

  function cloneJson(obj, fallback){
    try { return JSON.parse(JSON.stringify(obj ?? fallback)); }
    catch(e){ return fallback; }
  }

  function purgePlotlyNode(node){
    if(!node || !window.Plotly) return;
    try {
      if(node._fullLayout || node._context || node.classList?.contains('js-plotly-plot')) window.Plotly.purge(node);
    } catch(e) { console.warn('[GraphBuilder] Plotly purge ignored', e); }
  }

  function resetCanvas(el){
    if(!el) return;
    purgePlotlyNode(el);
    [...el.querySelectorAll('.js-plotly-plot')].forEach(purgePlotlyNode);
    el.replaceChildren();
    el.classList.remove('is-error','is-empty');
  }

  function showCanvasMessage(el, msg, klass='empty-canvas'){
    resetCanvas(el);
    const div = document.createElement('div');
    div.className = klass;
    div.innerHTML = msg;
    el.appendChild(div);
  }

  GB.PlotlyBridge = {

    /**
     * Layout de base partagé par toutes les extensions.
     * Garantit que title, marges, fonts, grille, log, légende
     * viennent tous du config panel unifié.
     */
    makeBaseLayout(config, xLabel, yLabel, opts = {}) {
      const afSize   = config.axisFontSize ?? 20;
      const standoff = config.axisLabelPad ?? 20;
      const marginR  = opts.marginR ?? 24;
      return {
        ...(config.title ? { title: { text: config.title, font: { size: config.titleFontSize ?? 16 } } } : {}),
        margin: { l: 60 + standoff, r: marginR, t: config.title ? 52 : 28, b: 60 + standoff },
        hovermode: 'closest',
        dragmode:  opts.dragmode ?? 'select',
        paper_bgcolor: 'rgba(0,0,0,0)',
        plot_bgcolor:  'rgba(0,0,0,0)',
        xaxis: {
          title:     { text: xLabel ?? '', font: { size: afSize }, standoff },
          type:      config.log_x ? 'log' : '-',
          showgrid:  config.showGrid !== false,
          gridcolor: config.gridColor || '#e5e7eb',
          tickfont:  { size: config.tickFontSize ?? 10 },
        },
        yaxis: {
          title:     { text: yLabel ?? '', font: { size: afSize }, standoff },
          type:      config.log_y ? 'log' : '-',
          showgrid:  config.showGrid !== false,
          gridcolor: config.gridColor || '#e5e7eb',
          tickfont:  { size: config.tickFontSize ?? 10 },
        },
        legend:     { orientation: 'h', y: -0.15, x: 0 },
        showlegend: opts.showlegend !== undefined ? opts.showlegend : (config.showLegend !== false),
      };
    },

    bind(){
      GB.on('extensions:changed', () => { GB.UI?.renderExtensions?.(); this.renderConfig(); });
      GB.on('hidden:changed', () => { GB.UI?.renderHiddenToolbar?.(); });
      window.addEventListener('resize', () => this.resize());
    },

    defaultConfig(){
      const ext = GB.extensions[GB.activeExtension];
      return Object.assign({}, ext?.defaultConfig || {}, GB.currentConfig || {});
    },

    renderConfig(){
      const ext = GB.extensions[GB.activeExtension];
      const body = GB.qs('#config-body');
      if(!body) return;
      if(!ext){ body.innerHTML = '<div class="rail-meta">Aucune extension sélectionnée.</div>'; return; }
      const previous = GB.currentConfig || {};
      GB.currentConfig = Object.assign({}, ext.defaultConfig || {}, previous);
      if(typeof ext.configPanel === 'function') body.innerHTML = ext.configPanel({ columns: GB.columns, config: GB.currentConfig, esc: GB.esc });
      else body.innerHTML = this.basicPanel();
      const onChange = e => {
        const k = e.target?.dataset?.cfg;
        if(!k) return;
        GB.currentConfig[k] = e.target.type === 'checkbox' ? e.target.checked : e.target.value;
        GB.activeView = null;
        this.render();
      };
      body.onchange = onChange;
      body.oninput = onChange;
    },

    selectOptions(value, type=null){
      const cols = GB.columns || [];
      return '<option value="">—</option>' + cols
        .filter(c => !type || c.type === type)
        .map(c => `<option value="${GB.esc(c.name)}" ${c.name===value?'selected':''}>${GB.esc(c.name)} · ${c.type}</option>`)
        .join('');
    },

    basicPanel(){
      const c = GB.currentConfig || {};
      return `<div class="cfg-section">
        <div class="cfg-row"><label>X</label><select class="cfg-input" data-cfg="x">${this.selectOptions(c.x)}</select></div>
        <div class="cfg-row"><label>Y</label><select class="cfg-input" data-cfg="y">${this.selectOptions(c.y)}</select></div>
        <div class="cfg-row"><label>Color</label><select class="cfg-input" data-cfg="color">${this.selectOptions(c.color)}</select></div>
        <div class="cfg-row"><label>Titre</label><input class="cfg-input" data-cfg="title" value="${GB.esc(c.title||'')}"></div>
        <div class="cfg-row"><label><input type="checkbox" data-cfg="log_x" ${c.log_x?'checked':''}> Log X</label></div>
        <div class="cfg-row"><label><input type="checkbox" data-cfg="log_y" ${c.log_y?'checked':''}> Log Y</label></div>
      </div>`;
    },

    attachSelectionHandlers(){
      const canvas = GB.qs('#graph-canvas');
      if(!canvas || !window.Plotly) return;
      const plots = canvas.classList.contains('js-plotly-plot') ? [canvas] : [...canvas.querySelectorAll('.js-plotly-plot')];
      plots.forEach(plot => {
        if(plot.__gbSelectionBound) return;
        plot.__gbSelectionBound = true;
        plot.on?.('plotly_selected', ev => {
          const ids = [];
          (ev?.points || []).forEach(pt => {
            const cd = pt.customdata;
            if(Array.isArray(cd)) ids.push(cd[0]); else if(cd) ids.push(cd);
          });
          GB.hidden.lastSelection = [...new Set(ids.filter(Boolean))];
          GB.UI.renderHiddenToolbar?.();
        });
        plot.on?.('plotly_deselect', () => { GB.hidden.lastSelection = []; GB.UI.renderHiddenToolbar?.(); });
        plot.addEventListener('contextmenu', e => {
          if((GB.hidden.lastSelection || []).length){
            e.preventDefault();
            if(confirm(`Masquer ${GB.hidden.lastSelection.length} point(s) sélectionné(s) ?`)) this.hideSelection();
          }
        });
      });
    },

    hideSelection(){
      const ids = GB.hidden.lastSelection || [];
      if(!ids.length){ GB.toast('Aucune sélection à masquer'); return; }
      GB.hideIds(ids);
      GB.UI.renderTable();
      this.render();
      GB.toast(`${ids.length} point(s) masqué(s)`);
    },

    render(){
      const el = GB.qs('#chart-plot') || GB.qs('#graph-canvas');
      if(!el) return;
      const ext = GB.extensions[GB.activeExtension];
      if(!ext){ showCanvasMessage(el, 'Sélectionne une extension graphique.'); return; }
      if(!window.Plotly){ showCanvasMessage(el, 'Plotly non chargé.', 'empty-canvas is-error'); return; }
      const rows = GB.Data?.filteredRows?.() || [];
      if(!rows.length){ showCanvasMessage(el, 'Aucune donnée.<br>Lance le DAG ou charge un asset.'); return; }
      try {
        resetCanvas(el);
        const cfg = cloneJson(GB.currentConfig, {});

        // Normalise les axes array vers scalaire pour les extensions existantes
        const xArr = [].concat(cfg.x||[]).filter(Boolean);
        const yArr = [].concat(cfg.y||[]).filter(Boolean);
        const y2Arr = [].concat(cfg.y2||[]).filter(Boolean);
        const facetCol = xArr[1] || null;    // 2ème X = facette colonne
        const facetRow = yArr[1] || null;    // 2ème Y = facette ligne
        const xCol = xArr[0], yCol = yArr[0], y2Col = y2Arr[0] || null;

        const flatCfg = { ...cfg, x:xCol, y:yCol, y2:y2Col,
          _xArr: xArr, _yArr: yArr,
          xLabel:cfg.xLabel||xCol||'', yLabel:cfg.yLabel||yCol||'' };

        if(facetCol || facetRow) {
          this._renderFacet(el, rows, flatCfg, xCol, yCol, facetCol, facetRow);
        } else {
          // Rendu standard via extension
          ext.render({ el, data:rows.slice(), columns:GB.columns||[], config:flatCfg, Plotly:window.Plotly, GB });
          // Y2 overlay si présent
          if(y2Col) this._addY2Overlay(el, rows, flatCfg, y2Col);
        }
        GB.setStep('graph');
        requestAnimationFrame(() => { this.attachSelectionHandlers(); this.resize(); GB.UI?.renderHiddenToolbar?.(); });
      } catch(e) {
        console.error('[GraphBuilder] render failed', e);
        showCanvasMessage(el, `Erreur : ${GB.esc(e.message||e)}`, 'empty-canvas is-error');
      }
    },

    _renderFacet(el, rows, cfg, xCol, yCol, facetCol, facetRow) {
      const Plotly = window.Plotly;
      const GB_    = GB || window.LumiereGraphBuilder;
      const ext    = GB_.extensions[GB_.activeExtension];

      const sortUniq = (arr) => [...new Set(arr)].sort((a,b) =>
        String(a).localeCompare(String(b), undefined, {numeric:true}));
      const colVals = facetCol ? sortUniq(rows.map(r=>r[facetCol])) : [null];
      const rowVals = facetRow ? sortUniq(rows.map(r=>r[facetRow])) : [null];
      const nCols   = colVals.length, nRows = rowVals.length;

      const afSize   = cfg.axisFontSize ?? 14;
      const standoff = cfg.axisLabelPad ?? 20;

      // ── Contexte couleur partagé (transmis aux extensions) ────────────
      const CAT_COLORS = ['#636efa','#ef553b','#00cc96','#ab63fa','#ffa15a',
                          '#19d3f3','#ff6692','#b6e880','#ff97ff','#fecb52'];
      const colorCol = cfg.color || null;
      const colDef   = colorCol ? (GB_?.columns||[]).find(c=>c.name===colorCol) : null;
      const isCont   = colorCol && (cfg.colorMode==='continuous' ||
                       ((cfg.colorMode==='auto'||!cfg.colorMode) && colDef?.type==='number'));
      const colorMap = (colorCol && !isCont)
        ? Object.fromEntries(sortUniq(rows.map(r=>String(r[colorCol]??'')))
            .map((v,i) => [v, CAT_COLORS[i%CAT_COLORS.length]]))
        : null;

      // Gaps absolus en coordonnées paper (0–1).
      // facetSpacingH/V sont des entiers 0-40 (% de la largeur paper).
      const colGap = Math.max(0.02, (cfg.facetSpacingH ?? 14) / 100);
      const rowGap = Math.max(0.02, (cfg.facetSpacingV ?? 18) / 100);

      // Formule absolue : on retire les gaps puis on divise le reste
      const domColW = nCols > 1 ? (1 - colGap*(nCols-1)) / nCols : 1;
      const domRowH = nRows > 1 ? (1 - rowGap*(nRows-1)) / nRows : 1;

      const traces = [], annotations = [];
      const layout = {
        ...(cfg.title ? {title:{text:cfg.title,font:{size:cfg.titleFontSize??16}}} : {}),
        margin: { l:60+standoff, r:isCont?80:24, t:cfg.title?70:48, b:60+standoff },
        hovermode: 'closest', dragmode: 'select',
        showlegend: false,
        paper_bgcolor: 'rgba(0,0,0,0)', plot_bgcolor: 'rgba(0,0,0,0)',
      };

      rowVals.forEach((rv, ri) => colVals.forEach((cv, ci) => {
        const idx  = ri*nCols + ci + 1;
        const xKey = idx===1 ? 'xaxis'  : `xaxis${idx}`;
        const yKey = idx===1 ? 'yaxis'  : `yaxis${idx}`;
        const xRef = idx===1 ? 'x'      : `x${idx}`;
        const yRef = idx===1 ? 'y'      : `y${idx}`;

        const filtered = rows.filter(r =>
          (!facetCol || r[facetCol]===cv) && (!facetRow || r[facetRow]===rv)
        );

        const x0 = ci * (domColW + colGap);
        const x1 = x0 + domColW;
        const y1 = 1 - ri * (domRowH + rowGap);
        const y0 = y1 - domRowH;

        const isBottomCenter = ri===nRows-1 && ci===Math.floor(nCols/2);
        const isMiddleLeft   = ci===0        && ri===Math.floor(nRows/2);

        layout[xKey] = {
          title: { text: isBottomCenter ? (cfg.xLabel||xCol||'') : '', font:{size:afSize}, standoff },
          domain: [Math.max(0,x0), Math.min(1,x1)], anchor: yRef,
          type: cfg.log_x ? 'log' : '-',
          showgrid: cfg.showGrid!==false, gridcolor: cfg.gridColor||'#e5e7eb',
          tickfont: { size: cfg.tickFontSize||10 },
        };
        layout[yKey] = {
          title: { text: isMiddleLeft ? (cfg.yLabel||yCol||'') : '', font:{size:afSize}, standoff },
          domain: [Math.max(0,y0), Math.min(1,y1)], anchor: xRef,
          type: cfg.log_y ? 'log' : '-',
          showgrid: cfg.showGrid!==false, gridcolor: cfg.gridColor||'#e5e7eb',
          tickfont: { size: cfg.tickFontSize||10 },
        };

        // ── Déléguer à l'extension, fallback scatter ──────────────────
        const ctx = { filtered, xRef, yRef, cfg, GB: GB_,
                      colorCol, isCont, colorMap, CAT_COLORS, isFirstCell: idx===1 };
        const cellTraces = typeof ext?.facetTraces === 'function'
          ? ext.facetTraces(ctx)
          : _defaultFacetScatter(ctx);
        traces.push(...cellTraces);

        // ── Titre du sous-graphe : positionné DANS le subplot (top-center) ──
        const titleTxt = [
          cv!==null ? `${facetCol}=${cv}` : '',
          rv!==null ? `${facetRow}=${rv}` : '',
        ].filter(Boolean).join(' · ');
        if (titleTxt) annotations.push({
          // Ancré au sommet intérieur du subplot → ne déborde jamais sur le subplot au-dessus
          x: (x0+x1)/2, y: y1,
          xref:'paper', yref:'paper',
          text: `<b>${GB_.esc(titleTxt)}</b>`,
          showarrow: false,
          font: { size:9, family:'IBM Plex Mono,monospace', color:'#1e3a5f' },
          xanchor:'center', yanchor:'top',
          bgcolor:'rgba(238,242,255,0.88)', borderpad:3,
        });
      }));

      layout.annotations = annotations;
      Plotly.react(el, traces, layout, { responsive:true, displayModeBar:false });
    },

    _addY2Overlay(el, rows, cfg, y2Col) {
      const Plotly = window.Plotly;
      if(!el._fullLayout) return;
      // Use same chart type as active extension
      const extId = GB.activeExtension;
      const typeMap = {
        'scatter':   { type:'scattergl', mode:'markers' },
        'line':      { type:'scatter',   mode:'lines+markers' },
        'bar':       { type:'bar' },
      };
      const tc = typeMap[extId] || { type:'scattergl', mode:'markers' };
      const trace = {
        ...tc, name: y2Col,
        x: rows.map(r=>r[cfg.x]),
        y: rows.map(r=>r[y2Col]),
        yaxis: 'y2',
        marker: { size:(cfg.pointSize||6)*0.8 },
      };
      Plotly.addTraces(el, [trace]);
      Plotly.relayout(el, {
        yaxis2:{ title:cfg.y2Label||y2Col, overlaying:'y', side:'right', showgrid:false },
      });
    },

    resize(){
      if(!window.Plotly) return;
      // Cherche d'abord dans le nouveau layout, puis dans l'ancien
      const root = GB.qs('#chart-plot') || GB.qs('#graph-canvas');
      if(!root) return;
      const plots = root.classList.contains('js-plotly-plot') ? [root] : [...root.querySelectorAll('.js-plotly-plot')];
      if(!plots.length && root.classList.contains('js-plotly-plot')) plots.push(root);
      plots.forEach(p => { try { window.Plotly.Plots.resize(p); } catch(e) {} });
    },

    saveView(duplicate=false){
      let name = GB.activeView && !duplicate ? GB.activeView.name : prompt('Nom de la vue', GB.currentConfig.title || GB.extensions[GB.activeExtension]?.label || 'Vue graphique');
      if(!name) return;
      const visibility = confirm('Rendre cette vue publique ?\nOK = public · Annuler = privé') ? 'public' : 'private';
      const view = Object.assign({}, duplicate ? {} : (GB.activeView || {}), {
        name,
        visibility,
        description: GB.activeView?.description || '',
        dataset: GB.activeDataset,
        extension: GB.activeExtension,
        config: cloneJson(GB.currentConfig, {}),
        filters: cloneJson(GB.filters, {logic:'AND', rules:[]})
      });
      GB.activeView = GB.Storage.saveView ? GB.Storage.saveView(view) : GB.Storage.save(view);
      GB.UI.renderSavedViews();
      GB.toast('Vue sauvegardée');
    },

    loadView(view){
      GB.activeView = view;
      GB.activeDataset = view.dataset || GB.activeDataset;
      GB.activeExtension = view.extension || GB.activeExtension;
      GB.currentConfig = cloneJson(view.config, {});
      GB.filters = Object.assign({logic:'AND', rules:[]}, cloneJson(view.filters, {}));
      GB.resetHidden?.();
      GB.Data.refreshColumns();
      GB.UI.renderDatasetSelect();
      GB.UI.renderColumns();
      GB.UI.renderFilterSummary();
      GB.UI.renderExtensions();
      GB.UI.renderSavedViews();
      this.renderConfig();
      GB.UI.renderTable();
      this.render();
    }
  };

  // ── Fallback facet : scatter si l'extension n'implémente pas facetTraces ─
  function _defaultFacetScatter({ filtered, xRef, yRef, cfg, colorCol, isCont, colorMap, CAT_COLORS, isFirstCell }) {
    const tooltipCols = [].concat(cfg.tooltip||[]).filter(Boolean);
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
    const hoverExtra = tooltipCols.length ? {
      text: filtered.map(r => tooltipCols.map(c=>`${c}: ${r[c]??''}`).join('<br>')),
      hovertemplate: '%{text}<extra></extra>',
    } : {};
    return [{
      type:'scattergl', mode:'markers',
      x: filtered.map(r=>r[cfg.x]), y: filtered.map(r=>r[cfg.y]),
      xaxis: xRef, yaxis: yRef,
      marker: { size:cfg.pointSize??6, opacity:cfg.opacity??0.7,
                symbol:cfg.markerSymbol||'circle', color:markerColor, ...markerExtra },
      customdata: filtered.map(r=>r.__gb_row_id),
      showlegend: false, ...hoverExtra,
    }];
  }

})();
