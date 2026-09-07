'use strict';
(function(){
  const GB = window.LumiereGraphBuilder;

  function isPlainObject(v){
    return v && typeof v === 'object' && !Array.isArray(v);
  }

  function maybeParseJson(v){
    if(typeof v !== 'string') return v;
    const s = v.trim();
    if(!s || s === '[object Object]') return v;
    if(!(s.startsWith('{') || s.startsWith('['))) return v;
    try { return JSON.parse(s); } catch(e) { return v; }
  }

  function isRecordArray(v){
    return Array.isArray(v) && v.length > 0 && v.every((r, i) => {
      if(i > 30) return true;
      return isPlainObject(r);
    });
  }

  // Table technique renvoyée par /api/run : ce n'est PAS un dataset métier.
  // Colonnes typiques : instance_id, node_name, label, ok, error, duration_ms, outputs, preview_html, asset_path
  function isDagRunTable(rows){
    if(!isRecordArray(rows)) return false;
    const keys = new Set(Object.keys(rows[0] || {}));
    const score = [
      'instance_id', 'node_name', 'ok', 'duration_ms', 'outputs', 'preview_html'
    ].filter(k => keys.has(k)).length;
    return score >= 4;
  }

  function columnsRecordsToRows(obj){
    if(!isPlainObject(obj)) return null;

    const records = obj.records ?? obj.rows ?? obj.data ?? obj.values;
    if(isRecordArray(records)) return records;

    const cols = obj.columns;
    if(Array.isArray(cols) && Array.isArray(records) && Array.isArray(records[0])){
      return records.map(row => Object.fromEntries(cols.map((c, i) => [String(c), row[i]])));
    }

    return null;
  }

  function normalizeRows(rows, datasetKey='main'){
    if(!Array.isArray(rows)) return [];
    return rows.map((r, idx) => {
      const out = {};
      out.__gb_row_id = String(r?.__gb_row_id || `${datasetKey}::${idx}`);
      Object.entries(r || {}).forEach(([k,v]) => {
        if(Array.isArray(v)) out[k] = v;   // préserver les vecteurs/matrices tels quels
        else if(v && typeof v === 'object') out[k] = JSON.stringify(v);
        else out[k] = v;
      });
      return out;
    });
  }

  function niceKey(s){
    return String(s || 'main')
      .replace(/^result\./, '')
      .replace(/^steps\.\d+\./, '')
      .replace(/\s+/g, '_');
  }

  GB.Data = {
    ingest(result){
      const datasets = {};
      const seen = new WeakSet();

      const add = (name, rows, meta={}) => {
        // sécurité : ne jamais ajouter la table de logs DAG comme dataset métier
        if(isDagRunTable(rows)) return;

        let key = niceKey(name || meta.label || 'main');
        if(datasets[key]) key = key + '_' + (Object.keys(datasets).length + 1);

        const clean = normalizeRows(rows, key);
        if(!clean.length) return;

        datasets[key] = clean;
      };

      const scanOutputs = (outputs, basePath) => {
        outputs = maybeParseJson(outputs);
        if(!isPlainObject(outputs)) return;

        Object.entries(outputs).forEach(([outName, outVal]) => {
          scan(maybeParseJson(outVal), `${basePath}.${outName}`);
        });
      };

      const scanStep = (step, i=0) => {
        if(!isPlainObject(step)) return;
        const label = step.label || step.node_name || step.instance_id || `step_${i}`;
        scanOutputs(step.outputs, label);

        // Certains backends peuvent mettre directement le dataframe sur output/result/data.
        ['output', 'result', 'data', 'value'].forEach(k => {
          if(step[k] !== undefined) scan(maybeParseJson(step[k]), `${label}.${k}`);
        });
      };

      const scan = (obj, path='main') => {
        obj = maybeParseJson(obj);
        if(obj === null || obj === undefined) return;

        if(Array.isArray(obj)){
          if(isDagRunTable(obj)){
            obj.forEach((step, i) => scanStep(step, i));
            return;
          }
          if(isRecordArray(obj)){
            add(path, obj);
            return;
          }
          obj.forEach((v,i) => scan(v, `${path}.${i}`));
          return;
        }

        if(typeof obj !== 'object') return;
        if(seen.has(obj)) return;
        seen.add(obj);

        // Format dataframe : {type:'dataframe', columns:[...], records:[...]}
        if(obj.type === 'dataframe' || obj.kind === 'dataframe'){
          const rows = columnsRecordsToRows(obj);
          if(rows) add(path, rows);
          return;
        }

        // Formats directs : {columns, records}, {columns, rows}, {data:[{...}]}
        const rows = columnsRecordsToRows(obj);
        if(rows){
          add(path, rows);
          return;
        }

        // Format run : {ok:true, steps:[...]}
        if(Array.isArray(obj.steps)){
          obj.steps.forEach((step, i) => scanStep(step, i));
        }

        // Format alternatif : {outputs:{main:{type:'dataframe'}}}
        if(obj.outputs !== undefined){
          scanOutputs(obj.outputs, path === 'main' ? 'outputs' : `${path}.outputs`);
        }

        // Autres conventions fréquentes.
        ['datasets', 'dataframes', 'tables', 'results'].forEach(k => {
          if(obj[k] !== undefined) scan(obj[k], path === 'main' ? k : `${path}.${k}`);
        });

        // Scan récursif léger, en évitant les gros champs HTML/logs et les branches déjà traitées.
        Object.entries(obj).forEach(([k,v]) => {
          if(['steps','outputs','datasets','dataframes','tables','results','preview_html','error','asset_path'].includes(k)) return;
          scan(v, path === 'main' ? k : `${path}.${k}`);
        });
      };

      scan(result);

      GB.datasets = datasets;
      GB.activeDataset = Object.keys(datasets)[0] || null;
      GB.resetHidden?.();
      this.refreshColumns();

      GB.UI.renderDatasetSelect();
      GB.UI.renderColumns();
      GB.UI.renderTable();
      GB.Filters.render?.();
      GB.PlotlyBridge.renderConfig();
      GB.PlotlyBridge.render();

      if(!GB.activeDataset){
        console.warn('[GraphBuilder] Aucun dataset métier détecté dans le résultat du run:', result);
        GB.toast('Aucun dataset métier détecté dans la sortie du DAG');
      }
    },

    rows(){ return GB.activeDataset ? (GB.datasets[GB.activeDataset] || []) : []; },
    filteredRows(){
      const filtered = GB.Filters.apply(this.rows(), GB.filters);
      const hidden = GB.hidden?.ids || new Set();
      if(!hidden.size) return filtered;
      return filtered.filter(r => !hidden.has(r.__gb_row_id));
    },
    visibleRows(){ return this.filteredRows(); },
    hiddenCount(){ return GB.hidden?.ids?.size || 0; },

    refreshColumns(){
      const rows = this.rows();
      const names = new Set();
      rows.slice(0,200).forEach(r => Object.keys(r||{}).forEach(k => { if(k !== '__gb_row_id') names.add(k); }));
      GB.columns = [...names].map(name => ({name, type:this.typeOf(name, rows)}));
    },

    typeOf(name, rows){
      const vals = rows.map(r=>r?.[name]).filter(v=>v!==null && v!==undefined && v!=='').slice(0,40);
      if(!vals.length) return 'empty';
      if(vals.every(v => Array.isArray(v) && v.length > 0 && Array.isArray(v[0]))) return 'matrix';
      if(vals.every(v => Array.isArray(v))) return 'vector';
      if(vals.every(v => typeof v === 'number' || (!isNaN(Number(v)) && String(v).trim() !== ''))) return 'number';
      if(vals.every(v => !isNaN(Date.parse(v)))) return 'date';
      return 'string';
    },

    exportCsv(){
      const rows = this.filteredRows(); if(!rows.length) return;
      const cols = GB.columns.filter(c => c.type !== 'vector' && c.type !== 'matrix').map(c=>c.name);
      const csv = [cols.join(',')].concat(rows.map(r => cols.map(c => JSON.stringify(r[c] ?? '')).join(','))).join('\n');
      const a=document.createElement('a');
      a.href=URL.createObjectURL(new Blob([csv],{type:'text/csv'}));
      a.download=`${GB.dagId}_${GB.activeDataset || 'dataset'}.csv`;
      a.click();
      URL.revokeObjectURL(a.href);
    },

    profile(){
      return GB.columns.map(c => {
        const vals = this.filteredRows().map(r=>r[c.name]).filter(v=>v!==null&&v!==undefined&&v!=='');
        const nums = c.type==='number' ? vals.map(Number).filter(Number.isFinite) : [];
        return {
          name:c.name,
          type:c.type,
          n:vals.length,
          unique:new Set(vals.map(String)).size,
          min:nums.length?Math.min(...nums):null,
          max:nums.length?Math.max(...nums):null,
          mean:nums.length?nums.reduce((a,b)=>a+b,0)/nums.length:null
        };
      });
    }
  };
})();
