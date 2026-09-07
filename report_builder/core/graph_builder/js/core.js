// core.js — globals, palettes, helpers, gbReact

// ── State globals ─────────────────────────────────────────────────────────────
var mode      = 'scalar';   // current mode: scalar | vector | cie | facet | table
var chartType = 'scatter';  // current chart type within scalar mode

var FILTERS   = [];
var filterId  = 0;

var LAYOUT_PREFS = {};      // persisted across rebuilds via axes modal

// ── Grid style (shared by all chart builders) ─────────────────────────────────
var GSTYLE = {
  gridcolor:     '#E4E8F4',
  linecolor:     '#E4E8F4',
  zerolinecolor: '#E4E8F4',
  tickfont:      { size: 10, family: 'IBM Plex Mono', color: '#4A5580' },
  showgrid:      true,
  zeroline:      true,
};

// ── Colour palettes ───────────────────────────────────────────────────────────
var PALETTES = {
  aledia: ['#0A2463','#D4AF37','#1a6b8a','#E5826B','#5B8DB8','#C45BAA','#3CB371','#E07B39'],
  D3:     ['#1f77b4','#ff7f0e','#2ca02c','#d62728','#9467bd','#8c564b','#e377c2','#7f7f7f','#bcbd22','#17becf'],
  G10:    ['#3366cc','#dc3912','#ff9900','#109618','#990099','#0099c6','#dd4477','#66aa00','#b82e2e','#316395'],
  T10:    ['#4e79a7','#f28e2c','#e15759','#76b7b2','#59a14f','#edc949','#af7aa1','#ff9da7','#9c755f','#bab0ab'],
};

// ── Helpers ───────────────────────────────────────────────────────────────────

function groupBy(data, col) {
  var out = {};
  data.forEach(function(r) {
    var k = r[col] != null ? String(r[col]) : '(vide)';
    if (!out[k]) out[k] = [];
    out[k].push(r);
  });
  return out;
}

function normSize(vals, minPx, maxPx) {
  var fin = vals.filter(function(v) { return v != null && isFinite(v); });
  if (!fin.length) return minPx;
  var lo = Math.min.apply(null, fin);
  var hi = Math.max.apply(null, fin);
  var rng = hi - lo;
  return rng === 0
    ? vals.map(function() { return (minPx + maxPx) / 2; })
    : vals.map(function(v) {
        return v == null ? minPx : minPx + ((v - lo) / rng) * (maxPx - minPx);
      });
}

function linReg(xs, ys) {
  var n = xs.length;
  if (n < 2) return { slope: 0, intercept: ys[0] || 0 };
  var sumX = 0, sumY = 0, sumXY = 0, sumX2 = 0;
  for (var i = 0; i < n; i++) {
    sumX  += xs[i]; sumY  += ys[i];
    sumXY += xs[i] * ys[i]; sumX2 += xs[i] * xs[i];
  }
  var denom = n * sumX2 - sumX * sumX;
  if (denom === 0) return { slope: 0, intercept: sumY / n };
  var slope = (n * sumXY - sumX * sumY) / denom;
  return { slope: slope, intercept: (sumY - slope * sumX) / n };
}

// ── Status bar ────────────────────────────────────────────────────────────────
function setStatus(ok, txt, detail) {
  var dot = document.getElementById('status-dot');
  var span = document.getElementById('status-txt');
  var nspan = document.getElementById('status-n');
  if (dot)   { dot.className = 'gb-status-dot ' + (ok ? 'ok' : 'err'); }
  if (span)  { span.textContent = txt || ''; }
  if (nspan) { nspan.textContent = detail || ''; }
}



// ── App viewport / Plot resize ──────────────────────────────────────────────
function fitGraphBuilderToViewport() {
  var app = document.querySelector('.gb-app');
  if (!app) return;
  var top = Math.max(0, app.getBoundingClientRect().top);
  document.documentElement.style.setProperty('--gb-top-offset', top + 'px');
}

function resizePlot() {
  fitGraphBuilderToViewport();
  var el = document.getElementById('gb-plot');
  if (!el || !el._plotlyData || typeof Plotly === 'undefined') return;
  var area = document.getElementById('plot-area');
  if (!area) return;
  var r = area.getBoundingClientRect();
  if (r.width < 20 || r.height < 20) return;
  Plotly.relayout(el, { width: r.width, height: r.height });
}

window.addEventListener('resize', function(){
  fitGraphBuilderToViewport();
  requestAnimationFrame(resizePlot);
});
window.addEventListener('load', function(){
  fitGraphBuilderToViewport();
  requestAnimationFrame(resizePlot);
});
fitGraphBuilderToViewport();

// ── Plot renderer — gbReact ───────────────────────────────────────────────────
// Uses Plotly.react for efficient updates (no full redraw)
function gbReact(traces, layout) {
  var el = document.getElementById('gb-plot');
  var empty = document.getElementById('plot-empty');
  if (empty) empty.style.display = 'none';

  var config = {
    responsive:   true,
    displayModeBar: true,
    modeBarButtonsToRemove: ['sendDataToCloud', 'lasso2d'],
    displaylogo: false,
    toImageButtonOptions: { format: 'svg', filename: 'graph_builder' },
  };

  if (el._plotlyData) {
    Plotly.react('gb-plot', traces, layout, config);
  } else {
    Plotly.newPlot('gb-plot', traces, layout, config);
    el._plotlyData = true;
  }
  requestAnimationFrame(resizePlot);
}

// Resize observer — keeps plot filling the container on sidebar drag
(function() {
  var area = document.getElementById('plot-area');
  if (!area || typeof ResizeObserver === 'undefined') return;
  new ResizeObserver(function() {
    var el = document.getElementById('gb-plot');
    if (el && el._plotlyData) {
      Plotly.Plots.resize('gb-plot');
    }
  }).observe(area);
})();

// ── Sidebar resize handle ─────────────────────────────────────────────────────
(function() {
  var resizer  = document.getElementById('resizer');
  var sidebar  = document.getElementById('sidebar');
  if (!resizer || !sidebar) return;
  var dragging = false;
  var startX, startW;
  resizer.addEventListener('mousedown', function(e) {
    dragging = true; startX = e.clientX; startW = sidebar.offsetWidth;
    resizer.classList.add('drag');
    document.body.style.cursor = 'col-resize';
    document.body.style.userSelect = 'none';
  });
  document.addEventListener('mousemove', function(e) {
    if (!dragging) return;
    var w = Math.max(220, Math.min(480, startW + e.clientX - startX));
    sidebar.style.width = w + 'px';
  });
  document.addEventListener('mouseup', function() {
    if (!dragging) return;
    dragging = false;
    resizer.classList.remove('drag');
    document.body.style.cursor = '';
    document.body.style.userSelect = '';
    var el = document.getElementById('gb-plot');
    if (el && el._plotlyData) { Plotly.Plots.resize('gb-plot'); }
  });
})();
