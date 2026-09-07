// scalar.js

// ── AUTO-REBUILD ──────────────────────────────────────────────────────────────
var _autoRebuildTimer = null;
function scheduleRebuild() {
  if (!document.getElementById('tog-auto').classList.contains('on')) return;
  clearTimeout(_autoRebuildTimer);
  _autoRebuildTimer = setTimeout(function() { build(); }, 220);
}

// ── HUE HELPERS ───────────────────────────────────────────────────────────────
function _isNumCol(col) {
  return col && (typeof SCALAR_NUM !== 'undefined') && SCALAR_NUM.indexOf(col) !== -1;
}

function _currentCS() {
  var el = document.getElementById('s-cs');
  return el ? el.value : 'Viridis';
}


// ── CONTEXT OPTIONS VISIBILITY ───────────────────────────────────────────────
function _updateContextOpts() {
  var t = chartType;
  var show = function(id, v) { var el = document.getElementById(id); if (el) el.style.display = v ? '' : 'none'; };
  // nbins: histogram only
  show('row-nbins',  t === 'histogram');
  // boxpoints: box + violin
  show('row-boxpts', t === 'box' || t === 'violin');
  // barmode: bar only
  show('row-barmode', t === 'bar');
  // trendline: scatter/line/bubble only
  show('row-trendline', t === 'scatter' || t === 'line' || t === 'bubble');
  // Y col: hidden for histogram
  show('row-sy', t !== 'histogram');
  // size: hidden for box/violin/histogram
  show('row-sz', t !== 'box' && t !== 'violin' && t !== 'histogram');
  // symbol: hidden for bar/histogram
  show('row-sym', t !== 'bar' && t !== 'histogram');
  // colorscale selector: shown only when cCol is numeric
  var cCol = document.getElementById('s-c').value;
  show('row-cs', _isNumCol(cCol));
}

// Expose so setChartType can call it
window._updateContextOpts = _updateContextOpts;

// ── HUE COL CHANGE — show/hide colorscale row ────────────────────────────────
window.onCColChange = function() {
  _updateContextOpts();
  scheduleRebuild();
};

