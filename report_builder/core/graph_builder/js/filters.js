// filters.js

// ─────────────────────────────────────────────────────────────────────────────
//  Filters
// ─────────────────────────────────────────────────────────────────────────────
window.addFilter = function() {
  var id = ++filterId;
  FILTERS.push({id:id, col:SN[0]||SA[0]||'', op:'gt', val:''});
  renderFilters();
};
window.rmFilter = function(id) { FILTERS=FILTERS.filter(function(f){return f.id!==id;}); renderFilters(); };
window.setFcol = function(id,v) { var f=FILTERS.find(function(f){return f.id===id;}); if(f){f.col=v;f.val='';renderFilters();} };
window.setFop  = function(id,v) { var f=FILTERS.find(function(f){return f.id===id;}); if(f) f.op=v; };
window.setFval = function(id,v) { var f=FILTERS.find(function(f){return f.id===id;}); if(f) f.val=v; };

function renderFilters() {
  var cont = document.getElementById('filt-list');
  cont.innerHTML='';
  FILTERS.forEach(function(f) {
    var isNum = SN.indexOf(f.col)>=0;
    var allCols = SA;
    var colOpts = allCols.map(function(c){return '<option value="'+c+'"'+(c===f.col?' selected':'')+'>'+c+'</option>';}).join('');
    var ops = isNum
      ? [['gt','>'],['gte','≥'],['lt','<'],['lte','≤'],['eq','='],['neq','≠']]
      : [['eq','='],['neq','≠'],['contains','⊃']];
    var opOpts = ops.map(function(o){return '<option value="'+o[0]+'"'+(o[0]===f.op?' selected':'')+'>'+o[1]+'</option>';}).join('');
    var row = document.createElement('div');
    row.className='gb-filter-row';
    row.innerHTML=
      '<div class="gb-select-wrap" style="flex:1.3"><select class="gb-select" style="font-size:9px" onchange="setFcol('+f.id+',this.value)">'+colOpts+'</select></div>'+
      '<div class="gb-select-wrap" style="flex:.7"><select class="gb-select" style="font-size:9px" onchange="setFop('+f.id+',this.value)">'+opOpts+'</select></div>'+
      '<input class="gb-input" style="flex:1;height:28px;font-size:10px" placeholder="val" value="'+esc(f.val)+'" oninput="setFval('+f.id+',this.value)">'+
      '<button class="gb-rm-btn" onclick="rmFilter('+f.id+')">×</button>';
    cont.appendChild(row);
  });
  document.getElementById('filt-badge').textContent = FILTERS.length ? '('+FILTERS.length+')' : '';
}

function esc(s){ return String(s).replace(/"/g,'&quot;'); }

function applyFilters(rows) {
  return FILTERS.reduce(function(acc,f) {
    if(!f.col||f.val==='') return acc;
    var num=parseFloat(f.val), isNum=!isNaN(num);
    return acc.filter(function(r) {
      var v=r[f.col]; if(v==null) return false;
      if(isNum) {
        var rv=parseFloat(v);
        return f.op==='gt'?rv>num:f.op==='gte'?rv>=num:f.op==='lt'?rv<num:f.op==='lte'?rv<=num:f.op==='eq'?rv===num:rv!==num;
      }
      var sv=String(v).toLowerCase(),sv2=f.val.toLowerCase();
      return f.op==='eq'?sv===sv2:f.op==='neq'?sv!==sv2:sv.includes(sv2);
    });
  }, rows);
}

