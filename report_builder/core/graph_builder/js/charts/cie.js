// cie.js

// ── CIE 1931 ────────────────────────────────────────────────────────────────
function buildCIE() {
  var activeWafer = document.getElementById('cie-wafer').value;
  var sizeBy      = document.getElementById('cie-size').value;
  var showTraj    = document.getElementById('tog-traj').classList.contains('on');
  var showLocus   = document.getElementById('tog-locus').classList.contains('on');
  var showPlanck  = document.getElementById('tog-planck').classList.contains('on');

  var rows = applyFilters(DATA_FULL);
  if(activeWafer) rows=rows.filter(function(r){return r['wafername']===activeWafer;});

  /* Compute global J range for size normalization */
  var allJ=[];
  rows.forEach(function(r){(r['J']||[]).forEach(function(v){if(v>1e-12)allJ.push(v);});});
  var jMin=allJ.length?Math.log10(Math.min.apply(null,allJ)):0;
  var jMax=allJ.length?Math.log10(Math.max.apply(null,allJ)):1;
  function jToSz(v){
    if(!v||v<=1e-12) return 4;
    if(jMax===jMin) return 8;
    return 4+(Math.log10(v)-jMin)/(jMax-jMin)*18;
  }
  function eqeToSz(v){
    if(!v||isNaN(v)) return 4;
    return 4 + v/0.3*14;
  }

  function hexToRgba(hex,a){
    hex=hex.replace('#','');
    if(hex.length===3)hex=hex[0]+hex[0]+hex[1]+hex[1]+hex[2]+hex[2];
    var r=parseInt(hex.slice(0,2),16),g=parseInt(hex.slice(2,4),16),b=parseInt(hex.slice(4,6),16);
    return 'rgba('+r+','+g+','+b+','+a+')';
  }

  var traces=[];

  if(showLocus) traces.push({type:'scatter',mode:'lines',x:LOCUS_X,y:LOCUS_Y,
    line:{color:'rgba(0,0,0,.4)',width:1.5},hoverinfo:'skip',showlegend:false});
  if(showPlanck) traces.push({type:'scatter',mode:'lines',x:PLANCK_X,y:PLANCK_Y,
    line:{color:'rgba(180,120,0,.5)',width:1,dash:'dot'},hoverinfo:'skip',showlegend:false});
  traces.push({type:'scatter',mode:'markers+text',x:[0.3127],y:[0.3290],
    marker:{color:'white',size:8,line:{color:'#555',width:1.5}},
    text:['D65'],textposition:'top right',textfont:{family:'IBM Plex Mono',size:8,color:'#555'},
    hoverinfo:'skip',showlegend:false});

  /* All points batched */
  var allX=[],allY=[],allCol=[],allSz=[],allTxt=[];
  rows.forEach(function(r) {
    var cx=r['CIEx']||[],cy=r['CIEy']||[];
    var jv=r['J']||[],ev=r['EQE']||[];
    var cols=r['srgb']||[];
    cx.forEach(function(x,i) {
      if(x==null||cy[i]==null||isNaN(x)||isNaN(cy[i])) return;
      allX.push(x); allY.push(cy[i]);
      var sz = sizeBy==='J'?jToSz(jv[i]):sizeBy==='EQE'?eqeToSz(ev[i]):8;
      allSz.push(sz);
      var hex=cols[i]||'#D4AF37';
      allCol.push(hexToRgba(hex,.85));
      allTxt.push('<b>'+r['Led_Name']+'</b><br>CIEx:'+x.toFixed(4)+'<br>CIEy:'+cy[i].toFixed(4)+
        (jv[i]?'<br>J:'+Number(jv[i]).toExponential(2):''));
    });

    /* Trajectories */
    if(showTraj && cx.length>1) {
      var txs=[],tys=[];
      cx.forEach(function(x,i){if(x!=null&&cy[i]!=null&&!isNaN(x)&&!isNaN(cy[i])){txs.push(x);tys.push(cy[i]);}  });
      traces.push({type:'scatter',mode:'lines',x:txs,y:tys,
        line:{color:'rgba(10,36,99,.2)',width:1,dash:'dot'},
        hoverinfo:'skip',showlegend:false});
    }
  });

  if(allX.length) traces.push({
    type:'scatter',mode:'markers',x:allX,y:allY,
    marker:{color:allCol,size:allSz,line:{width:.5,color:'rgba(0,0,0,.2)'}},
    text:allTxt,hovertemplate:'%{text}<extra></extra>',
    showlegend:false,
  });

  /* Lambda colorbar */
  if(allX.length) traces.push({
    type:'scatter',mode:'markers',x:[allX[0]],y:[allY[0]],
    marker:{color:[550],colorscale:LAMBDA_CS,showscale:true,
      cmin:400,cmax:700,opacity:0,size:.1,
      colorbar:{title:{text:'λ (nm)',font:{size:10},side:'right'},
        thickness:12,len:.7,x:1.01,
        tickvals:[400,450,500,550,600,650,700],
        tickfont:{size:9,family:'IBM Plex Mono'}}},
    hoverinfo:'skip',showlegend:false});

  var area=document.getElementById('plot-area');
  var _lay3={



    autosize:true,
    paper_bgcolor:'white',plot_bgcolor:'white',
    font:{family:'IBM Plex Mono',size:10,color:'#4A5580'},
    margin:{t:16,r:72,b:48,l:56},
    xaxis:Object.assign({},GSTYLE,{title:{text:'CIE x',font:{size:12,color:'#0A2463'},standoff:8},range:[0,.8],tickfont:{size:10}}),
    yaxis:Object.assign({},GSTYLE,{title:{text:'CIE y',font:{size:12,color:'#0A2463'},standoff:8},range:[0,.9],tickfont:{size:10},scaleanchor:'x',scaleratio:1}),
    hovermode:'closest',showlegend:false,
    hoverlabel:{bgcolor:'#0A2463',bordercolor:'#D4AF37',font:{family:'IBM Plex Mono',size:10,color:'white'}},
  
  };
  gbReact(traces, _lay3);
  setStatus(true,'✓ CIE 1931 · '+rows.length+' LEDs'+(activeWafer?' — '+activeWafer:''),allX.length+' pts');
}

