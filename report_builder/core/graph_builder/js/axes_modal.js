// axes_modal.js

//  Axes modal
// ─────────────────────────────────────────────────────────────────────────────
/* openAxesModal devient syncAxesFields — sync les champs depuis le layout Plotly actuel */
window.syncAxesFields = function() {
  var el = document.getElementById('gb-plot');
  if(el && el.layout) {
    var l = el.layout;
    if(l.xaxis) {
      document.getElementById('ax-xtitle').value = (l.xaxis.title&&l.xaxis.title.text)||'';
      document.getElementById('ax-xtype').value  = l.xaxis.type||'auto';
      if(l.xaxis.range) { document.getElementById('ax-xmin').value=l.xaxis.range[0]; document.getElementById('ax-xmax').value=l.xaxis.range[1]; }
    }
    if(l.yaxis) {
      document.getElementById('ax-ytitle').value = (l.yaxis.title&&l.yaxis.title.text)||'';
      document.getElementById('ax-ytype').value  = l.yaxis.type||'auto';
      if(l.yaxis.range) { document.getElementById('ax-ymin').value=l.yaxis.range[0]; document.getElementById('ax-ymax').value=l.yaxis.range[1]; }
    }
    /* Prefill typography from current layout */
    if(l.title&&l.title.font&&l.title.font.size) {
      var fs=l.title.font.size;
      document.getElementById('ax-fs-title').value=fs;
      document.getElementById('ax-fs-title-val').textContent=fs;
    }
    if(l.xaxis&&l.xaxis.title&&l.xaxis.title.font&&l.xaxis.title.font.size) {
      var fs=l.xaxis.title.font.size;
      document.getElementById('ax-fs-axlabel').value=fs;
      document.getElementById('ax-fs-axlabel-val').textContent=fs;
    }
    if(l.xaxis&&l.xaxis.tickfont&&l.xaxis.tickfont.size) {
      var fs=l.xaxis.tickfont.size;
      document.getElementById('ax-fs-tick').value=fs;
      document.getElementById('ax-fs-tick-val').textContent=fs;
    }
    if(l.legend&&l.legend.font&&l.legend.font.size) {
      var fs=l.legend.font.size;
      document.getElementById('ax-fs-legend').value=fs;
      document.getElementById('ax-fs-legend-val').textContent=fs;
    }
    if(l.font&&l.font.family) {
      document.getElementById('ax-font').value=l.font.family;
    }
  }
};

window.closeAxesModal = function() { /* no-op: axes inline dans sidebar */ };

window.resetAxes = function() {
  ['ax-xtitle','ax-xmin','ax-xmax','ax-xdtick','ax-ytitle','ax-ymin','ax-ymax','ax-ydtick'].forEach(function(id){
    document.getElementById(id).value='';
  });
  document.getElementById('ax-xtype').value='auto';
  document.getElementById('ax-ytype').value='auto';
  document.getElementById('ax-grid').classList.add('on');
  document.getElementById('ax-equal').classList.remove('on');
  document.getElementById('ax-plotbg').value='#F8F9FD';
  document.getElementById('ax-paperbg').value='#ffffff';
  /* Reset typography */
  [['ax-fs-title',13],['ax-fs-axlabel',12],['ax-fs-tick',10],['ax-fs-legend',10]].forEach(function(t){
    document.getElementById(t[0]).value = t[1];
    document.getElementById(t[0]+'-val').textContent = t[1];
  });
  document.getElementById('ax-font').value = 'IBM Plex Mono,monospace';
  applyAxes();
};

