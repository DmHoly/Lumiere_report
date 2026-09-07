// table.js

var TBL = {
  excluded: {},          /* rowIndex → true */
  computedCols: [],       /* {name, expr} */
  sortCol: null,
  sortDir: 1,
  searchQ: '',
  customCols: {},        /* name → array of values (index = DATA index) */
};

/* Scalar columns only (no vectors) */
function tblScalarCols() {
  var base = SCALAR_NUM.concat(SCALAR_CAT);
  TBL.computedCols.forEach(function(c){ if(base.indexOf(c.name)<0) base.push(c.name); });
  return base;
}

/* Get effective DATA (with computed values) */
function tblGetRow(r, idx) {
  var row = Object.assign({}, r);
  TBL.computedCols.forEach(function(c) {
    if(TBL.customCols[c.name]) row[c.name] = TBL.customCols[c.name][idx];
  });
  return row;
}

/* ── Render table ── */
window.tblRender = function() {
  var cols = tblScalarCols();
  var q = TBL.searchQ.toLowerCase();

  /* Header */
  var thead = document.getElementById('tbl-head');
  thead.innerHTML = '<tr>' +
    '<th style="width:60px;">Statut</th>' +
    cols.map(function(c) {
      var cls = TBL.sortCol===c ? (TBL.sortDir>0?'sort-asc':'sort-desc') : '';
      return '<th class="'+cls+'" onclick="tblSort(this)" data-col="'+c+'" title="'+c+'">'+c+'</th>';
    }).join('') + '</tr>';

  /* Body */
  var tbody = document.getElementById('tbl-body');
  var rows = DATA.map(function(r,i){ return {r:tblGetRow(r,i), i:i}; });

  /* Search filter */
  if(q) {
    rows = rows.filter(function(obj) {
      return cols.some(function(c) {
        var v = obj.r[c];
        return v!=null && String(v).toLowerCase().includes(q);
      });
    });
  }

  /* Sort */
  if(TBL.sortCol) {
    rows.sort(function(a,b) {
      var av=a.r[TBL.sortCol], bv=b.r[TBL.sortCol];
      var an=parseFloat(av), bn=parseFloat(bv);
      if(!isNaN(an)&&!isNaN(bn)) return (an-bn)*TBL.sortDir;
      return String(av||'').localeCompare(String(bv||''))*TBL.sortDir;
    });
  }

  var nExcl = Object.keys(TBL.excluded).length;
  var nVisible = rows.filter(function(obj){return !TBL.excluded[obj.i];}).length;

  tbody.innerHTML = rows.map(function(obj) {
    var r=obj.r, idx=obj.i;
    var excl = TBL.excluded[idx];
    var trCls = excl ? 'tbl-excluded' : '';
    var btn = excl
      ? '<button class="tbl-restore-btn" onclick="tblToggle('+idx+')">↺ Restaurer</button>'
      : '<button class="tbl-excl-btn" onclick="tblToggle('+idx+')">✕ Exclure</button>';
    var cells = cols.map(function(c) {
      var v = r[c];
      var isNum = typeof v==='number' || (!isNaN(parseFloat(v)) && v!=='' && v!=null);
      var isComputed = TBL.customCols[c] !== undefined;
      var disp = v==null ? '—' : (typeof v==='number' ? (Math.abs(v)>999||Math.abs(v)<0.001&&v!==0 ? v.toExponential(2) : v.toFixed(3)) : v);
      var cls = isComputed ? 'tbl-computed' : (isNum?'tbl-num':'');
      return '<td class="'+cls+'" title="'+String(v||'')+'">'+disp+'</td>';
    }).join('');
    return '<tr class="'+trCls+'"><td>'+btn+'</td>'+cells+'</tr>';
  }).join('');

  document.getElementById('tbl-info').textContent = nVisible+' / '+DATA.length+' lignes affichées';
  document.getElementById('tbl-status').textContent = rows.length+' lignes · '+cols.length+' colonnes';
  document.getElementById('tbl-excluded-info').textContent = nExcl > 0 ? nExcl+' ligne'+(nExcl>1?'s':'')+' exclue'+(nExcl>1?'s':'') : '';
};

/* ── Toggle exclude ── */
window.tblToggle = function(idx) {
  if(TBL.excluded[idx]) delete TBL.excluded[idx];
  else TBL.excluded[idx] = true;
  /* Sync DATA_ACTIVE globally */
  syncExcluded();
  tblRender();
};

window.tblRestoreAll = function() {
  TBL.excluded = {};
  syncExcluded();
  tblRender();
};

/* Keep DATA in sync — excluded rows filtered out */
function syncExcluded() {
  /* Replace DATA with filtered version so all builds pick it up */
  DATA = DATA_ORIG.filter(function(_,i){ return !TBL.excluded[i]; });
  DATA_FULL = DATA_FULL_ORIG.filter(function(_,i){ return !TBL.excluded[i]; });
  /* Recompute custom cols on filtered data */
  TBL.computedCols.forEach(function(c){ applyComputedCol(c); });
}

/* ── Sort ── */
window.tblSort = function(el) {
  var col = typeof el === 'string' ? el : el.dataset.col;
  if(TBL.sortCol===col) TBL.sortDir *= -1;
  else { TBL.sortCol=col; TBL.sortDir=1; }
  tblRender();
};