// ── MAIN BUILD ────────────────────────────────────────────────────────────────
function buildScalar() {
  var xCol  = document.getElementById('s-x').value;
  var yCol  = document.getElementById('s-y').value;
  var cCol  = document.getElementById('s-c').value;
  var zCol  = document.getElementById('s-z').value;
  var szFix = parseInt(document.getElementById('s-szfix').value) || 8;
  var bdrW  = parseFloat(document.getElementById('s-border').value) || 0.5;
  var pal   = PALETTES[document.getElementById('s-pal').value] || PALETTES.aledia;
  var op    = parseFloat(document.getElementById('s-op').value);
  var logX  = document.getElementById('tog-lx').classList.contains('on');
  var logY  = document.getElementById('tog-ly').classList.contains('on');
  var tl    = document.getElementById('tog-tl').classList.contains('on');
  var ch    = document.getElementById('tog-ch').classList.contains('on');
  var titl  = document.getElementById('s-title').value;
  var sym   = activeSymbol || 'circle';
  var symCol = document.getElementById('s-sym-col').value;
  var useSymVar = symCol && Object.keys(symByGroup).length > 0;

  if (!xCol) { setStatus(false, '⚠ Sélectionner X'); return; }

  // Box/Violin with categorical X: Y required (numeric value to distribute)
  var _chartIsBoxViolin = (chartType === 'box' || chartType === 'violin');
  if (_chartIsBoxViolin && !_isNumCol(xCol) && !yCol) {
    setStatus(false, '⚠ Box/Violin : sélectionner Y (valeur numérique à distribuer)');
    return;
  }

  var FDATA = applyFilters(DATA);
  var nFilt = DATA.length - FDATA.length;
  var cIsNum = cCol && _isNumCol(cCol);

  // ── CONTINUOUS HUE ────────────────────────────────────────────────────────
  if (cIsNum && (chartType === 'scatter' || chartType === 'bubble' || chartType === 'line')) {
    var cVals = FDATA.map(function(r) { return r[cCol] != null ? r[cCol] : null; });
    var fin   = cVals.filter(function(v) { return v != null; });
    var cmin  = fin.length ? Math.min.apply(null, fin) : 0;
    var cmax  = fin.length ? Math.max.apply(null, fin) : 1;
    var cs    = _currentCS();

    var xs = FDATA.map(function(r) { return r[xCol]; });
    var ys = yCol ? FDATA.map(function(r) { return r[yCol]; }) : null;
    var sz = zCol ? normSize(FDATA.map(function(r) { return r[zCol] || 0; }), 4, 28) : szFix;
    var syms = useSymVar
      ? FDATA.map(function(r) { return symByGroup[String(r[symCol])] || 'circle'; })
      : sym;

    var htexts = FDATA.map(function(r) {
      var t = '<b>' + (r['Led_Name'] || '') + '</b>';
      t += '<br>' + xCol + ': ' + (r[xCol] != null ? r[xCol] : '—');
      if (yCol) t += '<br>' + yCol + ': ' + (r[yCol] != null ? r[yCol] : '—');
      t += '<br><i>' + cCol + ': ' + (r[cCol] != null ? r[cCol] : '—') + '</i>';
      hoverCols.forEach(function(h) { if (h.col && r[h.col] != null) t += '<br>' + h.col + ': ' + r[h.col]; });
      return t;
    });

    var mode = chartType === 'line' ? 'lines+markers' : 'markers';
    var traces = [{
      type: 'scatter', mode: mode, name: cCol,
      x: xs, y: ys,
      text: htexts, hovertemplate: '%{text}<extra></extra>',
      opacity: op,
      marker: {
        color: cVals, colorscale: cs, cmin: cmin, cmax: cmax,
        showscale: true,
        colorbar: {
          title: { text: cCol, font: { family: 'IBM Plex Mono', size: 9 }, side: 'right' },
          thickness: 10, len: 0.7,
          tickfont: { family: 'IBM Plex Mono', size: 9 },
          outlinewidth: 0, borderwidth: 0,
        },
        size: sz, symbol: syms,
        line: { width: bdrW, color: 'rgba(0,0,0,' + (bdrW > 0 ? 0.2 : 0) + ')' },
      },
    }];

    if (tl && ys && xs.length > 1) {
      var reg = linReg(xs.map(Number), ys.map(Number));
      var xs2 = xs.map(Number).slice().sort(function(a, b) { return a - b; });
      traces.push({
        type: 'scatter', mode: 'lines', name: '↗ OLS', showlegend: false,
        x: [xs2[0], xs2[xs2.length-1]],
        y: [reg.slope*xs2[0]+reg.intercept, reg.slope*xs2[xs2.length-1]+reg.intercept],
        line: { color: '#999', width: 1.5, dash: 'dash' }, hoverinfo: 'skip',
      });
    }
    _renderLayout(traces, xCol, yCol, titl, logX, logY, ch, FDATA.length, nFilt, 1);
    return;
  }

  // ── DISCRETE HUE (groupBy) ────────────────────────────────────────────────
  /* Pour box/violin: si xCol est catégoriel et cCol vide → grouper par xCol (chaque valeur = 1 box)
     Sinon: comportement standard (cCol pour couleur/groupe) */
  var _xIsStr = !_isNumCol(xCol);
  var _isBoxViolin = (chartType === 'box' || chartType === 'violin');
  var _boxGroupCol = (_isBoxViolin && _xIsStr && !cCol) ? xCol : cCol;
  var groups = _boxGroupCol ? groupBy(FDATA, _boxGroupCol) : { '': FDATA };
  /* Pour box/violin groupé par xCol: yCol est la valeur distribuée, pas xs */
  var _boxGroupedByX = (_isBoxViolin && _xIsStr && !cCol);
  var traces = [];

  Object.keys(groups).sort().forEach(function(gk, gi) {
    var gdata = groups[gk];
    var color = pal[gi % pal.length];
    var xs = gdata.map(function(r) { return r[xCol]; });
    var ys = yCol ? gdata.map(function(r) { return r[yCol]; }) : null;
    var sz = zCol ? normSize(gdata.map(function(r) { return r[zCol] || 0; }), 4, 28) : szFix;
    var base = { name: gk || 'Série', opacity: op };

    var syms = useSymVar
      ? gdata.map(function(r) { return symByGroup[String(r[symCol])] || 'circle'; })
      : sym;

    var htexts = gdata.map(function(r) {
      var t = '<b>' + (r['Led_Name'] || gk) + '</b>';
      t += '<br>' + xCol + ': ' + (r[xCol] != null ? r[xCol] : '—');
      if (yCol) t += '<br>' + yCol + ': ' + (r[yCol] != null ? r[yCol] : '—');
      if (symCol && r[symCol] != null) t += '<br>' + symCol + ': ' + r[symCol];
      hoverCols.forEach(function(h) { if (h.col && r[h.col] != null) t += '<br>' + h.col + ': ' + r[h.col]; });
      return t;
    });

    var mk = {
      color: color, size: sz, opacity: op, symbol: syms,
      line: { width: bdrW, color: 'rgba(0,0,0,' + (bdrW > 0 ? 0.25 : 0) + ')' },
    };

    if (chartType === 'scatter' || chartType === 'bubble') {
      traces.push(Object.assign({}, base, {
        type: 'scatter', mode: 'markers', x: xs, y: ys,
        marker: mk, text: htexts, hovertemplate: '%{text}<extra></extra>',
      }));
    } else if (chartType === 'line') {
      traces.push(Object.assign({}, base, {
        type: 'scatter', mode: 'lines+markers', x: xs, y: ys,
        line: { color: color, width: 2 },
        marker: Object.assign({}, mk, { size: typeof sz === 'number' ? sz : 6 }),
        text: htexts, hovertemplate: '%{text}<extra></extra>',
      }));
    } else if (chartType === 'bar') {
      var barmode = document.getElementById('s-barmode') ? document.getElementById('s-barmode').value : 'group';
      traces.push(Object.assign({}, base, {
        type: 'bar', x: xs, y: ys || xs.map(function() { return 1; }),
        marker: { color: color, opacity: op },
        text: htexts, hovertemplate: '%{text}<extra></extra>',
      }));
    } else if (chartType === 'histogram') {
      var nbins = parseInt((document.getElementById('s-nbins') || {}).value) || 0;
      traces.push(Object.assign({}, base, {
        type: 'histogram', x: xs,
        marker: { color: color }, opacity: op,
        nbinsx: nbins || undefined,
      }));
    } else if (chartType === 'box') {
      var bxpts = (document.getElementById('s-boxpts') || {}).value || 'suspectedoutliers';
      /* y = numeric values; name = group label (from cCol groupBy or xCol if cat) */
      var boxY = ys || xs;
      traces.push(Object.assign({}, base, {
        type: 'box', y: boxY, name: gk || xCol,
        marker: { color: color, size: 4, symbol: sym },
        boxpoints: bxpts,
        hovertemplate: '<b>' + (gk || xCol) + '</b><br>%{y}<extra></extra>',
      }));
    } else if (chartType === 'violin') {
      var vioPts = (document.getElementById('s-boxpts') || {}).value || 'outliers';
      var violinY = ys || xs;
      traces.push(Object.assign({}, base, {
        type: 'violin', y: violinY, name: gk || xCol,
        line: { color: color }, fillcolor: color, opacity: 0.6,
        points: vioPts, box: { visible: true },
        hovertemplate: '<b>' + (gk || xCol) + '</b><br>%{y}<extra></extra>',
      }));
    } else if (chartType === 'kde2d') {
      /* handled separately */
    }

    if (tl && ys && xs.length > 1 && chartType !== 'histogram' && chartType !== 'box' && chartType !== 'violin') {
      var xn = xs.map(Number), yn = ys.map(Number);
      var reg = linReg(xn, yn);
      var xs2 = xn.slice().sort(function(a, b) { return a - b; });
      traces.push({
        type: 'scatter', mode: 'lines', name: '↗ ' + gk, showlegend: false,
        x: [xs2[0], xs2[xs2.length-1]],
        y: [reg.slope*xs2[0]+reg.intercept, reg.slope*xs2[xs2.length-1]+reg.intercept],
        line: { color: color, width: 1.5, dash: 'dash' }, hoverinfo: 'skip',
      });
    }
  });

  if (chartType === 'kde2d') {
    buildKDE2D(xCol, yCol, FDATA, cCol, titl, logX, logY);
    return;
  }

  if (chartType === 'box' || chartType === 'violin') {
  } else {
  }

  // barmode for bar chart
  var extraLayout = {};
  if (chartType === 'bar') {
    var bm = (document.getElementById('s-barmode') || {}).value || 'group';
    extraLayout.barmode = bm;
  }

  _renderLayout(traces, xCol, yCol, titl, logX, logY, ch, FDATA.length, nFilt, Object.keys(groups).length, extraLayout);
}