window.applyAxes = function() {
  var el = document.getElementById('gb-plot');
  if(!el || !el.data) { return; }

  var xmin = document.getElementById('ax-xmin').value;
  var xmax = document.getElementById('ax-xmax').value;
  var ymin = document.getElementById('ax-ymin').value;
  var ymax = document.getElementById('ax-ymax').value;
  var xdtk = document.getElementById('ax-xdtick').value;
  var ydtk = document.getElementById('ax-ydtick').value;
  var grid    = document.getElementById('ax-grid').classList.contains('on');
  var equal   = document.getElementById('ax-equal').classList.contains('on');
  var plotbg  = document.getElementById('ax-plotbg').value;
  var paperbg = document.getElementById('ax-paperbg').value;
  var fsTitle  = parseInt(document.getElementById('ax-fs-title').value)||13;
  var fsAxlabel= parseInt(document.getElementById('ax-fs-axlabel').value)||12;
  var fsTick   = parseInt(document.getElementById('ax-fs-tick').value)||10;
  var fsLegend = parseInt(document.getElementById('ax-fs-legend').value)||10;
  var font     = document.getElementById('ax-font').value||'IBM Plex Mono,monospace';
  var xtitle   = document.getElementById('ax-xtitle').value;
  var ytitle   = document.getElementById('ax-ytitle').value;
  var xType    = document.getElementById('ax-xtype').value;
  var yType    = document.getElementById('ax-ytype').value;

  var upd = {
    'plot_bgcolor':  plotbg,
    'paper_bgcolor': paperbg,
    'font.family':   font,
    'font.size':     fsTick,
    /* Title */
    'title.font.size':   fsTitle,
    'title.font.family': font,
    /* X axis */
    'xaxis.showgrid':  grid,
    'xaxis.zeroline':  grid,
    'xaxis.tickfont.size':   fsTick,
    'xaxis.tickfont.family': font,
    'xaxis.title.font.size':   fsAxlabel,
    'xaxis.title.font.family': font,
    /* Y axis */
    'yaxis.showgrid':  grid,
    'yaxis.zeroline':  grid,
    'yaxis.tickfont.size':   fsTick,
    'yaxis.tickfont.family': font,
    'yaxis.title.font.size':   fsAxlabel,
    'yaxis.title.font.family': font,
    /* Legend */
    'legend.font.size':   fsLegend,
    'legend.font.family': font,
  };

  if(xmin!==''&&xmax!=='') { upd['xaxis.range'] = [parseFloat(xmin),parseFloat(xmax)]; LAYOUT_PREFS['xaxis.range']=[parseFloat(xmin),parseFloat(xmax)]; }
  else { upd['xaxis.autorange'] = true; delete LAYOUT_PREFS['xaxis.range']; }
  if(ymin!==''&&ymax!=='') { upd['yaxis.range'] = [parseFloat(ymin),parseFloat(ymax)]; LAYOUT_PREFS['yaxis.range']=[parseFloat(ymin),parseFloat(ymax)]; }
  else { upd['yaxis.autorange'] = true; delete LAYOUT_PREFS['yaxis.range']; }

  if(xdtk!=='') { upd['xaxis.dtick'] = parseFloat(xdtk); LAYOUT_PREFS['xaxis.dtick']=parseFloat(xdtk); }
  else { delete LAYOUT_PREFS['xaxis.dtick']; }
  if(ydtk!=='') { upd['yaxis.dtick'] = parseFloat(ydtk); LAYOUT_PREFS['yaxis.dtick']=parseFloat(ydtk); }
  else { delete LAYOUT_PREFS['yaxis.dtick']; }

  if(xtitle) { upd['xaxis.title.text'] = xtitle; LAYOUT_PREFS['xaxis.title.text'] = xtitle; }
  else delete LAYOUT_PREFS['xaxis.title.text'];
  if(ytitle) { upd['yaxis.title.text'] = ytitle; LAYOUT_PREFS['yaxis.title.text'] = ytitle; }
  else delete LAYOUT_PREFS['yaxis.title.text'];

  if(xType!=='auto') { upd['xaxis.type'] = xType; LAYOUT_PREFS['xaxis.type'] = xType; }
  else delete LAYOUT_PREFS['xaxis.type'];
  if(yType!=='auto') { upd['yaxis.type'] = yType; LAYOUT_PREFS['yaxis.type'] = yType; }
  else delete LAYOUT_PREFS['yaxis.type'];

  if(equal) { upd['yaxis.scaleanchor']='x'; upd['yaxis.scaleratio']=1; LAYOUT_PREFS['yaxis.scaleanchor']='x'; LAYOUT_PREFS['yaxis.scaleratio']=1; }
  else { upd['yaxis.scaleanchor']=undefined; delete LAYOUT_PREFS['yaxis.scaleanchor']; delete LAYOUT_PREFS['yaxis.scaleratio']; }

  /* ── Save to LAYOUT_PREFS so they persist across rebuilds ── */
  LAYOUT_PREFS['plot_bgcolor']  = plotbg;
  LAYOUT_PREFS['paper_bgcolor'] = paperbg;
  LAYOUT_PREFS['font.family']   = font;
  LAYOUT_PREFS['font.size']     = fsTick;
  LAYOUT_PREFS['title.font.size']   = fsTitle;
  LAYOUT_PREFS['title.font.family'] = font;
  LAYOUT_PREFS['xaxis.showgrid']  = grid;
  LAYOUT_PREFS['xaxis.zeroline']  = grid;
  LAYOUT_PREFS['xaxis.tickfont.size']     = fsTick;
  LAYOUT_PREFS['xaxis.tickfont.family']   = font;
  LAYOUT_PREFS['xaxis.title.font.size']   = fsAxlabel;
  LAYOUT_PREFS['xaxis.title.font.family'] = font;
  LAYOUT_PREFS['yaxis.showgrid']  = grid;
  LAYOUT_PREFS['yaxis.zeroline']  = grid;
  LAYOUT_PREFS['yaxis.tickfont.size']     = fsTick;
  LAYOUT_PREFS['yaxis.tickfont.family']   = font;
  LAYOUT_PREFS['yaxis.title.font.size']   = fsAxlabel;
  LAYOUT_PREFS['yaxis.title.font.family'] = font;
  LAYOUT_PREFS['legend.font.size']   = fsLegend;
  LAYOUT_PREFS['legend.font.family'] = font;

  Plotly.relayout('gb-plot', upd);
};