/* ── Search ── */
window.tblFilter = function() {
  TBL.searchQ = document.getElementById('tbl-search').value;
  tblRender();
};

/* ── Add computed column ── */
window.tblAddCol = function() {
  var name = document.getElementById('tbl-newcol-name').value.trim().replace(/\s+/g,'_');
  var expr = document.getElementById('tbl-newcol-expr').value.trim();
  var errEl = document.getElementById('tbl-col-err');
  errEl.textContent = '';

  if(!name) { errEl.textContent = '⚠ Nom requis'; return; }
  if(!expr)  { errEl.textContent = '⚠ Expression requise'; return; }

  /* Available col names for substitution */
  var allCols = SCALAR_NUM.concat(SCALAR_CAT);
  TBL.computedCols.forEach(function(c){ allCols.push(c.name); });

  /* Test on first row */
  try {
    var testRow = tblGetRow(DATA_ORIG[0], 0);
    evalExpr(expr, testRow, allCols);
  } catch(e) {
    errEl.textContent = '⚠ Erreur: '+e.message.slice(0,50);
    return;
  }

  /* Apply to all rows */
  if(TBL.computedCols.findIndex(function(c){return c.name===name;})<0)
    TBL.computedCols.push({name:name, expr:expr});
  else
    TBL.computedCols.find(function(c){return c.name===name;}).expr = expr;

  applyComputedCol({name:name, expr:expr});

  /* Add to SCALAR_NUM if numeric */
  if(SCALAR_NUM.indexOf(name)<0) SCALAR_NUM.push(name);

  document.getElementById('tbl-newcol-name').value = '';
  document.getElementById('tbl-newcol-expr').value = '';
  tblRender();

  /* Refresh selects in graph panels */
  refreshSelects();
};

function applyComputedCol(c) {
  var allCols = SCALAR_NUM.concat(SCALAR_CAT);
  var vals = DATA_ORIG.map(function(r,i) {
    try { return evalExpr(c.expr, tblGetRow(r,i), allCols); }
    catch(e) { return null; }
  });
  TBL.customCols[c.name] = vals;
  /* Inject into DATA and DATA_ORIG */
  DATA_ORIG.forEach(function(r,i){ r[c.name] = vals[i]; });
  DATA.forEach(function(r,i) {
    var origIdx = DATA_ORIG.indexOf(r);
    if(origIdx>=0) r[c.name] = vals[origIdx];
    else r[c.name] = null;
  });
}

function evalExpr(expr, row, cols) {
  /* Replace col names with numeric values, longest first */
  var sortedCols = cols.slice().sort(function(a,b){return b.length-a.length;});
  var jsExpr = expr;
  sortedCols.forEach(function(col) {
    var v = row[col];
    var num = typeof v==='number' ? v : parseFloat(v);
    var replacement = isNaN(num) ? 'null' : String(num);
    /* Simple whole-word replace using split/join to avoid regex escaping issues */
    var parts = jsExpr.split(col);
    /* Only replace occurrences where col is not part of a longer word */
    var result = '';
    for(var pi=0; pi<parts.length; pi++) {
      if(pi>0) {
        var prev = parts[pi-1], next = parts[pi];
        var prevOk = prev==='' || !/[A-Za-z0-9_$]/.test(prev[prev.length-1]);
        var nextOk = next==='' || !/[A-Za-z0-9_$]/.test(next[0]);
        result += (prevOk && nextOk) ? replacement : col;
      }
      result += parts[pi];
    }
    jsExpr = result;
  });
  return (new Function('Math','return ('+jsExpr+')'))(Math);
}

/* ── Export ── */
window.tblExport = function(fmt) {
  var cols = tblScalarCols();
  var rows = DATA.map(function(r,i){ return tblGetRow(r,i); });

  if(fmt==='csv') {
    var lines = [cols.map(function(c){return '"'+c+'"';}).join(',')];
    rows.forEach(function(r) {
      lines.push(cols.map(function(c){
        var v=r[c]; if(v==null) return ''; if(typeof v==='string') return '"'+v.replace(/"/g,'""')+'"'; return v;
      }).join(','));
    });
    var NL = String.fromCharCode(13)+String.fromCharCode(10);
    download('led_data.csv', lines.join(NL), 'text/csv');
  } else {
    download('led_data.json', JSON.stringify(rows, null, 2), 'application/json');
  }
};

function download(name, content, type) {
  var a = document.createElement('a');
  a.href = URL.createObjectURL(new Blob([content], {type:type}));
  a.download = name; a.click();
  setTimeout(function(){URL.revokeObjectURL(a.href);}, 1000);
}

/* ── Refresh selects after new col ── */
function refreshSelects() {
  var SN2 = SCALAR_NUM, SA2 = SN2.concat(SCALAR_CAT);
  [['s-x',SA2],['s-y',SN2],['s-z',SN2,true],['s-c',SA2,true],
   ['f-x',SN2],['f-y',SN2],['f-c',SA2,true]].forEach(function(t) {
    var sel=document.getElementById(t[0]);
    if(!sel) return;
    var cur=sel.value;
    opts(sel, t[1], t[2]);
    if(cur) sel.value=cur;
  });
}

/* Keep originals for restore */
var DATA_ORIG      = DATA.slice();
var DATA_FULL_ORIG = DATA_FULL.slice();

