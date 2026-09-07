// init.js

// ─────────────────────────────────────────────────────────────────────────────
//  Init selects
// ─────────────────────────────────────────────────────────────────────────────
function opts(sel, cols, withEmpty) {
  sel.innerHTML = withEmpty ? '<option value="">— aucune —</option>' : '';
  cols.forEach(function(c) {
    var o = document.createElement('option'); o.value = c; o.textContent = c; sel.appendChild(o);
  });
}

var SN = SCALAR_NUM, SC = SCALAR_CAT, SA = SN.concat(SC), V = VECTORS;

opts(document.getElementById('s-x'),  SA);
opts(document.getElementById('s-y'),  SN, false);
opts(document.getElementById('s-z'),  SN, true);
opts(document.getElementById('s-c'),  SA, true);
opts(document.getElementById('s-sym-col'), SC, true);  // categorical only for symbol
opts(document.getElementById('v-x'),  V);
opts(document.getElementById('v-y'),  V, true);
opts(document.getElementById('v-grp'),SA, true);
opts(document.getElementById('v-col'),SA, true);

// ─────────────────────────────────────────────────────────────────────────────
//  Symbol system
// ─────────────────────────────────────────────────────────────────────────────
var SYMBOLS = [
  {n:'circle',      g:'●'}, {n:'square',     g:'■'}, {n:'diamond',    g:'◆'},
  {n:'triangle-up', g:'▲'}, {n:'triangle-down',g:'▼'},{n:'cross',     g:'✕'},
  {n:'x',           g:'×'}, {n:'star',       g:'★'}, {n:'pentagon',   g:'⬠'},
  {n:'hexagon',     g:'⬡'},
];
var activeSymbol = 'circle';
var symByGroup = {};  // col value → symbol

// Fixed symbol picker dropdown
var dropdown = document.getElementById('sym-picker-dropdown');
dropdown.style.display = 'none';
dropdown.style.cssText += ';display:none!important';
var dropdownVisible = false;

SYMBOLS.forEach(function(s) {
  var btn = document.createElement('button');
  btn.title = s.n; btn.textContent = s.g;
  btn.style.cssText = 'padding:6px;border:1px solid var(--border);background:var(--slate-50);border-radius:4px;cursor:pointer;font-size:15px;transition:all .12s;';
  btn.onclick = function(e) {
    e.stopPropagation();
    activeSymbol = s.n;
    document.getElementById('sym-picker-btn').textContent = s.g;
    dropdown.style.display = 'none'; dropdownVisible = false;
    dropdown.style.cssText = dropdown.style.cssText.replace('grid','none');
  };
  dropdown.appendChild(btn);
});

window.toggleSymPicker = function() {
  dropdownVisible = !dropdownVisible;
  dropdown.style.display = dropdownVisible ? 'grid' : 'none';
};
document.addEventListener('click', function() {
  if(dropdownVisible) { dropdown.style.display='none'; dropdownVisible=false; }
});

// Variable symbol: col selection
window.onSymColChange = function() {
  var col = document.getElementById('s-sym-col').value;
  var pickerWrap = document.getElementById('sym-picker-wrap');
  var legend = document.getElementById('sym-var-legend');
  if(!col) {
    pickerWrap.style.display = '';
    legend.style.display = 'none';
    symByGroup = {};
    return;
  }
  pickerWrap.style.display = 'none';
  // Assign symbols to each unique value
  var vals = [];
  DATA.forEach(function(r) { if(r[col]!=null && vals.indexOf(String(r[col]))<0) vals.push(String(r[col])); });
  vals.sort();
  symByGroup = {};
  vals.forEach(function(v,i) { symByGroup[v] = SYMBOLS[i % SYMBOLS.length].n; });
  // Show legend
  legend.style.display = 'block';
  legend.innerHTML = vals.map(function(v) {
    var sym = symByGroup[v];
    var glyph = (SYMBOLS.find(function(s){return s.n===sym;})||SYMBOLS[0]).g;
    return '<span style="margin-right:8px;">'+glyph+' '+v+'</span>';
  }).join('');
};


// ─────────────────────────────────────────────────────────────────────────────
//  Size col change
// ─────────────────────────────────────────────────────────────────────────────
window.onSizeColChange = function() {
  var v = document.getElementById('s-z').value;
  var slider = document.getElementById('s-szfix');
  slider.style.display = v ? 'none' : '';
  document.getElementById('sz-val').textContent = v ? '∝ '+v : slider.value+'px fixe';
};