// ─────────────────────────────────────────────────────────────────────────────
//  Helpers
// ─────────────────────────────────────────────────────────────────────────────
function hexAlpha(hex,a){
  if(!hex||hex[0]!=='#') return 'rgba(212,175,55,'+a+')';
  hex=hex.replace('#','');
  if(hex.length===3)hex=hex[0]+hex[0]+hex[1]+hex[1]+hex[2]+hex[2];
  var r=parseInt(hex.slice(0,2),16),g=parseInt(hex.slice(2,4),16),b=parseInt(hex.slice(4,6),16);
  return 'rgba('+r+','+g+','+b+','+a+')';
}

// ─────────────────────────────────────────────────────────────────────────────
//  Resize handle
// ─────────────────────────────────────────────────────────────────────────────
var _rHandle=document.getElementById('resizer');
var _rSidebar=document.getElementById('sidebar');
var _rDrag=false,_rStartX=0,_rStartW=0;
_rHandle.addEventListener('mousedown',function(e){_rDrag=true;_rStartX=e.clientX;_rStartW=_rSidebar.offsetWidth;_rHandle.classList.add('drag');document.body.style.cursor='col-resize';document.body.style.userSelect='none';e.preventDefault();});
document.addEventListener('mousemove',function(e){if(!_rDrag)return;var w=Math.min(480,Math.max(200,_rStartW+(e.clientX-_rStartX)));_rSidebar.style.width=w+'px';resizePlot();});
document.addEventListener('mouseup',function(){if(!_rDrag)return;_rDrag=false;_rHandle.classList.remove('drag');document.body.style.cursor='';document.body.style.userSelect='';});

// Auto-resize
var _plotAreaEl = document.getElementById('plot-area');
if(_plotAreaEl) new ResizeObserver(resizePlot).observe(_plotAreaEl);