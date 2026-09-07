// facet.js

// ── FACET GRID ───────────────────────────────────────────────────────────────
function buildFacet() {
  var xCol  = document.getElementById('f-x').value;
  var yCol  = document.getElementById('f-y').value;
  var colBy = document.getElementById('f-col').value;
  var rowBy = document.getElementById('f-row').value;
  var cCol  = document.getElementById('f-c').value;
  var shX   = document.getElementById('tog-fshx').classList.contains('on');
  var shY   = document.getElementById('tog-fshy').classList.contains('on');
  var logX  = document.getElementById('tog-flx').classList.contains('on');
  var logY  = document.getElementById('tog-fly').classList.contains('on');
  var rowH  = parseInt(document.getElementById('f-rowh').value)||220;
  var pal   = PALETTES.aledia;

  if(!xCol) { setStatus(false,'⚠ Sélectionner X'); return; }

  var FDATA = applyFilters(DATA);

  /* Get unique values for rows and cols */
  var colVals = colBy ? getUnique(FDATA, colBy) : [''];
  var rowVals = rowBy ? getUnique(FDATA, rowBy) : [''];
  var nCols = colVals.length;
  var nRows = rowVals.length;

  /* Color groups */
  var colorVals = cCol ? getUnique(FDATA, cCol) : [];
  var colorMap = {};
  colorVals.forEach(function(v,i){ colorMap[v] = pal[i%pal.length]; });

  /* Build subplot specs */
  var traces = [];
  var annotations = [];

  rowVals.forEach(function(rv, ri) {
    colVals.forEach(function(cv, ci) {
      var plotIdx = ri * nCols + ci + 1;
      var xaxis = 'x' + (plotIdx===1?'':plotIdx);
      var yaxis = 'y' + (plotIdx===1?'':plotIdx);

      /* Filter data for this cell */
      var cellData = FDATA.filter(function(r) {
        var okCol = !colBy || String(r[colBy])===String(cv);
        var okRow = !rowBy || String(r[rowBy])===String(rv);
        return okCol && okRow;
      });

      /* Color groups within cell */
      var groups = cCol ? groupBy(cellData, cCol) : {'':cellData};

      Object.keys(groups).sort().forEach(function(gk, gi) {
        var gdata = groups[gk];
        var color = cCol ? (colorMap[gk]||pal[gi%pal.length]) : pal[0];
        var xs = gdata.map(function(r){return r[xCol];});
        var ys = yCol ? gdata.map(function(r){return r[yCol];}) : null;
        var showLeg = (ri===0 && ci===0);  /* legend only in first cell */

        var base = {
          xaxis:xaxis, yaxis:yaxis,
          name:cCol?gk:(colBy?cv:rv)||'',
          legendgroup:cCol?gk:(colBy?cv:rv)||'all',
          showlegend:showLeg && !!cCol,
          marker:{color:color, size:6, opacity:.8},
        };

        if(facetType==='scatter') {
          traces.push(Object.assign({},base,{
            type:'scatter', mode:'markers', x:xs, y:ys,
            hovertemplate:'<b>%{text}</b><br>'+xCol+': %{x}'+(yCol?'<br>'+yCol+': %{y}':'')+'<extra></extra>',
            text:gdata.map(function(r){return r['Led_Name']||gk||'';})
          }));
        } else if(facetType==='histogram') {
          traces.push(Object.assign({},base,{
            type:'histogram', x:xs, opacity:.75,
            marker:{color:color},
          }));
        } else if(facetType==='box') {
          traces.push(Object.assign({},base,{
            type:'box', y:ys||xs,
            x:ys?xs:null,
            marker:{color:color, size:3}, boxpoints:'suspectedoutliers',
          }));
        } else if(facetType==='violin') {
          traces.push(Object.assign({},base,{
            type:'violin', y:ys||xs,
            line:{color:color}, fillcolor:color, opacity:.6,
            points:'outliers', box:{visible:true},
          }));
        }
      });

      /* Column header annotation (top of each column) */
      if(ri===0 && colBy) {
        annotations.push({
          text:'<b>'+colBy+'</b> = '+cv,
          xref:'x'+plotIdx+' domain', yref:'paper',
          x:0.5, y:1+(0.04/nRows),
          xanchor:'center', yanchor:'bottom',
          showarrow:false,
          font:{family:'IBM Plex Mono',size:10,color:'#0A2463'},
          bgcolor:'rgba(212,175,55,.1)',
          bordercolor:'rgba(212,175,55,.3)',
          borderpad:3,
        });
      }
      /* Row header annotation (right of each row) */
      if(ci===nCols-1 && rowBy) {
        annotations.push({
          text:'<b>'+rowBy+'</b> = '+rv,
          xref:'paper', yref:'y'+plotIdx+' domain',
          x:1+(0.03/nCols), y:0.5,
          xanchor:'left', yanchor:'middle',
          showarrow:false,
          textangle:90,
          font:{family:'IBM Plex Mono',size:10,color:'#0A2463'},
          bgcolor:'rgba(212,175,55,.1)',
          bordercolor:'rgba(212,175,55,.3)',
          borderpad:3,
        });
      }
    });
  });

  /* Build layout with subplot grid */
  var area = document.getElementById('plot-area');
  var totalH = Math.max(rowH * nRows, area.clientHeight);
  var GSTYLE2 = {gridcolor:'#E4E8F4',linecolor:'#E4E8F4',zerolinecolor:'#E4E8F4',
    showgrid:true, zeroline:false, tickfont:{size:9,family:'IBM Plex Mono'}};

  var layout = {
    autosize:false, width:area.clientWidth, height:totalH,
    paper_bgcolor:'#fff', plot_bgcolor:'#F8F9FD',
    font:{family:'IBM Plex Mono,monospace',size:10,color:'#4A5580'},
    grid:{rows:nRows, columns:nCols, pattern:'independent',
      xgap:0.08, ygap:0.1},
    barmode:'overlay',
    annotations:annotations,
    legend:{bgcolor:'rgba(0,0,0,0)',font:{size:10},
      x:1.02,xanchor:'left',y:1,yanchor:'top'},
    margin:{l:50,r:colBy?100:20,t:rowBy||colBy?50:20,b:50},
    hoverlabel:{bgcolor:'#0A2463',bordercolor:'#D4AF37',
      font:{family:'IBM Plex Mono',size:10,color:'white'}},
    hovermode:'closest',
  };

  /* Add per-subplot axis config */
  for(var ri=0; ri<nRows; ri++) {
    for(var ci=0; ci<nCols; ci++) {
      var idx = ri*nCols + ci + 1;
      var xk = 'xaxis'+(idx===1?'':idx);
      var yk = 'yaxis'+(idx===1?'':idx);
      layout[xk] = Object.assign({}, GSTYLE2, {
        type: logX?'log':'linear',
        title: ri===nRows-1 ? {text:xCol,font:{size:10,color:'#0A2463'}} : {},
        matches: shX && idx>1 ? 'x' : undefined,
      });
      layout[yk] = Object.assign({}, GSTYLE2, {
        type: logY?'log':'linear',
        title: ci===0 ? {text:yCol||'Count',font:{size:10,color:'#0A2463'}} : {},
        matches: shY && idx>1 ? 'y' : undefined,
      });
    }
  }

  gbReact(traces, layout);
  setStatus(true,
    '✓ Facet '+nRows+'×'+nCols+' · '+FDATA.length+' LEDs',
    (colBy||'—')+' × '+(rowBy||'—'));
}

function getUnique(arr, col) {
  var seen={}, out=[];
  arr.forEach(function(r){
    var v=String(r[col]!=null?r[col]:'?');
    if(!seen[v]){seen[v]=true;out.push(v);}
  });
  return out.sort();
}