// ── LAYOUT RENDERER ──────────────────────────────────────────────────────────
function _renderLayout(traces, xCol, yCol, titl, logX, logY, ch, nData, nFilt, nGroups, extraLayout) {
  var area = document.getElementById('plot-area');

  var layout = Object.assign({
    autosize: true,
    title: { text: titl, font: { family: 'Syne,sans-serif', size: 13, color: '#0A2463' }, x: 0.05 },
    paper_bgcolor: '#fff', plot_bgcolor: '#F8F9FD',
    font: { family: 'IBM Plex Mono,monospace', size: 11, color: '#4A5580' },
    xaxis: Object.assign({}, GSTYLE, {
      title: { text: xCol, font: { size: 12, color: '#0A2463' }, standoff: 8 },
      type: logX ? 'log' : 'linear', tickfont: { size: 10 },
      showspikes: ch, spikecolor: 'rgba(10,36,99,.3)', spikemode: 'across', spikethickness: 1, spikedash: 'dot',
    }),
    yaxis: Object.assign({}, GSTYLE, {
      title: { text: yCol, font: { size: 12, color: '#0A2463' }, standoff: 8 },
      type: logY ? 'log' : 'linear', tickfont: { size: 10 },
      showspikes: ch, spikecolor: 'rgba(10,36,99,.3)', spikemode: 'across', spikethickness: 1, spikedash: 'dot',
    }),
    legend: { bgcolor: 'rgba(0,0,0,0)', font: { size: 10 } },
    hovermode: 'closest',
    margin: { l: 64, r: 20, t: titl ? 44 : 28, b: 56 },
    hoverlabel: { bgcolor: '#0A2463', bordercolor: '#D4AF37', font: { family: 'IBM Plex Mono', size: 10, color: 'white' } },
  }, extraLayout || {});

  // ── Apply persisted LAYOUT_PREFS (from axes modal) — survives rebuild ──────
  if (typeof LAYOUT_PREFS !== 'undefined') {
    Object.keys(LAYOUT_PREFS).forEach(function(k) {
      var v = LAYOUT_PREFS[k];
      if (v === undefined) return;
      var parts = k.split('.');
      var obj = layout;
      for (var i = 0; i < parts.length - 1; i++) {
        if (obj[parts[i]] == null || typeof obj[parts[i]] !== 'object') obj[parts[i]] = {};
        obj = obj[parts[i]];
      }
      obj[parts[parts.length - 1]] = v;
    });
  }

  gbReact(traces, layout);

  setStatus(
    true,
    '✓ ' + nData + ' LEDs · ' + nGroups + ' groupe' + (nGroups > 1 ? 's' : '') + (nFilt ? ' · ' + nFilt + ' filtrés' : ''),
    xCol + (yCol ? ' × ' + yCol : '')
  );
}

// ── HUE BADGE UPDATE ─────────────────────────────────────────────────────────
// Surcharge onCColChange définie dans scalar_panel.html
// (si init.js définit déjà onCColChange, on le wrape)
window.onCColChange = function() {
  var cCol = document.getElementById('s-c').value;
  var isNum = _isNumCol(cCol);
  var badgeNum = document.getElementById('hue-badge');
  var badgeCat = document.getElementById('hue-badge-cat');
  var rowCs    = document.getElementById('row-cs');
  if (badgeNum) badgeNum.style.display = (cCol && isNum) ? '' : 'none';
  if (badgeCat) badgeCat.style.display = (cCol && !isNum) ? '' : 'none';
  if (rowCs)    rowCs.style.display    = (cCol && isNum) ? '' : 'none';
  scheduleRebuild();
};
