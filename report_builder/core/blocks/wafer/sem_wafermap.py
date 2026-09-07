"""
SEMWafermapBlock — v10.

Col 1 — Wafermap
  • Un marqueur par die (champ de mesure SEM).
  • Position = centroïde des wafer_loc de toutes les images de ce die.
  • ← / → : champ précédent / suivant.  Clic direct possible.

Col 2 — Schéma du champ sélectionné
  • Positions physiques des spots au sein du champ (coordonnées relatives au centroïde).
  • Vignette TIF directement dans chaque spot.
  • Fond gris = enveloppe du champ + marge.
  • ↑ / ↓ : spot précédent / suivant.

Col 3 — Preview
  • Image grand format du spot actif.
  • Switcher FOV  ‹ label ›  (si plusieurs zooms au même endroit).
  • Switcher Détecteur ‹ label ›.
  • Bouton Zoom ⤢ → modal plein écran.

Vue Grille  — toutes les images du wafer en grille.
Vue Mosaïque — positions physiques sur wafer (SVG + thumbnails).
"""

from __future__ import annotations
import json
import html as _h
from collections import defaultdict
from pathlib import Path
import pandas as pd
from ..._helpers import Block, _safe_json
from ..data.data_mixin import DataMixin, DataArg


# ── Helpers image ──────────────────────────────────────────────────────────────

def read_meta_data(image_path) -> dict:
    try:
        from PIL import Image
        with Image.open(image_path) as img:
            value   = img.tag[270][0].split('\n')
            size_px = img.size[0]
        fov_x_um    = float(value[13].replace('mX: ', ''))   # µm
        fov_y_um    = float(value[14].replace('mY: ', ''))   # µm
        scale_nm_px = round((fov_x_um * 1e3) / size_px, 3)  # nm/px
        wafer_x_um  = float(value[16].replace('mX: ', ''))   # µm → /1000 = mm
        wafer_y_um  = float(value[17].replace('mY: ', ''))
        tilt        = float(value[18].replace('Stage-Angle: ', ''))
        return {
            "FOV":         [round(fov_x_um / 1000, 6), round(fov_y_um / 1000, 6)],  # mm
            "scale_nm_px": scale_nm_px,
            "size_px":     size_px,
            "wafer_loc":   [round(wafer_x_um / 1000, 4), round(wafer_y_um / 1000, 4)],  # mm
            "tilt_deg":    tilt,
        }
    except Exception as e:
        print(f"[SEM] ⚠️  Métadonnées illisibles {Path(image_path).name} : {e}")
        return {}


def convert_tif_all_frames(
    tif_path: str | Path,
    quality:  int = 40,
    max_size: tuple[int, int] = (800, 800),
) -> tuple[list[str], dict]:
    """Retourne ([b64_frame0, …], meta). Chaque frame = un détecteur."""
    try:
        from PIL import Image
    except ImportError:
        return [], {}
    import base64
    from io import BytesIO
    tif_path = Path(tif_path)
    meta     = read_meta_data(tif_path)
    frames: list[str] = []
    try:
        with Image.open(tif_path) as img:
            n = getattr(img, 'n_frames', 1)
            for i in range(n):
                try:
                    img.seek(i)
                    frame = img.copy().convert("RGB")
                    frame.thumbnail(max_size, Image.LANCZOS)
                    buf = BytesIO()
                    frame.save(buf, format="JPEG", quality=quality, optimize=True)
                    frames.append(
                        f"data:image/jpeg;base64,{base64.b64encode(buf.getvalue()).decode()}"
                    )
                except EOFError:
                    break
    except Exception as e:
        print(f"[SEM] ⚠️  {Path(tif_path).name}: {e}")
    return frames, meta


# ── Bloc ───────────────────────────────────────────────────────────────────────

