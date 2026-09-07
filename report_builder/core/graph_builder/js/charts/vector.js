// vector.js

// ── Ridge plot helpers ──
window.toggleRidgeOpts = function() {
  var on = document.getElementById('tog-ridge').classList.contains('on');
  document.getElementById('ridge-opts').style.display = on ? '' : 'none';
};
window.updateRidgeOffLabel = function(v) {
  document.getElementById('ridge-off-val').textContent = parseFloat(v)===0 ? 'auto' : parseFloat(v).toFixed(2)+'×';
};

/* Generate ridge colorscale */
function ridgeColor(t, palName) {
  /* t in [0,1], 0=bottom/cold, 1=top/hot */
  var stops = {
    navy_gold: [[0,'#0A2463'],[0.5,'#1a6b8a'],[1,'#D4AF37']],
    blues:     [[0,'#deebf7'],[0.5,'#6baed6'],[1,'#08519c']],
    viridis:   [[0,'#440154'],[0.33,'#31688e'],[0.67,'#35b779'],[1,'#fde725']],
    plasma:    [[0,'#0d0887'],[0.33,'#7e03a8'],[0.67,'#f89441'],[1,'#f0f921']],
    spectral:  [[0,'#9e0142'],[0.33,'#fdae61'],[0.67,'#abdda4'],[1,'#3288bd']],
  };
  var s = stops[palName] || stops.navy_gold;
  /* Find segment */
  for(var i=0;i<s.length-1;i++) {
    if(t<=s[i+1][0]) {
      var lt=(t-s[i][0])/(s[i+1][0]-s[i][0]);
      return lerpHex(s[i][1],s[i+1][1],lt);
    }
  }
  return s[s.length-1][1];
}
function lerpHex(a,b,t) {
  a=a.replace('#',''); b=b.replace('#','');
  var ri=parseInt(a.slice(0,2),16),gi=parseInt(a.slice(2,4),16),bi=parseInt(a.slice(4,6),16);
  var rf=parseInt(b.slice(0,2),16),gf=parseInt(b.slice(2,4),16),bf=parseInt(b.slice(4,6),16);
  return 'rgb('+Math.round(ri+(rf-ri)*t)+','+Math.round(gi+(gf-gi)*t)+','+Math.round(bi+(bf-bi)*t)+')';
}

