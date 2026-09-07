'use strict';
/**
 * _gb3_standalone.js — Graph Builder V3 standalone adapter
 *
 * Chargé après graph_builder.core.js, avant les autres modules.
 * Fournit :
 *   - GB.Storage  → localStorage uniquement (pas de server API)
 *   - GB.DAG      → stub no-op
 *   - GB.Assets   → stub no-op
 *   - GB.boot     → override qui injecte directement les données
 */
(function () {
  const GB = window.LumiereGraphBuilder;

  // ── Storage localStorage only ─────────────────────────────────────────
  function uuid() {
    return crypto.randomUUID
      ? crypto.randomUUID()
      : Date.now() + '_' + Math.random().toString(16).slice(2);
  }

  const _KEY  = () => 'lumiere.gb3.views.'   + (window.GB3_CONTEXT || 'standalone');
  const _FKEY = () => 'lumiere.gb3.filters.' + (window.GB3_CONTEXT || 'standalone');

  let _vcache = null;

  GB.Storage = {
    bind() {},

    _load()       { try { return JSON.parse(localStorage.getItem(_KEY()) || '[]'); } catch { return []; } },
    _save(list)   { localStorage.setItem(_KEY(), JSON.stringify(list)); },

    listViews()   { return _vcache || (_vcache = this._load()); },
    list()        { return this.listViews(); },

    async listViewsAsync(force = false) {
      if (!force && _vcache) return _vcache;
      _vcache = this._load();
      GB.emit('views:changed', _vcache);
      return _vcache;
    },

    async prefetch() {
      _vcache = this._load();
      GB.emit('views:changed', _vcache);
    },

    async saveView(view) {
      const list = this._load();
      const now  = new Date().toISOString();
      const v    = { ...view, id: view.id || uuid(), updated_at: now, created_at: view.created_at || now };
      const i    = list.findIndex(x => x.id === v.id);
      if (i >= 0) list[i] = v; else list.unshift(v);
      this._save(list); _vcache = list;
      GB.emit('views:changed', list);
      return v;
    },
    save(v) { return this.saveView(v); },

    async removeView(id) {
      const list = this._load().filter(v => v.id !== id);
      this._save(list); _vcache = list;
      if (GB.activeView?.id === id) GB.activeView = null;
      GB.emit('views:changed', list);
    },
    remove(id) { return this.removeView(id); },

    exportView(id) {
      const v = this._load().find(x => x.id === id);
      if (!v) return;
      const name = (v.name || id).replace(/\W+/g, '_');
      const a    = document.createElement('a');
      a.href     = URL.createObjectURL(new Blob([JSON.stringify(v, null, 2)], { type: 'application/json' }));
      a.download = 'gb3_view_' + name + '.json';
      a.click(); URL.revokeObjectURL(a.href);
    },

    async importViewFile(file) {
      try {
        const text = await file.text();
        const obj  = JSON.parse(text);
        obj.id     = uuid();
        const list = this._load();
        list.unshift(obj); this._save(list); _vcache = list;
        GB.emit('views:changed', list);
        GB.toast('✓ Vue "' + (obj.name || 'importée') + '" importée');
        return obj;
      } catch (e) {
        GB.toast('Erreur import : ' + e.message);
        return null;
      }
    },

    // Filter presets
    listFilters() { try { return JSON.parse(localStorage.getItem(_FKEY()) || '[]'); } catch { return []; } },
    saveFilterPreset(p) {
      const list = this.listFilters();
      p.id         = p.id || uuid();
      p.updated_at = new Date().toISOString();
      p.created_at = p.created_at || p.updated_at;
      const i = list.findIndex(v => v.id === p.id);
      if (i >= 0) list[i] = p; else list.unshift(p);
      localStorage.setItem(_FKEY(), JSON.stringify(list));
      GB.emit('filters:presets:changed', list);
      return p;
    },
    removeFilterPreset(id) {
      const list = this.listFilters().filter(v => v.id !== id);
      localStorage.setItem(_FKEY(), JSON.stringify(list));
      GB.emit('filters:presets:changed', list);
    },
  };

  // ── DAG stub ──────────────────────────────────────────────────────────
  GB.DAG = {
    async load()         {},
    detectInputs()       {},
    async run()          {},
    async fetchJson(url) { throw new Error('[GB3] Standalone mode: no server (' + url + ')'); },
  };

  // ── Assets stub ───────────────────────────────────────────────────────
  GB.Assets = {
    bind()            {},
    openDrawer()      {},
    async bootExplore() {},
  };

  // ── Boot override (data injection directe, pas de DAG) ────────────────
  GB.boot = async function () {
    this.UI.bindStatic();
    this.PlotlyBridge.bind();
    this.Storage.bind();
    this.UI.renderExtensions();
    await this.Storage.prefetch();
    this.UI.renderSavedViews();
    this.UI.renderFilterPresets?.();
    this.Filters?.close?.();

    // Titre standalone
    const titleEl = this.qs('#gb3-title');
    if (titleEl) titleEl.textContent = window.GB3_TITLE || 'Graph Builder V3';
    document.title = (window.GB3_TITLE || 'Graph Builder V3') + ' — LUMIÈRE';

    const pill = this.qs('#source-pill');
    if (pill) { pill.textContent = 'DATA'; pill.className = 'gbr-source-pill asset'; }

    // Ingest données injectées par Python
    if (window.GB3_DATA) {
      this.Data.ingest(window.GB3_DATA);
      this.emit('data:ready');
      this.toast('Données chargées');
    } else {
      this.qs('#col-groups').innerHTML = '<div class="gbr-col-empty">Aucune donnée fournie.</div>';
    }
  };

  // Prefetch non-bloquant au DOMContentLoaded
  document.addEventListener('DOMContentLoaded', () => {
    GB.Storage.prefetch().catch(() => {});
  });

})();
