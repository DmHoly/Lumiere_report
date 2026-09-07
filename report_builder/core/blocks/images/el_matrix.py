"""
ELMatrixBlock — Grille N×N d'images EL par design (led_name).

196 designs disposés en matrice comme DesignMatrixBlock,
mais chaque cellule affiche directement l'image EL plutôt qu'un carré KPI coloré.
Navigation globale image_number, filtre type, zoom modal.
"""
from __future__ import annotations
import json
import math
import html as _h
import pandas as pd
from report_builder.core._helpers import Block
from report_builder.core.blocks.data.data_mixin import DataMixin, DataArg


class ELMatrixBlock(DataMixin, Block):
    """
    Grille N×N d'images EL par design LED.

    Paramètres
    ----------
    data / df       : DataFrame ou clé DataStore.
    led_col         : colonne design/led (défaut "led_name") — définit les cellules.
    image_col       : chemin image (défaut "full_path").
    wafer_col       : colonne wafer (défaut "wafername").
    imgnum_col      : colonne image_number (défaut "image_number").
    type_col        : colonne type (défaut "type").
    grid_cols       : nb de colonnes forcé (défaut : √n arrondi).
    cell_size       : taille d'une cellule en px (défaut 80).
    show_labels     : afficher le led_name sous chaque cellule.
    num / title / subtitle : métadonnées du bloc.
    height          : hauteur totale du bloc en px (défaut 600).
    """

    def __init__(
        self,
        data: DataArg = None,
        df=None,
        led_col: str = "led_name",
        image_col: str = "full_path",
        wafer_col: str = "wafername",
        imgnum_col: str = "image_number",
        type_col: str = "type",
        grid_cols: int | None = None,
        cell_size: int = 80,
        show_labels: bool = False,
        num: str = "01",
        title: str = "EL Matrix",
        subtitle: str = "",
        height: int = 600,
    ):
        self._init_data(data if data is not None else df)
        self.led_col    = led_col
        self.image_col  = image_col
        self.wafer_col  = wafer_col
        self.imgnum_col = imgnum_col
        self.type_col   = type_col
        self.grid_cols  = grid_cols
        self.cell_size  = cell_size
        self.show_labels = show_labels
        self.num      = num
        self.title    = title
        self.subtitle = subtitle
        self.height   = height
        self._id = f"elm_{id(self)}"

    # ── Sérialisation ────────────────────────────────────────────────────

    def _build_js_data(self, df: pd.DataFrame) -> tuple[str, str, int, int]:
        """
        Retourne (data_json, order_json, n_cols, n_rows).

        data_json  : {wafer: {led: {type: [{src, imgnum}]}}}
        order_json : [led_name, ...] dans l'ordre de la grille
        """
        result: dict = {}

        # Ordre des designs : basé sur le wafer avec le plus de designs
        counts = df.groupby(self.wafer_col)[self.led_col].count() if self.wafer_col in df.columns else None
        if counts is not None and len(counts):
            ref_wafer = counts.idxmax()
            ref_rows  = df[df[self.wafer_col] == ref_wafer]
        else:
            ref_rows = df

        ordered_leds: list[str] = []
        seen: set = set()
        for led in ref_rows[self.led_col].dropna().astype(str):
            if led not in seen:
                ordered_leds.append(led)
                seen.add(led)

        # Ajouter les leds absentes du wafer de référence
        extra = len(ordered_leds)
        for led in df[self.led_col].dropna().astype(str).unique():
            if led not in seen:
                ordered_leds.append(led)
                seen.add(led)

        n = len(ordered_leds)
        nc = self.grid_cols or int(math.ceil(math.sqrt(n)))
        nr = int(math.ceil(n / nc))

        # Construire les données
        for _, row in df.iterrows():
            led = str(row.get(self.led_col, "")) if self.led_col in df.columns else ""
            if not led:
                continue
            wafer  = str(row.get(self.wafer_col, "unknown"))
            typ    = str(row.get(self.type_col, "")) if self.type_col and self.type_col in df.columns else ""
            imgnum = row.get(self.imgnum_col, None)
            src    = str(row.get(self.image_col, "")).replace("\\", "/")
            if not src:
                continue

            result.setdefault(wafer, {})
            result[wafer].setdefault(led, {})
            result[wafer][led].setdefault(typ, [])
            result[wafer][led][typ].append({
                "src":    src,
                "imgnum": str(imgnum) if imgnum is not None else "",
            })

        return json.dumps(result), json.dumps(ordered_leds), nc, nr

    def _all_types(self, df: pd.DataFrame) -> list[str]:
        if not self.type_col or self.type_col not in df.columns:
            return []
        return sorted(df[self.type_col].dropna().unique().tolist())

    # ── Render ───────────────────────────────────────────────────────────

    def render(self, store=None) -> str:
        df = self.resolve_df(store)
        sid = self._id
        data_json, order_json, nc, nr = self._build_js_data(df)
        all_types   = self._all_types(df)
        types_json  = json.dumps(all_types)
        show_labels = "true" if self.show_labels else "false"
        cs          = self.cell_size
        main_h      = self.height - 90

        title_h = _h.escape(self.title)
        sub_h   = _h.escape(self.subtitle)
        num_h   = _h.escape(self.num)

        return f"""
<div class="led-block" id="{sid}_wrap"
  style="font-family:'IBM Plex Mono',monospace;">

  <!-- En-tête -->
  <div class="led-block-header">
    <span class="led-block-num">{num_h}</span>
    <span class="led-block-title">{title_h}</span>
    <span class="led-block-sub">{sub_h}</span>
  </div>
  <div class="led-block-rule"></div>

  <!-- Toolbar -->
  <div style="display:flex;align-items:center;gap:8px;margin-bottom:8px;flex-wrap:wrap;">

    <select id="{sid}_wsel" onchange="{sid}_changeWafer(this.value)"
      class="spt-filter-op"
      style="font-size:11px;padding:4px 8px;min-width:140px;">
    </select>

    <!-- Filtre type -->
    <div style="display:flex;align-items:center;gap:4px;">
      <span style="font-size:10px;color:rgba(10,36,99,.5);white-space:nowrap;">Type :</span>
      <div id="{sid}_type_btns"
        style="display:flex;border:0.5px solid rgba(10,36,99,.2);border-radius:4px;overflow:hidden;">
      </div>
    </div>

    <!-- Navigation image_number globale -->
    <div id="{sid}_imgnum_nav"
      style="display:none;align-items:center;gap:4px;">
      <span style="font-size:10px;color:rgba(10,36,99,.5);white-space:nowrap;">Image # :</span>
      <button onclick="{sid}_stepImgNum(-1)"
        style="width:20px;height:20px;border:0.5px solid rgba(10,36,99,.2);border-radius:3px;
               background:transparent;cursor:pointer;font-size:12px;color:#0A2463;padding:0;line-height:1;">
        &#8249;</button>
      <div id="{sid}_imgnum_btns" style="display:flex;gap:3px;"></div>
      <button onclick="{sid}_stepImgNum(1)"
        style="width:20px;height:20px;border:0.5px solid rgba(10,36,99,.2);border-radius:3px;
               background:transparent;cursor:pointer;font-size:12px;color:#0A2463;padding:0;line-height:1;">
        &#8250;</button>
    </div>

    <span id="{sid}_badge"
      style="font-size:10px;color:#D4AF37;border:1px solid rgba(212,175,55,.4);
             padding:2px 6px;border-radius:3px;white-space:nowrap;margin-left:auto;">
    </span>

    <!-- Filtre texte design -->
    <input id="{sid}_search" type="text" placeholder="Filtrer design…"
      oninput="{sid}_onSearch(this.value)"
      style="height:26px;padding:0 8px;border:0.5px solid rgba(10,36,99,.2);border-radius:4px;
             font-family:'IBM Plex Mono',monospace;font-size:10px;
             background:transparent;color:#0A2463;width:140px;">

    <!-- Slider taille cellule -->
    <div style="display:flex;align-items:center;gap:4px;">
      <span style="font-size:9px;color:rgba(10,36,99,.4);">Taille</span>
      <input id="{sid}_size_sl" type="range" min="40" max="220" step="10" value="{cs}"
        oninput="{sid}_onSize(parseInt(this.value))"
        style="width:70px;accent-color:#0A2463;cursor:pointer;height:3px;">
      <span id="{sid}_size_val"
        style="font-size:9px;color:#0A2463;min-width:34px;
               font-family:'IBM Plex Mono',monospace;">{cs}px</span>
    </div>
  </div>

  <!-- Grille -->
  <div id="{sid}_outer"
    style="height:{main_h}px;overflow:auto;background:#0A0E1A;border-radius:8px;
           border:0.5px solid rgba(10,36,99,.2);padding:8px;">
    <div id="{sid}_grid"
      style="display:grid;gap:3px;grid-template-columns:repeat({nc},{cs}px);">
    </div>
  </div>

  <!-- Modale zoom -->
  <div id="{sid}_zm_modal"
    style="display:none;position:fixed;inset:0;z-index:9999;
           background:rgba(10,18,40,.9);align-items:center;justify-content:center;">
    <div style="position:absolute;top:0;left:0;right:0;height:44px;
                display:flex;align-items:center;padding:0 14px;gap:6px;">
      <span id="{sid}_zm_label"
        style="font-family:'IBM Plex Mono',monospace;font-size:11px;
               color:rgba(255,255,255,.75);flex:1;overflow:hidden;text-overflow:ellipsis;
               white-space:nowrap;"></span>
      <button onclick="{sid}_zmZoom(1.25)"
        style="width:28px;height:28px;border:0.5px solid rgba(255,255,255,.25);
               border-radius:4px;background:transparent;color:#fff;
               cursor:pointer;font-size:16px;line-height:1;">+</button>
      <button onclick="{sid}_zmZoom(0.8)"
        style="width:28px;height:28px;border:0.5px solid rgba(255,255,255,.25);
               border-radius:4px;background:transparent;color:#fff;
               cursor:pointer;font-size:16px;line-height:1;">−</button>
      <button onclick="{sid}_zmReset()"
        style="height:28px;padding:0 8px;border:0.5px solid rgba(255,255,255,.25);
               border-radius:4px;background:transparent;color:rgba(255,255,255,.7);
               cursor:pointer;font-size:10px;font-family:'IBM Plex Mono',monospace;">reset</button>
      <button onclick="{sid}_zmNav(-1)"
        style="width:28px;height:28px;border:0.5px solid rgba(255,255,255,.25);
               border-radius:4px;background:transparent;color:#fff;
               cursor:pointer;font-size:16px;line-height:1;">&#8249;</button>
      <button onclick="{sid}_zmNav(1)"
        style="width:28px;height:28px;border:0.5px solid rgba(255,255,255,.25);
               border-radius:4px;background:transparent;color:#fff;
               cursor:pointer;font-size:16px;line-height:1;">&#8250;</button>
      <button onclick="{sid}_closeZoom()"
        style="width:28px;height:28px;border:0.5px solid rgba(255,255,255,.25);
               border-radius:4px;background:transparent;color:#fff;
               cursor:pointer;font-size:18px;line-height:1;">✕</button>
    </div>
    <div id="{sid}_zm_vp"
      style="position:absolute;inset:44px 0 0 0;overflow:hidden;cursor:grab;">
      <img id="{sid}_zm_img" src="" alt=""
        style="position:absolute;transform-origin:0 0;user-select:none;max-width:none;">
    </div>
  </div>

</div>

<script>
(function(){{
  var ALL       = {data_json};
  var ORDER     = {order_json};
  var ALL_TYPES = {types_json};
  var sid       = "{sid}";
  var NC_INIT   = {nc};
  var SHOW_LBL  = {show_labels};

  var cellSize     = {cs};
  var currentWafer = Object.keys(ALL)[0] || null;
  var activeType   = ALL_TYPES[0] || "";
  var searchFilter = "";
  var allImgNums   = [];
  var globalImgNum = 0;
  var cellRegistry = [];  /* {{led, images, setImg, el}} */

  /* ── Wafer selector ─────────────────────────────── */
  var wsel = document.getElementById(sid+"_wsel");
  Object.keys(ALL).forEach(function(w){{
    var o = document.createElement("option");
    o.value = w; o.textContent = w;
    wsel.appendChild(o);
  }});

  /* ── Type buttons ───────────────────────────────── */
  var typeBtnCon = document.getElementById(sid+"_type_btns");

  function buildTypeButtons(){{
    typeBtnCon.innerHTML = "";
    var types = (ALL_TYPES.length > 1 ? ["all"] : []).concat(ALL_TYPES);
    if(ALL_TYPES.length === 1 && activeType === "") activeType = ALL_TYPES[0];
    types.forEach(function(t, i){{
      var btn = document.createElement("button");
      btn.textContent = t === "all" ? "Tous" : t;
      btn.dataset.type = t;
      btn.style.cssText =
        "height:26px;padding:0 8px;border:none;cursor:pointer;"+
        "font-family:'IBM Plex Mono',monospace;font-size:10px;"+
        (i>0?"border-left:0.5px solid rgba(10,36,99,.15);":"")+
        (t === activeType
          ? "background:rgba(10,36,99,0.1);color:#0A2463;font-weight:600;"
          : "background:transparent;color:#888;");
      btn.addEventListener("click", function(){{
        activeType = t;
        refreshTypeButtons();
        buildGrid(currentWafer);
      }});
      typeBtnCon.appendChild(btn);
    }});
  }}

  function refreshTypeButtons(){{
    typeBtnCon.querySelectorAll("button").forEach(function(btn){{
      var t = btn.dataset.type;
      btn.style.background = (t===activeType)?"rgba(10,36,99,0.1)":"transparent";
      btn.style.color      = (t===activeType)?"#0A2463":"#888";
      btn.style.fontWeight = (t===activeType)?"600":"normal";
    }});
  }}

  buildTypeButtons();

  /* ── Images pour une LED ────────────────────────── */
  function getLedImages(wafer, led){{
    var ledData = ((ALL[wafer]||{{}})[led])||{{}};
    if(activeType === "all"){{
      var imgs = [];
      Object.values(ledData).forEach(function(arr){{ arr.forEach(function(img){{ imgs.push(img); }}); }});
      return imgs;
    }}
    return ledData[activeType] || [];
  }}

  /* ── Image number nav ───────────────────────────── */
  function collectImgNums(wafer){{
    var numSet = {{}};
    ORDER.forEach(function(led){{
      getLedImages(wafer, led).forEach(function(img){{
        if(img.imgnum) numSet[img.imgnum] = true;
      }});
    }});
    allImgNums = Object.keys(numSet).sort(function(a,b){{
      var na=parseFloat(a),nb=parseFloat(b);
      return isNaN(na)||isNaN(nb)?a.localeCompare(b):na-nb;
    }});
    globalImgNum = 0;
  }}

  function buildImgNumBar(){{
    var nav  = document.getElementById(sid+"_imgnum_nav");
    var btns = document.getElementById(sid+"_imgnum_btns");
    if(!btns) return;
    btns.innerHTML = "";
    if(allImgNums.length <= 1){{ if(nav) nav.style.display="none"; return; }}
    if(nav) nav.style.display="flex";
    allImgNums.forEach(function(num,i){{
      var btn = document.createElement("button");
      btn.textContent = num; btn.dataset.idx = i;
      btn.style.cssText =
        "height:20px;min-width:20px;padding:0 5px;border-radius:3px;"+
        "border:0.5px solid rgba(212,175,55,.3);cursor:pointer;"+
        "font-family:'IBM Plex Mono',monospace;font-size:9px;"+
        (i===0?"background:#D4AF37;color:#0A0E1A;border-color:#D4AF37;"
              :"background:transparent;color:rgba(212,175,55,.7);");
      btn.addEventListener("click",(function(idx){{return function(){{window[sid+"_globalImgSet"](idx);}};}})(i));
      btns.appendChild(btn);
    }});
  }}

  function refreshImgNumBar(){{
    var btns = document.getElementById(sid+"_imgnum_btns");
    if(!btns) return;
    btns.querySelectorAll("button").forEach(function(btn){{
      var i=parseInt(btn.dataset.idx);
      if(i===globalImgNum){{btn.style.background="#D4AF37";btn.style.color="#0A0E1A";btn.style.borderColor="#D4AF37";}}
      else{{btn.style.background="transparent";btn.style.color="rgba(212,175,55,.7)";btn.style.borderColor="rgba(212,175,55,.3)";}}
    }});
  }}

  function applyGlobalImgNum(){{
    var targetNum = allImgNums[globalImgNum];
    cellRegistry.forEach(function(entry){{
      if(!entry.images.length) return;
      var idx = 0;
      for(var i=0;i<entry.images.length;i++){{
        if(entry.images[i].imgnum===targetNum){{idx=i;break;}}
      }}
      entry.setImg(idx);
    }});
    refreshImgNumBar();
  }}

  window[sid+"_globalImgSet"] = function(idx){{
    globalImgNum = Math.max(0,Math.min(allImgNums.length-1,idx));
    applyGlobalImgNum();
  }};
  window[sid+"_stepImgNum"] = function(dir){{ window[sid+"_globalImgSet"](globalImgNum+dir); }};

  /* ── Search filter ──────────────────────────────── */
  window[sid+"_onSearch"] = function(val){{
    searchFilter = val.trim().toLowerCase();
    cellRegistry.forEach(function(entry){{
      var visible = !searchFilter || entry.led.toLowerCase().indexOf(searchFilter)>=0;
      entry.el.style.opacity  = visible?"1":"0.12";
      entry.el.style.outline  = visible&&searchFilter?"2px solid #D4AF37":"none";
    }});
  }};

  /* ── Cell size ──────────────────────────────────── */
  window[sid+"_onSize"] = function(val){{
    cellSize = val;
    var lbl = document.getElementById(sid+"_size_val");
    if(lbl) lbl.textContent = val+"px";
    /* Resize toutes les cellules sans rebuild complet */
    var grid = document.getElementById(sid+"_grid");
    var nc = Math.ceil(Math.sqrt(ORDER.length));
    if(grid){{
      grid.style.gridTemplateColumns = "repeat("+nc+","+val+"px)";
      cellRegistry.forEach(function(e){{
        e.el.style.width  = val+"px";
        e.el.style.height = val+"px";
      }});
    }}
  }};

  /* ── Build grid ─────────────────────────────────── */
  function buildGrid(wafer){{
    cellRegistry = [];
    var grid = document.getElementById(sid+"_grid");
    if(!grid) return;
    grid.innerHTML = "";

    var nc = Math.ceil(Math.sqrt(ORDER.length));
    grid.style.gridTemplateColumns = "repeat("+nc+","+cellSize+"px)";

    var nVisible = 0;

    ORDER.forEach(function(led){{
      var images = getLedImages(wafer, led);
      var n      = images.length;
      var hasImg = n > 0;
      if(hasImg) nVisible++;

      var cell = document.createElement("div");
      cell.style.cssText =
        "width:"+cellSize+"px;height:"+cellSize+"px;"+
        "position:relative;overflow:hidden;box-sizing:border-box;"+
        "background:"+(hasImg?"#111827":"#0d1117")+";"+
        "border-radius:2px;cursor:"+(hasImg?"pointer":"default")+";"+
        "border:1px solid "+(hasImg?"rgba(30,58,138,0.5)":"rgba(15,23,42,0.8)")+";"+
        "transition:border-color .1s,box-shadow .1s;"+
        (hasImg?"":"opacity:0.25;");

      if(!hasImg){{
        /* Placeholder vide */
        grid.appendChild(cell);
        cellRegistry.push({{led:led, images:[], setImg:function(){{}}, el:cell}});
        return;
      }}

      var cellIdx = 0;

      var img = document.createElement("img");
      img.dataset.lazySrc = images[0].src;
      img.style.cssText =
        "position:absolute;inset:0;width:100%;height:100%;"+
        "object-fit:cover;display:block;";
      cell.appendChild(img);

      if(window[sid+"_io"]) window[sid+"_io"].observe(img);

      function setImg(idx){{
        cellIdx = (idx+n)%n;
        var newSrc = images[cellIdx].src;
        if(img.dataset.lazySrc!==undefined && !img.src){{
          img.dataset.lazySrc = newSrc;
        }} else {{
          img.src = newSrc;
        }}
      }}

      /* Label LED (optionnel ou au hover) */
      var tip = document.createElement("div");
      var shortLed = led.length>18?led.slice(0,17)+"…":led;
      tip.textContent = SHOW_LBL ? shortLed : shortLed;
      tip.style.cssText =
        "position:absolute;bottom:0;left:0;right:0;"+
        "background:rgba(10,14,26,0.78);color:rgba(255,255,255,.8);"+
        "font-size:7px;padding:2px 3px;white-space:nowrap;overflow:hidden;"+
        "text-overflow:ellipsis;pointer-events:none;"+
        (SHOW_LBL?"opacity:1;":"opacity:0;transition:opacity .1s;");
      tip.title = led;
      cell.appendChild(tip);

      /* Badge multi-image */
      if(n > 1){{
        var cnt = document.createElement("div");
        cnt.textContent = n+"×";
        cnt.style.cssText =
          "position:absolute;top:2px;right:2px;"+
          "font-size:7px;color:rgba(212,175,55,.7);pointer-events:none;"+
          "font-family:'IBM Plex Mono',monospace;background:rgba(10,14,26,0.6);"+
          "padding:0 2px;border-radius:2px;";
        cell.appendChild(cnt);
      }}

      cell.addEventListener("mouseenter", function(){{
        cell.style.borderColor = "#D4AF37";
        cell.style.boxShadow   = "inset 0 0 0 1.5px #D4AF37,0 0 6px rgba(212,175,55,.3)";
        cell.style.zIndex      = "5";
        if(!SHOW_LBL) tip.style.opacity = "1";
      }});
      cell.addEventListener("mouseleave", function(){{
        cell.style.borderColor = "rgba(30,58,138,0.5)";
        cell.style.boxShadow   = "";
        cell.style.zIndex      = "";
        if(!SHOW_LBL) tip.style.opacity = "0";
      }});

      cell.addEventListener("click", (function(capturedLed, getIdx){{
        return function(){{ openZoom(capturedLed, getIdx()); }};
      }})(led, function(){{ return cellIdx; }}));

      cellRegistry.push({{led:led, images:images, setImg:setImg, el:cell}});
      grid.appendChild(cell);
    }});

    /* Badge */
    var badge = document.getElementById(sid+"_badge");
    if(badge) badge.textContent = nVisible+" design"+(nVisible>1?"s":"")+" · "+ORDER.length+" total";

    collectImgNums(wafer);
    buildImgNumBar();
    if(allImgNums.length > 1) applyGlobalImgNum();
  }}

  /* ── Lazy loading ───────────────────────────────── */
  (function(){{
    var outer = document.getElementById(sid+"_outer");
    window[sid+"_io"] = new IntersectionObserver(function(entries){{
      entries.forEach(function(e){{
        if(e.isIntersecting && e.target.dataset.lazySrc){{
          e.target.src = e.target.dataset.lazySrc;
          delete e.target.dataset.lazySrc;
          window[sid+"_io"].unobserve(e.target);
        }}
      }});
    }}, {{root:outer, rootMargin:"300px"}});
  }})();

  /* ── Wafer change ───────────────────────────────── */
  window[sid+"_changeWafer"] = function(w){{
    currentWafer = w;
    globalImgNum = 0;
    buildGrid(w);
  }};

  /* ── Zoom modal ─────────────────────────────────── */
  var zmScale=1, zmX=0, zmY=0;
  var zmDragging=false, zmDX=0, zmDY=0, zmOX=0, zmOY=0;
  var zmImages=[], zmIdx=0, zmLed="";

  function zmApply(){{
    var img=document.getElementById(sid+"_zm_img");
    if(img) img.style.transform="translate("+zmX+"px,"+zmY+"px) scale("+zmScale+")";
  }}

  function openZoom(led, idx){{
    var images = getLedImages(currentWafer, led);
    if(!images.length) return;
    zmImages=images; zmIdx=idx; zmLed=led;
    document.getElementById(sid+"_zm_modal").style.display="flex";
    loadZoomImg();
  }}

  function loadZoomImg(){{
    var entry=zmImages[zmIdx]; if(!entry) return;
    var zm=document.getElementById(sid+"_zm_img");
    zm.src=entry.src;
    var lbl=document.getElementById(sid+"_zm_label");
    if(lbl) lbl.textContent=zmLed+(entry.imgnum?" · #"+entry.imgnum:"")+"  ["+(zmIdx+1)+"/"+zmImages.length+"]";
    zm.onload=function(){{
      var vp=document.getElementById(sid+"_zm_vp");
      var vpW=vp.offsetWidth, vpH=vp.offsetHeight;
      zmScale=Math.min(vpW/zm.naturalWidth,vpH/zm.naturalHeight,1);
      zmX=(vpW-zm.naturalWidth*zmScale)/2;
      zmY=(vpH-zm.naturalHeight*zmScale)/2;
      zmApply();
    }};
  }}

  window[sid+"_zmNav"] = function(dir){{
    if(!zmImages.length) return;
    zmIdx=(zmIdx+dir+zmImages.length)%zmImages.length;
    loadZoomImg();
  }};
  window[sid+"_closeZoom"]=function(){{ document.getElementById(sid+"_zm_modal").style.display="none"; }};
  window[sid+"_zmZoom"]=function(f){{
    var vp=document.getElementById(sid+"_zm_vp");
    var cx=vp.offsetWidth/2,cy=vp.offsetHeight/2;
    zmX=cx-(cx-zmX)*f; zmY=cy-(cy-zmY)*f; zmScale*=f; zmApply();
  }};
  window[sid+"_zmReset"]=function(){{
    var vp=document.getElementById(sid+"_zm_vp");
    var zm=document.getElementById(sid+"_zm_img");
    zmScale=Math.min(vp.offsetWidth/zm.naturalWidth,vp.offsetHeight/zm.naturalHeight,1);
    zmX=(vp.offsetWidth-zm.naturalWidth*zmScale)/2;
    zmY=(vp.offsetHeight-zm.naturalHeight*zmScale)/2;
    zmApply();
  }};

  (function(){{
    var vp=document.getElementById(sid+"_zm_vp");
    vp.addEventListener("wheel",function(e){{
      e.preventDefault();
      var rect=vp.getBoundingClientRect();
      var mx=e.clientX-rect.left,my=e.clientY-rect.top;
      var f=e.deltaY<0?1.12:0.89;
      zmX=mx-(mx-zmX)*f; zmY=my-(my-zmY)*f; zmScale*=f; zmApply();
    }},{{passive:false}});
    vp.addEventListener("mousedown",function(e){{zmDragging=true;zmDX=e.clientX;zmDY=e.clientY;zmOX=zmX;zmOY=zmY;vp.style.cursor="grabbing";}});
    window.addEventListener("mousemove",function(e){{if(!zmDragging)return;zmX=zmOX+(e.clientX-zmDX);zmY=zmOY+(e.clientY-zmDY);zmApply();}});
    window.addEventListener("mouseup",function(){{zmDragging=false;var v=document.getElementById(sid+"_zm_vp");if(v)v.style.cursor="grab";}});
    document.addEventListener("keydown",function(e){{
      if(e.key==="Escape") window[sid+"_closeZoom"]&&window[sid+"_closeZoom"]();
      if(e.key==="ArrowLeft")  window[sid+"_zmNav"]&&window[sid+"_zmNav"](-1);
      if(e.key==="ArrowRight") window[sid+"_zmNav"]&&window[sid+"_zmNav"](1);
    }});
    document.getElementById(sid+"_zm_modal").addEventListener("click",function(e){{
      if(e.target===this) window[sid+"_closeZoom"]();
    }});
  }})();

  /* ── Init ───────────────────────────────────────── */
  if(currentWafer) buildGrid(currentWafer);
}})();
</script>
"""
