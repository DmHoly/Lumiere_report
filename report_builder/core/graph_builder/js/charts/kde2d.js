// kde2d.js

// ── KDE 2D + marginal histograms ─────────────────────────────────────────────
function buildKDE2D(xCol, yCol, FDATA, cCol, titl, logX, logY) {
  if(!yCol) { setStatus(false,'⚠ KDE 2D nécessite X et Y'); return; }

  var cs      = document.getElementById('kde-cs').value||'Hot';
  var bins    = parseInt(document.getElementById('kde-bins').value)||40;
  var margins = document.getElementById('tog-kde-marg').classList.contains('on');
  var conts   = document.getElementById('tog-kde-cont').classList.contains('on');
  var pts     = document.getElementById('tog-kde-pts').classList.contains('on');
  var dark    = document.getElementById('tog-kde-dark').classList.contains('on');

  var bg      = dark ? '#0a0a0a' : '#fff';
  var plotbg  = dark ? '#0a0a0a' : '#f8f9fd';
  var axcol   = dark ? 'rgba(255,255,255,.5)' : '#4A5580';
  var gridcol = dark ? 'rgba(255,255,255,.07)' : '#E4E8F4';

  /* Color groups */
  var pal = PALETTES.aledia;
  var groups = cCol ? groupBy(FDATA, cCol) : {'': FDATA};
  var groupKeys = Object.keys(groups).sort();

  var allXs = FDATA.map(function(r){return r[xCol];}).filter(function(v){return v!=null&&!isNaN(v);});
  var allYs = FDATA.map(function(r){return r[yCol];}).filter(function(v){return v!=null&&!isNaN(v);});

  var area = document.getElementById('plot-area');
  var W = area.clientWidth, H = area.clientHeight;
  /* Subplot proportions: margins take 20% each */
  var marg = margins ? 0.22 : 0;

  var traces = [];

  /* ── Main KDE/density traces ── */
  groupKeys.forEach(function(gk, gi) {
    var gdata = groups[gk];
    var xs = gdata.map(function(r){return r[xCol];});
    var ys = gdata.map(function(r){return r[yCol];});
    var color = pal[gi % pal.length];

    /* 2D density heatmap */
    traces.push({
      type:'histogram2d',
      x:xs, y:ys,
      colorscale: groupKeys.length>1 ? [[0,'rgba(0,0,0,0)'],[1,color]] : cs,
      showscale: gi===0,
      nbinsx: bins, nbinsy: bins,
      opacity: groupKeys.length>1 ? 0.7 : 1,
      xaxis: margins?"x2":"x",
      yaxis: margins?"y2":"y",
      name: gk||'density',
      hovertemplate:'x: %{x}<br>y: %{y}<br>count: %{z}<extra></extra>',
    });

    /* Contour lines */
    if(conts) {
      traces.push({
        type:'histogram2dcontour',
        x:xs, y:ys,
        colorscale: groupKeys.length>1 ? [[0,color],[1,color]] : cs,
        showscale:false,
        reversescale: false,
        nbinsx:bins, nbinsy:bins,
        contours:{showlabels:false, coloring:'none'},
        line:{color: groupKeys.length>1?color:'rgba(255,255,255,.4)', width:1},
        opacity:0.8,
        xaxis: margins?"x2":"x",
        yaxis: margins?"y2":"y",
        hoverinfo:'skip', showlegend:false,
      });
    }

    /* Scatter points */
    if(pts) {
      traces.push({
        type:'scatter', mode:'markers',
        x:xs, y:ys,
        marker:{color:color, size:3, opacity:0.4, line:{width:0}},
        xaxis: margins?"x2":"x",
        yaxis: margins?"y2":"y",
        name:gk||'points',
        hovertemplate:'<b>'+(gdata[0]&&gdata[0]['Led_Name']||gk)+'</b><br>'+xCol+': %{x}<br>'+yCol+': %{y}<extra></extra>',
        showlegend:false,
      });
    }

    /* ── Marginal histograms ── */
    if(margins) {
      /* Top: X marginal */
      traces.push({
        type:'histogram', x:xs,
        marker:{color: groupKeys.length>1?color:(dark?'rgba(255,255,255,.7)':'#0A2463')},
        nbinsx:bins, opacity:0.7,
        xaxis:'x2', yaxis:'y',
        name:gk||'', showlegend:false,
        hoverinfo:'skip',
      });
      /* Right: Y marginal */
      traces.push({
        type:'histogram', y:ys,
        marker:{color: groupKeys.length>1?color:(dark?'rgba(255,255,255,.7)':'#0A2463')},
        nbinsy:bins, opacity:0.7,
        xaxis:'x', yaxis:'y2',
        name:gk||'', showlegend:false,
        hoverinfo:'skip',
      });
    }
  });

  /* ── Layout ── */
  var GSTYLE2 = {gridcolor:gridcol,linecolor:gridcol,zerolinecolor:gridcol,tickfont:{size:9,family:'IBM Plex Mono',color:axcol}};
  var titleFont = {family:'Syne,sans-serif',size:13,color:axcol};

  var layout = {
    autosize:true,
    paper_bgcolor:bg, plot_bgcolor:bg,
    font:{family:'IBM Plex Mono',size:10,color:axcol},
    title:{text:titl||(xCol+' × '+yCol+' — KDE 2D'),font:titleFont,x:.05},
    barmode:'overlay',
    hovermode:'closest',
    showlegend:cCol&&groupKeys.length>1,
    legend:{bgcolor:'rgba(0,0,0,0)',font:{size:9,color:axcol}},
    hoverlabel:{bgcolor:'#0A2463',bordercolor:'#D4AF37',font:{family:'IBM Plex Mono',size:10,color:'white'}},
    margin:{l:60,r:margins?80:20,t:titl?50:margins?60:30,b:60},
  };

  if(margins) {
    /* 4-axis subplot layout:
       x (right hist), y (top hist), x2 (main), y2 (main)
       Main plot: [marg, 1] × [0, 1-marg]
       Top hist:  [marg, 1] × [1-marg, 1]
       Right hist:[0, marg] × [0, 1-marg]   (swapped because plotly y goes bottom-up)
    */
    var mainX = [marg, 1.0];
    var mainY = [0.0, 1-marg];
    var topY  = [1-marg+0.02, 1.0];
    var rightX= [0.0, marg-0.02];

    layout['xaxis']  = Object.assign({},GSTYLE2,{domain:rightX, title:{}, showticklabels:false, type:logY?'log':'linear'});
    layout['yaxis']  = Object.assign({},GSTYLE2,{domain:mainY,  title:{text:yCol,font:{size:11,color:axcol},standoff:6}, type:logY?'log':'linear'});
    layout['xaxis2'] = Object.assign({},GSTYLE2,{domain:mainX,  title:{text:xCol,font:{size:11,color:axcol},standoff:6}, type:logX?'log':'linear', anchor:'y2'});
    layout['yaxis2'] = Object.assign({},GSTYLE2,{domain:topY,   title:{}, showticklabels:false, type:logY?'log':'linear', anchor:'x2'});
  } else {
    layout['xaxis'] = Object.assign({},GSTYLE2,{title:{text:xCol,font:{size:12,color:axcol},standoff:8},type:logX?'log':'linear'});
    layout['yaxis'] = Object.assign({},GSTYLE2,{title:{text:yCol,font:{size:12,color:axcol},standoff:8},type:logY?'log':'linear'});
  }

  gbReact(traces, layout);
  setStatus(true,'✓ KDE 2D · '+FDATA.length+' pts'+(cCol?' · '+groupKeys.length+' groupes':''),
    xCol+' × '+yCol+(margins?" + marginaux":""));
}