// ── VECTOR ──────────────────────────────────────────────────────────────────
function buildVector() {
  var vxCol  = document.getElementById('v-x').value;
  var vyCol  = document.getElementById('v-y').value;
  var vgCol  = document.getElementById('v-grp').value;
  var vcCol  = document.getElementById('v-col').value;
  var vlim   = parseInt(document.getElementById('v-lim').value)||0;
  var logX   = document.getElementById('tog-vlx').classList.contains('on');
  var logY   = document.getElementById('tog-vly').classList.contains('on');
  var fill   = document.getElementById('tog-fill').classList.contains('on');
  var mks    = document.getElementById('tog-mks').classList.contains('on');
  var ridge  = document.getElementById('tog-ridge').classList.contains('on');
  var op     = parseFloat(document.getElementById('v-op').value);
  var titl   = document.getElementById('v-title').value;
  var pal    = PALETTES.aledia;

  if(!vxCol) { setStatus(false,'⚠ Sélectionner X vectoriel'); return; }

  var FDATA = applyFilters(DATA);
  var rows  = vlim>0 ? FDATA.slice(0,vlim) : FDATA;

  /* ── RIDGE PLOT ── */
  if(ridge) {
    var ridgeOff   = parseFloat(document.getElementById('ridge-off').value)||0;
    var ridgeAlpha = parseFloat(document.getElementById('ridge-alpha').value)||0.6;
    var ridgePal   = document.getElementById('ridge-pal').value||'navy_gold';
    var orderBy    = document.getElementById('ridge-order').value;

    /* Flatten: one curve per (LED × current_level) for spectral ridge
       OR one curve per LED for normal vectoriel */
    var curves = [];
    rows.forEach(function(r) {
      var xArr = Array.isArray(r[vxCol]) ? r[vxCol] : [];
      if(!xArr.length) return;

      /* If Y is 2D (Spectra-like: array of arrays), make one curve per inner array */
      if(vyCol && Array.isArray(r[vyCol]) && Array.isArray(r[vyCol][0])) {
        var jVals = Array.isArray(r['J']) ? r['J'] : [];
        r[vyCol].forEach(function(sp, si) {
          if(!Array.isArray(sp)) return;
          curves.push({
            x: xArr,
            y: sp,
            label: (r['Led_Name']||'')+' J='+(jVals[si]!=null?Number(jVals[si]).toExponential(1):'#'+si),
            sortKey: jVals[si] || si,
            led: r['Led_Name']||'',
          });
        });
      } else {
        /* Normal vector: one curve per LED */
        var yArr = vyCol && Array.isArray(r[vyCol]) ? r[vyCol] : xArr.map(function(_,i){return i;});
        curves.push({
          x: xArr, y: yArr,
          label: r['Led_Name']||'',
          sortKey: orderBy!=='index' && r[orderBy]!=null ? parseFloat(r[orderBy]) : curves.length,
          led: r['Led_Name']||'',
        });
      }
    });

    if(!curves.length) { setStatus(false,'⚠ Aucune donnée'); return; }

    /* Sort */
    curves.sort(function(a,b){ return a.sortKey - b.sortKey; });
    var n = curves.length;

    /* Compute global Y max for auto-offset */
    var globalMax = 0;
    curves.forEach(function(c) {
      var m = Math.max.apply(null, c.y.filter(function(v){return !isNaN(v)&&v>0;}));
      if(m > globalMax) globalMax = m;
    });
    var autoOff = globalMax * 0.6;
    var offset  = ridgeOff > 0 ? ridgeOff * globalMax : autoOff;

    /* Build traces bottom→top (index 0 = bottom) */
    var traces = [];
    var ytickVals = [], ytickText = [];

    curves.forEach(function(c, i) {
      var t = n>1 ? i/(n-1) : 0.5;
      var col = ridgeColor(t, ridgePal);
      var yOff = i * offset;

      /* Shifted Y */
      var ys = c.y.map(function(v){ return (isNaN(v)||v==null?0:v) + yOff; });

      /* Baseline at offset level */
      var xBaseline = [c.x[0], c.x[c.x.length-1]];
      var yBaseline = [yOff, yOff];

      /* Fill trace (from curve down to its baseline) */
      traces.push({
        type:'scatter', mode:'lines',
        x: c.x.concat(c.x.slice().reverse()),
        y: ys.concat(yBaseline.slice().reverse()),
        fill:'toself',
        fillcolor: hexAlpha(col, ridgeAlpha),
        line:{width:0, color:'rgba(0,0,0,0)'},
        hoverinfo:'skip', showlegend:false,
      });

      /* Line trace */
      traces.push({
        type:'scatter', mode:mks?'lines+markers':'lines',
        x: c.x, y: ys,
        line:{color:col, width:1.5},
        marker:{color:col, size:3},
        name: c.label,
        hovertemplate:'<b>'+c.label+'</b><br>x: %{x}<br>y: %{customdata}<extra></extra>',
        customdata: c.y,
        showlegend: false,
      });

      ytickVals.push(yOff);
      ytickText.push(c.label);
    });

    var area = document.getElementById('plot-area');
    var totalH = Math.max(area.clientHeight, n * 40 + 80);

    var _lay2={
      autosize:false, width:area.clientWidth, height:totalH,
      title:{text:titl||vxCol+' × '+(vyCol||'index')+' — Ridge',font:{family:'Syne',size:13,color:'#0A2463'},x:.05},
      paper_bgcolor:'#fff', plot_bgcolor:'white',
      font:{family:'IBM Plex Mono',size:10,color:'#4A5580'},
      xaxis:Object.assign({},GSTYLE,{
        title:{text:vxCol,font:{size:12,color:'#0A2463'},standoff:8},
        type:logX?'log':'linear', tickfont:{size:10},
        showgrid:true,
      }),
      yaxis:{
        tickvals: ytickVals,
        ticktext: ytickText,
        tickfont:{family:'IBM Plex Mono',size:9,color:'#4A5580'},
        showgrid:false, zeroline:false,
        range:[-offset*0.2, offset*(n+0.3)],
      },
      showlegend:false,
      hovermode:'closest',
      margin:{l:120,r:20,t:titl?50:30,b:50},
      hoverlabel:{bgcolor:'#0A2463',bordercolor:'#D4AF37',font:{family:'IBM Plex Mono',size:10,color:'white'}},
    };
    gbReact(traces, _lay2);

    setStatus(true, '✓ Ridge · '+n+' courbes', vxCol+(vyCol?' × '+vyCol:''));
    return;
  }

  /* ── NORMAL VECTOR ── */
  var groups = vgCol ? groupBy(rows,vgCol) : {'':rows};
  var traces = [];

  Object.keys(groups).sort().forEach(function(gk,gi) {
    var gdata=groups[gk], baseColor=pal[gi%pal.length];
    gdata.forEach(function(r,ri) {
      var xArr=Array.isArray(r[vxCol])?r[vxCol]:[];
      var yArr=vyCol&&Array.isArray(r[vyCol])?r[vyCol]:xArr.map(function(_,i){return i;});
      if(!xArr.length) return;
      var col = vcCol && r[vcCol]!=null ? null : (vgCol ? baseColor : pal[ri%pal.length]);
      traces.push({
        x:xArr, y:yArr,
        type:'scatter', mode:mks?'lines+markers':'lines',
        line:{color:col||baseColor, width:1.5},
        marker:{color:col||baseColor,size:4},
        fill:fill?'tozeroy':'none',
        fillcolor:fill?hexAlpha(col||baseColor,.1):'',
        opacity:op,
        name:(vgCol?gk+' — ':'')+r['Led_Name'],
        showlegend:!vgCol||(ri===0),
        hovertemplate:'<b>'+(r['Led_Name']||'')+'</b><br>x:%{x}<br>y:%{y}<extra></extra>',
      });
    });
  });

  var area=document.getElementById('plot-area');
  var _lay_vec={
    autosize:true,
    title:{text:titl,font:{family:'Syne',size:13,color:'#0A2463'},x:.05},
    paper_bgcolor:'#fff',plot_bgcolor:'#F8F9FD',
    font:{family:'IBM Plex Mono',size:11,color:'#4A5580'},
    xaxis:Object.assign({},GSTYLE,{title:{text:vxCol,font:{size:12,color:'#0A2463'},standoff:8},type:logX?'log':'linear',tickfont:{size:10}}),
    yaxis:Object.assign({},GSTYLE,{title:{text:vyCol||'index',font:{size:12,color:'#0A2463'},standoff:8},type:logY?'log':'linear',tickfont:{size:10}}),
    legend:{bgcolor:'rgba(0,0,0,0)',font:{size:9},itemsizing:'constant'},
    hovermode:'closest',margin:{l:64,r:16,t:titl?44:24,b:56},
    hoverlabel:{bgcolor:'#0A2463',bordercolor:'#D4AF37',font:{family:'IBM Plex Mono',size:10,color:'white'}},
  };
  gbReact(traces, _lay_vec);
  setStatus(true,'✓ '+rows.length+' courbes · '+vxCol+(vyCol?' × '+vyCol:''),
    (DATA.length-FDATA.length)?DATA.length-FDATA.length+' filtrés':'');
}

