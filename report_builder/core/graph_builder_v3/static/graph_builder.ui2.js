'use strict';
/**
 * graph_builder.ui2.js — UI refondu
 * Multi-slot X/Y DnD · Config inline · Double-clic axe renommer
 * Refresh · Facet grid · Tableau intégré
 */
(function () {
  const GB = window.LumiereGraphBuilder;

  const TYPE_ICONS = { number:'#', string:'A', date:'📅', vector:'∿', matrix:'⊞' };
  const PALETTES   = ['lumiere','viridis','plasma','blues','reds','greens','set1','dark24'];
  const SYMBOLS    = ['circle','square','diamond','triangle-up','cross','x'];

  let _colFilter   = '';
  let _configOpen  = false;
  let _tableOpen   = false;
  let _tableH      = 0;   // hauteur mémorisée après redimensionnement splitter

  GB.UI = {

    // ── Boot ─────────────────────────────────────────────────────────
    bindStatic() {
      // Drawers
      ['inputs','filters','assets'].forEach(n => {
        GB.qs(`#${n}-backdrop`)?.addEventListener('click', () => this.closeDrawer(n));
        GB.qs(`[data-close="${n}"]`)?.addEventListener('click', () => this.closeDrawer(n));
      });
      GB.qs('#btn-open-inputs')?.addEventListener('click',  () => this.openDrawer('inputs'));
      GB.qs('#btn-open-assets')?.addEventListener('click',  () => GB.Assets?.openDrawer());
      GB.qs('#btn-open-filters')?.addEventListener('click', () => GB.Filters?.open?.());
      GB.qs('#btn-export-csv')?.addEventListener('click',   () => GB.Data?.exportCsv?.());

      // Views modal
      GB.qs('#views-backdrop')?.addEventListener('click', () => this.closeModal('views'));
      GB.qs('#views-close')?.addEventListener('click',    () => this.closeModal('views'));
      GB.qs('#btn-open-views')?.addEventListener('click', () => { this.renderViewsPanel(); this.openModal('views'); });
      GB.qs('#btn-save-view')?.addEventListener('click',  () => this.saveCurrentView());
      // Import
      GB.qs('#btn-import-view')?.addEventListener('click', () => GB.qs('#import-view-input')?.click());
      GB.qs('#import-view-input')?.addEventListener('change', async e => {
        const file = e.target.files?.[0];
        if (!file) return;
        e.target.value = '';   // reset pour permettre re-import même fichier
        await GB.Storage?.importViewFile?.(file);
        this.renderViewsPanel();
      });

      // Run
      GB.qs('#btn-run')?.addEventListener('click', () => GB.DAG?.run());

      // Refresh
      GB.qs('#btn-refresh')?.addEventListener('click', () => this._render(true));

      // Config inline toggle
      GB.qs('#btn-toggle-config')?.addEventListener('click', () => this.toggleConfig());
      GB.qs('#config-close')?.addEventListener('click',      () => this.toggleConfig(false));

      // Table toggle
      GB.qs('#btn-toggle-table')?.addEventListener('click', () => this.toggleTable());
      GB.qs('#btn-close-table')?.addEventListener('click',  () => this.toggleTable(false));

      // Collapse col-panel
      GB.qs('#btn-collapse-col')?.addEventListener('click', () => this._toggleColPanel());

      // Table splitter
      this._bindSplitter();

      // Unhide
      GB.qs('#btn-unhide-all')?.addEventListener('click', () => GB.unhideAll());

      // Clear all axes + channels
      GB.qs('#btn-clear-axes')?.addEventListener('click', () => {
        ['x','y','y2','color','size','tooltip'].forEach(ch => {
          GB.currentConfig[ch] = null;
          this._renderSlots(ch);
        });
        this._render();
      });

      // Dataset select
      GB.qs('#dataset-select')?.addEventListener('change', e => {
        GB.activeDataset = e.target.value;
        GB.filters = { logic:'AND', rules:[] };
        GB.Data?.refreshColumns?.();
        this.renderColumns();
        this._render();
        GB.Table?.render?.();
      });

      // Column search
      GB.qs('#col-search')?.addEventListener('input', e => { _colFilter = e.target.value; this.renderColumns(); });

      // Type strip
      GB.qs('#type-strip')?.addEventListener('click', e => {
        const btn = e.target.closest('[data-ext]');
        if (btn) this._setExt(btn.dataset.ext);
      });

      // DnD
      this._bindDnD();

      // Axis label double-click renaming
      this._bindAxisLabelEdit();

      // Keyboard ESC
      document.addEventListener('keydown', e => {
        if (e.key === 'Escape') this.closeModal('views');
      });

      // Events
      GB.on('data:ready', () => {
        this.renderDatasetSelect();
        this.renderColumns();
        this._updateMeta();
        this._render();
        if (_tableOpen) GB.Table?.render?.();
        GB.Filters?._updateBadge?.();
        GB.Filters?._renderColList?.();
        // S'assurer que le modal filtre reste fermé après chargement
        GB.Filters?.close?.();
      });
      GB.on('hidden:changed',     () => { this._updateHidden(); this._render(); });
      GB.on('extensions:changed', () => this.renderTypeStrip());
      GB.on('views:changed',      () => { if(GB.qs('#views-panel')?.classList.contains('open')) this.renderViewsPanel(); });
    },

    // ── Drawers ───────────────────────────────────────────────────────
    openDrawer(n)  { GB.qs(`#${n}-drawer`)?.classList.add('open');    GB.qs(`#${n}-backdrop`)?.classList.add('show'); },
    closeDrawer(n) { GB.qs(`#${n}-drawer`)?.classList.remove('open'); GB.qs(`#${n}-backdrop`)?.classList.remove('show'); },

    // ── Overlay modal (views) ─────────────────────────────────────────
    openModal(n)  { GB.qs(`#${n}-panel`)?.classList.add('open');    GB.qs(`#${n}-backdrop`)?.classList.add('show'); },
    closeModal(n) { GB.qs(`#${n}-panel`)?.classList.remove('open'); GB.qs(`#${n}-backdrop`)?.classList.remove('show'); },

    // ── Collapse col-panel ────────────────────────────────────────────
    _toggleColPanel() {
      const panel = GB.qs('.gbr-col-panel');
      const btn   = GB.qs('#btn-collapse-col');
      if (!panel) return;
      const collapsed = panel.classList.toggle('collapsed');
      if (btn) btn.textContent = collapsed ? '›' : '‹';
      setTimeout(() => GB.PlotlyBridge?.resize?.(), 220);
    },

    // ── Splitter table / chart ────────────────────────────────────────
    _bindSplitter() {
      const splitter   = GB.qs('#table-splitter');
      const tablePanel = GB.qs('#table-panel');
      const center     = GB.qs('.gbr-center');
      if (!splitter || !tablePanel) return;
      let dragging = false, startY = 0, startH = 0;

      splitter.addEventListener('mousedown', e => {
        dragging = true;
        startY   = e.clientY;
        startH   = tablePanel.getBoundingClientRect().height;
        // Désactiver la transition CSS pendant le drag pour éviter le lag
        tablePanel.style.transition = 'none';
        tablePanel.style.minHeight  = '0';
        splitter.classList.add('dragging');
        e.preventDefault();
      });
      window.addEventListener('mousemove', e => {
        if (!dragging) return;
        const delta  = startY - e.clientY;   // haut = agrandir table
        // Limiter la hauteur max pour que le splitter reste toujours visible
        const centerH = center?.getBoundingClientRect().height || 700;
        const maxH    = Math.max(80, centerH - 120);
        const newH    = Math.max(80, Math.min(maxH, startH + delta));
        tablePanel.style.height = newH + 'px';
      });
      window.addEventListener('mouseup', () => {
        if (!dragging) return;
        dragging = false;
        _tableH = Math.round(tablePanel.getBoundingClientRect().height);
        tablePanel.style.transition = '';
        splitter.classList.remove('dragging');
        GB.PlotlyBridge?.resize?.();
      });
    },

    // ── Inline config panel ───────────────────────────────────────────
    toggleConfig(force) {
      _configOpen = (force !== undefined) ? force : !_configOpen;
      const panel = GB.qs('#config-panel');
      if (panel) panel.classList.toggle('open', _configOpen);
      const btn = GB.qs('#btn-toggle-config');
      if (btn) btn.classList.toggle('active', _configOpen);
      if (_configOpen) { this.renderConfigPanel(); setTimeout(() => GB.PlotlyBridge?.resize?.(), 350); }
      else { setTimeout(() => GB.PlotlyBridge?.resize?.(), 350); }
    },

    // ── Table panel ───────────────────────────────────────────────────
    toggleTable(force) {
      _tableOpen = (force !== undefined) ? force : !_tableOpen;
      const panel    = GB.qs('#table-panel');
      const splitter = GB.qs('#table-splitter');
      if (panel) {
        panel.classList.toggle('open', _tableOpen);
        if (_tableOpen) {
          // Restaurer la hauteur mémorisée par le splitter, sinon laisser le CSS gérer (320px)
          panel.style.height = _tableH ? _tableH + 'px' : '';
        } else {
          // Vider le style inline pour laisser CSS appliquer height:0
          panel.style.height = '';
        }
      }
      if (splitter) splitter.style.display = _tableOpen ? '' : 'none';
      const btn = GB.qs('#btn-toggle-table');
      if (btn) btn.classList.toggle('active', _tableOpen);
      if (_tableOpen) GB.Table?.render?.();
      setTimeout(() => GB.PlotlyBridge?.resize?.(), 30);
    },

    // ── Type strip ────────────────────────────────────────────────────
    renderTypeStrip() {
      const strip = GB.qs('#type-strip');
      if (!strip) return;
      strip.innerHTML = Object.values(GB.extensions).map(e => `
        <button class="gbr-type-btn${GB.activeExtension===e.id?' active':''}" data-ext="${GB.esc(e.id)}" title="${GB.esc(e.description||e.label)}">
          <span class="gbr-type-icon">${GB.esc(e.icon||'◇')}</span>
          <span class="gbr-type-lbl">${GB.esc(e.label)}</span>
        </button>`).join('');
    },

    _setExt(id) {
      if (!GB.extensions[id]) return;
      const p = GB.currentConfig || {};
      GB.activeExtension = id;
      GB.currentConfig = Object.assign({}, GB.extensions[id].defaultConfig||{}, {
        x:p.x, y:p.y, y2:p.y2, color:p.color, size:p.size, tooltip:p.tooltip,
        title:p.title||'', xLabel:p.xLabel||'', yLabel:p.yLabel||'', y2Label:p.y2Label||'',
        log_x:p.log_x, log_y:p.log_y, pointSize:p.pointSize, opacity:p.opacity,
        markerSymbol:p.markerSymbol, colorPalette:p.colorPalette,
        titleFontSize:p.titleFontSize, axisFontSize:p.axisFontSize, tickFontSize:p.tickFontSize,
        showGrid:p.showGrid, gridColor:p.gridColor, showLegend:p.showLegend,
      });
      GB.qsa('.gbr-type-btn').forEach(b => b.classList.toggle('active', b.dataset.ext===id));
      if (_configOpen) this.renderConfigPanel();
      this._render();
    },

    // ── Dataset ───────────────────────────────────────────────────────
    renderDatasetSelect() {
      const sel  = GB.qs('#dataset-select');
      if (!sel) return;
      const keys = Object.keys(GB.datasets||{});
      if (!keys.length) return;
      if (!GB.activeDataset || !GB.datasets[GB.activeDataset]) GB.activeDataset = keys[0];
      sel.innerHTML = keys.map(k=>`<option value="${GB.esc(k)}"${k===GB.activeDataset?' selected':''}>${GB.esc(k)}</option>`).join('');
    },
    _updateMeta() {
      const meta = GB.qs('#dataset-meta');
      const cnt  = GB.qs('#chart-row-count');
      const ds   = GB.datasets?.[GB.activeDataset];
      if (!ds) return;
      const r = Array.isArray(ds) ? ds.length : (ds.records?.length ?? ds.rows?.length ?? '?');
      const c = Array.isArray(ds) ? (GB.columns?.length ?? '?') : (ds.columns?.length ?? '?');
      if (meta) meta.textContent = `${r} lignes · ${c} colonnes`;
      if (cnt)  cnt.textContent  = `${r} lignes`;
    },

    // ── Columns ───────────────────────────────────────────────────────
    renderColumns() {
      const box  = GB.qs('#col-groups');
      if (!box) return;
      const cols = GB.columns||[];
      const q    = _colFilter.trim().toLowerCase();
      const list = q ? cols.filter(c=>c.name.toLowerCase().includes(q)) : cols;
      if (!list.length) {
        box.innerHTML=`<div class="gbr-col-empty">${q?'Aucune colonne.':'Lancez un run.'}</div>`; return;
      }
      const groups = [{label:'Numériques',type:'number',badge:'#'},{label:'Texte',type:'string',badge:'A'},{label:'Dates',type:'date',badge:'📅'},{label:'Vecteurs',type:'vector',badge:'∿'},{label:'Matrices',type:'matrix',badge:'⊞'}];
      box.innerHTML = groups.map(g=>{
        const m = list.filter(c=>c.type===g.type);
        if(!m.length) return '';
        return `<div class="gbr-col-group">
          <div class="gbr-col-group-hd"><span class="gbr-col-badge gbr-col-badge-${g.type}">${g.badge}</span>${GB.esc(g.label)}</div>
          ${m.map(c=>`<div class="gbr-col-chip" draggable="true" data-col="${GB.esc(c.name)}" data-coltype="${GB.esc(c.type)}" title="${GB.esc(c.name)}">${GB.esc(c.name)}</div>`).join('')}
        </div>`;
      }).join('');
      this._bindChipDrag();
    },

    // ── Drag & Drop ───────────────────────────────────────────────────
    _bindChipDrag() {
      GB.qsa('.gbr-col-chip').forEach(chip=>{
        chip.addEventListener('dragstart', e=>{
          e.dataTransfer.setData('text/col',chip.dataset.col);
          e.dataTransfer.setData('text/coltype',chip.dataset.coltype);
          e.dataTransfer.effectAllowed='copy'; chip.classList.add('dragging');
        });
        chip.addEventListener('dragend',()=>chip.classList.remove('dragging'));
      });
    },

    _bindDnD() {
      // Les drop zones sont UNIQUEMENT dans .gbr-chart-zone (pas dans la palette col)
      const zone = el => {
        const z = el?.closest('[data-channel]');
        if (!z) return null;
        // Ignorer si la zone est dans la palette de colonnes (pas un axe du graphe)
        if (z.closest('.gbr-col-panel')) return null;
        return z;
      };

      document.addEventListener('dragover', e => {
        const z = zone(e.target);
        if (z) { e.preventDefault(); z.classList.add('drag-over'); }
      });
      document.addEventListener('dragleave', e => {
        const z = zone(e.target);
        if (z && !z.contains(e.relatedTarget)) z.classList.remove('drag-over');
      });
      document.addEventListener('drop', e => {
        const z = zone(e.target);
        if (!z) return;
        e.preventDefault(); z.classList.remove('drag-over');
        const col  = e.dataTransfer.getData('text/col');
        const type = e.dataTransfer.getData('text/coltype');
        if (col) this._setCh(z.dataset.channel, col, type);
      });
      document.addEventListener('click', e => {
        const btn = e.target.closest('[data-clear-ch]');
        if (btn) this._clearOneFromCh(btn.dataset.clearCh, btn.dataset.clearIdx);
      });
    },

    // channels x, y, y2, tooltip = arrays; color, size = scalars
    _isArrayCh(ch) { return ch==='x'||ch==='y'||ch==='y2'||ch==='tooltip'; },

    _setCh(ch, col, type) {
      if (this._isArrayCh(ch)) {
        // Normalise en array (supporte string existant venant du config panel)
        const cur = [].concat(GB.currentConfig[ch] || []).filter(Boolean);
        if (cur.includes(col)) return;
        cur.push(col);
        GB.currentConfig[ch] = cur;
      } else {
        GB.currentConfig[ch] = col;
      }
      this._renderSlots(ch);
      this._render();
    },

    _clearOneFromCh(ch, idx) {
      if (this._isArrayCh(ch)) {
        const cur = (GB.currentConfig[ch]||[]).slice();
        cur.splice(parseInt(idx), 1);
        GB.currentConfig[ch] = cur.length ? cur : null;
      } else {
        GB.currentConfig[ch] = null;
      }
      this._renderSlots(ch);
      this._render();
    },

    _renderSlots(ch) {
      if (ch==='x') this._renderXSlots();
      else if (ch==='y'||ch==='y2'||ch==='tooltip') this._renderYSlots(ch);
      else this._renderScalarSlot(ch);
    },

    _renderXSlots() {
      const box = GB.qs('#slots-x');
      if (!box) return;
      const cols = (GB.currentConfig.x||[]);
      if (!cols.length) {
        box.innerHTML='<span class="gbr-slot-hint">Glisser une colonne — 2ème = facette</span>'; return;
      }
      box.innerHTML = cols.map((c,i) => {
        const colObj = GB.columns?.find(x=>x.name===c);
        const type   = colObj?.type||'any';
        const badge  = `<span class="gbr-slot-badge gbr-col-badge-${type}">${TYPE_ICONS[type]||'·'}</span>`;
        const facet  = i===1 ? '<span class="gbr-facet-tag">facette</span>' : '';
        return `<div class="gbr-x-chip">${badge} ${GB.esc(c)} ${facet} <button class="gbr-slot-clear" data-clear-ch="x" data-clear-idx="${i}">✕</button></div>`;
      }).join('');
    },

    _renderYSlots(ch) {
      const box = GB.qs(`#slots-${ch}`);
      if (!box) return;
      const cols = (GB.currentConfig[ch]||[]);
      if (!cols.length) {
        const hint = ch === 'tooltip' ? 'gbr-slot-hint' : 'gbr-y-hint';
        box.innerHTML=`<span class="${hint}">Glisser…</span>`; return;
      }
      // Tooltip : disposition horizontale (chips en ligne)
      const isHoriz = ch === 'tooltip';
      if (isHoriz) {
        box.style.cssText = 'display:flex;flex-wrap:wrap;gap:4px;align-items:center;';
        box.innerHTML = cols.map((c, i) => `
          <div class="gbr-x-chip" style="font-size:10px;padding:3px 7px;">
            <span style="max-width:120px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">${GB.esc(c)}</span>
            <button class="gbr-slot-clear" data-clear-ch="${ch}" data-clear-idx="${i}" style="color:#6b7280;font-size:9px;">✕</button>
          </div>`).join('');
        return;
      }
      box.style.cssText = '';
      box.innerHTML = cols.map((c,i) => {
        const facet = i===1 ? '<span class="gbr-facet-tag vert">F</span>' : '';
        return `<div class="gbr-y-chip">
          <span class="gbr-y-chip-name">${GB.esc(c)}</span>${facet}
          <button class="gbr-slot-clear" data-clear-ch="${ch}" data-clear-idx="${i}">✕</button>
        </div>`;
      }).join('');
    },

    _renderScalarSlot(ch) {
      const slot = GB.qs(`#slot-${ch}`);
      if (!slot) return;
      const col = GB.currentConfig[ch];
      if (!col) {
        slot.innerHTML=`<span class="gbr-slot-hint">Glisser…</span>`; return;
      }
      const colObj = GB.columns?.find(x=>x.name===col);
      const type   = colObj?.type||'any';
      slot.innerHTML=`<div class="gbr-slot-filled">
        <span class="gbr-slot-badge gbr-col-badge-${type}">${TYPE_ICONS[type]||'·'}</span>
        <span class="gbr-slot-col">${GB.esc(col)}</span>
        <button class="gbr-slot-clear" data-clear-ch="${ch}" data-clear-idx="0">✕</button>
      </div>`;
    },

    _allSlotsFromView(cfg) {
      ['x','y','y2','tooltip'].forEach(ch => this._renderSlots(ch));
      ['color','size'].forEach(ch => this._renderScalarSlot(ch));
    },

    // ── Axis label double-click ───────────────────────────────────────
    _bindAxisLabelEdit() {
      ['x-label-text','y-label-text','y2-label-text'].forEach(id => {
        const el = GB.qs('#'+id);
        if (!el) return;
        el.addEventListener('dblclick', () => {
          const axis = el.dataset.axis;
          const key  = axis==='x' ? 'xLabel' : axis==='y' ? 'yLabel' : 'y2Label';
          const cur  = GB.currentConfig[key] || (axis==='x'?'X':axis==='y'?'Y':'Y2');
          const inp  = document.createElement('input');
          inp.type='text'; inp.value=cur;
          inp.className='gbr-axis-label-input';
          el.replaceWith(inp); inp.focus(); inp.select();
          const save = () => {
            const val = inp.value.trim()||cur;
            GB.currentConfig[key] = val;
            inp.replaceWith(el); el.textContent=val||axis.toUpperCase();
            this._render();
          };
          inp.addEventListener('blur', save);
          inp.addEventListener('keydown', e => { if(e.key==='Enter') save(); if(e.key==='Escape'){inp.replaceWith(el);} });
        });
      });
    },

    // ── Render ────────────────────────────────────────────────────────
    _render(force=false) {
      const cfg   = GB.currentConfig||{};
      const x     = [].concat(cfg.x||[]).filter(Boolean)[0] || null;
      const y     = [].concat(cfg.y||[]).filter(Boolean)[0] || null;
      const rows  = GB.Data?.filteredRows?.() || [];
      const empty = GB.qs('#chart-empty');
      const plot  = GB.qs('#chart-plot');

      // Afficher empty state uniquement si aucune donnée chargée
      if (!rows.length) {
        if(empty) empty.style.display='flex'; if(plot) plot.style.visibility='hidden'; return;
      }
      // Données présentes : toujours afficher la zone graphe et laisser l'extension gérer
      if(empty) empty.style.display='none'; if(plot) plot.style.visibility='visible';

      const flatCfg = { ...cfg, _xArr: [].concat(cfg.x||[]).filter(Boolean), _yArr: [].concat(cfg.y||[]).filter(Boolean), x, y };
      GB._lastFlatConfig = flatCfg;
      GB.PlotlyBridge?.render?.();
      this._updateHidden();
      const cnt  = GB.qs('#chart-row-count');
      if (cnt) cnt.textContent = `${rows.length} lignes`;
    },

    _updateHidden() {
      const n=GB.hidden?.ids?.size||0;
      const info=GB.qs('#hidden-info'); const btn=GB.qs('#btn-unhide-all');
      if(info) info.textContent=n>0?`${n} masqué${n>1?'s':''}`:'';
      if(btn)  btn.disabled=n===0;
    },

    // ── Config panel ──────────────────────────────────────────────────
    renderConfigPanel() {
      const body = GB.qs('#config-body');
      if (!body) return;
      const cfg = GB.currentConfig||{};
      const ext = GB.extensions[GB.activeExtension];
      const extPanel = typeof ext?.configPanel==='function' ? ext.configPanel({columns:GB.columns||[],config:cfg,esc:GB.esc}) : '';

      const af = cfg.axisFontSize ?? 20;
      // Facette active si 2ème X ou 2ème Y configuré
      const xArr = [].concat(cfg.x||[]).filter(Boolean);
      const yArr = [].concat(cfg.y||[]).filter(Boolean);
      const isFacet = xArr.length > 1 || yArr.length > 1;
      body.innerHTML = `
        <div class="gbr-cfg-section">
          <div class="gbr-cfg-hd">Titre</div>
          <input class="gbr-cfg-input" id="cfg-title" value="${GB.esc(cfg.title||'')}" placeholder="Titre du graphe">
        </div>
        <div class="gbr-cfg-section">
          <div class="gbr-cfg-hd">Axes</div>
          <div class="gbr-cfg-row"><span>Label X</span><input class="gbr-cfg-input sm" id="cfg-xlabel" value="${GB.esc(cfg.xLabel||'')}" placeholder="Auto"></div>
          <div class="gbr-cfg-row"><span>Log X</span><label class="gbr-toggle"><input type="checkbox" id="cfg-logx" ${cfg.log_x?'checked':''}><span></span></label></div>
          <div class="gbr-cfg-row"><span>Label Y</span><input class="gbr-cfg-input sm" id="cfg-ylabel" value="${GB.esc(cfg.yLabel||'')}" placeholder="Auto"></div>
          <div class="gbr-cfg-row"><span>Log Y</span><label class="gbr-toggle"><input type="checkbox" id="cfg-logy" ${cfg.log_y?'checked':''}><span></span></label></div>
          <div class="gbr-cfg-row"><span>Padding label</span><div class="gbr-cfg-pm-row"><button class="gbr-cfg-pm" data-pm-key="axisLabelPad" data-pm-delta="-5" data-pm-min="0">−</button><span id="v-pad">${cfg.axisLabelPad??20}</span><button class="gbr-cfg-pm" data-pm-key="axisLabelPad" data-pm-delta="5" data-pm-max="80">+</button></div></div>
        </div>
        ${isFacet ? `
        <div class="gbr-cfg-section">
          <div class="gbr-cfg-hd">Espacement facettes</div>
          <div class="gbr-cfg-row">
            <span>Horiz. <b id="v-fsh">${cfg.facetSpacingH??14}</b>%</span>
            <input type="range" class="gbr-range" id="cfg-fsh" min="2" max="40" step="1" value="${cfg.facetSpacingH??14}">
          </div>
          <div class="gbr-cfg-row">
            <span>Vert. <b id="v-fsv">${cfg.facetSpacingV??18}</b>%</span>
            <input type="range" class="gbr-range" id="cfg-fsv" min="2" max="40" step="1" value="${cfg.facetSpacingV??18}">
          </div>
        </div>` : ''}
        <div class="gbr-cfg-section">
          <div class="gbr-cfg-hd">Points</div>
          <div class="gbr-cfg-row"><span>Taille <b id="v-size">${cfg.pointSize??15}</b></span><input type="range" class="gbr-range" id="cfg-size" min="2" max="30" value="${cfg.pointSize??15}"></div>
          <div class="gbr-cfg-row"><span>Opacité <b id="v-opacity">${cfg.opacity??0.85}</b></span><input type="range" class="gbr-range" id="cfg-opacity" min="0.05" max="1" step="0.05" value="${cfg.opacity??0.85}"></div>
          <div class="gbr-cfg-row"><span>Symbole</span><select class="gbr-cfg-select" id="cfg-symbol">${SYMBOLS.map(s=>`<option value="${s}"${cfg.markerSymbol===s?' selected':''}>${s}</option>`).join('')}</select></div>
        </div>
        <div class="gbr-cfg-section">
          <div class="gbr-cfg-hd">Polices</div>
          <div class="gbr-cfg-row"><span>Titre <b id="v-tf">${cfg.titleFontSize??16}</b></span><input type="range" class="gbr-range" id="cfg-tf" min="10" max="40" value="${cfg.titleFontSize??16}"></div>
          <div class="gbr-cfg-row"><span>Axes <b id="v-af">${af}</b></span><div class="gbr-cfg-pm-row"><button class="gbr-cfg-pm" data-pm-key="axisFontSize" data-pm-delta="-10" data-pm-min="8">−</button><input type="range" class="gbr-range" id="cfg-af" min="8" max="60" step="2" value="${af}" style="width:80px"><button class="gbr-cfg-pm" data-pm-key="axisFontSize" data-pm-delta="10" data-pm-max="60">+</button></div></div>
          <div class="gbr-cfg-row"><span>Ticks <b id="v-tk">${cfg.tickFontSize??10}</b></span><input type="range" class="gbr-range" id="cfg-tk" min="6" max="24" value="${cfg.tickFontSize??10}"></div>
        </div>
        <div class="gbr-cfg-section">
          <div class="gbr-cfg-hd">Grille & Légende</div>
          <div class="gbr-cfg-row"><span>Grille</span><label class="gbr-toggle"><input type="checkbox" id="cfg-grid" ${cfg.showGrid!==false?'checked':''}><span></span></label></div>
          <div class="gbr-cfg-row"><span>Couleur grille</span><input type="color" id="cfg-grid-color" value="${cfg.gridColor||'#e5e7eb'}"></div>
          <div class="gbr-cfg-row"><span>Légende</span><label class="gbr-toggle"><input type="checkbox" id="cfg-legend" ${cfg.showLegend!==false?'checked':''}><span></span></label></div>
        </div>
        ${extPanel?`<div class="gbr-cfg-section"><div class="gbr-cfg-hd">Extension</div>${extPanel}</div>`:''}
      `;
      this._bindCfg(body);
    },

    _bindCfg(body) {
      const up=(k,v)=>{GB.currentConfig[k]=v;this._render();};
      const rng=(id,lbl,k,parse=parseFloat)=>{const el=body.querySelector('#'+id);if(!el)return;el.addEventListener('input',e=>{const v=parse(e.target.value);const l=body.querySelector('#'+lbl);if(l)l.textContent=v;up(k,v);});};
      const inp=(id,k)=>{const el=body.querySelector('#'+id);if(el)el.addEventListener('input',e=>up(k,e.target.value));};
      const chk=(id,k)=>{const el=body.querySelector('#'+id);if(el)el.addEventListener('change',e=>up(k,e.target.checked));};
      const sel=(id,k)=>{const el=body.querySelector('#'+id);if(el)el.addEventListener('change',e=>up(k,e.target.value));};
      inp('cfg-title','title');inp('cfg-xlabel','xLabel');inp('cfg-ylabel','yLabel');
      chk('cfg-logx','log_x');chk('cfg-logy','log_y');
      rng('cfg-size','v-size','pointSize',parseInt);
      rng('cfg-opacity','v-opacity','opacity');
      sel('cfg-symbol','markerSymbol');
      rng('cfg-tf','v-tf','titleFontSize',parseInt);
      rng('cfg-af','v-af','axisFontSize',parseInt);
      rng('cfg-tk','v-tk','tickFontSize',parseInt);
      chk('cfg-grid','showGrid');chk('cfg-legend','showLegend');
      body.querySelector('#cfg-grid-color')?.addEventListener('input',e=>up('gridColor',e.target.value));
      rng('cfg-fsh','v-fsh','facetSpacingH',parseInt);
      rng('cfg-fsv','v-fsv','facetSpacingV',parseInt);
      // Boutons +/- (axisFontSize, axisLabelPad)
      body.querySelectorAll('[data-pm-key]').forEach(btn => {
        btn.addEventListener('click', () => {
          const k     = btn.dataset.pmKey;
          const delta = parseInt(btn.dataset.pmDelta);
          const min   = btn.dataset.pmMin !== undefined ? parseInt(btn.dataset.pmMin) : -Infinity;
          const max   = btn.dataset.pmMax !== undefined ? parseInt(btn.dataset.pmMax) :  Infinity;
          const cur   = GB.currentConfig[k] ?? (k === 'axisFontSize' ? 20 : 20);
          const nv    = Math.max(min, Math.min(max, cur + delta));
          // Mettre à jour l'affichage label + slider
          const lbl = body.querySelector('#v-af');  if (lbl && k==='axisFontSize') lbl.textContent = nv;
          const pad = body.querySelector('#v-pad');  if (pad && k==='axisLabelPad') pad.textContent = nv;
          const sl  = body.querySelector('#cfg-af'); if (sl  && k==='axisFontSize') sl.value = nv;
          up(k, nv);
        });
      });
      const extCb=e=>{
        const k=e.target?.dataset?.cfg; if(!k) return;
        GB.currentConfig[k]=e.target.type==='checkbox'?e.target.checked:e.target.value;
        // Mettre à jour le label associé si data-lbl-id est défini
        const lbl=e.target.dataset.lblId; if(lbl){const l=body.querySelector('#'+lbl);if(l)l.textContent=e.target.value;}
        // Re-render le panel de config si le type de colonne peut changer (vector/matrix)
        if(k==='vectorX'||k==='vectorY'){this.renderConfigPanel();}
        this._render();
      };
      body.addEventListener('change',extCb);body.addEventListener('input',extCb);
    },

    // ── Views panel ───────────────────────────────────────────────────
    renderViewsPanel() {
      const list = GB.qs('#views-list');
      if (!list) return;
      const views = GB.Storage?.listViews?.() || [];

      const TYPE_BADGE = {
        asset:      { label:'Asset',      cls:'gbr-vbadge-asset'      },
        dag:        { label:'DAG',        cls:'gbr-vbadge-dag'        },
        standalone: { label:'Global',     cls:'gbr-vbadge-standalone' },
      };
      const fmt = s => { try { return new Date(s).toLocaleDateString('fr-FR',{day:'2-digit',month:'short',year:'2-digit'}); } catch { return ''; } };

      if (!views.length) {
        list.innerHTML = '<div class="gbr-views-empty">Aucune vue sauvegardée.</div>';
        return;
      }

      // Grouper par type
      const groups = { asset:[], dag:[], standalone:[] };
      views.forEach(v => (groups[v.view_type || 'standalone'] ||= groups.standalone).push(v));

      const renderGroup = (title, items) => {
        if (!items.length) return '';
        return `<div class="gbr-views-group">
          <div class="gbr-views-group-hd">${title}</div>
          ${items.map(v => {
            const tb = TYPE_BADGE[v.view_type || 'standalone'];
            const ctx = v.asset_name ? GB.esc(v.asset_name) : v.dag_id ? GB.esc(v.dag_id) : '';
            const xInfo = v.config?.x ? [].concat(v.config.x).filter(Boolean).slice(0,2).join(', ') : '';
            return `<div class="gbr-view-item">
              <div class="gbr-view-info">
                <div class="gbr-view-name-row">
                  <span class="gbr-view-name">${GB.esc(v.name || 'Vue sans nom')}</span>
                  <span class="gbr-vbadge ${tb.cls}">${tb.label}</span>
                  ${v.visibility === 'public' ? '<span class="gbr-vbadge gbr-vbadge-pub">Public</span>' : ''}
                </div>
                <div class="gbr-view-meta">
                  ${GB.esc(v.extension||'')}${xInfo?' · '+GB.esc(xInfo):''}
                  ${ctx?' · <span class="gbr-view-ctx">'+ctx+'</span>':''}
                  · ${fmt(v.updated_at || v.created_at)}
                </div>
              </div>
              <div class="gbr-view-btns">
                <button class="gbr-vbtn load"   data-load="${GB.esc(v.id)}"   title="Charger">↩</button>
                <button class="gbr-vbtn export" data-export="${GB.esc(v.id)}" title="Exporter JSON">⬇</button>
                <button class="gbr-vbtn del"    data-del="${GB.esc(v.id)}"    title="Supprimer">✕</button>
              </div>
            </div>`;
          }).join('')}
        </div>`;
      };

      list.innerHTML =
        renderGroup('🔗 Liées à un asset', groups.asset) +
        renderGroup('⚡ Liées à un DAG',   groups.dag)   +
        renderGroup('🌐 Globales',          groups.standalone);

      list.querySelectorAll('[data-load]').forEach(b =>
        b.addEventListener('click', () => { this._loadView(b.dataset.load); this.closeModal('views'); }));
      list.querySelectorAll('[data-export]').forEach(b =>
        b.addEventListener('click', () => GB.Storage?.exportView?.(b.dataset.export)));
      list.querySelectorAll('[data-del]').forEach(b =>
        b.addEventListener('click', async () => {
          if (!confirm('Supprimer cette vue ?')) return;
          await GB.Storage?.removeView?.(b.dataset.del);
          this.renderViewsPanel();
        }));
    },

    saveCurrentView() {
      // Déterminer le contexte courant automatiquement
      const mode  = GB.mode || 'dag';
      const asset = GB.assetName || window.LUMIERE_ASSET || null;
      const dag   = GB.dagId || null;
      let autoType = 'standalone';
      if (mode === 'explore' && asset) autoType = 'asset';
      else if (dag) autoType = 'dag';

      const name = prompt(
        'Nom de la vue :',
        GB.currentConfig?.title || `Vue ${new Date().toLocaleDateString('fr-FR')}`
      );
      if (!name) return;

      // Choix du type (pré-sélection auto, l'utilisateur peut changer)
      const typeChoice = prompt(
        `Type de vue :\n  1 = ${autoType === 'asset' ? '🔗 Liée à l\'asset "'+asset+'"' : autoType === 'dag' ? '⚡ Liée au DAG "'+dag+'"' : '🌐 Globale'} (recommandé)\n  2 = 🌐 Globale (accessible partout)\n\nEntrez 1 ou 2 :`,
        '1'
      );
      if (typeChoice === null) return;
      const useAuto  = typeChoice.trim() !== '2';
      const viewType = useAuto ? autoType : 'standalone';

      const visChoice = prompt('Visibilité :\n  1 = Privée (par défaut)\n  2 = Publique (visible par tous)\n\nEntrez 1 ou 2 :', '1');
      if (visChoice === null) return;
      const visibility = visChoice.trim() === '2' ? 'public' : 'private';

      GB.Storage?.saveView?.({
        name,
        view_type:  viewType,
        asset_name: viewType === 'asset' ? asset : null,
        dag_id:     viewType === 'dag'   ? dag   : null,
        dataset:    GB.activeDataset,
        extension:  GB.activeExtension,
        config:     JSON.parse(JSON.stringify(GB.currentConfig || {})),
        filters:    JSON.parse(JSON.stringify(GB.filters || { logic:'AND', rules:[] })),
        visibility,
      }).then(() => {
        GB.toast(`✓ Vue "${name}" sauvegardée`);
        this.renderViewsPanel();
      }).catch(e => GB.toast('Erreur sauvegarde : ' + e.message));
    },

    _loadView(id) {
      const view=(GB.Storage?.listViews?.()||[]).find(v=>v.id===id);
      if(!view) { GB.toast('Vue introuvable'); return; }
      if(view.dataset&&GB.datasets?.[view.dataset]){
        GB.activeDataset=view.dataset;
        GB.Data?.refreshColumns?.();
        this.renderDatasetSelect();
        this.renderColumns();
      }
      if(view.extension&&GB.extensions?.[view.extension]){
        GB.activeExtension=view.extension;
        this.renderTypeStrip();
      }
      try {
        GB.currentConfig = JSON.parse(JSON.stringify(view.config||{}));
        if(view.filters) GB.filters = JSON.parse(JSON.stringify(view.filters));
      } catch(e) {
        GB.currentConfig = Object.assign({}, view.config||{});
        if(view.filters) GB.filters = Object.assign({logic:'AND',rules:[]}, view.filters);
      }
      GB.resetHidden?.();
      this._allSlotsFromView(GB.currentConfig);
      if(_configOpen) this.renderConfigPanel();
      this._render();
      GB.Table?.render?.();
      GB.toast('✓ Vue chargée');
    },

    // ── Header (dag mode) ─────────────────────────────────────────────
    renderHeader() {
      const dag=GB.dag||{};
      const name=GB.qs('#dag-name');const pill=GB.qs('#source-pill');
      if(name) name.textContent=dag.name||GB.dagId||'Pipeline';
      if(pill){pill.textContent='DAG';pill.className='gbr-source-pill dag';}
      document.title=(dag.name||GB.dagId||'Graph Builder')+' — LUMIÈRE';
    },

    renderInputs() {
      const body=GB.qs('#inputs-body');const cnt=GB.qs('#input-count');
      if(!body) return;
      const nodes=GB.inputNodes||[];
      if(cnt) cnt.textContent=nodes.length?` · ${nodes.length} param.`:'';
      if(!nodes.length){body.innerHTML='<div class="gbr-col-empty">Aucun paramètre.</div>';return;}
      body.innerHTML=nodes.map(n=>{
        const p=GB.inputs[n.instance_id]||{};
        return `<div class="gbr-cfg-section"><div class="gbr-cfg-hd">${GB.esc(n.label||n.instance_id)}</div>
          ${Object.entries(p).map(([k,v])=>`<div class="gbr-cfg-row"><span>${GB.esc(k)}</span><input class="gbr-cfg-input sm" value="${GB.esc(String(v))}" onchange="LumiereGraphBuilder.inputs['${n.instance_id}']['${k}']=this.value"></div>`).join('')}
        </div>`;
      }).join('');
    },

    // Legacy stubs
    renderExtensions()    { this.renderTypeStrip(); },
    renderSavedViews()    { this.renderViewsPanel(); },
    renderFilterPresets() {},
    renderHiddenToolbar() { this._updateHidden(); },
    renderTable()         { if(_tableOpen) GB.Table?.render?.(); },
    renderFilterSummary() {},
    renderDatasetSelect() {
      const sel=GB.qs('#dataset-select');if(!sel) return;
      const keys=Object.keys(GB.datasets||{});
      if(!GB.activeDataset||!GB.datasets[GB.activeDataset]) GB.activeDataset=keys[0];
      sel.innerHTML=keys.map(k=>`<option value="${GB.esc(k)}"${k===GB.activeDataset?' selected':''}>${GB.esc(k)}</option>`).join('');
      this._updateMeta();
    },
  };
})();
