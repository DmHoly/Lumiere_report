'use strict';
(function () {
  const GB = window.LumiereGraphBuilder;

  function uid() { return Math.random().toString(36).slice(2, 8); }
  function clone(obj, fb) { try { return JSON.parse(JSON.stringify(obj ?? fb)); } catch { return fb; } }

  // ── Cleanup any leftover drag listeners ────────────────────────────
  let _dragCleanup = null;
  function cleanupDrag() { if (_dragCleanup) { _dragCleanup(); _dragCleanup = null; } }

  // ── Core filter logic ──────────────────────────────────────────────
  GB.Filters = {

    apply(rows, group) {
      const rules = (group && group.rules) || [];
      if (!rules.length) return rows;
      return rows.filter(row => {
        const checks = rules.map(r => this.match(row, r));
        return (group.logic || 'AND') === 'OR' ? checks.some(Boolean) : checks.every(Boolean);
      });
    },

    match(row, r) {
      const v = row[r.column];
      if (r.op === 'range')  { const n = Number(v); return n >= Number(r.min) && n <= Number(r.max); }
      if (r.op === 'in_arr') return Array.isArray(r.values) && r.values.includes(String(v ?? ''));
      const op = r.op, raw = r.value, n = Number(v), rv = Number(raw);
      if (op === '=')        return String(v) === String(raw);
      if (op === '!=')       return String(v) !== String(raw);
      if (op === '>')        return n > rv;
      if (op === '>=')       return n >= rv;
      if (op === '<')        return n < rv;
      if (op === '<=')       return n <= rv;
      if (op === 'contains') return String(v ?? '').toLowerCase().includes(String(raw ?? '').toLowerCase());
      if (op === 'in')       return String(raw).split(',').map(s => s.trim()).includes(String(v));
      return true;
    },

    // ── Presets ────────────────────────────────────────────────────────
    savePreset() {
      const name = prompt('Nom de la configuration', GB.activeFilterPreset?.name || 'Filtre');
      if (!name) return;
      GB.activeFilterPreset = GB.Storage.saveFilterPreset({
        ...(GB.activeFilterPreset || {}), name, visibility: 'private',
        dataset: GB.activeDataset,
        filters: clone(GB.filters, { logic: 'AND', rules: [] }),
      });
      GB.UI.renderFilterPresets?.();
      GB.toast('✓ Filtre sauvegardé');
    },

    loadPreset(p) {
      GB.activeFilterPreset = p;
      GB.filters = Object.assign({ logic: 'AND', rules: [] }, clone(p.filters, {}));
      GB.filters.rules.forEach(r => { if (!r.id) r.id = uid(); });
      if (p.dataset && GB.datasets[p.dataset]) GB.activeDataset = p.dataset;
      GB.Data.refreshColumns?.();
      GB.UI.renderDatasetSelect?.();
      GB.UI.renderColumns?.();
      GB.UI.renderFilterPresets?.();
      this._refresh();
      this._renderPanel();
    },

    // ── Internal refresh ───────────────────────────────────────────────
    _refresh() {
      GB.activeFilterPreset = null;
      GB.UI.renderTable?.();
      GB.PlotlyBridge?.render?.();
      this._renderActiveChips();
      this._updateBadge();
    },

    // ── Modal open/close ───────────────────────────────────────────────
    open() {
      const backdrop = GB.qs('#filter-modal-backdrop');
      const modal    = GB.qs('#filter-modal');
      if (backdrop) backdrop.classList.add('open');
      if (modal)    modal.classList.add('open');
      this._renderPanel();
    },

    close() {
      cleanupDrag();
      GB.qs('#filter-modal-backdrop')?.classList.remove('open');
      GB.qs('#filter-modal')?.classList.remove('open');
    },

    _bindModal() {
      GB.qs('#filter-modal-backdrop')?.addEventListener('click', () => this.close());
      GB.qs('#fm-close')?.addEventListener('click',  () => this.close());
      GB.qs('#fm-save')?.addEventListener('click',   () => this.savePreset());
      GB.qs('#fm-clear')?.addEventListener('click',  () => {
        GB.filters = { logic: GB.filters.logic || 'AND', rules: [] };
        this._refresh();
        this._renderPanel();
      });
      GB.qs('#fm-logic-and')?.addEventListener('click', () => this._setLogic('AND'));
      GB.qs('#fm-logic-or')?.addEventListener('click',  () => this._setLogic('OR'));
      GB.qs('#fm-col-search')?.addEventListener('input', e => {
        this._renderColList(e.target.value);
      });
    },

    _setLogic(logic) {
      GB.filters.logic = logic;
      GB.qs('#fm-logic-and')?.classList.toggle('active', logic === 'AND');
      GB.qs('#fm-logic-or')?.classList.toggle('active',  logic === 'OR');
      this._refresh();
    },

    // ── Panel render ───────────────────────────────────────────────────
    _renderPanel() {
      const logic = GB.filters.logic || 'AND';
      GB.qs('#fm-logic-and')?.classList.toggle('active', logic === 'AND');
      GB.qs('#fm-logic-or')?.classList.toggle('active',  logic === 'OR');
      this._renderColList();
      this._renderActiveChips();
      this._updateBadge();
    },

    _updateBadge() {
      const n = (GB.filters.rules || []).length;
      const badge = GB.qs('#filter-badge');
      if (badge) { badge.textContent = n > 0 ? String(n) : ''; badge.style.display = n > 0 ? '' : 'none'; }
      GB.qs('#btn-open-filters')?.classList.toggle('active', n > 0);
    },

    // ── Active chips ───────────────────────────────────────────────────
    _renderActiveChips() {
      const box = GB.qs('#fm-active-filters');
      if (!box) return;
      const rules = GB.filters.rules || [];
      if (!rules.length) {
        box.innerHTML = '<span class="gbr-fm-chips-empty">Aucun filtre actif.</span>';
        return;
      }
      box.innerHTML = rules.map(r => `
        <div class="gbr-fm-chip" data-rule-id="${GB.esc(r.id)}">
          <span class="gbr-fm-chip-lbl">
            <b>${GB.esc(r.column)}</b>
            ${GB.esc(this._ruleLabel(r))}
          </span>
          <button class="gbr-fm-chip-del" data-del="${GB.esc(r.id)}">✕</button>
        </div>`).join('');
      box.onclick = e => {
        const del = e.target.closest('[data-del]');
        if (del) {
          GB.filters.rules = GB.filters.rules.filter(r => r.id !== del.dataset.del);
          this._refresh();
          this._renderColList();
          return;
        }
        const chip = e.target.closest('.gbr-fm-chip');
        if (chip && !e.target.closest('[data-del]')) {
          const rule = GB.filters.rules.find(r => r.id === chip.dataset.ruleId);
          if (rule) this._openEditor(rule.column);
        }
      };
    },

    _ruleLabel(r) {
      if (r.op === 'range') return ` ∈ [${this._fmt(r.min)} – ${this._fmt(r.max)}]`;
      if (r.op === 'in_arr') {
        const shown = r.values.slice(0, 3).join(', ');
        return ` ∈ {${shown}${r.values.length > 3 ? '…' : ''}}`;
      }
      return ` ${r.op} ${r.value ?? ''}`;
    },

    // ── Column list ────────────────────────────────────────────────────
    _renderColList(q = '') {
      const box = GB.qs('#fm-col-list');
      if (!box) return;
      const cols  = (GB.columns || []).filter(c => c.type !== 'vector' && c.type !== 'matrix');
      const lq    = q.trim().toLowerCase();
      const list  = lq ? cols.filter(c => c.name.toLowerCase().includes(lq)) : cols;
      if (!list.length) {
        box.innerHTML = `<div style="padding:12px;font-family:var(--gb-mono);font-size:10px;color:#b0b8c8">${q ? 'Aucune colonne.' : 'Aucune donnée chargée.'}</div>`;
        return;
      }
      const active = new Set((GB.filters.rules || []).map(r => r.column));
      const typeIcon = { number: '#', string: 'A', date: '📅' };
      box.innerHTML = list.map(c => `
        <div class="gbr-fm-col-item${active.has(c.name) ? ' has-filter' : ''}" data-col="${GB.esc(c.name)}" data-coltype="${GB.esc(c.type)}">
          <span class="gbr-col-badge gbr-col-badge-${c.type}">${typeIcon[c.type] || '?'}</span>
          <span class="gbr-fm-col-name" title="${GB.esc(c.name)}">${GB.esc(c.name)}</span>
          ${active.has(c.name) ? '<span class="gbr-fm-col-dot">●</span>' : ''}
        </div>`).join('');
      box.querySelectorAll('.gbr-fm-col-item').forEach(el => {
        el.addEventListener('click', () => this._openEditor(el.dataset.col, el.dataset.coltype));
      });
    },

    // ── Editor dispatch ────────────────────────────────────────────────
    _openEditor(colName, colTypeHint) {
      cleanupDrag();
      const editor = GB.qs('#fm-editor');
      if (!editor) return;
      GB.qsa('.gbr-fm-col-item').forEach(el => el.classList.toggle('selected', el.dataset.col === colName));
      const col  = GB.columns?.find(c => c.name === colName) || { name: colName, type: colTypeHint || 'string' };
      const rows = GB.Data?.rows?.() || [];
      if (col.type === 'number') this._renderHistEditor(editor, col, rows);
      else                       this._renderCbEditor(editor, col, rows);
    },

    // ── Histogram editor ───────────────────────────────────────────────
    _renderHistEditor(editor, col, rows) {
      const colName = col.name;
      const vals = rows.map(r => Number(r[colName])).filter(v => isFinite(v)).sort((a, b) => a - b);
      if (!vals.length) {
        editor.innerHTML = '<div class="gbr-fm-ed-empty"><div class="gbr-fm-ed-icon">∅</div><div>Aucune valeur numérique</div></div>';
        return;
      }
      const allMin = vals[0], allMax = vals[vals.length - 1];
      const existing = (GB.filters.rules || []).find(r => r.column === colName && r.op === 'range');
      let curMin = existing ? +existing.min : allMin;
      let curMax = existing ? +existing.max : allMax;

      // Build histogram
      const N = 40;
      const span = allMax - allMin || 1;
      const bins = Array.from({ length: N }, (_, i) => ({ count: 0, from: allMin + i * span / N, to: allMin + (i + 1) * span / N }));
      vals.forEach(v => { const i = Math.min(N - 1, Math.floor((v - allMin) / span * N)); bins[i].count++; });
      const maxCnt = Math.max(...bins.map(b => b.count), 1);
      const W = 400, H = 80;
      const xs = v => Math.max(0, Math.min(W, (v - allMin) / span * W));

      const barsSvg = bins.map((b, i) => {
        const bx = (i / N * W).toFixed(1);
        const bw = Math.max(0.5, W / N - 0.5).toFixed(1);
        const bh = Math.max(1, (b.count / maxCnt) * H).toFixed(1);
        const by = (H - +bh).toFixed(1);
        return `<rect class="fm-bar" x="${bx}" y="${by}" width="${bw}" height="${bh}"/>`;
      }).join('');

      editor.innerHTML = `
        <div class="gbr-fm-ed-hd">
          ${GB.esc(colName)}
          <span class="gbr-fm-type-pill num">#</span>
        </div>

        <div class="gbr-fm-hist-wrap">
          <svg class="gbr-fm-hist-svg" id="fm-hist-svg" viewBox="0 0 ${W} ${H}" preserveAspectRatio="none">
            <g>${barsSvg}</g>
            <rect class="fm-dim" id="fm-dim-l" x="0" y="0" width="${xs(curMin).toFixed(1)}" height="${H}"/>
            <rect class="fm-dim" id="fm-dim-r" x="${xs(curMax).toFixed(1)}" y="0" width="${(W - xs(curMax)).toFixed(1)}" height="${H}"/>
            <g id="fm-h-min" class="fm-handle-grp">
              <line class="fm-handle" x1="${xs(curMin).toFixed(1)}" y1="0" x2="${xs(curMin).toFixed(1)}" y2="${H}"/>
              <rect class="fm-handle-hit" x="${(xs(curMin) - 7).toFixed(1)}" y="0" width="14" height="${H}" fill="transparent" style="cursor:ew-resize"/>
            </g>
            <g id="fm-h-max" class="fm-handle-grp">
              <line class="fm-handle" x1="${xs(curMax).toFixed(1)}" y1="0" x2="${xs(curMax).toFixed(1)}" y2="${H}"/>
              <rect class="fm-handle-hit" x="${(xs(curMax) - 7).toFixed(1)}" y="0" width="14" height="${H}" fill="transparent" style="cursor:ew-resize"/>
            </g>
          </svg>
          <div class="gbr-fm-hist-axis">
            <span>${this._fmt(allMin)}</span>
            <span>${this._fmt((allMin + allMax) / 2)}</span>
            <span>${this._fmt(allMax)}</span>
          </div>
        </div>

        <div class="gbr-fm-range-row">
          <div class="gbr-fm-range-grp">
            <label>Min</label>
            <input class="gbr-fm-range-inp" id="fm-inp-min" type="number" step="any" value="${curMin}">
          </div>
          <div class="gbr-fm-range-grp">
            <label>Max</label>
            <input class="gbr-fm-range-inp" id="fm-inp-max" type="number" step="any" value="${curMax}">
          </div>
        </div>

        <div class="gbr-fm-ed-actions">
          <button class="gbr-fm-apply-btn" id="fm-apply">Appliquer</button>
          <button class="gbr-fm-reset-btn" id="fm-reset">Reset</button>
        </div>

        <div class="gbr-fm-stats">${this._numStats(vals)}</div>
      `;

      // Input → SVG sync
      const syncHandles = () => {
        const mn = parseFloat(GB.qs('#fm-inp-min')?.value);
        const mx = parseFloat(GB.qs('#fm-inp-max')?.value);
        if (!isNaN(mn) && !isNaN(mx)) this._moveHandles(xs(mn), xs(mx), W);
      };
      GB.qs('#fm-inp-min')?.addEventListener('input', syncHandles);
      GB.qs('#fm-inp-max')?.addEventListener('input', syncHandles);

      // Apply button
      GB.qs('#fm-apply')?.addEventListener('click', () => {
        const mn = parseFloat(GB.qs('#fm-inp-min')?.value);
        const mx = parseFloat(GB.qs('#fm-inp-max')?.value);
        if (!isNaN(mn) && !isNaN(mx)) {
          this._setRangeRule(colName, Math.min(mn, mx), Math.max(mn, mx));
          this._refresh();
          this._renderColList(GB.qs('#fm-col-search')?.value || '');
        }
      });

      // Reset
      GB.qs('#fm-reset')?.addEventListener('click', () => {
        GB.filters.rules = (GB.filters.rules || []).filter(r => !(r.column === colName && r.op === 'range'));
        this._refresh();
        this._renderColList(GB.qs('#fm-col-search')?.value || '');
        this._renderHistEditor(editor, col, rows);
      });

      // Drag
      this._bindHistDrag(colName, allMin, allMax, W, H, xs);
    },

    _bindHistDrag(colName, allMin, allMax, W, H, xs) {
      const svg = GB.qs('#fm-hist-svg');
      if (!svg) return;
      let which = null;

      const getVal = clientX => {
        const rect = svg.getBoundingClientRect();
        const ratio = Math.max(0, Math.min(1, (clientX - rect.left) / rect.width));
        return allMin + (allMax - allMin) * ratio;
      };

      const onDown = (e, handle) => { e.preventDefault(); which = handle; svg.classList.add('dragging'); };
      svg.querySelector('#fm-h-min')?.addEventListener('mousedown', e => onDown(e, 'min'));
      svg.querySelector('#fm-h-max')?.addEventListener('mousedown', e => onDown(e, 'max'));

      const onMove = e => {
        if (!which) return;
        const v = getVal(e.clientX);
        const inMin = GB.qs('#fm-inp-min'), inMax = GB.qs('#fm-inp-max');
        if (!inMin || !inMax) return;
        if (which === 'min') inMin.value = Math.min(v, parseFloat(inMax.value)).toFixed(4);
        else                 inMax.value = Math.max(v, parseFloat(inMin.value)).toFixed(4);
        this._moveHandles(xs(parseFloat(inMin.value)), xs(parseFloat(inMax.value)), W);
      };

      const onUp = () => {
        if (!which) return;
        svg.classList.remove('dragging');
        which = null;
        const mn = parseFloat(GB.qs('#fm-inp-min')?.value);
        const mx = parseFloat(GB.qs('#fm-inp-max')?.value);
        if (!isNaN(mn) && !isNaN(mx)) {
          this._setRangeRule(colName, Math.min(mn, mx), Math.max(mn, mx));
          this._refresh();
          this._renderColList(GB.qs('#fm-col-search')?.value || '');
        }
      };

      window.addEventListener('mousemove', onMove);
      window.addEventListener('mouseup', onUp);
      _dragCleanup = () => { window.removeEventListener('mousemove', onMove); window.removeEventListener('mouseup', onUp); };
    },

    _moveHandles(xMin, xMax, W) {
      xMin = Math.max(0, Math.min(W, xMin));
      xMax = Math.max(0, Math.min(W, xMax));
      const hMin = GB.qs('#fm-h-min'), hMax = GB.qs('#fm-h-max');
      const dL   = GB.qs('#fm-dim-l'),  dR  = GB.qs('#fm-dim-r');
      // Move min handle (line + hit rect)
      if (hMin) {
        const l = hMin.querySelector('line'), r = hMin.querySelector('rect');
        if (l) { l.setAttribute('x1', xMin.toFixed(1)); l.setAttribute('x2', xMin.toFixed(1)); }
        if (r) r.setAttribute('x', (xMin - 7).toFixed(1));
      }
      // Move max handle (line + hit rect)
      if (hMax) {
        const l = hMax.querySelector('line'), r = hMax.querySelector('rect');
        if (l) { l.setAttribute('x1', xMax.toFixed(1)); l.setAttribute('x2', xMax.toFixed(1)); }
        if (r) r.setAttribute('x', (xMax - 7).toFixed(1));
      }
      if (dL) dL.setAttribute('width', xMin.toFixed(1));
      if (dR) { dR.setAttribute('x', xMax.toFixed(1)); dR.setAttribute('width', (W - xMax).toFixed(1)); }
    },

    _setRangeRule(colName, mn, mx) {
      GB.filters.rules = (GB.filters.rules || []).filter(r => !(r.column === colName && r.op === 'range'));
      GB.filters.rules.push({ id: uid(), column: colName, op: 'range', min: mn, max: mx });
    },

    _numStats(vals) {
      const sum  = vals.reduce((a, b) => a + b, 0);
      const mean = sum / vals.length;
      const med  = vals[Math.floor(vals.length / 2)];
      const q1   = vals[Math.floor(vals.length * 0.25)];
      const q3   = vals[Math.floor(vals.length * 0.75)];
      return `
        <span class="gbr-fm-stat">n <b>${vals.length}</b></span>
        <span class="gbr-fm-stat">min <b>${this._fmt(vals[0])}</b></span>
        <span class="gbr-fm-stat">max <b>${this._fmt(vals[vals.length - 1])}</b></span>
        <span class="gbr-fm-stat">∅ <b>${this._fmt(mean)}</b></span>
        <span class="gbr-fm-stat">med <b>${this._fmt(med)}</b></span>
        <span class="gbr-fm-stat">Q1 <b>${this._fmt(q1)}</b></span>
        <span class="gbr-fm-stat">Q3 <b>${this._fmt(q3)}</b></span>`;
    },

    _fmt(n) {
      if (n == null || !isFinite(n)) return '?';
      if (Math.abs(n) >= 10000) return n.toExponential(2);
      if (Math.abs(n) >= 1)     return parseFloat(n.toPrecision(4)).toString();
      return parseFloat(n.toPrecision(3)).toString();
    },

    // ── Checkbox editor ────────────────────────────────────────────────
    _renderCbEditor(editor, col, rows) {
      const colName = col.name;
      const uniques = [...new Set(rows.map(r => String(r[colName] ?? '')).filter(v => v !== ''))].sort((a, b) => a.localeCompare(b, undefined, { numeric: true }));
      const existing = (GB.filters.rules || []).find(r => r.column === colName && r.op === 'in_arr');
      let selected = existing ? new Set(existing.values) : null; // null = tout sélectionné

      const renderList = (q = '') => {
        const listEl = GB.qs('#fm-cb-list');
        if (!listEl) return;
        const shown = q ? uniques.filter(v => v.toLowerCase().includes(q.toLowerCase())) : uniques;
        listEl.innerHTML = shown.map(v => {
          const checked = selected === null || selected.has(v);
          return `<label class="gbr-fm-cb-item">
            <input type="checkbox" data-cbv="${GB.esc(v)}" ${checked ? 'checked' : ''}>
            <span>${GB.esc(v)}</span>
          </label>`;
        }).join('');
        listEl.querySelectorAll('[data-cbv]').forEach(inp => {
          inp.addEventListener('change', e => {
            e.stopPropagation();
            if (selected === null) selected = new Set(uniques);
            if (inp.checked) selected.add(inp.dataset.cbv); else selected.delete(inp.dataset.cbv);
            if (selected.size === uniques.length) selected = null;
            this._setInArrRule(colName, selected ? [...selected] : null);
            this._refresh();
            this._renderColList(GB.qs('#fm-col-search')?.value || '');
          });
        });
      };

      editor.innerHTML = `
        <div class="gbr-fm-ed-hd">
          ${GB.esc(colName)}
          <span class="gbr-fm-type-pill str">A</span>
        </div>
        <div class="gbr-fm-cb-toolbar">
          <input class="gbr-fm-cb-search" id="fm-cb-q" type="text" placeholder="🔍 Filtrer…">
          <button class="gbr-fm-sel-btn" id="fm-cb-all">Tout</button>
          <button class="gbr-fm-sel-btn" id="fm-cb-none">Rien</button>
        </div>
        <div class="gbr-fm-cb-list" id="fm-cb-list"></div>
        <div class="gbr-fm-cb-info">${uniques.length} valeur${uniques.length > 1 ? 's' : ''} unique${uniques.length > 1 ? 's' : ''}</div>
        <div class="gbr-fm-ed-actions">
          <button class="gbr-fm-reset-btn" id="fm-reset">Reset</button>
        </div>
      `;

      renderList();

      GB.qs('#fm-cb-q')?.addEventListener('input', e => renderList(e.target.value));

      GB.qs('#fm-cb-all')?.addEventListener('click', () => {
        selected = null;
        GB.filters.rules = (GB.filters.rules || []).filter(r => !(r.column === colName && r.op === 'in_arr'));
        this._refresh();
        this._renderColList(GB.qs('#fm-col-search')?.value || '');
        renderList(GB.qs('#fm-cb-q')?.value || '');
      });

      GB.qs('#fm-cb-none')?.addEventListener('click', () => {
        selected = new Set();
        this._setInArrRule(colName, []);
        this._refresh();
        this._renderColList(GB.qs('#fm-col-search')?.value || '');
        renderList(GB.qs('#fm-cb-q')?.value || '');
      });

      GB.qs('#fm-reset')?.addEventListener('click', () => {
        selected = null;
        GB.filters.rules = (GB.filters.rules || []).filter(r => !(r.column === colName && r.op === 'in_arr'));
        this._refresh();
        this._renderColList(GB.qs('#fm-col-search')?.value || '');
        renderList('');
      });
    },

    _setInArrRule(colName, values) {
      GB.filters.rules = (GB.filters.rules || []).filter(r => !(r.column === colName && r.op === 'in_arr'));
      if (values !== null) {
        GB.filters.rules.push({ id: uid(), column: colName, op: 'in_arr', values });
      }
    },

    // ── Legacy compat shim ─────────────────────────────────────────────
    render() { this.open(); },
  };

  // ── Boot: bind modal events once DOM is ready ─────────────────────
  document.addEventListener('DOMContentLoaded', () => {
    GB.Filters._bindModal();
  });
})();
