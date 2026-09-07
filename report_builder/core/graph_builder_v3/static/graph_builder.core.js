'use strict';
(function(){
  const GB = {
    // ── Identité de la session ────────────────────────────────────────
    mode:      window.LUMIERE_MODE   || 'dag',      // 'dag' | 'explore'
    dagId:     window.LUMIERE_DAG_ID || null,
    assetName: window.LUMIERE_ASSET  || null,

    // ── État de données ───────────────────────────────────────────────
    dag: null,
    schemas: {},
    inputs: {},
    datasets: {},
    activeDataset: null,
    columns: [],
    filters: { logic:'AND', rules:[] },
    hidden: { ids:new Set(), lastSelection:[] },

    // ── Extensions & vues ─────────────────────────────────────────────
    extensions: {},
    activeExtension: 'scatter',
    activeView: null,
    activeFilterPreset: null,
    currentConfig: {},
    _stepperEl: null,   // référence au stepper actif (dag ou explore)

    // ── Event system ──────────────────────────────────────────────────
    events: new EventTarget(),
    on(name, fn){ this.events.addEventListener(name, e => fn(e.detail)); },
    emit(name, detail){ this.events.dispatchEvent(new CustomEvent(name, {detail})); },

    // ── Helpers ───────────────────────────────────────────────────────
    qs(sel, root=document){ return root.querySelector(sel); },
    qsa(sel, root=document){ return [...root.querySelectorAll(sel)]; },
    esc(s){ return String(s ?? '').replace(/[&<>"']/g, m => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#039;'}[m])); },
    toast(msg){
      const el = this.qs('#toast');
      if (!el) return;
      el.textContent = msg;
      el.classList.add('show');
      clearTimeout(this._toastT);
      this._toastT = setTimeout(() => el.classList.remove('show'), 2400);
    },

    // ── Stepper ───────────────────────────────────────────────────────
    // Gère les deux steppers (dag : 4 étapes / explore : 3 étapes)
    setStep(step) {
      const dagOrder     = ['inputs', 'run', 'data', 'graph'];
      const exploreOrder = ['source', 'data', 'graph'];
      const order = this.mode === 'explore' ? exploreOrder : dagOrder;
      const idx   = order.indexOf(step);

      // Stepper dag
      this.qsa('#stepper span').forEach(s => {
        const i = dagOrder.indexOf(s.dataset.step);
        s.classList.toggle('active', i === idx && this.mode === 'dag');
        s.classList.toggle('done',   i < idx  && this.mode === 'dag');
      });

      // Stepper explore
      this.qsa('#stepper-explore span').forEach(s => {
        const i = exploreOrder.indexOf(s.dataset.step);
        s.classList.toggle('active', i === idx && this.mode === 'explore');
        s.classList.toggle('done',   i < idx  && this.mode === 'explore');
      });
    },

    // ── Extensions ───────────────────────────────────────────────────
    registerExtension(ext){
      if (!ext || !ext.id || typeof ext.render !== 'function') return;
      this.extensions[ext.id] = Object.assign({category:'General', icon:'◇', defaultConfig:{}}, ext);
      this.emit('extensions:changed');
    },

    // ── Hidden rows ───────────────────────────────────────────────────
    resetHidden(){ this.hidden.ids = new Set(); this.hidden.lastSelection = []; this.emit('hidden:changed'); },
    hideIds(ids){
      (ids||[]).filter(Boolean).forEach(id => this.hidden.ids.add(id));
      this.hidden.lastSelection = [];
      this.emit('hidden:changed');
    },
    unhideAll(){
      this.resetHidden();
      this.UI?.renderTable?.();
      this.PlotlyBridge?.render?.();
      this.toast('Points masqués réaffichés');
    },

    // ── Boot ─────────────────────────────────────────────────────────
    async boot(){
      this.UI.bindStatic();
      this.PlotlyBridge.bind();
      this.Storage.bind();
      this.Assets?.bind?.();
      this.UI.renderExtensions();
      this.UI.renderSavedViews();
      this.UI.renderFilterPresets?.();

      if (this.mode === 'explore') {
        // Mode asset : pas de DAG à charger, stepper simplifié
        await this.Assets.bootExplore();
      } else {
        // Mode dag : comportement existant
        await this.DAG.load();
        this.UI.renderHeader();
        this.UI.renderInputs();
        const runBtn = this.qs('#btn-run');
        if (runBtn) runBtn.disabled = false;
        this.setStep('inputs');
        this.toast('Graph Builder prêt');
      }
      // S'assurer que le modal filtre est fermé au démarrage
      this.Filters?.close?.();
    }
  };
  window.LumiereGraphBuilder = GB;
})();
