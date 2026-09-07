"""
SEM101WafermapBlock — wafermap interactif pour images SEM101 (JPEG).

Philosophie proche de SEMWafermapBlock, mais :
  - pas d'encodage base64 (les JPEG sont référencés via leur chemin)
  - 1 ligne == 1 image
  - placement sur grille (field_x, field_y)
  - affichage par wafer (select)

Frontend aligné sur SEMWafermapBlock v4 :
  - toolbar : sélecteur wafer + slider taille + boutons 3 vues
  - Vue Wafermap : SVG grille + panneau image avec switcher multi-image/field
  - Vue Grille   : thumbnails triables
  - Vue Image wafer : mosaïque positionnée sur grille physique
  - Zoom modal   : pan / wheel / +/− / reset

Pré-requis: le HTML doit pouvoir accéder aux chemins (ex: lecteur réseau monté,
serveur HTTP, ou chemins relatifs copiés à côté du report).
"""

from __future__ import annotations

import html as _h
import json
from pathlib import Path

import pandas as pd

from ..._helpers import Block, _safe_json
from ..data.data_mixin import DataMixin, DataArg


class SEM101WafermapBlock(DataMixin, Block):
    def __init__(
        self,
        data: DataArg,
        wafer_col: str = "wafer",
        x_col: str = "field_x",
        y_col: str = "field_y",
        path_col: str = "image_path",
        meta_cols: list[str] | None = None,
        num: str = "01",
        title: str = "SEM101 images par field",
        subtitle: str = "",
        height: int = 560,
    ):
        self._init_data(data)
        self.wafer_col = wafer_col
        self.x_col = x_col
        self.y_col = y_col
        self.path_col = path_col
        self.meta_cols = meta_cols  # None => auto
        self.num = num
        self.title = title
        self.subtitle = subtitle
        self.height = height
        self._id = f"sem101_{id(self)}"

    def _default_meta_cols(self, df: pd.DataFrame) -> list[str]:
        preferred = [
            "run", "recipe1", "recipe2", "nb_fields", "nb_designs",
            "target_num", "target", "diameter", "pitch", "frame",
            "zoom", "rr", "tr", "version",
        ]
        cols = [c for c in preferred if c in df.columns]
        if not cols:
            excluded = {self.wafer_col, self.x_col, self.y_col, self.path_col}
            cols = [c for c in df.columns if c not in excluded]
        return cols

    def _build_js_data(self, df: pd.DataFrame) -> str:
        """
        Structure JS :
        {
          wafer_name: {
            "x,y": {
              x, y,
              images: [{ src, label, meta }]
            }
          }
        }
        """
        meta_cols = self.meta_cols or self._default_meta_cols(df)
        wafers: dict[str, dict[str, dict]] = {}

        for _, row in df.iterrows():
            wafer = str(row.get(self.wafer_col, "unknown"))
            x = row.get(self.x_col)
            y = row.get(self.y_col)
            if x is None or y is None:
                continue
            try:
                x = int(x)
                y = int(y)
            except (TypeError, ValueError):
                continue

            img_path = row.get(self.path_col, "")
            src = str(img_path).replace("\\", "/") if img_path else ""
            if not src:
                continue

            meta = {c: _safe_json(row.get(c)) for c in meta_cols if c in row.index}
            key = f"{x},{y}"

            if wafer not in wafers:
                wafers[wafer] = {}
            if key not in wafers[wafer]:
                wafers[wafer][key] = {"x": x, "y": y, "images": []}

            wafers[wafer][key]["images"].append({
                "src": src,
                "label": Path(src).name,
                "meta": meta,
            })

        json_str = json.dumps(wafers)
        json_str = json_str.replace("</script>", "<\\/script>")
        json_str = json_str.replace("<!--", "<\\!--")
        return json_str

    def render(self, store=None) -> str:
        df = self.resolve_df(store)
        sid = self._id
        data_json = self._build_js_data(df)

        title_h = _h.escape(self.title)
        sub_h   = _h.escape(self.subtitle)
        num_h   = _h.escape(self.num)
        h       = self.height
        panel_h = h - 80

        json_tag = (
            f'<script type="application/json" id="{sid}_data">'
            f'{data_json}'
            f'</script>'
        )

        js = f"""
<script>
(function() {{
  var ALL = JSON.parse(document.getElementById("{sid}_data").textContent);
  var sid = "{sid}";

  var waferNames   = Object.keys(ALL);
  var currentWafer = waferNames[0] || null;
  var currentView  = "map";
  var thumbSize    = 1.0;

  var switcherItems = [];
  var switcherIdx   = 0;
  var _selectedRect = null;

  /* ══════════ UTILS ══════════ */
  function toFileUrl(p) {{
    if (!p) return '';
    if (/^(https?:|file:|data:)/i.test(p)) return p;
    if (/^[a-zA-Z]:[/\\\\]/.test(p)) {{
      return 'file:///' + p.replace(/\\\\/g, '/');
    }}
    if (/^\\\\\\\\/.test(p)) {{
      return 'file:' + p.replace(/\\\\/g, '/');
    }}
    return p;
  }}

  function itemLabel(item) {{
    return '(' + item.x + ',' + item.y + ') \u00b7 ' + (item.label || 'image');
  }}

  /* ══════════ META BADGES ══════════ */
  function metaBadges(meta) {{
    if (!meta) return [];
    var out = [];
    Object.keys(meta).forEach(function(k) {{
      var v = meta[k];
      if (v !== null && v !== undefined && v !== '') {{
        out.push({{ l: k, v: String(v) }});
      }}
    }});
    return out;
  }}

  function renderMetaBar(meta, filename) {{
    var footer = document.getElementById(sid + '_footer');
    if (footer) footer.style.display = 'flex';
    var file = document.getElementById(sid + '_footer_file');
    if (file) file.textContent = filename || '';
    var bar = document.getElementById(sid + '_footer_meta');
    if (!bar) return;
    bar.innerHTML = '';
    metaBadges(meta).forEach(function(b) {{
      var span = document.createElement('span');
      span.style.cssText =
        "font-family:'IBM Plex Mono',monospace;font-size:9px;" +
        "background:rgba(10,36,99,.06);border-radius:3px;padding:1px 5px;" +
        "color:#0A2463;white-space:nowrap;";
      span.textContent = b.l + ': ' + b.v;
      bar.appendChild(span);
    }});
  }}

  /* ══════════ SLIDER TAILLE ══════════ */
  window[sid + '_onSizeChange'] = function(val) {{
    thumbSize = parseFloat(val);
    var lbl = document.getElementById(sid + '_size_lbl');
    if (lbl) lbl.textContent = 'x' + thumbSize.toFixed(2).replace(/\\.?0+$/, '');
    if (currentView === 'map'    && currentWafer) drawMap(currentWafer);
    if (currentView === 'mosaic') window[sid + '_renderMosaic']();
    if (currentView === 'grid')   window[sid + '_renderGrid']();
  }};

  /* ══════════ TOGGLE VUE ══════════ */
  window[sid + '_setView'] = function(v) {{
    currentView = v;
    ['map','mosaic','grid'].forEach(function(k) {{
      var el = document.getElementById(sid + '_view_' + k);
      if (el) el.style.display = 'none';
    }});
    var target = document.getElementById(sid + '_view_' + v);
    if (target) target.style.display = (v==='map') ? 'grid' : (v==='mosaic' ? 'flex' : 'block');
    ['map','mosaic','grid'].forEach(function(k) {{
      var btn = document.getElementById(sid + '_btn_' + k);
      if (btn) {{
        btn.style.background = (k===v) ? '#0A2463' : '#fff';
        btn.style.color      = (k===v) ? '#fff'    : '#0A2463';
        btn.style.fontWeight = (k===v) ? '600'     : '400';
      }}
    }});
    if (v==='grid')   window[sid + '_renderGrid']();
    if (v==='mosaic') {{ buildMetaFilters(currentWafer); window[sid + '_renderMosaic'](); }}
  }};

  /* ══════════ DROPDOWN WAFER ══════════ */
  (function() {{
    var wsel = document.getElementById(sid + '_wsel');
    if (!wsel) return;
    waferNames.forEach(function(w) {{
      var o = document.createElement('option');
      o.value = w; o.textContent = w;
      wsel.appendChild(o);
    }});
  }})();

  /* ══════════ DRAW MAP ══════════ */
  function highlightRect(rectEl) {{
    if (_selectedRect) {{
      _selectedRect.setAttribute('stroke', 'rgba(10,36,99,0.35)');
      _selectedRect.setAttribute('stroke-width', '1');
      _selectedRect.setAttribute('fill', 'rgba(10,36,99,0.12)');
    }}
    _selectedRect = rectEl;
    rectEl.setAttribute('stroke', '#D4AF37');
    rectEl.setAttribute('stroke-width', '1.4');
    rectEl.setAttribute('fill', 'rgba(212,175,55,0.28)');
  }}

  function drawMap(waferName) {{
    var svg = document.getElementById(sid + '_map_svg');
    var g   = document.getElementById(sid + '_map_dies');
    if (!g) return;
    g.innerHTML = '';
    _selectedRect = null;

    var fields = ALL[waferName] || {{}};
    var keys   = Object.keys(fields);
    if (!keys.length) return;

    var xs = keys.map(function(k) {{ return fields[k].x; }});
    var ys = keys.map(function(k) {{ return fields[k].y; }});
    var xmin = Math.min.apply(null, xs), xmax = Math.max.apply(null, xs);
    var ymin = Math.min.apply(null, ys), ymax = Math.max.apply(null, ys);

    var baseCell = 20;
    var cell = baseCell * thumbSize;

    function tx(x) {{
      if (xmax === xmin) return 500;
      return 80 + (x - xmin) * (840 / (xmax - xmin));
    }}
    function ty(y) {{
      if (ymax === ymin) return 500;
      return 920 - (y - ymin) * (840 / (ymax - ymin));
    }}

    var ns = 'http://www.w3.org/2000/svg';
    function svgEl(name, attrs) {{
      var n = document.createElementNS(ns, name);
      Object.keys(attrs || {{}}).forEach(function(k) {{ n.setAttribute(k, attrs[k]); }});
      return n;
    }}

    /* Axes */
    if (svg) {{
      /* clear static decorations first (re-append each redraw) */
      ['_map_axis_bg','_map_axis_h','_map_axis_v'].forEach(function(id) {{
        var old = document.getElementById(sid + id);
        if (old) old.parentNode.removeChild(old);
      }});
      var axbg = svgEl('rect', {{id: sid+'_map_axis_bg', x:60,y:60,width:880,height:880,
        fill:'none',stroke:'rgba(10,36,99,.10)','stroke-width':1}});
      var axh = svgEl('line', {{id: sid+'_map_axis_h', x1:60,y1:490,x2:940,y2:490,
        stroke:'rgba(10,36,99,.06)','stroke-width':0.5,'stroke-dasharray':'3,3'}});
      var axv = svgEl('line', {{id: sid+'_map_axis_v', x1:500,y1:60,x2:500,y2:940,
        stroke:'rgba(10,36,99,.06)','stroke-width':0.5,'stroke-dasharray':'3,3'}});
      svg.insertBefore(axv, g);
      svg.insertBefore(axh, g);
      svg.insertBefore(axbg, g);
    }}

    var total = keys.length, found = 0;

    keys.forEach(function(k) {{
      var f  = fields[k];
      var cx = tx(f.x);
      var cy = ty(f.y);
      var n  = (f.images || []).length;
      if (n) found++;

      var rect = svgEl('rect', {{
        x: cx - cell/2, y: cy - cell/2, width: cell, height: cell,
        fill: n ? 'rgba(10,36,99,0.12)' : 'rgba(180,30,30,0.15)',
        stroke: n ? 'rgba(10,36,99,0.35)' : 'rgba(180,30,30,0.4)',
        'stroke-width': 1, rx: 3, ry: 3
      }});
      rect.style.cursor = n ? 'pointer' : 'default';

      if (thumbSize >= 0.8 && n > 0) {{
        var txt = svgEl('text', {{
          x: cx, y: cy + 1,
          'text-anchor': 'middle', 'dominant-baseline': 'middle',
          'font-size': Math.max(cell * 0.35, 5),
          fill: 'rgba(10,36,99,0.8)',
          'pointer-events': 'none'
        }});
        txt.textContent = n > 1 ? (String(n) + ' \u00d7') : '1';
        g.appendChild(txt);
      }}

      if (n) {{
        rect.addEventListener('click', (function(field, r) {{
          return function() {{ highlightRect(r); selectField(field); }};
        }})(f, rect));
      }}
      g.appendChild(rect);
    }});

    var badge = document.getElementById(sid + '_badge');
    if (badge) badge.textContent = found + '/' + total + ' fields';
  }}

  /* ══════════ SELECT FIELD ══════════ */
  function selectField(field) {{
    switcherItems = (field.images || []).map(function(im) {{
      return {{ x: field.x, y: field.y, src: toFileUrl(im.src), label: im.label, meta: im.meta }};
    }});
    switcherIdx = 0;
    if (!switcherItems.length) return;
    renderSwitcher(0);
    loadItemInPanel(switcherItems[0]);
  }}

  /* ══════════ SWITCHER compact (prev · N/total · select · next) ══════════ */
  var BTN_CSS =
    "font-family:'IBM Plex Mono',monospace;font-size:12px;font-weight:600;" +
    "width:24px;height:24px;border-radius:4px;cursor:pointer;border:0.5px solid rgba(10,36,99,.25);" +
    "background:#fff;color:#0A2463;display:flex;align-items:center;justify-content:center;" +
    "flex-shrink:0;padding:0;line-height:1;";

  function renderSwitcher(activeIdx) {{
    var bar = document.getElementById(sid + '_sib_bar');
    if (!bar) return;
    bar.innerHTML = '';
    if (switcherItems.length <= 1) {{ bar.style.display = 'none'; return; }}
    bar.style.display = 'flex';

    /* ‹ */
    var prev = document.createElement('button');
    prev.innerHTML = '\u2039';
    prev.style.cssText = BTN_CSS;
    prev.addEventListener('click', function() {{
      if (switcherIdx > 0) activateSwitcherItem(switcherIdx - 1);
    }});
    bar.appendChild(prev);

    /* compteur N / total */
    var counter = document.createElement('span');
    counter.id = sid + '_sw_counter';
    counter.style.cssText =
      "font-family:'IBM Plex Mono',monospace;font-size:10px;color:#0A2463;" +
      "white-space:nowrap;min-width:44px;text-align:center;flex-shrink:0;";
    counter.textContent = (activeIdx + 1) + '\u200a/\u200a' + switcherItems.length;
    bar.appendChild(counter);

    /* select dropdown */
    var sel = document.createElement('select');
    sel.id = sid + '_sw_select';
    sel.style.cssText =
      "font-family:'IBM Plex Mono',monospace;font-size:9px;color:#0A2463;" +
      "border:0.5px solid rgba(10,36,99,.25);border-radius:4px;padding:2px 4px;" +
      "background:#fff;cursor:pointer;flex:1;min-width:0;max-width:340px;";
    switcherItems.forEach(function(item, idx) {{
      var opt = document.createElement('option');
      opt.value = idx;
      opt.textContent = item.label || itemLabel(item);
      if (idx === activeIdx) opt.selected = true;
      sel.appendChild(opt);
    }});
    sel.addEventListener('change', function() {{
      activateSwitcherItem(parseInt(sel.value));
    }});
    bar.appendChild(sel);

    /* › */
    var next = document.createElement('button');
    next.innerHTML = '\u203a';
    next.style.cssText = BTN_CSS;
    next.addEventListener('click', function() {{
      if (switcherIdx < switcherItems.length - 1) activateSwitcherItem(switcherIdx + 1);
    }});
    bar.appendChild(next);
  }}

  function activateSwitcherItem(idx) {{
    switcherIdx = idx;
    /* met à jour counter + select sans tout reconstruire */
    var counter = document.getElementById(sid + '_sw_counter');
    if (counter) counter.textContent = (idx + 1) + '\u200a/\u200a' + switcherItems.length;
    var sel = document.getElementById(sid + '_sw_select');
    if (sel) sel.value = idx;
    loadItemInPanel(switcherItems[idx]);
  }}

  /* ══════════ LOAD IMAGE PANEL ══════════ */
  function loadItemInPanel(item) {{
    var lbl = document.getElementById(sid + '_img_lbl');
    if (lbl) lbl.textContent = itemLabel(item);

    var info = document.getElementById(sid + '_img_info');
    if (info) info.textContent = item.label || '';

    var btnZoom = document.getElementById(sid + '_btn_zoom');
    if (btnZoom) {{ btnZoom.style.display = 'flex'; btnZoom._zoomItem = item; }}

    var imgEl = document.getElementById(sid + '_img');
    var ph    = document.getElementById(sid + '_ph');
    if (imgEl) imgEl.style.display = 'none';
    if (ph)    ph.style.display    = 'flex';

    if (item.src) {{
      if (imgEl) {{
        imgEl.onload = function() {{
          if (ph) ph.style.display = 'none';
          imgEl.style.display = 'block';
        }};
        imgEl.onerror = function() {{
          if (ph) {{
            var s = ph.querySelector('span');
            if (s) s.textContent = 'Image inaccessible (chemin local)';
          }}
        }};
        imgEl.src = item.src;
      }}
    }} else {{
      if (ph) {{ var s2 = ph.querySelector('span'); if (s2) s2.textContent = 'Image non disponible'; }}
    }}

    renderMetaBar(item.meta, item.label || '-');
  }}

  /* ══════════ VUE GRILLE ══════════ */
  window[sid + '_renderGrid'] = function() {{
    var container = document.getElementById(sid + '_grid_container');
    var sortSel   = document.getElementById(sid + '_gsort');
    if (!container) return;
    var sortKey = sortSel ? sortSel.value : 'x';
    var fields  = ALL[currentWafer] || {{}};

    var flat = [];
    Object.values(fields).forEach(function(f) {{
      (f.images || []).forEach(function(im) {{
        flat.push({{ x: f.x, y: f.y, src: toFileUrl(im.src), label: im.label, meta: im.meta }});
      }});
    }});

    flat.sort(function(a, b) {{
      if (sortKey === 'y') return a.y !== b.y ? a.y - b.y : a.x - b.x;
      return a.x !== b.x ? a.x - b.x : a.y - b.y;
    }});

    var gbadge = document.getElementById(sid + '_gbadge');
    if (gbadge) gbadge.textContent = flat.length + ' images';
    container.innerHTML = '';

    var cardW   = Math.round(140 * thumbSize);
    var imgMaxH = Math.round(100 * thumbSize);

    flat.forEach(function(item) {{
      var card = document.createElement('div');
      card.style.cssText =
        'width:' + cardW + 'px;border:0.5px solid rgba(10,36,99,.12);border-radius:6px;' +
        'overflow:hidden;cursor:pointer;background:#fff;transition:box-shadow .15s;flex-shrink:0;';
      card.addEventListener('mouseenter', function() {{ card.style.boxShadow = '0 2px 8px rgba(10,36,99,.18)'; }});
      card.addEventListener('mouseleave', function() {{ card.style.boxShadow = 'none'; }});
      card.addEventListener('click', (function(it) {{ return function() {{ openZoomDirect(it); }}; }})(item));

      var img = document.createElement('img');
      img.src = item.src;
      img.style.cssText = 'width:100%;max-height:' + imgMaxH + 'px;object-fit:contain;display:block;background:#f5f7ff;';

      var info = document.createElement('div');
      info.style.cssText =
        "padding:4px 6px;font-family:'IBM Plex Mono',monospace;" +
        'font-size:9px;color:#0A2463;border-top:0.5px solid rgba(10,36,99,.08);';
      info.innerHTML = '<b>(' + item.x + ',' + item.y + ')</b><br>' + (item.label || '');

      card.appendChild(img);
      card.appendChild(info);
      container.appendChild(card);
    }});
  }};

  /* ══════════ FILTRES META (mosaïque) ══════════ */

  /* Collecte toutes les clés meta + valeurs uniques sur le wafer courant */
  function collectMetaKeys(waferName) {{
    var fields = ALL[waferName] || {{}};
    var keys = {{}};  /* key -> Set of values */
    Object.values(fields).forEach(function(f) {{
      (f.images || []).forEach(function(im) {{
        if (!im.meta) return;
        Object.keys(im.meta).forEach(function(k) {{
          var v = im.meta[k];
          if (v === null || v === undefined || v === '') return;
          if (!keys[k]) keys[k] = {{}};
          keys[k][String(v)] = true;
        }});
      }});
    }});
    /* Ne garder que les clés avec >= 2 valeurs distinctes (sinon inutile) */
    var result = {{}};
    Object.keys(keys).forEach(function(k) {{
      var vals = Object.keys(keys[k]).sort();
      if (vals.length >= 2) result[k] = vals;
    }});
    return result;
  }}

  /* Construit la barre de filtres dans #sid_mos_filters */
  function buildMetaFilters(waferName) {{
    var bar = document.getElementById(sid + '_mos_filters');
    if (!bar) return;
    bar.innerHTML = '';
    var metaKeys = collectMetaKeys(waferName);
    var keys = Object.keys(metaKeys);
    if (!keys.length) {{ bar.style.display = 'none'; return; }}
    bar.style.display = 'flex';

    var lbl = document.createElement('span');
    lbl.style.cssText = "font-size:10px;color:rgba(10,36,99,.5);white-space:nowrap;flex-shrink:0;";
    lbl.textContent = 'Filtre :';
    bar.appendChild(lbl);

    keys.forEach(function(k) {{
      var wrap = document.createElement('div');
      wrap.style.cssText = "display:flex;align-items:center;gap:3px;flex-shrink:0;";

      var klbl = document.createElement('span');
      klbl.style.cssText =
        "font-family:'IBM Plex Mono',monospace;font-size:9px;color:rgba(10,36,99,.6);" +
        "white-space:nowrap;";
      klbl.textContent = k + ':';
      wrap.appendChild(klbl);

      var sel = document.createElement('select');
      sel.setAttribute('data-filter-key', k);
      sel.style.cssText =
        "font-family:'IBM Plex Mono',monospace;font-size:9px;color:#0A2463;" +
        "border:0.5px solid rgba(10,36,99,.25);border-radius:4px;padding:1px 4px;" +
        "background:#fff;cursor:pointer;max-width:160px;";

      var optAll = document.createElement('option');
      optAll.value = ''; optAll.textContent = 'Tous';
      sel.appendChild(optAll);

      metaKeys[k].forEach(function(v) {{
        var opt = document.createElement('option');
        opt.value = v; opt.textContent = v;
        sel.appendChild(opt);
      }});

      sel.addEventListener('change', function() {{
        window[sid + '_renderMosaic']();
      }});
      wrap.appendChild(sel);
      bar.appendChild(wrap);
    }});

    /* Bouton reset */
    var rst = document.createElement('button');
    rst.textContent = 'Reset';
    rst.style.cssText =
      "font-family:'IBM Plex Mono',monospace;font-size:9px;padding:1px 8px;" +
      "border-radius:4px;border:0.5px solid rgba(10,36,99,.2);background:#fff;" +
      "color:rgba(10,36,99,.5);cursor:pointer;flex-shrink:0;margin-left:4px;";
    rst.addEventListener('click', function() {{
      var bar2 = document.getElementById(sid + '_mos_filters');
      if (!bar2) return;
      bar2.querySelectorAll('select[data-filter-key]').forEach(function(s) {{ s.value = ''; }});
      window[sid + '_renderMosaic']();
    }});
    bar.appendChild(rst);
  }}

  /* Lit les filtres actifs depuis la barre */
  function getActiveFilters() {{
    var bar = document.getElementById(sid + '_mos_filters');
    var active = {{}};
    if (!bar) return active;
    bar.querySelectorAll('select[data-filter-key]').forEach(function(s) {{
      if (s.value !== '') active[s.getAttribute('data-filter-key')] = s.value;
    }});
    return active;
  }}

  /* Teste si une image passe les filtres */
  function imagePassesFilters(im, filters) {{
    var keys = Object.keys(filters);
    if (!keys.length) return true;
    if (!im.meta) return false;
    for (var i = 0; i < keys.length; i++) {{
      var k = keys[i];
      if (String(im.meta[k]) !== filters[k]) return false;
    }}
    return true;
  }}

  /* ══════════ VUE MOSAÏQUE ══════════ */
  window[sid + '_renderMosaic'] = function() {{
    var svg = document.getElementById(sid + '_mos_svg');
    var g   = document.getElementById(sid + '_mos_imgs');
    var tip = document.getElementById(sid + '_mos_tip');
    if (!svg || !g) return;
    g.innerHTML = '';

    var filters = getActiveFilters();
    var fields  = ALL[currentWafer] || {{}};

    /* Pour chaque field, ne garder que la 1ère image qui passe les filtres */
    var arr = [];
    Object.values(fields).forEach(function(f) {{
      if (!f.images || !f.images.length) return;
      var matching = f.images.filter(function(im) {{ return imagePassesFilters(im, filters); }});
      if (matching.length) arr.push({{ field: f, im: matching[0] }});
    }});

    var badge = document.getElementById(sid + '_mos_badge');
    if (badge) badge.textContent = arr.length + ' / ' + Object.keys(fields).length + ' fields';
    if (!arr.length) return;

    var marg = 1.5;
    var xs = arr.map(function(e) {{ return e.field.x; }});
    var ys = arr.map(function(e) {{ return e.field.y; }});
    var xmin = Math.min.apply(null, xs) - marg;
    var xmax = Math.max.apply(null, xs) + marg;
    var ymin = Math.min.apply(null, ys) - marg;
    var ymax = Math.max.apply(null, ys) + marg;
    var dw = xmax - xmin, dh = ymax - ymin;
    var svgR = svg.getBoundingClientRect();
    var asp  = svgR.width > 0 ? svgR.width / svgR.height : 1.6;
    var vbx = xmin, vby = ymin, vbw = dw, vbh = dh;
    if (vbw / vbh < asp) {{ var ex = vbh * asp - vbw; vbx -= ex/2; vbw += ex; }}
    svg.setAttribute('viewBox', vbx + ' ' + vby + ' ' + vbw + ' ' + vbh);

    var cellSz = thumbSize * 0.85;
    var ns = 'http://www.w3.org/2000/svg';

    arr.forEach(function(e) {{
      var f       = e.field;
      var firstIm = e.im;
      var fo = document.createElementNS(ns, 'foreignObject');
      fo.setAttribute('x', f.x - cellSz/2);
      fo.setAttribute('y', f.y - cellSz/2);
      fo.setAttribute('width', cellSz);
      fo.setAttribute('height', cellSz);
      fo.style.cssText = 'cursor:pointer;overflow:hidden;';

      var div = document.createElement('div');
      div.setAttribute('xmlns', 'http://www.w3.org/1999/xhtml');
      div.style.cssText = 'width:100%;height:100%;overflow:hidden;';
      var img = document.createElement('img');
      img.src = toFileUrl(firstIm.src);
      img.style.cssText = 'width:100%;height:100%;object-fit:cover;display:block;';
      div.appendChild(img);
      fo.appendChild(div);

      fo.addEventListener('click', (function(field, im) {{
        return function() {{
          openZoomDirect({{ x: field.x, y: field.y, src: toFileUrl(im.src), label: im.label, meta: im.meta }});
        }};
      }})(f, firstIm));

      if (tip) {{
        fo.addEventListener('mouseenter', (function(field, im) {{
          return function() {{
            tip.style.display = 'block';
            var activeFilters = getActiveFilters();
            var fkeys = Object.keys(activeFilters);
            var filterInfo = fkeys.length
              ? ' <span style="opacity:.6">\u2014 ' + fkeys.map(function(k) {{ return k + '=' + activeFilters[k]; }}).join(', ') + '</span>'
              : '';
            tip.innerHTML = '<b>(' + field.x + ',' + field.y + ')</b>' + filterInfo +
              (field.images.length > 1 ? ' <span style="opacity:.7">(' + field.images.length + ' imgs)</span>' : '');
          }};
        }})(f, firstIm));
        fo.addEventListener('mousemove', function(e2) {{
          var r = svg.getBoundingClientRect();
          tip.style.left = (e2.clientX - r.left + 10) + 'px';
          tip.style.top  = (e2.clientY - r.top  - 28) + 'px';
        }});
        fo.addEventListener('mouseleave', function() {{ tip.style.display = 'none'; }});
      }}
      g.appendChild(fo);
    }});
  }};

  /* ══════════ CHANGEMENT WAFER ══════════ */
  window[sid + '_changeWafer'] = function(w) {{
    currentWafer  = w;
    switcherItems = [];
    switcherIdx   = 0;
    _selectedRect = null;

    var lbl = document.getElementById(sid + '_img_lbl');
    if (lbl) lbl.textContent = '\u2190 S\u00e9lectionner un field';
    var info = document.getElementById(sid + '_img_info');
    if (info) info.textContent = '';
    var btnZoom = document.getElementById(sid + '_btn_zoom');
    if (btnZoom) btnZoom.style.display = 'none';
    var imgEl = document.getElementById(sid + '_img');
    if (imgEl) {{ imgEl.style.display = 'none'; imgEl.src = ''; }}
    var ph = document.getElementById(sid + '_ph');
    if (ph) {{
      ph.style.display = 'flex';
      var s = ph.querySelector('span');
      if (s) s.textContent = 'Aucun field s\u00e9lectionn\u00e9';
    }}
    var footer = document.getElementById(sid + '_footer');
    if (footer) footer.style.display = 'none';
    var sibBar = document.getElementById(sid + '_sib_bar');
    if (sibBar) {{ sibBar.innerHTML = ''; sibBar.style.display = 'none'; }}

    drawMap(w);
    if (currentView === 'grid')   window[sid + '_renderGrid']();
    if (currentView === 'mosaic') {{
      buildMetaFilters(w);
      window[sid + '_renderMosaic']();
    }}
  }};

  /* ══════════ ZOOM MODAL ══════════ */
  var zmScale = 1, zmX = 0, zmY = 0;
  function zmApply() {{
    var zm = document.getElementById(sid + '_zm_img');
    if (zm) zm.style.transform = 'translate(' + zmX + 'px,' + zmY + 'px) scale(' + zmScale + ')';
  }}

  function openZoomDirect(item) {{
    var modal = document.getElementById(sid + '_modal');
    if (!modal) return;
    modal.style.display = 'flex';
    var zm  = document.getElementById(sid + '_zm_img');
    if (zm) zm.src = item.src || '';
    var lbl = document.getElementById(sid + '_zm_lbl');
    if (lbl) lbl.textContent = itemLabel(item);
    var zmMeta = document.getElementById(sid + '_zm_meta');
    if (zmMeta) {{
      zmMeta.innerHTML = '';
      metaBadges(item.meta).forEach(function(b) {{
        var span = document.createElement('span');
        span.style.cssText =
          "font-family:'IBM Plex Mono',monospace;font-size:9px;" +
          "background:rgba(255,255,255,.15);border-radius:3px;padding:1px 6px;color:#fff;white-space:nowrap;";
        span.textContent = b.l + ': ' + b.v;
        zmMeta.appendChild(span);
      }});
    }}
    if (zm) {{
      zm.onload = function() {{
        var vp = document.getElementById(sid + '_zm_vp');
        if (!vp) return;
        zmScale = Math.min(vp.offsetWidth / zm.naturalWidth, vp.offsetHeight / zm.naturalHeight, 1);
        zmX = (vp.offsetWidth  - zm.naturalWidth  * zmScale) / 2;
        zmY = (vp.offsetHeight - zm.naturalHeight * zmScale) / 2;
        zmApply();
      }};
    }}
  }}

  window[sid + '_openZoom'] = function() {{
    var btnZoom = document.getElementById(sid + '_btn_zoom');
    if (btnZoom && btnZoom._zoomItem) openZoomDirect(btnZoom._zoomItem);
  }};
  window[sid + '_closeZoom'] = function() {{
    var modal = document.getElementById(sid + '_modal');
    if (modal) modal.style.display = 'none';
  }};
  window[sid + '_zmZoom'] = function(f) {{
    var vp = document.getElementById(sid + '_zm_vp');
    if (!vp) return;
    var cx = vp.offsetWidth/2, cy = vp.offsetHeight/2;
    zmX = cx - (cx - zmX)*f; zmY = cy - (cy - zmY)*f; zmScale *= f; zmApply();
  }};
  window[sid + '_zmReset'] = function() {{
    var vp = document.getElementById(sid + '_zm_vp');
    var zm = document.getElementById(sid + '_zm_img');
    if (!vp || !zm) return;
    zmScale = Math.min(vp.offsetWidth/zm.naturalWidth, vp.offsetHeight/zm.naturalHeight, 1);
    zmX = (vp.offsetWidth  - zm.naturalWidth  * zmScale) / 2;
    zmY = (vp.offsetHeight - zm.naturalHeight * zmScale) / 2;
    zmApply();
  }};

  /* Drag + wheel modal */
  (function() {{
    var vp = document.getElementById(sid + '_zm_vp');
    if (!vp) return;
    var drag = false, lx = 0, ly = 0;
    vp.addEventListener('mousedown', function(e) {{
      drag=true; lx=e.clientX; ly=e.clientY; vp.style.cursor='grabbing'; e.preventDefault();
    }});
    window.addEventListener('mousemove', function(e) {{
      if (!drag) return;
      zmX += e.clientX-lx; zmY += e.clientY-ly; lx=e.clientX; ly=e.clientY; zmApply();
    }});
    window.addEventListener('mouseup', function() {{
      drag=false;
      var v2 = document.getElementById(sid+'_zm_vp');
      if (v2) v2.style.cursor='grab';
    }});
    vp.addEventListener('wheel', function(e) {{
      e.preventDefault();
      var f = e.deltaY < 0 ? 1.1 : 0.9;
      var r = vp.getBoundingClientRect();
      var cx = e.clientX-r.left, cy = e.clientY-r.top;
      zmX = cx-(cx-zmX)*f; zmY = cy-(cy-zmY)*f; zmScale *= f; zmApply();
    }}, {{passive: false}});
  }})();

  /* Keyboard */
  document.addEventListener('keydown', function(e) {{
    if (e.key === 'Escape') window[sid + '_closeZoom']();
    if (!switcherItems.length || currentView !== 'map') return;
    var next = switcherIdx;
    if (e.key === 'ArrowRight' || e.key === 'ArrowDown') next = Math.min(switcherIdx+1, switcherItems.length-1);
    if (e.key === 'ArrowLeft'  || e.key === 'ArrowUp')   next = Math.max(switcherIdx-1, 0);
    if (next !== switcherIdx) {{ e.preventDefault(); activateSwitcherItem(next); }}
  }});

  /* ══════════ INIT ══════════ */
  if (currentWafer) drawMap(currentWafer);

}})();
</script>
"""

        html = f"""
<div class="led-block" id="{sid}_wrap">
  <div class="led-block-header">
    <span class="led-block-num">{num_h}</span>
    <span class="led-block-title">{title_h}</span>
    <span class="led-block-sub">{sub_h}</span>
  </div>
  <div class="led-block-rule"></div>

  <!-- toolbar -->
  <div class="scatter-led-toolbar" style="margin-bottom:8px;display:flex;align-items:center;gap:6px;flex-wrap:wrap;">
    <span style="font-size:10px;color:rgba(10,36,99,.5);white-space:nowrap;">Wafer :</span>
    <select id="{sid}_wsel" onchange="{sid}_changeWafer(this.value)"
      style="font-size:10px;border:0.5px solid rgba(10,36,99,.2);border-radius:4px;
             padding:2px 6px;background:#fff;color:#0A2463;cursor:pointer;">
    </select>
    <span class="lsb-val-badge empty" id="{sid}_badge"
      style="margin-left:4px;font-family:'IBM Plex Mono',monospace;font-size:10px;color:#0A2463;"></span>

    <div style="display:flex;align-items:center;gap:5px;margin-left:8px;
                border-left:1px solid rgba(10,36,99,.1);padding-left:10px;">
      <span style="font-size:10px;color:rgba(10,36,99,.5);white-space:nowrap;">Taille :</span>
      <input type="range" id="{sid}_size_slider" min="0.5" max="10" step="0.25" value="1"
        style="width:80px;accent-color:#0A2463;"
        oninput="{sid}_onSizeChange(this.value)">
      <span id="{sid}_size_lbl"
        style="font-family:'IBM Plex Mono',monospace;font-size:10px;color:#0A2463;min-width:28px;">x1</span>
    </div>

    <div style="margin-left:auto;display:flex;gap:4px;align-items:center;">
      <button id="{sid}_btn_map"    onclick="{sid}_setView('map')"
        style="font-size:10px;padding:3px 10px;border-radius:4px;border:0.5px solid rgba(10,36,99,.3);
               cursor:pointer;background:#0A2463;color:#fff;font-weight:600;">Wafermap</button>
      <button id="{sid}_btn_mosaic" onclick="{sid}_setView('mosaic')"
        style="font-size:10px;padding:3px 10px;border-radius:4px;border:0.5px solid rgba(10,36,99,.3);
               cursor:pointer;background:#fff;color:#0A2463;font-weight:400;">Image wafer</button>
      <button id="{sid}_btn_grid"   onclick="{sid}_setView('grid')"
        style="font-size:10px;padding:3px 10px;border-radius:4px;border:0.5px solid rgba(10,36,99,.3);
               cursor:pointer;background:#fff;color:#0A2463;font-weight:400;">Grille</button>
    </div>
  </div>

  <!-- ═══ VUE WAFERMAP ═══ -->
  <div id="{sid}_view_map" style="display:grid;grid-template-columns:380px 1fr;gap:10px;height:{panel_h}px;">

    <div style="border:0.5px solid rgba(10,36,99,.15);border-radius:8px;overflow:hidden;
                background:#fafbff;display:flex;align-items:center;justify-content:center;">
      <svg id="{sid}_map_svg" viewBox="0 0 1000 1000"
           style="width:100%;height:100%;max-height:{panel_h}px;background:#fff;">
        <g id="{sid}_map_dies"></g>
      </svg>
    </div>

    <div style="border:0.5px solid rgba(10,36,99,.15);border-radius:8px;overflow:hidden;
                background:#fafbff;display:flex;flex-direction:column;">
      <!-- header -->
      <div style="padding:8px 12px;border-bottom:0.5px solid rgba(10,36,99,.08);
                  display:flex;align-items:center;gap:8px;flex-shrink:0;flex-wrap:wrap;">
        <span id="{sid}_img_lbl"
          style="font-family:'IBM Plex Mono',monospace;font-size:10px;color:#0A2463;flex:1;">
          \u2190 S\u00e9lectionner un field</span>
        <span id="{sid}_img_info"
          style="font-family:'IBM Plex Mono',monospace;font-size:9px;color:rgba(10,36,99,.5);"></span>
        <button id="{sid}_btn_zoom" onclick="{sid}_openZoom()"
          style="display:none;font-size:10px;padding:2px 8px;border-radius:4px;
                 border:0.5px solid rgba(10,36,99,.3);cursor:pointer;background:#fff;color:#0A2463;">Zoom</button>
      </div>
      <!-- switcher images du field : ‹ N/total [select] › -->
      <div id="{sid}_sib_bar"
        style="display:none;padding:4px 10px;border-bottom:0.5px solid rgba(10,36,99,.06);
               gap:6px;align-items:center;flex-shrink:0;background:rgba(10,36,99,.02);">
      </div>
      <!-- image -->
      <div style="flex:1;display:flex;align-items:center;justify-content:center;
                  overflow:hidden;position:relative;min-height:0;">
        <div id="{sid}_ph"
          style="display:flex;flex-direction:column;align-items:center;gap:6px;color:rgba(10,36,99,.3);">
          <span style="font-size:11px;">Aucun field s\u00e9lectionn\u00e9</span>
        </div>
        <img id="{sid}_img" style="display:none;max-width:100%;max-height:100%;object-fit:contain;" alt="">
      </div>
      <!-- footer méta -->
      <div id="{sid}_footer"
        style="display:none;padding:5px 10px;border-top:0.5px solid rgba(10,36,99,.08);
               flex-direction:column;gap:3px;">
        <span id="{sid}_footer_file"
          style="font-family:'IBM Plex Mono',monospace;font-size:8px;color:rgba(10,36,99,.4);"></span>
        <div id="{sid}_footer_meta" style="display:flex;flex-wrap:wrap;gap:4px;"></div>
      </div>
    </div>
  </div>

  <!-- ═══ VUE MOSAÏQUE ═══ -->
  <div id="{sid}_view_mosaic" style="display:none;flex-direction:column;gap:6px;">
    <!-- ligne infos + badge -->
    <div style="display:flex;align-items:center;gap:8px;flex-shrink:0;flex-wrap:wrap;">
      <span style="font-size:10px;color:rgba(10,36,99,.5);">
        Images positionn\u00e9es selon coordonn\u00e9es grille (field_x, field_y)</span>
      <span id="{sid}_mos_badge"
        style="font-family:'IBM Plex Mono',monospace;font-size:10px;color:#0A2463;"></span>
    </div>
    <!-- barre de filtres meta (construite dynamiquement) -->
    <div id="{sid}_mos_filters"
      style="display:none;align-items:center;gap:8px;flex-wrap:wrap;flex-shrink:0;
             padding:5px 10px;border:0.5px solid rgba(10,36,99,.12);border-radius:6px;
             background:rgba(10,36,99,.02);">
    </div>
    <div style="border:0.5px solid rgba(10,36,99,.15);border-radius:8px;overflow:hidden;
                background:#fafbff;position:relative;flex:1;min-height:0;">
      <svg id="{sid}_mos_svg" style="width:100%;height:{panel_h}px;display:block;">
        <g id="{sid}_mos_imgs"></g>
      </svg>
      <div id="{sid}_mos_tip"
        style="display:none;position:absolute;pointer-events:none;
               background:rgba(10,36,99,.85);color:#fff;font-size:9px;
               font-family:'IBM Plex Mono',monospace;padding:3px 7px;
               border-radius:4px;white-space:nowrap;z-index:10;"></div>
    </div>
  </div>

  <!-- ═══ VUE GRILLE ═══ -->
  <div id="{sid}_view_grid" style="display:none;">
    <div style="display:flex;align-items:center;gap:8px;margin-bottom:8px;">
      <span style="font-size:10px;color:rgba(10,36,99,.5);">Tri :</span>
      <select id="{sid}_gsort" onchange="{sid}_renderGrid()"
        style="font-size:10px;border:0.5px solid rgba(10,36,99,.2);border-radius:4px;
               padding:2px 6px;background:#fff;color:#0A2463;cursor:pointer;">
        <option value="x">X (field_x)</option>
        <option value="y">Y (field_y)</option>
      </select>
      <span id="{sid}_gbadge"
        style="font-family:'IBM Plex Mono',monospace;font-size:10px;color:#0A2463;"></span>
    </div>
    <div id="{sid}_grid_container"
      style="display:flex;flex-wrap:wrap;gap:8px;overflow-y:auto;max-height:{panel_h}px;padding:4px;">
    </div>
  </div>

  <!-- modale zoom -->
  <div id="{sid}_modal"
    style="display:none;position:fixed;inset:0;z-index:9999;
           background:rgba(5,10,30,.92);flex-direction:column;
           align-items:center;justify-content:center;">
    <div style="position:absolute;top:0;left:0;right:0;height:42px;
                background:rgba(10,36,99,.85);display:flex;align-items:center;
                padding:0 14px;gap:10px;z-index:2;">
      <span id="{sid}_zm_lbl"
        style="font-family:'IBM Plex Mono',monospace;font-size:11px;color:#fff;flex:1;"></span>
      <button onclick="{sid}_zmZoom(1.25)"
        style="font-size:12px;padding:2px 8px;border-radius:4px;border:none;
               background:rgba(255,255,255,.15);color:#fff;cursor:pointer;">+</button>
      <button onclick="{sid}_zmZoom(0.8)"
        style="font-size:12px;padding:2px 8px;border-radius:4px;border:none;
               background:rgba(255,255,255,.15);color:#fff;cursor:pointer;">\u2212</button>
      <button onclick="{sid}_zmReset()"
        style="font-size:10px;padding:2px 8px;border-radius:4px;border:none;
               background:rgba(255,255,255,.15);color:#fff;cursor:pointer;">Reset</button>
      <button onclick="{sid}_closeZoom()"
        style="font-size:14px;padding:2px 8px;border-radius:4px;border:none;
               background:rgba(255,255,255,.2);color:#fff;cursor:pointer;">\u2715</button>
    </div>
    <div id="{sid}_zm_meta"
      style="position:absolute;bottom:0;left:0;right:0;background:rgba(10,36,99,.75);
             padding:5px 14px;display:flex;flex-wrap:wrap;gap:5px;z-index:2;align-items:center;"></div>
    <div id="{sid}_zm_vp"
      style="position:absolute;inset:42px 0 32px 0;overflow:hidden;
             cursor:grab;display:flex;align-items:center;justify-content:center;">
      <img id="{sid}_zm_img" style="position:absolute;transform-origin:0 0;max-width:none;" alt="zoom">
    </div>
  </div>

</div>
{json_tag}
{js}
"""
        return html