class SEMWafermapBlock(DataMixin, Block):

    def __init__(
        self,
        data: DataArg,
        wafer_col:      str   = "wafername",
        x_col:          str   = "X",
        y_col:          str   = "Y",
        path_col:       str   = "path",
        die_col:        str   = "die",
        round_col:      str   = "round",
        wafer_diam_mm:  float = 200.0,
        die_w_mm:       float = 22.0,    # largeur physique d'un die (mm)
        die_h_mm:       float = 9.0,     # hauteur physique d'un die (mm)
        detector_names: list[str] | None = None,
        num:      str = "01",
        title:    str = "SEM Wafermap",
        subtitle: str = "",
        height:   int = 640,
        report_dir: str | Path | None = None,
    ):
        self._init_data(data)
        self.wafer_col      = wafer_col
        self.x_col          = x_col
        self.y_col          = y_col
        self.path_col       = path_col
        self.die_col        = die_col
        self.round_col      = round_col
        self.wafer_diam_mm  = wafer_diam_mm
        self.die_w_mm       = die_w_mm
        self.die_h_mm       = die_h_mm
        self.detector_names = detector_names or ["Det 1", "Det 2", "Det 3"]
        self.num            = num
        self.title          = title
        self.subtitle       = subtitle
        self.height         = height
        self.report_dir     = Path(report_dir) if report_dir else None
        self._id            = f"sem_{id(self)}"

    # ── Sérialisation ─────────────────────────────────────────────────────────

    def _build_js_data(self, df: pd.DataFrame) -> str:
        """
        Structure finale :
        {
          "wafer_name": [         ← liste de fields (triés par die N°)
            {
              "die": 1,
              "cx_mm": X,         ← centroïde wafer
              "cy_mm": Y,
              "spots": [          ← positions uniques dans le field
                {
                  "x_mm": X, "y_mm": Y,      ← absolu wafer
                  "dx_mm": dX, "dy_mm": dY,  ← relatif au centroïde
                  "fov_keys": ["100µm×100µm", "500µm×500µm"],
                  "fov_groups": {
                    "100µm×100µm": [
                      { "round": 1, "fov": [0.1,0.1], "detectors": ["b64...","b64..."], "meta": {...} }
                    ]
                  }
                }
              ]
            }
          ]
        }
        """
        dw = self.die_w_mm
        dh = self.die_h_mm

        # 1. Collecter toutes les images valides par wafer
        raw: dict[str, list[dict]] = defaultdict(list)
        for _, row in df.iterrows():
            wafer   = str(row.get(self.wafer_col, "unknown"))
            rnd_raw = row.get(self.round_col, None)
            rnd     = int(rnd_raw) if pd.notna(rnd_raw) else None
            path    = str(row.get(self.path_col, "")).replace("\\", "/")
            exists  = bool(row.get("exists", True))

            dets, meta = [], {}
            if exists and path.lower().endswith((".tif", ".tiff")):
                dets, meta = convert_tif_all_frames(path, quality=40, max_size=(800, 800))
                if not dets:
                    continue

            loc  = meta.get("wafer_loc", [None, None])
            x_mm = float(loc[0]) if loc[0] is not None else None
            y_mm = float(loc[1]) if loc[1] is not None else None
            if x_mm is None or y_mm is None:
                continue

            fov     = meta.get("FOV", [0.1, 0.1])
            fov_key = f"{round(fov[0]*1000):.0f}µm×{round(fov[1]*1000):.0f}µm"

            raw[wafer].append({
                "round": rnd, "x_mm": x_mm, "y_mm": y_mm,
                "fov": fov, "fov_key": fov_key,
                "detectors": dets, "meta": meta,
            })

        # 2. Par wafer : grouper par die via grille physique (arrondi au die le plus proche)
        #    Deux mesures sont dans le même die si elles tombent dans la même cellule dw×dh.
        result: dict[str, list] = defaultdict(list)

        for wafer, items in raw.items():
            # Grouper par cellule de grille
            by_die: dict[tuple[int, int], list[dict]] = defaultdict(list)
            for img in items:
                cell = (round(img["x_mm"] / dw), round(img["y_mm"] / dh))
                by_die[cell].append(img)

            die_counter = 0
            for cell, die_items in sorted(by_die.items()):
                die_counter += 1

                # Centroïde du die = centre de la cellule de grille
                cx = cell[0] * dw
                cy = cell[1] * dh

                # 3. Dans chaque die : clustering FOV-aware
                #    Deux images sont le même spot si la distance < max(fov_a, fov_b) / 2
                #    → un dezoom couvre toujours son zoom fils
                assigned = [-1] * len(die_items)
                spot_id  = 0
                for i, img_a in enumerate(die_items):
                    if assigned[i] >= 0:
                        continue
                    assigned[i] = spot_id
                    fov_a = max(img_a["fov"])
                    for j in range(i + 1, len(die_items)):
                        if assigned[j] >= 0:
                            continue
                        img_b = die_items[j]
                        fov_b = max(img_b["fov"])
                        tol   = max(fov_a, fov_b) / 2.0
                        dist  = ((img_a["x_mm"] - img_b["x_mm"])**2
                                 + (img_a["y_mm"] - img_b["y_mm"])**2) ** 0.5
                        if dist < tol:
                            assigned[j] = spot_id
                    spot_id += 1

                spots_out: list[dict] = []
                for sid in range(spot_id):
                    group = [die_items[k] for k, a in enumerate(assigned) if a == sid]
                    # Centroïde du spot = moyenne des positions (zooms fins ont le même poids)
                    rx = sum(g["x_mm"] for g in group) / len(group)
                    ry = sum(g["y_mm"] for g in group) / len(group)

                    # Trier les FOV du plus petit (zoom fort) au plus grand (dezoom)
                    fov_groups: dict[str, list] = defaultdict(list)
                    for g in group:
                        fov_groups[g["fov_key"]].append({
                            "round":     g["round"],
                            "fov":       g["fov"],
                            "detectors": g["detectors"],
                            "meta":      g["meta"],
                        })
                    fov_keys_sorted = sorted(
                        fov_groups.keys(),
                        key=lambda k: fov_groups[k][0]["fov"][0]
                    )

                    spots_out.append({
                        "x_mm":  rx, "y_mm":  ry,
                        "dx_mm": round(rx - cx, 5), "dy_mm": round(ry - cy, 5),
                        "fov_keys":   fov_keys_sorted,
                        "fov_groups": {k: fov_groups[k] for k in fov_keys_sorted},
                    })

                result[wafer].append({
                    "die":   die_counter,
                    "cx_mm": round(cx, 4),
                    "cy_mm": round(cy, 4),
                    "spots": spots_out,
                })

        for wafer in result:
            result[wafer].sort(key=lambda f: (f["cx_mm"], f["cy_mm"]))

        return json.dumps(dict(result))

    # ── Render ────────────────────────────────────────────────────────────────

    def render(self, store=None, report_dir=None) -> str:
        df        = self.resolve_df(store)
        sid       = self._id
        data_json = self._build_js_data(df)
        title_h   = _h.escape(self.title)
        sub_h     = _h.escape(self.subtitle)
        num_h     = _h.escape(self.num)
        wafer_r   = self.wafer_diam_mm / 2.0
        h         = self.height
        det_names = json.dumps(self.detector_names)
        panel_h   = h - 90
        left_w    = 300
        schema_w0 = 280

        json_tag = (
            f'<script type="application/json" id="{sid}_data">'
            f'{data_json}'
            f'</script>'
        )

        js = f"""
<script>
(function(){{
var ALL  = JSON.parse(document.getElementById("{sid}_data").textContent);
var sid  = "{sid}";
var WR   = {wafer_r};
var SM   = 50.0 / WR;    /* mm → SVG (wafer diam = 100 SVG units) */
var DET_NAMES = {det_names};
var SVG_NS = "http://www.w3.org/2000/svg";

/* ═══════════════════════════════════════════════════════ État ═══════ */
var waferNames   = Object.keys(ALL);
var curWafer     = waferNames[0] || null;
var fields       = [];    /* ALL[curWafer] */
var fieldIdx     = -1;    /* champ courant */
var spotIdx      = -1;    /* spot courant dans le champ */
var fovIdx       = 0;     /* FOV courant au spot courant */
var detIdx       = 0;     /* détecteur courant */
var curView      = "normal";
var curFovFilter = null;   /* null = tous les FOV, sinon clé FOV sélectionnée */

/* ═══════════════════════════════════ ViewBox animé (wafermap) ═══════ */
var VB0 = [-55, -55, 110, 110];
var _vb = VB0.slice(), _vbT = VB0.slice(), _raf = null;
function _animVB(t, now){{ _vbT=t.slice(); if(now){{_vb=t.slice();_applyVB();}} else if(!_raf) _raf=requestAnimationFrame(_stepVB); }}
function _stepVB(){{ var ok=true; for(var i=0;i<4;i++){{ _vb[i]+=(_vbT[i]-_vb[i])*.18; if(Math.abs(_vbT[i]-_vb[i])>.0005)ok=false; }} _applyVB(); _raf=ok?null:requestAnimationFrame(_stepVB); }}
function _applyVB(){{ var s=document.getElementById(sid+"_wsvg"); if(s) s.setAttribute("viewBox",_vb.map(function(v){{return v.toFixed(4);}}).join(" ")); }}

/* ═══════════════════════════════════ Wheel + drag wafermap ══════════ */
(function(){{
  var svg=document.getElementById(sid+"_wsvg"); if(!svg) return;
  svg.addEventListener("wheel",function(e){{
    e.preventDefault();
    var f=e.deltaY<0?.75:1.33, r=svg.getBoundingClientRect();
    var mx=_vb[0]+(e.clientX-r.left)/r.width*_vb[2];
    var my=_vb[1]+(e.clientY-r.top)/r.height*_vb[3];
    var nw=Math.max(.5,Math.min(_vb[2]*f,200));
    var nh=Math.max(.5,Math.min(_vb[3]*f,200));
    _vb[0]=mx-(e.clientX-r.left)/r.width*nw;
    _vb[1]=my-(e.clientY-r.top)/r.height*nh;
    _vb[2]=nw;_vb[3]=nh;_vbT=_vb.slice();_applyVB();
  }},{{passive:false}});
  var drag=false,lx=0,ly=0,v0=null;
  svg.addEventListener("mousedown",function(e){{if(e.button!==0)return;drag=true;lx=e.clientX;ly=e.clientY;v0=_vb.slice();svg.style.cursor="grabbing";e.preventDefault();}});
  window.addEventListener("mousemove",function(e){{if(!drag)return;var r=svg.getBoundingClientRect();_vb[0]=v0[0]-(e.clientX-lx)/r.width*v0[2];_vb[1]=v0[1]-(e.clientY-ly)/r.height*v0[3];_vbT=_vb.slice();_applyVB();}});
  window.addEventListener("mouseup",function(){{if(drag){{drag=false;var s=document.getElementById(sid+"_wsvg");if(s)s.style.cursor="";}}}});
  svg.addEventListener("dblclick",function(e){{e.preventDefault();_animVB(VB0,false);}});
}})();

/* ═══════════════════════════════════ Chargement wafer ═══════════════ */
function loadWafer(w){{
  curWafer = w; fields = ALL[w]||[];
  fieldIdx = -1; spotIdx = -1;
  drawWafermap();
  if(fields.length) goToField(0);
  var bs=document.getElementById(sid+"_wbadge");
  if(bs) bs.textContent=fields.length+" champs";
}}
window[sid+"_changeWafer"]=function(w){{loadWafer(w);}};

/* ═══════════════════════════════════ Wafermap ════════════════════════ */
var DIE_W = 22 * SM;   /* largeur die 22mm en unités SVG */
var DIE_H = 9 * SM;    /* hauteur die 9mm en unités SVG */
function drawWafermap(){{
  var g=document.getElementById(sid+"_wg"); if(!g) return; g.innerHTML="";
  fields.forEach(function(f,fi){{
    var active = fi===fieldIdx;
    var cx=f.cx_mm*SM, cy=-f.cy_mm*SM;
    /* Rectangle die 22×9mm */
    var r=document.createElementNS(SVG_NS,"rect");
    r.setAttribute("x",cx-DIE_W/2); r.setAttribute("y",cy-DIE_H/2);
    r.setAttribute("width",DIE_W); r.setAttribute("height",DIE_H);
    r.setAttribute("rx",DIE_W*0.04);
    r.setAttribute("fill", active?"rgba(212,175,55,0.25)":"rgba(10,36,99,0.08)");
    r.setAttribute("stroke", active?"#D4AF37":"rgba(10,36,99,0.45)");
    r.setAttribute("stroke-width", active?DIE_W*0.025:DIE_W*0.012);
    r.style.cursor="pointer";
    r.addEventListener("click",(function(i){{return function(){{goToField(i);}}}})(fi));
    g.appendChild(r);
    /* Label die */
    var t=document.createElementNS(SVG_NS,"text");
    t.setAttribute("x",cx); t.setAttribute("y",cy-DIE_H/2-DIE_W*0.03);
    t.setAttribute("text-anchor","middle"); t.setAttribute("font-size",DIE_H*.45);
    t.setAttribute("fill", active?"#8B6914":"rgba(10,36,99,0.4)");
    t.setAttribute("pointer-events","none");
    t.textContent="d"+f.die;
    g.appendChild(t);
  }});
}}

/* ═══════════════════════════════════ Navigation champs ══════════════ */
function goToField(fi){{
  fi = Math.max(0,Math.min(fi,fields.length-1));
  fieldIdx = fi; spotIdx = -1; fovIdx=0;
  /* Pas de zoom-in : wafermap reste au niveau global */
  drawWafermap();
  updateFieldNav();
  updateFovFilter();
  renderFieldSchema();
  if(fields[fi]&&fields[fi].spots&&fields[fi].spots.length) goToSpot(0);
}}

function updateFieldNav(){{
  var f = fieldIdx>=0 ? fields[fieldIdx] : null;
  var lbl=document.getElementById(sid+"_field_lbl");
  if(lbl) lbl.textContent = f
    ? "Die "+f.die+"  ("+f.cx_mm.toFixed(2)+", "+f.cy_mm.toFixed(2)+") mm  ["+(fieldIdx+1)+"/"+fields.length+"]"
    : "Aucun champ";
  var btnP=document.getElementById(sid+"_field_prev");
  var btnN=document.getElementById(sid+"_field_next");
  if(btnP){{ btnP.disabled=fieldIdx<=0; }}
  if(btnN){{ btnN.disabled=fieldIdx>=fields.length-1; }}
}}
window[sid+"_prevField"]=function(){{ if(fieldIdx>0) goToField(fieldIdx-1); }};
window[sid+"_nextField"]=function(){{ if(fieldIdx<fields.length-1) goToField(fieldIdx+1); }};

/* ═══════════════════════════════════ Filtre FOV (col 2) ════════════ */
function updateFovFilter(){{
  var sel=document.getElementById(sid+"_fov_filter"); if(!sel) return;
  var f=fieldIdx>=0?fields[fieldIdx]:null;
  /* Collecter tous les FOV keys du champ courant */
  var keys={{}};
  if(f) f.spots.forEach(function(s){{s.fov_keys.forEach(function(k){{keys[k]=1;}});}});
  var kList=Object.keys(keys);
  /* Reconstruire options */
  sel.innerHTML="";
  var all=document.createElement("option"); all.value=""; all.textContent="Tous les FOV";
  sel.appendChild(all);
  kList.forEach(function(k){{
    var o=document.createElement("option"); o.value=k; o.textContent=k; sel.appendChild(o);
  }});
  /* Réinitialiser filtre si clé disparue */
  if(curFovFilter && !keys[curFovFilter]) curFovFilter=null;
  sel.value=curFovFilter||"";
  var wrap=document.getElementById(sid+"_fov_filter_wrap");
  if(wrap) wrap.style.display=kList.length>1?"flex":"none";
}}
window[sid+"_setFovFilter"]=function(v){{
  curFovFilter=v||null;
  renderFieldSchema();
  if(fields[fieldIdx]&&fields[fieldIdx].spots.length) goToSpot(0);
}};

/* ═══════════════════════════════════ Navigation spots ════════════════ */
function goToSpot(si){{
  var f=fields[fieldIdx]; if(!f) return;
  si = Math.max(0,Math.min(si,f.spots.length-1));
  spotIdx=si; fovIdx=0;
  updateSpotNav();
  highlightSpot();
  renderPreview();
}}
function updateSpotNav(){{
  var f=fieldIdx>=0?fields[fieldIdx]:null;
  var n=f?f.spots.length:0;
  var btnP=document.getElementById(sid+"_spot_prev");
  var btnN=document.getElementById(sid+"_spot_next");
  var lbl =document.getElementById(sid+"_spot_lbl");
  if(btnP) btnP.disabled = spotIdx<=0;
  if(btnN) btnN.disabled = spotIdx>=n-1;
  if(lbl && f && spotIdx>=0){{
    var s=f.spots[spotIdx];
    lbl.textContent="Spot "+(spotIdx+1)+"/"+n
      +"  ("+(s.x_mm.toFixed(3))+", "+(s.y_mm.toFixed(3))+") mm";
  }}
}}
window[sid+"_prevSpot"]=function(){{ if(spotIdx>0) goToSpot(spotIdx-1); }};
window[sid+"_nextSpot"]=function(){{ if(fieldIdx>=0&&spotIdx<fields[fieldIdx].spots.length-1) goToSpot(spotIdx+1); }};

/* ═══════════════════════════════════ Schéma du champ (col 2) ════════ */
/* Vue die-centrique : rectangle 22×9mm + points de mesure relatifs au centroïde */
var DIE_HALF_W = 11;   /* mm — demi-largeur die */
var DIE_HALF_H = 4.5;  /* mm — demi-hauteur die */
function renderFieldSchema(){{
  var svgEl=document.getElementById(sid+"_schema_svg"); if(!svgEl) return;
  svgEl.innerHTML="";
  var f=fields[fieldIdx];
  if(!f) return;

  /* Filtrer les spots par FOV si filtre actif */
  var spots=curFovFilter
    ? f.spots.filter(function(s){{return s.fov_keys.indexOf(curFovFilter)>=0;}})
    : f.spots;

  /* ViewBox = die boundary 22×9mm centré à (0,0), avec petite marge */
  var pad=1.2; /* mm */
  var vbx=-DIE_HALF_W-pad, vby=-DIE_HALF_H-pad;
  var vbw=(DIE_HALF_W+pad)*2, vbh=(DIE_HALF_H+pad)*2;
  svgEl.setAttribute("viewBox",[vbx,vby,vbw,vbh].join(" "));

  /* Fond neutre */
  var bg=document.createElementNS(SVG_NS,"rect");
  bg.setAttribute("x",vbx); bg.setAttribute("y",vby);
  bg.setAttribute("width",vbw); bg.setAttribute("height",vbh);
  bg.setAttribute("fill","#f5f7ff"); bg.setAttribute("stroke","none");
  svgEl.appendChild(bg);

  /* Contour die 22×9mm */
  var die=document.createElementNS(SVG_NS,"rect");
  die.setAttribute("x",-DIE_HALF_W); die.setAttribute("y",-DIE_HALF_H);
  die.setAttribute("width",DIE_HALF_W*2); die.setAttribute("height",DIE_HALF_H*2);
  die.setAttribute("rx",0.4);
  die.setAttribute("fill","rgba(240,244,255,0.9)");
  die.setAttribute("stroke","rgba(10,36,99,0.35)"); die.setAttribute("stroke-width",0.15);
  svgEl.appendChild(die);

  /* Axes */
  function line(x1,y1,x2,y2,op){{
    var l=document.createElementNS(SVG_NS,"line");
    l.setAttribute("x1",x1);l.setAttribute("y1",y1);l.setAttribute("x2",x2);l.setAttribute("y2",y2);
    l.setAttribute("stroke","rgba(10,36,99,"+(op||0.07)+")");l.setAttribute("stroke-width",0.06);
    l.setAttribute("stroke-dasharray","0.5 0.5"); svgEl.appendChild(l);
  }}
  line(-DIE_HALF_W,0,DIE_HALF_W,0); line(0,-DIE_HALF_H,0,DIE_HALF_H);

  /* Label dimensions */
  function txt(x,y,s,anchor,fsz,op){{
    var t=document.createElementNS(SVG_NS,"text");
    t.setAttribute("x",x);t.setAttribute("y",y);t.setAttribute("text-anchor",anchor||"middle");
    t.setAttribute("font-size",fsz||0.5);t.setAttribute("fill","rgba(10,36,99,"+(op||0.3)+")");
    t.setAttribute("pointer-events","none");t.textContent=s;svgEl.appendChild(t);
  }}
  txt(0, -DIE_HALF_H-0.5, "22 mm", "middle", 0.55);
  /* Label hauteur die (rotation via transform) */
  var trot=document.createElementNS(SVG_NS,"text");
  trot.setAttribute("x",-DIE_HALF_W-0.6); trot.setAttribute("y",0);
  trot.setAttribute("text-anchor","middle");trot.setAttribute("font-size",0.55);
  trot.setAttribute("fill","rgba(10,36,99,0.3)");trot.setAttribute("pointer-events","none");
  trot.setAttribute("transform","rotate(-90,-"+(DIE_HALF_W+0.6)+",0)");
  trot.textContent="9 mm"; svgEl.appendChild(trot);

  /* Rayon des marqueurs de mesure (physique : ≈ FOV/2, avec min lisible) */
  var MR=0.35; /* mm */

  if(!spots.length){{
    txt(0,0.3,"Aucune mesure","middle",0.6,0.3);
    return;
  }}

  /* Points de mesure */
  spots.forEach(function(s,filtIdx){{
    var oi=f.spots.indexOf(s);
    var active=(oi===spotIdx);
    var fk0=curFovFilter||s.fov_keys[0];
    var fg=s.fov_groups[fk0]||[];
    var img0=fg[0];

    /* Position relative au centroïde, axe Y inversé (SVG Y vers le bas) */
    var px=s.dx_mm, py=-s.dy_mm;

    /* Cercle de mesure */
    var c=document.createElementNS(SVG_NS,"circle");
    c.setAttribute("cx",px); c.setAttribute("cy",py); c.setAttribute("r",MR);
    c.setAttribute("fill", active?"rgba(212,175,55,0.85)":"rgba(10,36,99,0.65)");
    c.setAttribute("stroke", active?"#8B6914":"rgba(10,36,99,0.2)");
    c.setAttribute("stroke-width",MR*0.2);
    c.style.cursor="pointer";
    c.addEventListener("click",(function(i){{return function(){{goToSpot(i);}}}})(oi));
    svgEl.appendChild(c);

    /* Halo actif */
    if(active){{
      var h=document.createElementNS(SVG_NS,"circle");
      h.setAttribute("cx",px);h.setAttribute("cy",py);h.setAttribute("r",MR*2);
      h.setAttribute("fill","rgba(212,175,55,0.2)");
      h.setAttribute("stroke","#D4AF37");h.setAttribute("stroke-width",MR*0.15);
      h.setAttribute("pointer-events","none");
      svgEl.insertBefore(h,c);
    }}

    /* Label index spot */
    txt(px, py-MR*1.5, (oi+1)+"", "middle", MR*0.85, active?0.8:0.35);

    /* Badge FOV si plusieurs zooms */
    if(s.fov_keys.length>1&&!curFovFilter){{
      txt(px+MR*1.1, py-MR*0.8, s.fov_keys.length+"×", "start", MR*0.7, 0.5);
    }}
  }});
}}

function highlightSpot(){{
  /* Re-render suffit, renderFieldSchema gère l'état actif */
  renderFieldSchema();
  updateSpotNav();
}}

/* ═══════════════════════════════════ Preview (col 3) ════════════════ */
function currentImg(){{
  if(fieldIdx<0||spotIdx<0) return null;
  var s=fields[fieldIdx].spots[spotIdx];
  var fk=s.fov_keys[fovIdx<s.fov_keys.length?fovIdx:0];
  var fg=s.fov_groups[fk]||[];
  return fg[0]||null;
}}

function renderPreview(){{
  var img=currentImg();
  var ph=document.getElementById(sid+"_prev_ph");
  var ie=document.getElementById(sid+"_prev_img");
  var lbl=document.getElementById(sid+"_prev_lbl");
  var meta=document.getElementById(sid+"_prev_meta");
  var btnZm=document.getElementById(sid+"_btn_zoom");

  if(!img||!img.detectors||!img.detectors.length){{
    if(ph) ph.style.display="flex"; if(ie){{ie.style.display="none";ie.src="";}}
    if(lbl) lbl.textContent="← Sélectionner un spot";
    if(btnZm) btnZm.style.display="none";
    return;
  }}
  var di=Math.min(detIdx,img.detectors.length-1);
  var b64=img.detectors[di];
  if(ph) ph.style.display="none";
  if(ie){{ ie.style.display="block"; ie.src=b64; }}

  var f=fields[fieldIdx].spots[spotIdx];
  var fk=f.fov_keys[fovIdx<f.fov_keys.length?fovIdx:0];
  if(lbl){{
    var pos=img.meta&&img.meta.wafer_loc
      ?" — ("+img.meta.wafer_loc[0].toFixed(3)+", "+img.meta.wafer_loc[1].toFixed(3)+") mm":"";
    lbl.textContent=(img.round!=null?"r"+img.round+" · ":"")
      +(DET_NAMES[di]||("Det "+(di+1)))+" · "+fk+pos;
  }}
  if(meta){{
    meta.innerHTML="";
    buildMetaTags(img.meta).forEach(function(t){{
      var s=document.createElement("span");
      s.style.cssText="font-family:'IBM Plex Mono',monospace;font-size:9px;"+
        "background:rgba(10,36,99,.06);border-radius:3px;padding:1px 5px;color:#0A2463;white-space:nowrap;";
      s.textContent=t; meta.appendChild(s);
    }});
  }}
  if(btnZm){{ btnZm.style.display="inline-flex"; btnZm._b64=b64; btnZm._meta=img.meta; btnZm._di=di; }}
  updateSwitchers();
}}

function buildMetaTags(m){{
  if(!m) return [];
  var out=[];
  if(m.scale_nm_px)  out.push("Scale: "+m.scale_nm_px+" nm/px");
  if(m.FOV)          out.push("FOV: "+round1(m.FOV[0]*1000)+"×"+round1(m.FOV[1]*1000)+" µm");
  if(m.size_px)      out.push(m.size_px+" px");
  if(m.wafer_loc)    out.push("("+m.wafer_loc[0].toFixed(3)+", "+m.wafer_loc[1].toFixed(3)+") mm");
  if(m.tilt_deg!==undefined) out.push("Tilt "+m.tilt_deg+"°");
  return out;
}}
function round1(v){{ return Math.round(v); }}

/* ═══════════════════════════════════ Switchers FOV + Détecteur ══════ */
function updateSwitchers(){{
  if(fieldIdx<0||spotIdx<0){{ _hideSW("fov");_hideSW("det");return; }}
  var s=fields[fieldIdx].spots[spotIdx];
  var img=currentImg();

  /* FOV */
  if(s.fov_keys.length>1){{
    _showSW("fov",s.fov_keys,fovIdx,function(i){{fovIdx=i;renderFieldSchema();renderPreview();}},function(v){{return v;}});
  }} else _hideSW("fov");

  /* Détecteurs */
  var nd=img&&img.detectors?img.detectors.length:0;
  if(nd>1){{
    var dlist=Array.from({{length:nd}},function(_,i){{return i;}});
    _showSW("det",dlist,detIdx,function(i){{detIdx=i;renderFieldSchema();renderPreview();}},function(i){{return DET_NAMES[i]||("Det "+(i+1));}});
  }} else _hideSW("det");
}}

var SW_BTN="font-family:'IBM Plex Mono',monospace;font-size:9px;padding:1px 6px;"+
  "border-radius:3px;border:0.5px solid rgba(10,36,99,.25);cursor:pointer;"+
  "background:#fff;color:#0A2463;";
function _showSW(key,list,ai,onSet,labelFn){{
  var w=document.getElementById(sid+"_sw_"+key); if(!w) return; w.style.display="flex";
  var lbl=document.getElementById(sid+"_sw_"+key+"_lbl");
  var prev=document.getElementById(sid+"_sw_"+key+"_prev");
  var next=document.getElementById(sid+"_sw_"+key+"_next");
  if(lbl) lbl.textContent=labelFn(list[ai]);
  if(prev){{prev.disabled=(ai<=0);prev.onclick=function(){{onSet(Math.max(0,ai-1));}};}}
  if(next){{next.disabled=(ai>=list.length-1);next.onclick=function(){{onSet(Math.min(list.length-1,ai+1));}};}}
}}
function _hideSW(key){{var w=document.getElementById(sid+"_sw_"+key);if(w)w.style.display="none";}}

/* ═══════════════════════════════════ Vue Grille ════════════════════ */
function renderGridView(){{
  var c=document.getElementById(sid+"_grid_c"); if(!c) return;
  var sort=document.getElementById(sid+"_gsort");
  var sk=sort?sort.value:"die";
  var flt_fov=null; // could add filter
  c.innerHTML="";
  var flat=[];
  fields.forEach(function(f){{
    f.spots.forEach(function(s,si){{
      s.fov_keys.forEach(function(fk){{
        var fg=s.fov_groups[fk]||[];
        fg.forEach(function(img){{
          img.detectors.forEach(function(b64,di){{
            flat.push({{die:f.die,si:si,fk:fk,di:di,b64:b64,meta:img.meta,round:img.round,
                        x:s.x_mm,y:s.y_mm}});
          }});
        }});
      }});
    }});
  }});
  flat.sort(function(a,b){{
    if(sk==="x") return a.x-b.x;
    if(sk==="y") return a.y-b.y;
    return a.die!==b.die?a.die-b.die:(a.round||0)-(b.round||0);
  }});
  var badge=document.getElementById(sid+"_gbadge");
  if(badge) badge.textContent=flat.length+" images";
  flat.forEach(function(item){{
    var card=document.createElement("div");
    card.style.cssText="width:130px;flex-shrink:0;border:0.5px solid rgba(10,36,99,.12);"+
      "border-radius:6px;overflow:hidden;cursor:pointer;background:#fff;transition:box-shadow .15s;";
    card.addEventListener("mouseenter",function(){{card.style.boxShadow="0 2px 8px rgba(10,36,99,.18)";}});
    card.addEventListener("mouseleave",function(){{card.style.boxShadow="";}});
    card.addEventListener("click",(function(it){{return function(){{openModal(it.b64,it.meta,it.di);}};}})(item));
    var ie=document.createElement("img"); ie.src=item.b64;
    ie.style.cssText="width:100%;height:90px;object-fit:contain;display:block;background:#f5f7ff;";
    var info=document.createElement("div");
    info.style.cssText="padding:3px 5px;font-family:'IBM Plex Mono',monospace;font-size:7.5px;"+
      "color:#0A2463;border-top:0.5px solid rgba(10,36,99,.08);line-height:1.4;";
    info.innerHTML="<b>d"+item.die+"</b>"+(item.round!=null?" r"+item.round:"")
      +"<br>"+(DET_NAMES[item.di]||("Det "+(item.di+1)))+"<br>"+item.fk;
    card.appendChild(ie); card.appendChild(info); c.appendChild(card);
  }});
}}
window[sid+"_renderGrid"]=renderGridView;

/* ═══════════════════════════════════ Vue Mosaïque ════════════════════ */
function renderMosaic(){{
  var svg=document.getElementById(sid+"_mos_svg");
  var g=document.getElementById(sid+"_mos_g");
  var tip=document.getElementById(sid+"_mos_tip");
  if(!svg||!g) return; g.innerHTML="";
  var items=[];
  fields.forEach(function(f){{
    f.spots.forEach(function(s){{
      var fk=s.fov_keys[0]; var fg=s.fov_groups[fk]||[];
      var img=fg[0]; if(!img||!img.detectors.length) return;
      var b64=img.detectors[Math.min(detIdx,img.detectors.length-1)];
      items.push({{b64:b64,x:s.x_mm,y:s.y_mm,fov:img.fov||[0.1,0.1],die:f.die,round:img.round,fk:fk}});
    }});
  }});
  var badge=document.getElementById(sid+"_mos_badge");
  if(badge) badge.textContent=items.length+" spots";
  if(!items.length) return;
  var xs=items.map(function(e){{return e.x;}}), ys=items.map(function(e){{return e.y;}});
  var fws=items.map(function(e){{return e.fov[0];}}), fhs=items.map(function(e){{return e.fov[1];}});
  var xmn=Math.min.apply(null,xs.map(function(x,k){{return x-fws[k]/2;}}));
  var xmx=Math.max.apply(null,xs.map(function(x,k){{return x+fws[k]/2;}}));
  var ymn=Math.min.apply(null,ys.map(function(y,k){{return -y-fhs[k]/2;}}));
  var ymx=Math.max.apply(null,ys.map(function(y,k){{return -y+fhs[k]/2;}}));
  var dw=Math.max(xmx-xmn,.01),dh=Math.max(ymx-ymn,.01),p=Math.max(dw,dh)*.15+.001;
  var vbx=xmn-p,vby=ymn-p,vbw=dw+2*p,vbh=dh+2*p;
  var r=svg.getBoundingClientRect();
  if(r.width>0&&vbw/vbh<r.width/r.height){{var ex=vbh*(r.width/r.height)-vbw;vbx-=ex/2;vbw+=ex;}}
  svg.setAttribute("viewBox",[vbx,vby,vbw,vbh].join(" "));
  /* Wafer circle */
  var wc=document.getElementById(sid+"_mos_wc"),wf=document.getElementById(sid+"_mos_wf");
  if(wc){{wc.setAttribute("cx",0);wc.setAttribute("cy",0);wc.setAttribute("r",WR);}}
  if(wf){{wf.setAttribute("x1",-WR*.44);wf.setAttribute("y1",WR*.92);wf.setAttribute("x2",WR*.44);wf.setAttribute("y2",WR*.92);}}
  items.forEach(function(e){{
    var fw=e.fov[0],fh=e.fov[1];
    var cx=e.x,cy=-e.y;
    var fo=document.createElementNS(SVG_NS,"foreignObject");
    fo.setAttribute("x",cx-fw/2);fo.setAttribute("y",cy-fh/2);fo.setAttribute("width",fw);fo.setAttribute("height",fh);
    fo.style.cssText="cursor:pointer;overflow:hidden;";
    var div=document.createElement("div");div.setAttribute("xmlns","http://www.w3.org/1999/xhtml");div.style.cssText="width:100%;height:100%;";
    var ie=document.createElement("img");ie.src=e.b64;ie.style.cssText="width:100%;height:100%;object-fit:cover;display:block;";
    div.appendChild(ie);fo.appendChild(div);
    fo.addEventListener("click",(function(b,m,di2){{return function(){{openModal(b,m,di2);}};}})(e.b64,null,detIdx));
    if(tip){{
      fo.addEventListener("mouseenter",(function(ee){{return function(){{tip.style.display="block";tip.innerHTML="<b>Die "+ee.die+"</b>"+(ee.round!=null?" r"+ee.round:"")+" · "+ee.fk;}};}})(e));
      fo.addEventListener("mousemove",function(ev){{var rr=svg.getBoundingClientRect();tip.style.left=(ev.clientX-rr.left+10)+"px";tip.style.top=(ev.clientY-rr.top-26)+"px";}});
      fo.addEventListener("mouseleave",function(){{tip.style.display="none";}});
    }}
    g.appendChild(fo);
  }});
}}

/* ═══════════════════════════════════ Vue switch ════════════════════ */
window[sid+"_setView"]=function(v){{
  curView=v;
  ["normal","grid","mosaic"].forEach(function(k){{
    var el=document.getElementById(sid+"_view_"+k);
    if(el) el.style.display="none";
    var btn=document.getElementById(sid+"_btn_"+k);
    if(btn){{btn.style.background=k===v?"#0A2463":"#fff";btn.style.color=k===v?"#fff":"#0A2463";}}
  }});
  var el=document.getElementById(sid+"_view_"+v);
  if(el) el.style.display=v==="normal"?"flex":"block";
  if(v==="grid")    renderGridView();
  if(v==="mosaic")  renderMosaic();
}};

/* ═══════════════════════════════════ Modal zoom ════════════════════ */
var zmS=1,zmX=0,zmY=0;
function zmApply(){{var zm=document.getElementById(sid+"_zm_img");if(zm)zm.style.transform="translate("+zmX+"px,"+zmY+"px) scale("+zmS+")";}}
function openModal(b64,meta,di){{
  var modal=document.getElementById(sid+"_modal");if(!modal) return;modal.style.display="flex";
  var zm=document.getElementById(sid+"_zm_img"); if(zm) zm.src=b64||"";
  var lbl=document.getElementById(sid+"_zm_lbl");
  if(lbl) lbl.textContent=(DET_NAMES[di]||("Det "+(di+1)))+(meta&&meta.wafer_loc?" — ("+meta.wafer_loc[0].toFixed(3)+", "+meta.wafer_loc[1].toFixed(3)+") mm":"");
  var zmMeta=document.getElementById(sid+"_zm_meta");
  if(zmMeta){{zmMeta.innerHTML="";buildMetaTags(meta).forEach(function(t){{var s=document.createElement("span");s.style.cssText="font-family:'IBM Plex Mono',monospace;font-size:9px;background:rgba(255,255,255,.15);border-radius:3px;padding:1px 6px;color:#fff;white-space:nowrap;";s.textContent=t;zmMeta.appendChild(s);}});}}
  if(zm){{zm.onload=function(){{var vp=document.getElementById(sid+"_zm_vp");if(!vp)return;zmS=Math.min(vp.offsetWidth/zm.naturalWidth,vp.offsetHeight/zm.naturalHeight,1);zmX=(vp.offsetWidth-zm.naturalWidth*zmS)/2;zmY=(vp.offsetHeight-zm.naturalHeight*zmS)/2;zmApply();}};}}
}}
window[sid+"_openZoom"]=function(){{var btn=document.getElementById(sid+"_btn_zoom");if(btn&&btn._b64) openModal(btn._b64,btn._meta,btn._di);}};
window[sid+"_closeZoom"]=function(){{var m=document.getElementById(sid+"_modal");if(m)m.style.display="none";}};
window[sid+"_zmZoom"]=function(f){{var vp=document.getElementById(sid+"_zm_vp");if(!vp)return;var cx=vp.offsetWidth/2,cy=vp.offsetHeight/2;zmX=cx-(cx-zmX)*f;zmY=cy-(cy-zmY)*f;zmS*=f;zmApply();}};
window[sid+"_zmReset"]=function(){{var vp=document.getElementById(sid+"_zm_vp"),zm=document.getElementById(sid+"_zm_img");if(!vp||!zm)return;zmS=Math.min(vp.offsetWidth/zm.naturalWidth,vp.offsetHeight/zm.naturalHeight,1);zmX=(vp.offsetWidth-zm.naturalWidth*zmS)/2;zmY=(vp.offsetHeight-zm.naturalHeight*zmS)/2;zmApply();}};
(function(){{
  var vp=document.getElementById(sid+"_zm_vp");if(!vp)return;
  var drag=false,lx=0,ly=0;
  vp.addEventListener("mousedown",function(e){{drag=true;lx=e.clientX;ly=e.clientY;vp.style.cursor="grabbing";e.preventDefault();}});
  window.addEventListener("mousemove",function(e){{if(!drag)return;zmX+=e.clientX-lx;zmY+=e.clientY-ly;lx=e.clientX;ly=e.clientY;zmApply();}});
  window.addEventListener("mouseup",function(){{if(drag){{drag=false;var v=document.getElementById(sid+"_zm_vp");if(v)v.style.cursor="grab";}}}});
  vp.addEventListener("wheel",function(e){{e.preventDefault();var f=e.deltaY<0?1.1:.9,rr=vp.getBoundingClientRect();zmX=(e.clientX-rr.left)-(e.clientX-rr.left-zmX)*f;zmY=(e.clientY-rr.top)-(e.clientY-rr.top-zmY)*f;zmS*=f;zmApply();}},{{passive:false}});
}})();

/* ═══════════════════════════════════ Splitter ══════════════════════ */
(function(){{
  var spl=document.getElementById(sid+"_spl");
  var sp=document.getElementById(sid+"_schema_panel");
  var ra=document.getElementById(sid+"_right_area");
  if(!spl||!sp||!ra)return;
  var drag=false,sx=0,sw=0;
  spl.addEventListener("mousedown",function(e){{drag=true;sx=e.clientX;sw=sp.offsetWidth;document.body.style.userSelect="none";document.body.style.cursor="col-resize";e.preventDefault();}});
  window.addEventListener("mousemove",function(e){{if(!drag)return;sp.style.width=Math.max(180,Math.min(sw+(e.clientX-sx),ra.offsetWidth-200))+"px";}});
  window.addEventListener("mouseup",function(){{if(drag){{drag=false;document.body.style.userSelect="";document.body.style.cursor="";}}}});
}})();

/* ═══════════════════════════════════ Clavier ═══════════════════════ */
document.addEventListener("keydown",function(e){{
  if(e.key==="Escape"){{ window[sid+"_closeZoom"](); return; }}
  var modal=document.getElementById(sid+"_modal");
  if(modal&&modal.style.display!=="none") return;
  if(e.key==="ArrowLeft")  {{ e.preventDefault(); window[sid+"_prevField"](); }}
  else if(e.key==="ArrowRight") {{ e.preventDefault(); window[sid+"_nextField"](); }}
  else if(e.key==="ArrowUp")   {{ e.preventDefault(); window[sid+"_prevSpot"](); }}
  else if(e.key==="ArrowDown") {{ e.preventDefault(); window[sid+"_nextSpot"](); }}
}});

/* ═══════════════════════════════════ Init ══════════════════════════ */
(function(){{
  var wsel=document.getElementById(sid+"_wsel");
  if(wsel){{ waferNames.forEach(function(w){{var o=document.createElement("option");o.value=w;o.textContent=w;wsel.appendChild(o);}});}}
  if(curWafer) loadWafer(curWafer);
}})();

}})();
</script>
"""

        btn_sw = ("font-family:'IBM Plex Mono',monospace;font-size:9px;padding:1px 6px;"
                  "border-radius:3px;border:0.5px solid rgba(10,36,99,.25);"
                  "cursor:pointer;background:#fff;color:#0A2463;")
        lbl_sw = ("font-family:'IBM Plex Mono',monospace;font-size:9px;"
                  "color:#0A2463;min-width:80px;text-align:center;")

        def sw(key: str, label: str) -> str:
            return f"""
    <div id="{sid}_sw_{key}"
      style="display:none;align-items:center;gap:3px;
             border-left:1px solid rgba(10,36,99,.1);padding-left:8px;">
      <span style="font-size:9px;color:rgba(10,36,99,.45);">{label}</span>
      <button id="{sid}_sw_{key}_prev" style="{btn_sw}">‹</button>
      <span   id="{sid}_sw_{key}_lbl" style="{lbl_sw}">—</span>
      <button id="{sid}_sw_{key}_next" style="{btn_sw}">›</button>
    </div>"""

        nav_btn = ("font-size:10px;padding:2px 9px;border-radius:4px;"
                   "border:0.5px solid rgba(10,36,99,.25);cursor:pointer;"
                   "background:#fff;color:#0A2463;font-family:'IBM Plex Mono',monospace;")

        html = f"""
<div class="led-block" id="{sid}_wrap">
  <div class="led-block-header">
    <span class="led-block-num">{num_h}</span>
    <span class="led-block-title">{title_h}</span>
    <span class="led-block-sub">{sub_h}</span>
  </div>
  <div class="led-block-rule"></div>

  <!-- ── Toolbar globale ── -->
  <div style="display:flex;align-items:center;gap:6px;margin-bottom:6px;flex-wrap:wrap;">
    <span style="font-size:10px;color:rgba(10,36,99,.45);">Wafer</span>
    <select id="{sid}_wsel" onchange="{sid}_changeWafer(this.value)"
      style="font-size:10px;border:0.5px solid rgba(10,36,99,.2);border-radius:4px;
             padding:2px 6px;background:#fff;color:#0A2463;cursor:pointer;"></select>
    <span id="{sid}_wbadge"
      style="font-family:'IBM Plex Mono',monospace;font-size:10px;color:#0A2463;"></span>
    <div style="margin-left:auto;display:flex;gap:4px;">
      <button id="{sid}_btn_normal" onclick="{sid}_setView('normal')"
        style="font-size:10px;padding:3px 10px;border-radius:4px;border:0.5px solid rgba(10,36,99,.3);
               cursor:pointer;background:#0A2463;color:#fff;">Normal</button>
      <button id="{sid}_btn_grid" onclick="{sid}_setView('grid')"
        style="font-size:10px;padding:3px 10px;border-radius:4px;border:0.5px solid rgba(10,36,99,.3);
               cursor:pointer;background:#fff;color:#0A2463;">Grille</button>
      <button id="{sid}_btn_mosaic" onclick="{sid}_setView('mosaic')"
        style="font-size:10px;padding:3px 10px;border-radius:4px;border:0.5px solid rgba(10,36,99,.3);
               cursor:pointer;background:#fff;color:#0A2463;">Mosaïque</button>
    </div>
  </div>

  <!-- ══════════ VUE NORMALE ══════════ -->
  <div id="{sid}_view_normal"
    style="display:flex;gap:0;height:{panel_h}px;overflow:hidden;">

    <!-- Col 1 : wafermap -->
    <div style="width:{left_w}px;flex-shrink:0;display:flex;flex-direction:column;
                gap:4px;padding-right:10px;box-sizing:border-box;">
      <!-- nav champ -->
      <div style="display:flex;align-items:center;gap:4px;flex-shrink:0;">
        <button id="{sid}_field_prev" onclick="{sid}_prevField()" disabled
          style="{nav_btn}">←</button>
        <span style="font-size:9px;color:rgba(10,36,99,.4);">← →  champ</span>
        <button id="{sid}_field_next" onclick="{sid}_nextField()" disabled
          style="{nav_btn}">→</button>
        <span style="font-size:8px;color:rgba(10,36,99,.25);margin-left:2px;">↑↓ spot</span>
      </div>
      <!-- SVG wafermap -->
      <div style="flex:1;border:0.5px solid rgba(10,36,99,.15);border-radius:8px;
                  overflow:hidden;background:#fafbff;min-height:0;">
        <svg id="{sid}_wsvg" viewBox="-55 -55 110 110"
             style="width:100%;height:100%;display:block;cursor:crosshair;">
          <circle cx="0" cy="0" r="50"
            fill="rgba(240,244,255,0.7)" stroke="rgba(10,36,99,0.2)" stroke-width="0.5"/>
          <line x1="-22" y1="46" x2="22" y2="46"
            stroke="rgba(10,36,99,0.5)" stroke-width="0.8"/>
          <line x1="-52" y1="0" x2="52" y2="0"
            stroke="rgba(10,36,99,.06)" stroke-width="0.3" stroke-dasharray="2 2"/>
          <line x1="0" y1="-52" x2="0" y2="52"
            stroke="rgba(10,36,99,.06)" stroke-width="0.3" stroke-dasharray="2 2"/>
          <g id="{sid}_wg"></g>
        </svg>
      </div>
      <!-- info champ -->
      <div style="flex-shrink:0;">
        <div id="{sid}_field_lbl"
          style="font-family:'IBM Plex Mono',monospace;font-size:9px;
                 color:rgba(10,36,99,.55);overflow:hidden;text-overflow:ellipsis;white-space:nowrap;">
          —</div>
      </div>
    </div>

    <!-- Zone droite -->
    <div id="{sid}_right_area"
      style="flex:1;display:flex;min-width:0;overflow:hidden;">

      <!-- Col 2 : schéma du champ -->
      <div id="{sid}_schema_panel"
        style="width:{schema_w0}px;min-width:180px;flex-shrink:0;
               display:flex;flex-direction:column;
               border:0.5px solid rgba(10,36,99,.15);border-radius:8px;
               background:#fafbff;overflow:hidden;">
        <!-- header schéma + nav spot -->
        <div style="padding:4px 8px;border-bottom:0.5px solid rgba(10,36,99,.08);
                    flex-shrink:0;display:flex;align-items:center;gap:4px;flex-wrap:wrap;">
          <span style="font-family:'IBM Plex Mono',monospace;font-size:9px;
                       color:rgba(10,36,99,.4);flex:1;">Positions dans le champ</span>
          <button id="{sid}_spot_prev" onclick="{sid}_prevSpot()" disabled
            style="{nav_btn}font-size:9px;padding:1px 6px;">↑</button>
          <button id="{sid}_spot_next" onclick="{sid}_nextSpot()" disabled
            style="{nav_btn}font-size:9px;padding:1px 6px;">↓</button>
        </div>
        <!-- filtre FOV -->
        <div id="{sid}_fov_filter_wrap"
          style="display:none;align-items:center;gap:4px;padding:3px 8px;
                 border-bottom:0.5px solid rgba(10,36,99,.06);flex-shrink:0;">
          <span style="font-family:'IBM Plex Mono',monospace;font-size:8.5px;
                       color:rgba(10,36,99,.4);">FOV</span>
          <select id="{sid}_fov_filter"
            onchange="{sid}_setFovFilter(this.value)"
            style="font-size:9px;border:0.5px solid rgba(10,36,99,.2);border-radius:3px;
                   padding:1px 4px;background:#fff;color:#0A2463;cursor:pointer;flex:1;">
            <option value="">Tous les FOV</option>
          </select>
        </div>
        <!-- SVG schéma -->
        <div style="flex:1;overflow:hidden;min-height:0;">
          <svg id="{sid}_schema_svg"
            style="width:100%;height:100%;display:block;cursor:pointer;"></svg>
        </div>
        <!-- info spot -->
        <div style="flex-shrink:0;padding:3px 8px;
                    border-top:0.5px solid rgba(10,36,99,.06);">
          <span id="{sid}_spot_lbl"
            style="font-family:'IBM Plex Mono',monospace;font-size:8.5px;
                   color:rgba(10,36,99,.45);white-space:nowrap;overflow:hidden;
                   text-overflow:ellipsis;display:block;"></span>
        </div>
      </div>

      <!-- Splitter -->
      <div id="{sid}_spl"
        style="width:5px;flex-shrink:0;cursor:col-resize;
               background:rgba(10,36,99,.05);display:flex;align-items:center;justify-content:center;"
        onmouseenter="this.style.background='rgba(10,36,99,.18)'"
        onmouseleave="this.style.background='rgba(10,36,99,.05)'">
        <div style="display:flex;flex-direction:column;gap:2px;pointer-events:none;">
          <div style="width:2px;height:2px;border-radius:50%;background:rgba(10,36,99,.35);"></div>
          <div style="width:2px;height:2px;border-radius:50%;background:rgba(10,36,99,.35);"></div>
          <div style="width:2px;height:2px;border-radius:50%;background:rgba(10,36,99,.35);"></div>
        </div>
      </div>

      <!-- Col 3 : preview -->
      <div style="flex:1;min-width:150px;border:0.5px solid rgba(10,36,99,.15);
                  border-radius:8px;background:#fafbff;display:flex;flex-direction:column;overflow:hidden;">
        <!-- header preview -->
        <div style="padding:5px 10px;border-bottom:0.5px solid rgba(10,36,99,.08);
                    display:flex;align-items:center;gap:6px;flex-shrink:0;flex-wrap:wrap;">
          <span id="{sid}_prev_lbl"
            style="font-family:'IBM Plex Mono',monospace;font-size:9.5px;color:#0A2463;flex:1;">
            ← Sélectionner un spot</span>
          <button id="{sid}_btn_zoom" onclick="{sid}_openZoom()"
            style="display:none;{nav_btn}">Zoom ⤢</button>
        </div>
        <!-- switchers -->
        <div style="padding:4px 10px;border-bottom:0.5px solid rgba(10,36,99,.06);
                    display:flex;align-items:center;gap:6px;flex-wrap:wrap;flex-shrink:0;min-height:30px;">
          {sw("fov", "FOV")}
          {sw("det", "Détecteur")}
        </div>
        <!-- image -->
        <div style="flex:1;display:flex;align-items:center;justify-content:center;
                    overflow:hidden;min-height:0;">
          <div id="{sid}_prev_ph"
            style="color:rgba(10,36,99,.3);font-size:11px;text-align:center;padding:10px;">
            Aucune image</div>
          <img id="{sid}_prev_img"
            style="display:none;max-width:100%;max-height:100%;object-fit:contain;" alt="">
        </div>
        <!-- méta -->
        <div id="{sid}_prev_meta"
          style="display:flex;flex-wrap:wrap;gap:4px;padding:5px 10px;
                 border-top:0.5px solid rgba(10,36,99,.06);flex-shrink:0;min-height:22px;"></div>
      </div>
    </div>
  </div><!-- /view_normal -->

  <!-- ══════════ VUE GRILLE ══════════ -->
  <div id="{sid}_view_grid" style="display:none;">
    <div style="display:flex;align-items:center;gap:8px;margin-bottom:6px;">
      <span style="font-size:10px;color:rgba(10,36,99,.4);">Tri :</span>
      <select id="{sid}_gsort" onchange="{sid}_renderGrid()"
        style="font-size:10px;border:0.5px solid rgba(10,36,99,.2);border-radius:4px;
               padding:2px 6px;background:#fff;color:#0A2463;cursor:pointer;">
        <option value="die">Die N°</option>
        <option value="x">X mm</option>
        <option value="y">Y mm</option>
      </select>
      <span id="{sid}_gbadge"
        style="font-family:'IBM Plex Mono',monospace;font-size:10px;color:#0A2463;"></span>
    </div>
    <div id="{sid}_grid_c"
      style="display:flex;flex-wrap:wrap;gap:7px;overflow-y:auto;
             max-height:{panel_h}px;padding:2px;"></div>
  </div>

  <!-- ══════════ VUE MOSAÏQUE ══════════ -->
  <div id="{sid}_view_mosaic" style="display:none;">
    <div style="display:flex;align-items:center;gap:8px;margin-bottom:6px;">
      <span style="font-size:10px;color:rgba(10,36,99,.4);">Positions physiques (mm)</span>
      <span id="{sid}_mos_badge"
        style="font-family:'IBM Plex Mono',monospace;font-size:10px;color:#0A2463;"></span>
    </div>
    <div style="border:0.5px solid rgba(10,36,99,.15);border-radius:8px;
                overflow:hidden;background:#fafbff;position:relative;">
      <svg id="{sid}_mos_svg" style="width:100%;height:{panel_h}px;display:block;">
        <circle id="{sid}_mos_wc" fill="rgba(240,244,255,0.6)"
          stroke="rgba(10,36,99,0.2)" stroke-width="0.5"/>
        <line id="{sid}_mos_wf" stroke="rgba(10,36,99,0.4)" stroke-width="0.8"/>
        <g id="{sid}_mos_g"></g>
      </svg>
      <div id="{sid}_mos_tip"
        style="display:none;position:absolute;pointer-events:none;
               background:rgba(10,36,99,.85);color:#fff;font-size:9px;
               font-family:'IBM Plex Mono',monospace;padding:3px 7px;
               border-radius:4px;white-space:nowrap;z-index:10;"></div>
    </div>
  </div>

  <!-- ══════════ Modal zoom ══════════ -->
  <div id="{sid}_modal"
    style="display:none;position:fixed;inset:0;z-index:9999;
           background:rgba(5,10,30,.92);flex-direction:column;">
    <div style="height:42px;background:rgba(10,36,99,.85);display:flex;align-items:center;
                padding:0 14px;gap:10px;flex-shrink:0;">
      <span id="{sid}_zm_lbl"
        style="font-family:'IBM Plex Mono',monospace;font-size:11px;color:#fff;flex:1;"></span>
      <button onclick="{sid}_zmZoom(1.25)"
        style="font-size:12px;padding:2px 8px;border-radius:4px;border:none;background:rgba(255,255,255,.15);color:#fff;cursor:pointer;">+</button>
      <button onclick="{sid}_zmZoom(0.8)"
        style="font-size:12px;padding:2px 8px;border-radius:4px;border:none;background:rgba(255,255,255,.15);color:#fff;cursor:pointer;">−</button>
      <button onclick="{sid}_zmReset()"
        style="font-size:10px;padding:2px 8px;border-radius:4px;border:none;background:rgba(255,255,255,.15);color:#fff;cursor:pointer;">Reset</button>
      <button onclick="{sid}_closeZoom()"
        style="font-size:14px;padding:2px 8px;border-radius:4px;border:none;background:rgba(255,255,255,.2);color:#fff;cursor:pointer;">✕</button>
    </div>
    <div id="{sid}_zm_vp"
      style="flex:1;overflow:hidden;cursor:grab;position:relative;">
      <img id="{sid}_zm_img"
        style="position:absolute;transform-origin:0 0;max-width:none;" alt="zoom">
    </div>
    <div id="{sid}_zm_meta"
      style="background:rgba(10,36,99,.75);padding:5px 14px;display:flex;
             flex-wrap:wrap;gap:5px;flex-shrink:0;min-height:28px;"></div>
  </div>
</div>
{json_tag}
{js}
"""
        return html
