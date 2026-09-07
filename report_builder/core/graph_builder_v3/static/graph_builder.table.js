'use strict';
/**
 * graph_builder.table.js v3
 * - Suppression des filtres inline (gérés exclusivement par le modal filtre)
 * - Stats par colonne en 2e ligne de header (min/max/mean/σ pour number, uniques pour string)
 * - Sort, pagination, visibilité colonnes, recherche globale, stats footer
 */
(function () {
  const GB = window.LumiereGraphBuilder;

  let _page      = 0;
  let _pageSize  = 50;
  let _sortCol   = null;
  let _sortDir   = 'asc';
  let _globalQ   = '';
  let _hiddenCols = new Set();
  let _rows      = [];

  GB.Table = {

    render() {
      this._loadRows();
      this._renderHeader();
      this._renderBody();
      this._renderPagination();
      this._renderInfo();
      this._bindControls();
    },

    // ── Helpers stats ──────────────────────────────────────────────────
    _median(arr) {
      if (!arr.length) return null;
      const s = [...arr].sort((a, b) => a - b);
      const m = Math.floor(s.length / 2);
      return s.length % 2 ? s[m] : (s[m - 1] + s[m]) / 2;
    },
    _std(arr) {
      if (arr.length < 2) return 0;
      const mean = arr.reduce((a, b) => a + b, 0) / arr.length;
      const variance = arr.reduce((s, v) => s + (v - mean) ** 2, 0) / (arr.length - 1);
      return Math.sqrt(variance);
    },
    _fmt(n) {
      if (n == null || !isFinite(n)) return '?';
      if (Math.abs(n) >= 100000) return n.toExponential(2);
      if (Math.abs(n) >= 1)      return parseFloat(n.toPrecision(4)).toString();
      return parseFloat(n.toPrecision(3)).toString();
    },

    // ── Data pipeline ──────────────────────────────────────────────────
    _loadRows() {
      let rows = GB.Data?.filteredRows?.() || GB.Data?.visibleRows?.() || [];

      if (_globalQ.trim()) {
        const q = _globalQ.trim().toLowerCase();
        rows = rows.filter(r => Object.values(r).some(v => String(v ?? '').toLowerCase().includes(q)));
      }

      if (_sortCol) {
        rows = [...rows].sort((a, b) => {
          const av = a[_sortCol] ?? '', bv = b[_sortCol] ?? '';
          const n = parseFloat(av), m = parseFloat(bv);
          const cmp = !isNaN(n) && !isNaN(m) ? n - m : String(av).localeCompare(String(bv));
          return _sortDir === 'asc' ? cmp : -cmp;
        });
      }
      _rows = rows;
    },

    _allRows()    { return GB.Data?.filteredRows?.() || []; },
    _sourceRows() { return GB.Data?.rows?.() || []; },
    _visibleCols() { return (GB.columns || []).filter(c => !_hiddenCols.has(c.name)); },
    _pageRows() {
      if (_pageSize === 0) return _rows;
      return _rows.slice(_page * _pageSize, (_page + 1) * _pageSize);
    },

    // ── Header ─────────────────────────────────────────────────────────
    _renderHeader() {
      const thead = GB.qs('#data-thead');
      if (!thead) return;
      const cols    = this._visibleCols();
      const srcRows = this._sourceRows(); // stats sur TOUTES les données source

      const sortIcon = c => {
        if (_sortCol !== c.name) return '<span class="tbl-sort-icon">⇅</span>';
        return _sortDir === 'asc'
          ? '<span class="tbl-sort-icon active">↑</span>'
          : '<span class="tbl-sort-icon active">↓</span>';
      };

      // Ligne 1 : noms de colonnes + sort
      const hd1 = `<tr class="tbl-hd-row">
        <th class="tbl-rownum">#</th>
        ${cols.map(c => `
          <th class="tbl-th tbl-th-${c.type}" data-sort-col="${GB.esc(c.name)}">
            <div class="tbl-th-inner">
              <span class="tbl-col-badge gbr-col-badge-${c.type}">${c.type === 'number' ? '#' : c.type === 'date' ? '📅' : 'A'}</span>
              <span class="tbl-col-name" title="${GB.esc(c.name)}">${GB.esc(c.name)}</span>
              ${sortIcon(c)}
            </div>
          </th>`).join('')}
      </tr>`;

      // Ligne 2 : stats par colonne (remplace les filtres inline)
      const statsCell = c => {
        if (c.type === 'vector') {
          const cnt = srcRows.filter(r => Array.isArray(r[c.name])).length;
          const len = srcRows.find(r => Array.isArray(r[c.name]))?.[c.name]?.length ?? '?';
          return `<th class="tbl-col-stats-cell"><div class="tbl-col-stats"><span class="tbl-cs">∿ ${cnt} × ${len}</span></div></th>`;
        }
        if (c.type === 'matrix') {
          const ex = srcRows.find(r => Array.isArray(r[c.name]))?.[c.name];
          const dim = ex ? `${ex.length}×${ex[0]?.length??'?'}` : '?';
          return `<th class="tbl-col-stats-cell"><div class="tbl-col-stats"><span class="tbl-cs">⊞ ${dim}</span></div></th>`;
        }
        if (c.type === 'number') {
          const vals = srcRows.map(r => parseFloat(r[c.name])).filter(v => isFinite(v));
          if (!vals.length) return '<th class="tbl-col-stats-cell">—</th>';
          const min  = Math.min(...vals);
          const max  = Math.max(...vals);
          const mean = vals.reduce((a, b) => a + b, 0) / vals.length;
          const std  = this._std(vals);
          const nulls = srcRows.length - vals.length;
          const fmt = this._fmt.bind(this);
          return `<th class="tbl-col-stats-cell">
            <div class="tbl-col-stats">
              <span class="tbl-cs" title="minimum">▼ ${fmt(min)}</span>
              <span class="tbl-cs" title="maximum">▲ ${fmt(max)}</span>
              <span class="tbl-cs" title="moyenne">∅ ${fmt(mean)}</span>
              <span class="tbl-cs" title="écart-type">σ ${fmt(std)}</span>
              ${nulls ? `<span class="tbl-cs null" title="nulls">∅${nulls}</span>` : ''}
            </div>
          </th>`;
        }
        if (c.type === 'date') {
          const vals = srcRows.map(r => r[c.name]).filter(v => v != null && v !== '');
          const sorted = [...vals].sort();
          const trunc = s => s ? String(s).slice(0, 10) : '—';
          return `<th class="tbl-col-stats-cell">
            <div class="tbl-col-stats">
              <span class="tbl-cs" title="premier">${trunc(sorted[0])}</span>
              <span class="tbl-cs" title="dernier">${trunc(sorted[sorted.length - 1])}</span>
            </div>
          </th>`;
        }
        // string
        const uniques = new Set(srcRows.map(r => String(r[c.name] ?? '')).filter(v => v !== '')).size;
        const nulls   = srcRows.filter(r => r[c.name] == null || r[c.name] === '').length;
        return `<th class="tbl-col-stats-cell">
          <div class="tbl-col-stats">
            <span class="tbl-cs" title="valeurs uniques">◈ ${uniques}</span>
            ${nulls ? `<span class="tbl-cs null" title="nulls">∅${nulls}</span>` : ''}
          </div>
        </th>`;
      };

      const hd2 = `<tr class="tbl-filter-row">
        <th class="tbl-rownum"></th>
        ${cols.map(c => statsCell(c)).join('')}
      </tr>`;

      thead.innerHTML = hd1 + hd2;

      // Sort click
      thead.querySelectorAll('[data-sort-col]').forEach(th => {
        th.addEventListener('click', () => {
          const col = th.dataset.sortCol;
          if (_sortCol === col) {
            _sortDir = _sortDir === 'asc' ? 'desc' : _sortDir === 'desc' ? null : 'asc';
            if (_sortDir === null) { _sortCol = null; _sortDir = 'asc'; }
          } else { _sortCol = col; _sortDir = 'asc'; }
          _page = 0; this.render();
        });
      });
    },

    // ── Body ───────────────────────────────────────────────────────────
    _renderBody() {
      const tbody = GB.qs('#data-tbody'); if (!tbody) return;
      const cols  = this._visibleCols(), rows = this._pageRows();
      const offset = _pageSize ? _page * _pageSize : 0;

      if (!rows.length) {
        tbody.innerHTML = `<tr><td colspan="${cols.length + 1}" class="tbl-empty">Aucune donnée</td></tr>`;
        return;
      }

      tbody.innerHTML = rows.map((r, i) => {
        const hidden = GB.hidden?.ids?.has(r.__gb_row_id) ? 'tbl-row-hidden' : '';
        return `<tr class="tbl-row ${hidden}">
          <td class="tbl-rownum">${offset + i + 1}</td>
          ${cols.map(c => {
            const v = r[c.name];
            const isNull = v === null || v === undefined || v === '';
            const isArr  = Array.isArray(v);
            const cls    = isNull ? 'tbl-null' : (!isArr && c.type === 'number') ? 'tbl-num' : '';
            let disp;
            if (isNull) disp = '<span class="tbl-null-marker">null</span>';
            else if (isArr && Array.isArray(v[0])) disp = `<span class="tbl-vec-tag mat">⊞ ${v.length}×${v[0]?.length??'?'}</span>`;
            else if (isArr) disp = `<span class="tbl-vec-tag vec">∿ ${v.length}</span>`;
            else disp = GB.esc(String(v));
            const title = isArr ? '' : GB.esc(String(v ?? ''));
            return `<td class="tbl-td ${cls}" title="${title}">${disp}</td>`;
          }).join('')}
        </tr>`;
      }).join('');

      tbody.insertAdjacentHTML('beforeend', this._statsRow(cols, _rows));
    },

    _statsRow(cols, rows) {
      if (!rows.length) return '';
      const fmt = this._fmt.bind(this);
      return `<tr class="tbl-stats-row">
        <td class="tbl-rownum tbl-stats-lbl">Σ</td>
        ${cols.map(c => {
          if (c.type === 'number') {
            const vals = rows.map(r => parseFloat(r[c.name])).filter(v => isFinite(v));
            if (!vals.length) return '<td class="tbl-stats-cell">—</td>';
            const sum  = vals.reduce((a, b) => a + b, 0);
            const avg  = sum / vals.length;
            const nulls = rows.length - vals.length;
            return `<td class="tbl-stats-cell">
              <span class="tbl-stat" title="somme">Σ ${fmt(sum)}</span>
              <span class="tbl-stat" title="moyenne">∅ ${fmt(avg)}</span>
              <span class="tbl-stat" title="médiane">Med ${fmt(this._median(vals))}</span>
              <span class="tbl-stat" title="écart-type">σ ${fmt(this._std(vals))}</span>
              ${nulls ? `<span class="tbl-stat null">${nulls} null</span>` : ''}
            </td>`;
          }
          const nulls = rows.filter(r => r[c.name] == null || r[c.name] === '').length;
          const uniq  = new Set(rows.map(r => r[c.name])).size;
          return `<td class="tbl-stats-cell"><span class="tbl-stat">${uniq} uniq</span>${nulls ? `<span class="tbl-stat null">${nulls} null</span>` : ''}</td>`;
        }).join('')}
      </tr>`;
    },

    // ── Pagination ─────────────────────────────────────────────────────
    _renderPagination() {
      const pg = GB.qs('#table-pagination'); if (!pg) return;
      if (_pageSize === 0) { pg.innerHTML = ''; return; }
      const total = _rows.length, pages = Math.ceil(total / _pageSize);
      if (pages <= 1) { pg.innerHTML = ''; return; }
      const MAX = 7;
      const btns = () => {
        if (pages <= MAX) return [...Array(pages)].map((_, i) => i);
        const r = [0];
        let s = Math.max(1, _page - 2), e = Math.min(pages - 2, _page + 2);
        if (s > 1) r.push('...');
        for (let i = s; i <= e; i++) r.push(i);
        if (e < pages - 2) r.push('...');
        r.push(pages - 1); return r;
      };
      pg.innerHTML = `
        <button class="pgr-btn" ${_page === 0 ? 'disabled' : ''} data-pg="${_page - 1}">←</button>
        ${btns().map(p => p === '...'
          ? `<span class="pgr-ellipsis">…</span>`
          : `<button class="pgr-btn ${p === _page ? 'active' : ''}" data-pg="${p}">${p + 1}</button>`
        ).join('')}
        <button class="pgr-btn" ${_page >= pages - 1 ? 'disabled' : ''} data-pg="${_page + 1}">→</button>
        <span class="pgr-info">${_page * _pageSize + 1}–${Math.min((_page + 1) * _pageSize, total)} / ${total}</span>`;
      pg.querySelectorAll('[data-pg]').forEach(b =>
        b.addEventListener('click', () => { _page = parseInt(b.dataset.pg); this._renderBody(); this._renderPagination(); })
      );
    },

    _renderInfo() {
      const el = GB.qs('#table-info'); if (!el) return;
      const total = (GB.Data?.filteredRows?.() || []).length, shown = _rows.length;
      const active = !!_globalQ;
      el.innerHTML = `<b>${shown}</b> lignes${active && shown !== total ? ` (filtré de ${total})` : ''}`;
    },

    // ── Controls ───────────────────────────────────────────────────────
    _bindControls() {
      const gs = GB.qs('#table-search');
      if (gs && !gs._tbl) {
        gs._tbl = 1;
        gs.addEventListener('input', e => {
          _globalQ = e.target.value; _page = 0;
          this._loadRows(); this._renderBody(); this._renderPagination(); this._renderInfo();
        });
      }

      const ps = GB.qs('#table-pagesize');
      if (ps && !ps._tbl) {
        ps._tbl = 1;
        ps.addEventListener('change', e => {
          _pageSize = parseInt(e.target.value); _page = 0;
          this._loadRows(); this._renderBody(); this._renderPagination(); this._renderInfo();
        });
      }

      const clr = GB.qs('#btn-table-clear-filters');
      if (clr && !clr._tbl) {
        clr._tbl = 1;
        clr.addEventListener('click', () => {
          _globalQ = ''; const s = GB.qs('#table-search'); if (s) s.value = '';
          _page = 0; this.render();
        });
      }

      const cv = GB.qs('#btn-table-col-toggle');
      if (cv && !cv._tbl) {
        cv._tbl = 1;
        cv.addEventListener('click', () => {
          const p = GB.qs('#col-visibility-pop');
          if (!p) return;
          p.style.display = p.style.display === 'none' ? 'block' : 'none';
          if (p.style.display === 'block') this._renderColVisPop(p);
        });
      }

      document.addEventListener('click', e => {
        const p = GB.qs('#col-visibility-pop');
        if (p && !e.target.closest('#btn-table-col-toggle') && !e.target.closest('#col-visibility-pop'))
          p.style.display = 'none';
      });
    },

    _renderColVisPop(pop) {
      const cols = GB.columns || [];
      pop.innerHTML = `<div class="gbr-cv-hd">Colonnes<button class="gbr-cv-all" id="cv-all">Tout</button><button class="gbr-cv-all" id="cv-none">Aucun</button></div>
      ${cols.map(c => `<label class="gbr-cv-item"><input type="checkbox" data-cv="${GB.esc(c.name)}" ${_hiddenCols.has(c.name) ? '' : 'checked'}><span class="gbr-col-badge gbr-col-badge-${c.type}">${c.type === 'number' ? '#' : c.type === 'date' ? '📅' : 'A'}</span>${GB.esc(c.name)}</label>`).join('')}`;
      pop.querySelectorAll('[data-cv]').forEach(inp =>
        inp.addEventListener('change', e => {
          if (e.target.checked) _hiddenCols.delete(e.target.dataset.cv);
          else _hiddenCols.add(e.target.dataset.cv);
          this.render();
        })
      );
      pop.querySelector('#cv-all')?.addEventListener('click', () => { _hiddenCols.clear(); this.render(); this._renderColVisPop(pop); });
      pop.querySelector('#cv-none')?.addEventListener('click', () => { cols.forEach(c => _hiddenCols.add(c.name)); this.render(); this._renderColVisPop(pop); });
    },
  };
})();