// Auto-select sensible defaults
if(SN.length>0) document.getElementById('s-x').value = SN[0];
if(SN.length>1) document.getElementById('s-y').value = SN[1];
if(SC.length>0) document.getElementById('s-c').value = SC[0];
if(V.length>0)  document.getElementById('v-x').value = V[0];
if(V.length>1)  document.getElementById('v-y').value = V[1];
if(SC.length>0) document.getElementById('v-grp').value = SC[0];

// Init facet selects
opts(document.getElementById('f-x'),  SN);
opts(document.getElementById('f-y'),  SN, true);
opts(document.getElementById('f-col'), SC, true);
opts(document.getElementById('f-row'), SC, true);
opts(document.getElementById('f-c'),   SC, true);
if(SN.length>0) document.getElementById('f-x').value = SN[0];
if(SN.length>1) document.getElementById('f-y').value = SN[1];
if(SC.length>0) document.getElementById('f-col').value = SC[0];
if(SC.length>1) document.getElementById('f-row').value = SC[1]||'';

// Wafer filter for CIE
var cieWafer = document.getElementById('cie-wafer');
WAFERS.forEach(function(w) { var o=document.createElement('option');o.value=w;o.textContent=w;cieWafer.appendChild(o); });


window.openAxesModal = window.syncAxesFields;

// Debounce pour appliquer les axes inline (sans rebuild complet)
var _applyAxesTimer = null;
window.scheduleApplyAxes = function() {
  clearTimeout(_applyAxesTimer);
  _applyAxesTimer = setTimeout(function() { applyAxes(); }, 300);
};