// ─────────────────────────────────────────────────────────────────────────────
//  Hover cols
// ─────────────────────────────────────────────────────────────────────────────
var hoverCols = [];
var hoverColId = 0;
window.addHoverCol = function() {
  var id = ++hoverColId;
  hoverCols.push({id:id, col:SA[0]||''});
  renderHoverCols();
};
window.rmHoverCol = function(id) { hoverCols=hoverCols.filter(function(h){return h.id!==id;}); renderHoverCols(); };
window.setHoverCol = function(id,v) { var h=hoverCols.find(function(h){return h.id===id;}); if(h) h.col=v; };
function renderHoverCols() {
  var cont = document.getElementById('hover-cols-list');
  cont.innerHTML='';
  hoverCols.forEach(function(h) {
    var colOpts = SA.map(function(c){return '<option value="'+c+'"'+(c===h.col?' selected':'')+'>'+c+'</option>';}).join('');
    var row = document.createElement('div');
    row.style.cssText='display:flex;gap:4px;align-items:center;';
    row.innerHTML=
      '<div class="gb-select-wrap" style="flex:1"><select class="gb-select" style="font-size:9px" onchange="setHoverCol('+h.id+',this.value)">'+colOpts+'</select></div>'+
      '<button class="gb-rm-btn" onclick="rmHoverCol('+h.id+')">×</button>';
    cont.appendChild(row);
  });
}

// ─────────────────────────────────────────────────────────────────────────────

// ─────────────────────────────────────────────────────────────────────────────
//  Mode switch
// ─────────────────────────────────────────────────────────────────────────────
window.switchMode = function(m) {
  mode = m;
  var isTable = m === 'table';

  /* Cacher gb-main entier OU table-view */
  var mainEl = document.getElementById('canvas');
  if(mainEl) {
    var gbMain = mainEl.closest('.gb-main');
    if(gbMain) gbMain.style.display = isTable ? 'none' : '';
  }
  /* Fallback individuel si pas de .gb-main wrapper */
  ['sidebar','resizer','canvas'].forEach(function(id) {
    var el = document.getElementById(id);
    if(el && !el.closest('.gb-main')) el.style.display = isTable ? 'none' : '';
  });
  document.getElementById('table-view').style.display = isTable ? 'flex' : 'none';

  /* Highlight tab actif dans la barre de modes */
  ['scalar','vector','cie','facet','table'].forEach(function(x) {
    var btn = document.getElementById('tab-'+x);
    if(btn) btn.classList.toggle('active', x===m);
    var p = document.getElementById('panel-'+x);
    if(p) p.style.display = (x===m) ? '' : 'none';
  });

  if(isTable) tblRender();
};

// ─────────────────────────────────────────────────────────────────────────────
//  TABLE ENGINE
// ─────────────────────────────────────────────────────────────────────────────

// ─────────────────────────────────────────────────────────────────────────────
//  Chart types
// ─────────────────────────────────────────────────────────────────────────────
window.setChartType = function(btn) {
  document.querySelectorAll('#panel-scalar .gb-ctype').forEach(function(b){b.classList.remove('active');});
  btn.classList.add('active');
  chartType = btn.dataset.type;
  /* Show KDE options only for kde2d */
  document.getElementById('sec-kde').style.display = chartType==='kde2d' ? '' : 'none';
  /* Delegate contextual row visibility to scalar.js */
  if (typeof _updateContextOpts === 'function') _updateContextOpts();
};

var facetType = 'scatter';
window.setFacetType = function(btn) {
  document.querySelectorAll('#panel-facet .gb-ctype').forEach(function(b){b.classList.remove('active');});
  btn.classList.add('active');
  facetType = btn.dataset.ftype;
};

// ─────────────────────────────────────────────────────────────────────────────
//  Section toggle
// ─────────────────────────────────────────────────────────────────────────────
window.toggleSection = function(id) {
  document.getElementById(id).classList.toggle('open');
};

// ─────────────────────────────────────────────────────────────────────────────
//  Build dispatcher
// ─────────────────────────────────────────────────────────────────────────────
window.build = function() {
  if(mode==='scalar') buildScalar();
  else if(mode==='vector') buildVector();
  else if(mode==='cie') buildCIE();
  else if(mode==='facet') buildFacet();
};