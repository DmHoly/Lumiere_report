from __future__ import annotations
import json
import html as _h
import math
import pandas as pd
from ..._helpers import Block, _safe_json
from ..data.data_mixin import DataMixin, DataArg

class Imageviewer(DataMixin, Block):
    """
    Wafermap en grille de champs rectangulaires avec carrousel d'images.

    Chaque case = une LED identifiée par (led_name, X, Y).
    Navigation image : boutons image_number dans le header du carrousel.
    Filtre type : toolbar (LightImage / LIVSweepImages / Tous).

    Paramètres
    ----------
    df / data_key   : DataFrame ou clé DataStore.
    x_col           : colonne position X (défaut "X").
    y_col           : colonne position Y (défaut "Y").
    image_col       : chemin image (défaut "full_path").
    wafer_col       : colonne wafer (défaut "wafername").
    led_col         : colonne LED (défaut "led_name").
    imgnum_col      : colonne image_number (défaut "image_number").
    type_col        : colonne type (défaut "type").
    color_col       : colonne numérique pour colorier les champs.
    meta_cols       : colonnes affichées dans le footer du carrousel.
    field_w_mm      : largeur d'un champ en mm (défaut 20).
    field_h_mm      : hauteur d'un champ en mm (défaut 9).
    wafer_diam_mm   : diamètre du wafer en mm (défaut 200).
    color_label     : label de la colorbar.
    num / title / subtitle : métadonnées du bloc.
    height          : hauteur totale du bloc en px (défaut 520).
    """

    def __init__(
            self,
            data: DataArg = None,
            df=None,  # compat ancien code
            x_col: str = "X",
            y_col: str = "Y",
            image_col: str = "full_path",
            wafer_col: str = "wafername",
            led_col: str = "led_name",
            imgnum_col: str = "image_number",
            type_col: str = "type",
            color_col: str = "",
            meta_cols: list[str] | None = None,
            field_w_mm: float = 20.0,
            field_h_mm: float = 9.0,
            wafer_diam_mm: float = 200.0,
            color_label: str = "",
            num: str = "01",
            title: str = "Wafer Field Map",
            subtitle: str = "",
            height: int = 560,
    ):
        self._init_data(data if data is not None else df)
        self.x_col = x_col
        self.y_col = y_col
        self.image_col = image_col
        self.wafer_col = wafer_col
        self.led_col = led_col
        self.imgnum_col = imgnum_col
        self.type_col = type_col
        self.color_col = color_col
        self.meta_cols = meta_cols or []
        self.field_w_mm = field_w_mm
        self.field_h_mm = field_h_mm
        self.wafer_diam_mm = wafer_diam_mm
        self.color_label = color_label or color_col
        self.num = num
        self.title = title
        self.subtitle = subtitle
        self.height = height
        self._id = f"wfm_{id(self)}"

    # ── Sérialisation ────────────────────────────────────────────────────────

    def _build_js_data(self, df: pd.DataFrame) -> str:
        wafers: dict = {}

        for _, row in df.iterrows():
            x = row.get(self.x_col)
            y = row.get(self.y_col)
            if x is None or y is None:
                continue
            try:
                x, y = int(x), int(y)
            except (ValueError, TypeError):
                continue

            wafer = str(row.get(self.wafer_col, "unknown"))
            led   = str(row.get(self.led_col, "")) if self.led_col else ""
            typ   = str(row.get(self.type_col, "")) if self.type_col else ""
            imgnum = row.get(self.imgnum_col, None)
            key = f"{x},{y},{led}"

            img_path = row.get(self.image_col, "")
            src = str(img_path).replace("\\", "/") if img_path else ""

            label = led or src.split("/")[-1]

            meta = {
                c: _safe_json(row[c])
                for c in self.meta_cols
                if c in row.index
            }

            color_val = None
            if self.color_col and self.color_col in row.index:
                try:
                    color_val = float(row[self.color_col])
                except (TypeError, ValueError):
                    pass

            if wafer not in wafers:
                wafers[wafer] = {}

            if key not in wafers[wafer]:
                wafers[wafer][key] = {
                    "x": x, "y": y, "led": led,
                    "by_type": {},
                    "all_color_vals": [],
                }

            entry = wafers[wafer][key]

            if typ not in entry["by_type"]:
                entry["by_type"][typ] = {"images": [], "color_vals": []}

            if src:
                entry["by_type"][typ]["images"].append({
                    "src": src,
                    "label": label,
                    "imgnum": str(imgnum) if imgnum is not None else "",
                    "meta": meta,
                })
            if color_val is not None:
                entry["by_type"][typ]["color_vals"].append(color_val)
                entry["all_color_vals"].append(color_val)

        result: dict = {}
        for wafer, fields in wafers.items():
            result[wafer] = {}
            for key, f in fields.items():
                by_type_clean = {}
                for typ, td in f["by_type"].items():
                    avg_color = (
                        sum(td["color_vals"]) / len(td["color_vals"])
                        if td["color_vals"] else None
                    )
                    by_type_clean[typ] = {
                        "images": td["images"],
                        "color": avg_color,
                        "n": len(td["images"]),
                    }

                all_cv = f["all_color_vals"]
                avg_all = sum(all_cv) / len(all_cv) if all_cv else None
                total_n = sum(v["n"] for v in by_type_clean.values())

                result[wafer][key] = {
                    "x": f["x"],
                    "y": f["y"],
                    "led": f["led"],
                    "types": list(f["by_type"].keys()),
                    "by_type": by_type_clean,
                    "color": avg_all,
                    "n": total_n,
                }

        return json.dumps(result)

    def _color_range(self, df: pd.DataFrame) -> tuple[float, float]:
        if not self.color_col or self.color_col not in df.columns:
            return (0.0, 1.0)
        vals = pd.to_numeric(df[self.color_col], errors="coerce").dropna()
        if len(vals) == 0:
            return (0.0, 1.0)
        return (float(vals.min()), float(vals.max()))

    def _all_types(self, df: pd.DataFrame) -> list[str]:
        if self.type_col not in df.columns:
            return []
        return sorted(df[self.type_col].dropna().unique().tolist())

    # ── Render ────────────────────────────────────────────────────────────────

    def render(self, store=None) -> str:
        df = self.resolve_df(store)
        sid = self._id
        data_json = self._build_js_data(df)
        cmin, cmax = self._color_range(df)
        has_color = "true" if self.color_col else "false"
        wafer_r_mm = self.wafer_diam_mm / 2.0
        all_types = self._all_types(df)
        types_json = json.dumps(all_types)

        title_h  = _h.escape(self.title)
        sub_h    = _h.escape(self.subtitle)
        clabel_h = _h.escape(self.color_label)
        num_h    = _h.escape(self.num)

        main_h = self.height - 105

        return f"""
<div class="led-block" id="{sid}_wrap"
  style="font-family:'IBM Plex Mono',monospace;">

  <!-- ── En-tête bloc ── -->
  <div class="led-block-header">
    <span class="led-block-num">{num_h}</span>
    <span class="led-block-title">{title_h}</span>
    <span class="led-block-sub">{sub_h}</span>
  </div>
  <div class="led-block-rule"></div>

  <!-- ── Toolbar ligne 1 ── -->
  <div style="display:flex;align-items:center;gap:8px;margin-bottom:4px;flex-wrap:wrap;">

    <select id="{sid}_wsel" onchange="{sid}_changeWafer(this.value)"
      class="spt-filter-op"
      style="font-size:11px;padding:4px 8px;min-width:140px;">
    </select>

    <div style="display:flex;align-items:center;gap:4px;">
      <span style="font-size:10px;color:rgba(10,36,99,.5);white-space:nowrap;">Type :</span>
      <div id="{sid}_type_btns"
        style="display:flex;border:0.5px solid rgba(10,36,99,.2);border-radius:4px;overflow:hidden;">
      </div>
    </div>

    <span id="{sid}_wbadge"
      style="font-size:10px;color:#D4AF37;border:1px solid rgba(212,175,55,.4);
             padding:2px 6px;border-radius:3px;white-space:nowrap;margin-left:auto;">
    </span>

    <div style="display:flex;border:0.5px solid rgba(10,36,99,.2);border-radius:4px;overflow:hidden;">
      <button id="{sid}_tab_carousel"
        onclick="{sid}_setView('carousel')"
        title="Vue carrousel"
        style="width:28px;height:26px;border:none;cursor:pointer;font-size:12px;
               background:rgba(10,36,99,0.08);color:#0A2463;">&#9776;</button>
      <button id="{sid}_tab_imgmap"
        onclick="{sid}_setView('imgmap')"
        title="Vue image map"
        style="width:28px;height:26px;border:none;border-left:0.5px solid rgba(10,36,99,.2);
               cursor:pointer;font-size:12px;background:transparent;color:#888;">&#10753;</button>
    </div>
  </div>

  <!-- ── Toolbar ligne 2 ── -->
  <div id="{sid}_toolbar2"
    style="display:flex;align-items:center;gap:6px;margin-bottom:8px;flex-wrap:wrap;">

    <button id="{sid}_wafer_toggle"
      onclick="{sid}_toggleWafer()"
      title="Afficher/masquer la wafermap"
      style="height:24px;padding:0 8px;border:0.5px solid rgba(10,36,99,.2);border-radius:4px;
             background:rgba(10,36,99,0.06);color:#0A2463;cursor:pointer;
             font-family:'IBM Plex Mono',monospace;font-size:10px;white-space:nowrap;">
      &#9632; Wafer
    </button>

    <span id="{sid}_led_sep" style="color:rgba(10,36,99,.15);font-size:14px;">|</span>
    <span id="{sid}_led_lbl" style="font-size:10px;color:rgba(10,36,99,.5);white-space:nowrap;">LED :</span>
    <div id="{sid}_led_pills"
      style="display:flex;gap:3px;flex-wrap:wrap;"></div>

  </div>

  <!-- ── Layout principal ── -->
  <div id="{sid}_main"
    style="display:grid;grid-template-columns:40% 1fr;gap:10px;height:{main_h}px;
           transition:grid-template-columns .2s;">

    <!-- Wafermap SVG -->
    <div id="{sid}_wafer_col"
      style="border:0.5px solid rgba(10,36,99,.2);border-radius:8px;overflow:hidden;
             background:#F8F9FD;display:flex;align-items:center;justify-content:center;
             transition:opacity .2s;">
      <svg id="{sid}_svg" width="100%" viewBox="0 0 330 352"
           style="max-height:{main_h}px;" preserveAspectRatio="xMidYMid meet">

        <circle cx="165" cy="171" r="152"
          fill="#F8F9FD" stroke="#CBD5E1" stroke-width="1"/>
        <line id="{sid}_flat" x1="0" y1="0" x2="0" y2="0"
          stroke="#CBD5E1" stroke-width="1.5"/>
        <g id="{sid}_fields"></g>

        <g id="{sid}_colorbar" style="display:none;">
          <defs>
            <linearGradient id="{sid}_cgrad" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%"   stop-color="#EF4444"/>
              <stop offset="50%"  stop-color="#D4AF37"/>
              <stop offset="100%" stop-color="#3B82F6"/>
            </linearGradient>
          </defs>
          <rect x="305" y="44" width="8" height="100"
            fill="url(#{sid}_cgrad)" rx="2"/>
          <text id="{sid}_cb_max" x="315" y="48"
            font-family="IBM Plex Mono" font-size="7" fill="#888"></text>
          <text id="{sid}_cb_mid" x="315" y="95"
            font-family="IBM Plex Mono" font-size="7" fill="#888"></text>
          <text id="{sid}_cb_min" x="315" y="146"
            font-family="IBM Plex Mono" font-size="7" fill="#888"></text>
          <text id="{sid}_cb_lbl" x="322" y="100"
            font-family="IBM Plex Mono" font-size="6" fill="#0A2463"
            transform="rotate(90,322,100)" text-anchor="middle">
            {clabel_h}
          </text>
        </g>
      </svg>
    </div>

    <!-- Panneau droit -->
    <div style="position:relative;border:0.5px solid rgba(10,36,99,.2);border-radius:8px;
                overflow:hidden;background:#FFFFFF;display:flex;flex-direction:column;">

      <!-- ══ VUE CARROUSEL ══ -->
      <div id="{sid}_panel_carousel"
        style="display:flex;flex-direction:column;flex:1;overflow:hidden;">

        <div style="padding:6px 10px;border-bottom:0.5px solid rgba(10,36,99,.1);
                    display:flex;align-items:center;gap:6px;flex-wrap:wrap;flex-shrink:0;">
          <div style="display:flex;flex-direction:column;gap:1px;flex:1;min-width:0;">
            <span id="{sid}_field_lbl"
              style="font-size:11px;font-weight:500;color:#0A2463;
                     white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">
              Sélectionner un champ
            </span>
            <span id="{sid}_field_sub"
              style="font-size:9px;color:rgba(10,36,99,.4);">
            </span>
          </div>
          <div id="{sid}_imgnum_btns"
            style="display:flex;gap:3px;flex-wrap:wrap;justify-content:flex-end;max-width:60%;">
          </div>
          <button id="{sid}_btn_zoom" onclick="{sid}_openZoom()"
            title="Zoom image"
            style="display:none;width:24px;height:24px;border:0.5px solid rgba(10,36,99,.2);
                   border-radius:4px;background:transparent;cursor:pointer;
                   font-size:13px;line-height:1;padding:0;color:#0A2463;">
            &#9906;
          </button>
        </div>

        <!-- Modale zoom -->
        <div id="{sid}_zoom_modal"
          style="display:none;position:fixed;inset:0;z-index:9999;
                 background:rgba(10,18,40,.82);
                 align-items:center;justify-content:center;">
          <div style="position:absolute;top:0;left:0;right:0;height:40px;
                      display:flex;align-items:center;padding:0 14px;gap:8px;">
            <span id="{sid}_zm_label"
              style="font-family:'IBM Plex Mono',monospace;font-size:11px;
                     color:rgba(255,255,255,.7);flex:1;"></span>
            <span style="font-family:'IBM Plex Mono',monospace;font-size:10px;
                         color:rgba(255,255,255,.4);">
              scroll pour zoomer · drag pour déplacer
            </span>
            <button onclick="{sid}_zmZoom(1.25)"
              style="width:26px;height:26px;border:0.5px solid rgba(255,255,255,.2);
                     border-radius:4px;background:transparent;color:#fff;
                     cursor:pointer;font-size:15px;line-height:1;">+</button>
            <button onclick="{sid}_zmZoom(0.8)"
              style="width:26px;height:26px;border:0.5px solid rgba(255,255,255,.2);
                     border-radius:4px;background:transparent;color:#fff;
                     cursor:pointer;font-size:15px;line-height:1;">−</button>
            <button onclick="{sid}_zmReset()"
              style="height:26px;padding:0 8px;border:0.5px solid rgba(255,255,255,.2);
                     border-radius:4px;background:transparent;color:rgba(255,255,255,.7);
                     cursor:pointer;font-size:10px;font-family:'IBM Plex Mono',monospace;">
              reset
            </button>
            <button onclick="{sid}_closeZoom()"
              style="width:26px;height:26px;border:0.5px solid rgba(255,255,255,.2);
                     border-radius:4px;background:transparent;color:#fff;
                     cursor:pointer;font-size:16px;line-height:1;">✕</button>
          </div>
          <div id="{sid}_zm_viewport"
            style="position:absolute;inset:40px 0 0 0;overflow:hidden;cursor:grab;">
            <img id="{sid}_zm_img" src="" alt=""
              style="position:absolute;transform-origin:0 0;user-select:none;
                     max-width:none;border-radius:4px;">
          </div>
          <button onclick="{sid}_navigate(-1);{sid}_syncZoomImg()"
            style="position:absolute;left:12px;top:50%;transform:translateY(-50%);
                   width:36px;height:36px;border:0.5px solid rgba(255,255,255,.3);
                   border-radius:50%;background:rgba(255,255,255,.08);color:#fff;
                   cursor:pointer;font-size:20px;z-index:2;">&#8249;</button>
          <button onclick="{sid}_navigate(1);{sid}_syncZoomImg()"
            style="position:absolute;right:12px;top:50%;transform:translateY(-50%);
                   width:36px;height:36px;border:0.5px solid rgba(255,255,255,.3);
                   border-radius:50%;background:rgba(255,255,255,.08);color:#fff;
                   cursor:pointer;font-size:20px;z-index:2;">&#8250;</button>
        </div>

        <!-- Zone image + flèches -->
        <div style="flex:1;position:relative;overflow:hidden;background:#F8F9FD;
                    display:flex;align-items:center;justify-content:center;">
          <button id="{sid}_btn_prev" onclick="{sid}_navigate(-1)"
            style="display:none;position:absolute;left:8px;top:50%;transform:translateY(-50%);
                   width:28px;height:28px;border:0.5px solid rgba(10,36,99,.2);border-radius:50%;
                   background:#fff;cursor:pointer;font-size:16px;z-index:2;
                   align-items:center;justify-content:center;">
            &#8249;
          </button>
          <div id="{sid}_ph"
            style="display:flex;flex-direction:column;align-items:center;
                   justify-content:center;gap:8px;color:#888;">
            <svg width="36" height="36" viewBox="0 0 36 36" fill="none">
              <circle cx="18" cy="18" r="16" stroke="#CBD5E1" stroke-width="1"/>
              <line x1="18" y1="8" x2="18" y2="28" stroke="#CBD5E1" stroke-width="1"/>
              <line x1="8" y1="18" x2="28" y2="18" stroke="#CBD5E1" stroke-width="1"/>
            </svg>
            <span style="font-size:11px;">Aucun champ sélectionné</span>
          </div>
          <img id="{sid}_img" src="" alt=""
            style="display:none;max-width:92%;max-height:92%;
                   object-fit:contain;border-radius:4px;">
          <button id="{sid}_btn_next" onclick="{sid}_navigate(1)"
            style="display:none;position:absolute;right:8px;top:50%;transform:translateY(-50%);
                   width:28px;height:28px;border:0.5px solid rgba(10,36,99,.2);border-radius:50%;
                   background:#fff;cursor:pointer;font-size:16px;z-index:2;
                   align-items:center;justify-content:center;">
            &#8250;
          </button>
        </div>

        <!-- Footer -->
        <div style="padding:5px 10px;border-top:0.5px solid rgba(10,36,99,.1);
                    display:flex;align-items:center;gap:8px;min-height:28px;flex-shrink:0;">
          <span id="{sid}_footer_led"
            style="font-size:10px;font-weight:600;color:#0A2463;
                   white-space:nowrap;display:none;"></span>
          <div id="{sid}_meta"
            style="display:flex;gap:10px;font-size:10px;color:#888;flex-wrap:wrap;"></div>
        </div>

      </div><!-- fin panel_carousel -->

      <!-- ══ VUE IMAGE MAP ══ -->
      <div id="{sid}_panel_imgmap"
        style="display:none;flex-direction:column;flex:1;overflow:hidden;">

        <div style="padding:5px 10px;border-bottom:0.5px solid rgba(10,36,99,.1);
                    display:flex;align-items:center;gap:8px;flex-shrink:0;">
          <span style="font-size:11px;font-weight:500;color:#0A2463;white-space:nowrap;">
            Vue d'ensemble
          </span>
          <span id="{sid}_im_badge" style="font-size:10px;color:#888;flex:1;"></span>
          <span style="font-size:9px;color:rgba(10,36,99,.4);white-space:nowrap;">Taille</span>
          <input id="{sid}_zoom_slider" type="range"
            min="0.4" max="10.0" step="0.1" value="1.0"
            oninput="{sid}_onZoomSlider(this.value)"
            style="width:80px;accent-color:#0A2463;cursor:pointer;height:3px;">
          <span id="{sid}_zoom_val"
            style="font-size:9px;color:#0A2463;min-width:26px;text-align:right;
                   font-family:'IBM Plex Mono',monospace;">×1.0</span>
        </div>

        <div id="{sid}_imgnum_bar"
          style="display:none;padding:4px 10px;border-bottom:0.5px solid rgba(10,36,99,.08);
                 background:rgba(10,36,99,0.03);
                 align-items:center;gap:8px;flex-shrink:0;">
          <span style="font-size:9px;color:rgba(10,36,99,.5);white-space:nowrap;">
            Image #
          </span>
          <button onclick="{sid}_globalImgStep(-1)"
            style="width:20px;height:20px;border:0.5px solid rgba(10,36,99,.2);border-radius:3px;
                   background:transparent;cursor:pointer;font-size:12px;
                   color:#0A2463;padding:0;line-height:1;">&#8249;</button>
          <div id="{sid}_global_imgnum_btns"
            style="display:flex;gap:3px;flex-wrap:nowrap;"></div>
          <button onclick="{sid}_globalImgStep(1)"
            style="width:20px;height:20px;border:0.5px solid rgba(10,36,99,.2);border-radius:3px;
                   background:transparent;cursor:pointer;font-size:12px;
                   color:#0A2463;padding:0;line-height:1;">&#8250;</button>
          <input id="{sid}_global_imgnum_slider" type="range"
            min="0" max="0" step="1" value="0"
            oninput="{sid}_globalImgSet(parseInt(this.value))"
            style="flex:1;accent-color:#D4AF37;cursor:pointer;height:3px;min-width:60px;">
          <span id="{sid}_global_imgnum_lbl"
            style="font-size:9px;color:#D4AF37;min-width:30px;text-align:right;
                   font-family:'IBM Plex Mono',monospace;white-space:nowrap;"></span>
        </div>

        <div style="flex:1;display:flex;overflow:hidden;">

          <!-- Panel latéral LED -->
          <div id="{sid}_led_panel"
            style="width:0;overflow:hidden;transition:width .18s;
                   border-right:0px solid rgba(10,36,99,.1);
                   background:#F8F9FD;flex-shrink:0;display:flex;flex-direction:column;">
            <div style="padding:6px 8px;border-bottom:0.5px solid rgba(10,36,99,.1);
                        display:flex;align-items:center;gap:4px;">
              <span style="font-size:10px;font-weight:600;color:#0A2463;flex:1;">LEDs</span>
              <button onclick="{sid}_selectAllLeds(true)"
                style="font-size:9px;padding:1px 5px;border:0.5px solid rgba(10,36,99,.2);
                       border-radius:3px;background:transparent;cursor:pointer;color:#0A2463;">
                tout
              </button>
              <button onclick="{sid}_selectAllLeds(false)"
                style="font-size:9px;padding:1px 5px;border:0.5px solid rgba(10,36,99,.2);
                       border-radius:3px;background:transparent;cursor:pointer;color:#888;">
                aucun
              </button>
            </div>
            <div id="{sid}_led_checkboxes"
              style="overflow-y:auto;flex:1;padding:4px 6px;"></div>
          </div>

          <div style="position:relative;flex:1;overflow:hidden;display:flex;">
            <button id="{sid}_led_toggle"
              onclick="{sid}_toggleLedPanel()"
              title="Filtrer LEDs"
              style="position:absolute;left:6px;top:50%;transform:translateY(-50%);
                     z-index:20;width:18px;height:48px;
                     border:0.5px solid rgba(212,175,55,.5);border-radius:3px;
                     background:rgba(10,18,40,0.7);color:#D4AF37;
                     cursor:pointer;font-size:9px;padding:0;line-height:1;
                     display:flex;align-items:center;justify-content:center;
                     writing-mode:vertical-rl;">
              LEDs &#9660;
            </button>

            <div id="{sid}_im_outer"
              style="flex:1;position:relative;overflow:hidden;background:#0A0E1A;">
              <div id="{sid}_im_vp"
                style="position:absolute;top:0;left:0;transform-origin:0 0;">
                <svg id="{sid}_im_svg"
                  style="position:absolute;top:0;left:0;pointer-events:none;overflow:visible;">
                  <circle id="{sid}_im_wc" cx="0" cy="0" r="0"
                    fill="none" stroke="rgba(100,116,139,0.4)" stroke-width="1"/>
                  <line id="{sid}_im_flat" x1="0" y1="0" x2="0" y2="0"
                    stroke="rgba(100,116,139,0.4)" stroke-width="1.5"/>
                  <g id="{sid}_im_borders"></g>
                </svg>
                <div id="{sid}_im_cells" style="position:absolute;top:0;left:0;"></div>
              </div>
            </div>
          </div>

        </div>
      </div><!-- fin panel_imgmap -->

    </div><!-- fin panneau droit -->
  </div><!-- fin main grid -->
</div><!-- fin led-block -->

<script>
(function(){{
  var ALL       = {data_json};
  var ALL_TYPES = {types_json};
  var sid       = "{sid}";
  var FW        = {self.field_w_mm};
  var FH        = {self.field_h_mm};
  var WR        = {wafer_r_mm};
  var CMIN      = {cmin};
  var CMAX      = {cmax};
  var HAS_COLOR = {has_color};

  var SVG_CX = 165, SVG_CY = 171, SVG_R = 145;
  var scale  = SVG_R / WR;

  var waferNames   = Object.keys(ALL);
  var currentWafer = waferNames[0] || null;
  var currentField = null;
  var currentImages = [];
  var imgIdx  = 0;
  var activeType = "all";
  var currentView = "carousel";
  var imgZoom = 1.0;
  var activeLeds = null;
  var globalImgNum = 0;
  var allImgNums = [];
  var ledPanelOpen = false;
  var waferVisible = true;
  var imCellRegistry = [];

  /* ─────────────────────────────────────────────
     Toggle wafermap (vue carrousel)
  ───────────────────────────────────────────── */
  window[sid+"_toggleWafer"] = function(){{
    waferVisible = !waferVisible;
    var main = document.getElementById(sid+"_main");
    var col  = document.getElementById(sid+"_wafer_col");
    var btn  = document.getElementById(sid+"_wafer_toggle");
    if(main) main.style.gridTemplateColumns = waferVisible ? "40% 1fr" : "0px 1fr";
    if(col){{
      col.style.opacity = waferVisible ? "1" : "0";
      col.style.pointerEvents = waferVisible ? "" : "none";
    }}
    if(btn){{
      btn.style.background = waferVisible ? "rgba(10,36,99,0.06)" : "transparent";
      btn.style.color = waferVisible ? "#0A2463" : "#888";
    }}
  }};

  /* ─────────────────────────────────────────────
     Pills LED (vue carrousel)
  ───────────────────────────────────────────── */
  var activeLedCarousel = null;

  function buildLedPills(waferName){{
    var fields = ALL[waferName] || {{}};
    var ledSet = {{}};
    Object.values(fields).forEach(function(f){{ if(f.led) ledSet[f.led] = true; }});
    var leds = Object.keys(ledSet).sort();

    if(activeLedCarousel === null || !leds.includes(activeLedCarousel)){{
      activeLedCarousel = leds[0] || null;
    }}

    var container = document.getElementById(sid+"_led_pills");
    if(!container) return;
    container.innerHTML = "";

    leds.forEach(function(led){{
      var btn = document.createElement("button");
      var short = led.length > 18 ? led.slice(0,17)+"…" : led;
      btn.textContent = short;
      btn.title = led;
      btn.dataset.led = led;
      var active = (led === activeLedCarousel);
      btn.style.cssText =
        "height:22px;padding:0 7px;border-radius:3px;cursor:pointer;"+
        "font-family:'IBM Plex Mono',monospace;font-size:9px;"+
        "transition:background .1s,color .1s,border-color .1s;"+
        "border:0.5px solid "+(active?"#0A2463":"rgba(10,36,99,.2)")+";"+
        "background:"+(active?"#0A2463":"transparent")+";"+
        "color:"+(active?"#fff":"rgba(10,36,99,.6)")+";";
      btn.addEventListener("click", function(){{
        activeLedCarousel = led;
        refreshLedPills();
        currentField = null; currentImages = []; imgIdx = 0;
        document.getElementById(sid+"_field_lbl").textContent = "Sélectionner un champ";
        document.getElementById(sid+"_field_sub").textContent = "";
        document.getElementById(sid+"_img").style.display = "none";
        document.getElementById(sid+"_ph").style.display  = "flex";
        document.getElementById(sid+"_imgnum_btns").innerHTML = "";
        document.getElementById(sid+"_meta").innerHTML = "";
        var fl = document.getElementById(sid+"_footer_led");
        if(fl) fl.style.display = "none";
        drawFields(currentWafer);
      }});
      container.appendChild(btn);
    }});
  }}

  function refreshLedPills(){{
    var container = document.getElementById(sid+"_led_pills");
    if(!container) return;
    container.querySelectorAll("button").forEach(function(btn){{
      var active = (btn.dataset.led === activeLedCarousel);
      btn.style.background  = active ? "#0A2463" : "transparent";
      btn.style.color       = active ? "#fff" : "rgba(10,36,99,.6)";
      btn.style.borderColor = active ? "#0A2463" : "rgba(10,36,99,.2)";
    }});
  }}

  /* ─────────────────────────────────────────────
     Dropdown wafer
  ───────────────────────────────────────────── */
  var sel = document.getElementById(sid+"_wsel");
  waferNames.forEach(function(w){{
    var o = document.createElement("option");
    o.value = w; o.textContent = w;
    sel.appendChild(o);
  }});

  /* ─────────────────────────────────────────────
     Boutons filtre Type
  ───────────────────────────────────────────── */
  var typeBtnContainer = document.getElementById(sid+"_type_btns");

  function buildTypeButtons(){{
    typeBtnContainer.innerHTML = "";
    var types = ["all"].concat(ALL_TYPES);
    types.forEach(function(t, i){{
      var btn = document.createElement("button");
      btn.textContent = t === "all" ? "Tous" : t;
      btn.dataset.type = t;
      btn.style.cssText =
        "height:26px;padding:0 8px;border:none;cursor:pointer;"+
        "font-family:'IBM Plex Mono',monospace;font-size:10px;"+
        "transition:background .12s,color .12s;"+
        (i>0?"border-left:0.5px solid rgba(10,36,99,.15);":"")+
        (t === activeType
          ? "background:rgba(10,36,99,0.1);color:#0A2463;font-weight:600;"
          : "background:transparent;color:#888;");
      btn.addEventListener("click", function(){{
        activeType = t;
        refreshTypeButtons();
        if(currentField) loadFieldImages(currentField);
        if(currentView === "imgmap") requestAnimationFrame(function(){{
          drawImgMap(currentWafer);
        }});
      }});
      typeBtnContainer.appendChild(btn);
    }});
  }}

  function refreshTypeButtons(){{
    typeBtnContainer.querySelectorAll("button").forEach(function(btn){{
      var t = btn.dataset.type;
      if(t === activeType){{
        btn.style.background = "rgba(10,36,99,0.1)";
        btn.style.color = "#0A2463";
        btn.style.fontWeight = "600";
      }} else {{
        btn.style.background = "transparent";
        btn.style.color = "#888";
        btn.style.fontWeight = "normal";
      }}
    }});
  }}

  buildTypeButtons();

  /* ─────────────────────────────────────────────
     Badge wafer
  ───────────────────────────────────────────── */
  function updateBadge(w){{
    var fields = ALL[w] || {{}};
    var nFields = Object.keys(fields).length;
    var nImgs = Object.values(fields).reduce(function(s,f){{ return s+f.n; }}, 0);
    document.getElementById(sid+"_wbadge").textContent =
      nFields+" champ"+(nFields>1?"s":"")+" · "+nImgs+" image"+(nImgs>1?"s":"");
  }}

  /* ─────────────────────────────────────────────
     Palette couleur
  ───────────────────────────────────────────── */
  function valToColor(v){{
    if(CMIN===CMAX) return "#D4AF37";
    var t=Math.max(0,Math.min(1,(v-CMIN)/(CMAX-CMIN)));
    var r,g,b;
    if(t<0.5){{
      var s=t*2;
      r=Math.round(59+(212-59)*s);
      g=Math.round(130+(175-130)*s);
      b=Math.round(246+(55-246)*s);
    }}else{{
      var s=(t-0.5)*2;
      r=Math.round(212+(239-212)*s);
      g=Math.round(175-175*s);
      b=Math.round(55-55*s);
    }}
    return"rgb("+r+","+g+","+b+")";
  }}

  /* ─────────────────────────────────────────────
     Flat wafer
  ───────────────────────────────────────────── */
  (function(){{
    var flatY_mm  = WR*0.92;
    var flatY_svg = SVG_CY + flatY_mm*scale;
    var halfX     = Math.sqrt(Math.max(0, WR*WR - flatY_mm*flatY_mm))*scale;
    var el = document.getElementById(sid+"_flat");
    el.setAttribute("x1", SVG_CX-halfX);
    el.setAttribute("y1", flatY_svg);
    el.setAttribute("x2", SVG_CX+halfX);
    el.setAttribute("y2", flatY_svg);
  }})();

  /* ─────────────────────────────────────────────
     Dessin des champs (wafermap)
  ───────────────────────────────────────────── */
  function drawFields(waferName){{
    var g = document.getElementById(sid+"_fields");
    g.innerHTML = "";

    var fields = ALL[waferName] || {{}};
    Object.values(fields).forEach(function(f){{
      if(activeLedCarousel !== null && f.led !== activeLedCarousel) return;

      var nActive = activeType === "all"
        ? f.n
        : (f.by_type[activeType] ? f.by_type[activeType].n : 0);

      var cx_mm  = (f.x - 0.5)*FW;
      var cy_mm  = (f.y - 0.5)*FH;
      var cx_svg = SVG_CX + cx_mm*scale;
      var cy_svg = SVG_CY - cy_mm*scale;
      var fw_svg = FW*scale;
      var fh_svg = FH*scale;
      var rx_svg = cx_svg - fw_svg/2;
      var ry_svg = cy_svg - fh_svg/2;

      var colorSrc = activeType === "all" ? f.color
        : (f.by_type[activeType] ? f.by_type[activeType].color : null);

      var fill;
      if(HAS_COLOR && colorSrc!=null){{
        fill = valToColor(colorSrc);
      }} else if(nActive > 0){{
        fill = "rgba(10,36,99,0.12)";
      }} else {{
        fill = "rgba(10,36,99,0.03)";
      }}

      var rect = document.createElementNS("http://www.w3.org/2000/svg","rect");
      rect.setAttribute("x",  rx_svg);
      rect.setAttribute("y",  ry_svg);
      rect.setAttribute("width",  fw_svg);
      rect.setAttribute("height", fh_svg);
      rect.setAttribute("fill",   fill);
      rect.setAttribute("stroke", "rgba(10,36,99,0.2)");
      rect.setAttribute("stroke-width","0.5");
      rect.setAttribute("rx","1");
      rect.style.cursor = nActive>0 ? "pointer" : "default";

      rect.addEventListener("mouseenter", function(){{
        if(nActive>0) this.setAttribute("stroke","#D4AF37");
        this.setAttribute("stroke-width","1.2");
      }});
      rect.addEventListener("mouseleave", function(){{
        var isSel = currentField && currentField.x===f.x && currentField.y===f.y;
        this.setAttribute("stroke", isSel?"#D4AF37":"rgba(10,36,99,0.2)");
        this.setAttribute("stroke-width", isSel?"1.5":"0.5");
      }});

      if(nActive>0){{
        rect.addEventListener("click", function(){{ selectField(f, rect); }});
      }}

      if(fw_svg>10){{
        var lbl = document.createElementNS("http://www.w3.org/2000/svg","text");
        lbl.setAttribute("x", cx_svg);
        lbl.setAttribute("y", cy_svg);
        lbl.setAttribute("text-anchor","middle");
        lbl.setAttribute("dominant-baseline","central");
        lbl.setAttribute("font-family","IBM Plex Mono");
        var fs = Math.max(4, Math.min(7, Math.min(fw_svg*0.22, fh_svg*0.38)));
        lbl.setAttribute("font-size", fs);
        lbl.setAttribute("fill", nActive>0 ? "rgba(10,36,99,0.65)" : "rgba(10,36,99,0.2)");
        lbl.setAttribute("pointer-events","none");
        lbl.textContent = f.x+","+f.y;
        g.appendChild(lbl);
      }}

      if(nActive > 1){{
        var badge = document.createElementNS("http://www.w3.org/2000/svg","text");
        badge.setAttribute("x", rx_svg + fw_svg - 2);
        badge.setAttribute("y", ry_svg + 7);
        badge.setAttribute("text-anchor","end");
        badge.setAttribute("font-family","IBM Plex Mono");
        badge.setAttribute("font-size", Math.max(4, Math.min(6.5, fh_svg*0.3)));
        badge.setAttribute("fill","#D4AF37");
        badge.setAttribute("pointer-events","none");
        badge.textContent = nActive+"×";
        g.appendChild(badge);
      }}

      g.appendChild(rect);
    }});
  }}

  /* ─────────────────────────────────────────────
     Colorbar
  ───────────────────────────────────────────── */
  if(HAS_COLOR){{
    document.getElementById(sid+"_colorbar").style.display = "block";
    document.getElementById(sid+"_cb_max").textContent = CMAX.toFixed(2);
    document.getElementById(sid+"_cb_mid").textContent = ((CMIN+CMAX)/2).toFixed(2);
    document.getElementById(sid+"_cb_min").textContent = CMIN.toFixed(2);
  }}

  /* ─────────────────────────────────────────────
     Images actives d'un champ
  ───────────────────────────────────────────── */
  function getActiveImages(f){{
    if(activeType === "all"){{
      var all = [];
      Object.entries(f.by_type).forEach(function(kv){{
        kv[1].images.forEach(function(img){{ all.push(img); }});
      }});
      return all;
    }}
    return (f.by_type[activeType] ? f.by_type[activeType].images : []);
  }}

  function loadFieldImages(f){{
    currentImages = getActiveImages(f);
    imgIdx = 0;
    buildImgNumButtons();
    showImage();
  }}

  /* ─────────────────────────────────────────────
     Boutons image_number
  ───────────────────────────────────────────── */
  function buildImgNumButtons(){{
    var container = document.getElementById(sid+"_imgnum_btns");
    container.innerHTML = "";
    if(!currentImages.length) return;

    var seen = {{}};
    currentImages.forEach(function(img, i){{
      var num = img.imgnum || String(i+1);
      if(!seen[num]) seen[num] = [];
      seen[num].push(i);
    }});

    var nums = Object.keys(seen);
    if(nums.length <= 1) return;

    nums.forEach(function(num){{
      var btn = document.createElement("button");
      btn.textContent = num;
      btn.dataset.imgnum = num;
      btn.style.cssText =
        "height:20px;min-width:20px;padding:0 5px;border-radius:3px;"+
        "border:0.5px solid rgba(10,36,99,.25);cursor:pointer;"+
        "font-family:'IBM Plex Mono',monospace;font-size:9px;"+
        "transition:background .1s,color .1s;"+
        "background:transparent;color:rgba(10,36,99,.6);";
      btn.addEventListener("click", function(){{
        var firstIdx = seen[num][0];
        imgIdx = firstIdx;
        refreshImgNumButtons();
        showImage();
      }});
      container.appendChild(btn);
    }});

    refreshImgNumButtons();
  }}

  function refreshImgNumButtons(){{
    var container = document.getElementById(sid+"_imgnum_btns");
    var curNum = currentImages[imgIdx] ? currentImages[imgIdx].imgnum : "";
    container.querySelectorAll("button").forEach(function(btn){{
      if(btn.dataset.imgnum === curNum){{
        btn.style.background  = "#0A2463";
        btn.style.color       = "#fff";
        btn.style.borderColor = "#0A2463";
      }} else {{
        btn.style.background  = "transparent";
        btn.style.color       = "rgba(10,36,99,.6)";
        btn.style.borderColor = "rgba(10,36,99,.25)";
      }}
    }});
  }}

  /* ─────────────────────────────────────────────
     Sélection d'un champ
  ───────────────────────────────────────────── */
  function selectField(f, rect){{
    currentField = f;
    document.getElementById(sid+"_fields").querySelectorAll("rect").forEach(function(r){{
      r.setAttribute("stroke","rgba(10,36,99,0.2)");
      r.setAttribute("stroke-width","0.5");
    }});
    rect.setAttribute("stroke","#D4AF37");
    rect.setAttribute("stroke-width","1.5");

    document.getElementById(sid+"_field_lbl").textContent =
      f.led || ("Champ ("+f.x+", "+f.y+")");
    document.getElementById(sid+"_field_sub").textContent =
      "X="+f.x+" Y="+f.y+" · "+
      (activeType==="all"
        ? f.n+" images"
        : ((f.by_type[activeType]?f.by_type[activeType].n:0)+" images ("+activeType+")"));

    loadFieldImages(f);
  }}

  /* ─────────────────────────────────────────────
     Affichage image courante
  ───────────────────────────────────────────── */
  function showImage(){{
    var imgEl = document.getElementById(sid+"_img");
    var ph    = document.getElementById(sid+"_ph");
    var btnP  = document.getElementById(sid+"_btn_prev");
    var btnN  = document.getElementById(sid+"_btn_next");
    var meta  = document.getElementById(sid+"_meta");

    if(!currentImages || !currentImages[imgIdx]){{
      imgEl.style.display = "none";
      ph.style.display    = "flex";
      btnP.style.display = btnN.style.display = "none";
      document.getElementById(sid+"_btn_zoom").style.display = "none";
      meta.innerHTML = "";
      return;
    }}

    var entry = currentImages[imgIdx];
    ph.style.display    = "none";
    imgEl.style.display = "block";
    imgEl.src           = entry.src;

    var footerLed = document.getElementById(sid+"_footer_led");
    if(footerLed){{
      if(currentField && currentField.led){{
        footerLed.textContent = currentField.led;
        footerLed.style.display = "inline";
      }} else {{
        footerLed.style.display = "none";
      }}
    }}

    var multi = currentImages.length > 1;
    btnP.style.display = multi ? "flex" : "none";
    btnN.style.display = multi ? "flex" : "none";
    document.getElementById(sid+"_btn_zoom").style.display = "flex";

    refreshImgNumButtons();

    var html = "";
    Object.entries(entry.meta||{{}}).forEach(function(kv){{
      html += '<span style="white-space:nowrap"><span style="color:rgba(10,36,99,.5)">'+
              kv[0]+'</span> <b style="color:#0A2463">'+kv[1]+'</b></span>';
    }});
    meta.innerHTML = html;
  }}

  /* ─────────────────────────────────────────────
     Navigation carrousel
  ───────────────────────────────────────────── */
  window[sid+"_navigate"] = function(dir){{
    if(!currentImages.length) return;
    imgIdx = (imgIdx + dir + currentImages.length) % currentImages.length;
    showImage();
  }};

  /* ─────────────────────────────────────────────
     Changement de wafer
  ───────────────────────────────────────────── */
  window[sid+"_changeWafer"] = function(w){{
    currentWafer  = w;
    currentField  = null;
    currentImages = [];
    imgIdx = 0;
    imPanX = 0; imPanY = 0;
    globalImgNum = 0;
    activeLeds = null;
    activeLedCarousel = null;

    document.getElementById(sid+"_field_lbl").textContent = "Sélectionner un champ";
    document.getElementById(sid+"_field_sub").textContent = "";
    document.getElementById(sid+"_img").style.display     = "none";
    document.getElementById(sid+"_ph").style.display      = "flex";
    document.getElementById(sid+"_btn_prev").style.display = "none";
    document.getElementById(sid+"_btn_next").style.display = "none";
    document.getElementById(sid+"_imgnum_btns").innerHTML = "";
    document.getElementById(sid+"_meta").innerHTML = "";

    buildLedPills(w);
    drawFields(w);
    updateBadge(w);
    if(currentView === "imgmap"){{
      requestAnimationFrame(function(){{ drawImgMap(w); }});
    }}
  }};

  /* ─────────────────────────────────────────────
     Zoom modal (carrousel)
  ───────────────────────────────────────────── */
  var zmScale=1, zmX=0, zmY=0, zmDragging=false, zmDragSX=0, zmDragSY=0, zmDragOX=0, zmDragOY=0;

  function zmApply(){{
    var img = document.getElementById(sid+"_zm_img");
    img.style.transform = "translate("+zmX+"px,"+zmY+"px) scale("+zmScale+")";
  }}

  window[sid+"_openZoom"] = function(){{
    if(!currentImages[imgIdx]) return;
    document.getElementById(sid+"_zoom_modal").style.display = "flex";
    window[sid+"_syncZoomImg"]();
  }};

  window[sid+"_syncZoomImg"] = function(){{
    var entry = currentImages[imgIdx];
    if(!entry) return;
    var zm = document.getElementById(sid+"_zm_img");
    zm.src = entry.src;
    var lbl = document.getElementById(sid+"_zm_label");
    if(lbl && currentField)
      lbl.textContent = (currentField.led||("("+currentField.x+","+currentField.y+")")) +
        "  ·  #"+(entry.imgnum||imgIdx+1) +
        "  ["+(activeType==="all"?"Tous":activeType)+"]";
    zm.onload = function(){{
      var vp = document.getElementById(sid+"_zm_viewport");
      var vpW = vp.offsetWidth, vpH = vp.offsetHeight;
      zmScale = Math.min(vpW/zm.naturalWidth, vpH/zm.naturalHeight, 1);
      zmX = (vpW - zm.naturalWidth*zmScale)/2;
      zmY = (vpH - zm.naturalHeight*zmScale)/2;
      zmApply();
    }};
  }};

  window[sid+"_closeZoom"] = function(){{
    document.getElementById(sid+"_zoom_modal").style.display = "none";
  }};

  window[sid+"_zmZoom"] = function(factor){{
    var vp = document.getElementById(sid+"_zm_viewport");
    var cx = vp.offsetWidth/2, cy = vp.offsetHeight/2;
    zmX = cx - (cx - zmX)*factor;
    zmY = cy - (cy - zmY)*factor;
    zmScale *= factor;
    zmApply();
  }};

  window[sid+"_zmReset"] = function(){{
    var vp = document.getElementById(sid+"_zm_viewport");
    var zm = document.getElementById(sid+"_zm_img");
    var vpW = vp.offsetWidth, vpH = vp.offsetHeight;
    zmScale = Math.min(vpW/zm.naturalWidth, vpH/zm.naturalHeight, 1);
    zmX = (vpW - zm.naturalWidth*zmScale)/2;
    zmY = (vpH - zm.naturalHeight*zmScale)/2;
    zmApply();
  }};

  (function(){{
    var vp = document.getElementById(sid+"_zm_viewport");
    vp.addEventListener("wheel", function(e){{
      e.preventDefault();
      var rect = vp.getBoundingClientRect();
      var mx = e.clientX - rect.left, my = e.clientY - rect.top;
      var factor = e.deltaY < 0 ? 1.12 : 0.89;
      zmX = mx - (mx - zmX)*factor;
      zmY = my - (my - zmY)*factor;
      zmScale *= factor;
      zmApply();
    }}, {{passive:false}});

    vp.addEventListener("mousedown", function(e){{
      zmDragging=true; zmDragSX=e.clientX; zmDragSY=e.clientY;
      zmDragOX=zmX; zmDragOY=zmY;
      vp.style.cursor="grabbing";
    }});
    window.addEventListener("mousemove", function(e){{
      if(!zmDragging) return;
      zmX = zmDragOX + (e.clientX-zmDragSX);
      zmY = zmDragOY + (e.clientY-zmDragSY);
      zmApply();
    }});
    window.addEventListener("mouseup", function(){{
      zmDragging=false;
      vp.style.cursor="grab";
    }});

    var lastDist=0, lastTX=0, lastTY=0;
    vp.addEventListener("touchstart", function(e){{
      if(e.touches.length===2){{
        lastDist=Math.hypot(e.touches[0].clientX-e.touches[1].clientX,
                            e.touches[0].clientY-e.touches[1].clientY);
      }} else {{
        lastTX=e.touches[0].clientX; lastTY=e.touches[0].clientY;
        zmDragOX=zmX; zmDragOY=zmY;
      }}
    }},{{passive:true}});
    vp.addEventListener("touchmove", function(e){{
      e.preventDefault();
      if(e.touches.length===2){{
        var dist=Math.hypot(e.touches[0].clientX-e.touches[1].clientX,
                            e.touches[0].clientY-e.touches[1].clientY);
        var rect=vp.getBoundingClientRect();
        var mx=((e.touches[0].clientX+e.touches[1].clientX)/2)-rect.left;
        var my=((e.touches[0].clientY+e.touches[1].clientY)/2)-rect.top;
        var factor=dist/lastDist;
        zmX=mx-(mx-zmX)*factor; zmY=my-(my-zmY)*factor; zmScale*=factor;
        lastDist=dist; zmApply();
      }} else {{
        zmX=zmDragOX+(e.touches[0].clientX-lastTX);
        zmY=zmDragOY+(e.touches[0].clientY-lastTY);
        zmApply();
      }}
    }},{{passive:false}});
  }})();

  document.addEventListener("keydown", function(e){{
    if(e.key==="Escape") window[sid+"_closeZoom"]&&window[sid+"_closeZoom"]();
  }});

  /* ─────────────────────────────────────────────
     Pan / zoom état (vue image map) — RAF-locked
  ───────────────────────────────────────────── */
  var imPanX = 0, imPanY = 0;
  var imBaseScale = 1;
  var _rafPending = false;

  /* Accumulateurs — écrits par les event handlers, consommés par RAF */
  var _pendingPanDX = 0, _pendingPanDY = 0;
  var _pendingZoomFactor = 1.0;
  var _pendingZoomOriginX = 0, _pendingZoomOriginY = 0;
  var _sliderNeedsUpdate = false;

  function imApplyTransform(){{
    var vp = document.getElementById(sid+"_im_vp");
    if(!vp) return;
    var s = imBaseScale * imgZoom;
    vp.style.transform = "translate("+imPanX+"px,"+imPanY+"px) scale("+s+")";
  }}

  function _commitFrame(){{
    _rafPending = false;

    /* 1. Pan */
    if(_pendingPanDX !== 0 || _pendingPanDY !== 0){{
      imPanX += _pendingPanDX;
      imPanY += _pendingPanDY;
      _pendingPanDX = 0;
      _pendingPanDY = 0;
    }}

    /* 2. Zoom */
    if(_pendingZoomFactor !== 1.0){{
      var newZoom = Math.max(0.4, Math.min(10.0, imgZoom * _pendingZoomFactor));
      var mx = _pendingZoomOriginX, my = _pendingZoomOriginY;
      imPanX = mx - (mx - imPanX) * (newZoom / imgZoom);
      imPanY = my - (my - imPanY) * (newZoom / imgZoom);
      imgZoom = newZoom;
      _pendingZoomFactor = 1.0;
    }}

    /* 3. Une seule écriture DOM par frame */
    imApplyTransform();

    /* 4. Slider + label — hors chemin critique */
    if(_sliderNeedsUpdate){{
      _sliderNeedsUpdate = false;
      var sl = document.getElementById(sid+"_zoom_slider");
      var lbl = document.getElementById(sid+"_zoom_val");
      if(sl) sl.value = imgZoom.toFixed(1);
      if(lbl) lbl.textContent = "\xd7"+imgZoom.toFixed(1);
    }}
  }}

  function _scheduleFrame(){{
    if(_rafPending) return;
    _rafPending = true;
    requestAnimationFrame(_commitFrame);
  }}

  function imResetPan(){{
    var outer = document.getElementById(sid+"_im_outer");
    if(!outer) return;
    imPanX = outer.offsetWidth / 2;
    imPanY = outer.offsetHeight / 2;
    imApplyTransform();
  }}

  window[sid+"_onZoomSlider"] = function(val){{
    imgZoom = parseFloat(val);
    var label = document.getElementById(sid+"_zoom_val");
    if(label) label.textContent = "\xd7"+imgZoom.toFixed(1);
    imApplyTransform();
  }};

  /* ── Pan souris — RAF-locked ── */
  (function(){{
    var dragging = false, lastX = 0, lastY = 0;

    /* Promote layers GPU une fois pour toutes */
    var outer = document.getElementById(sid+"_im_outer");
    var vp    = document.getElementById(sid+"_im_vp");
    if(outer){{ outer.style.willChange = "transform"; outer.style.cursor = "grab"; }}
    if(vp) vp.style.willChange = "transform";

    document.addEventListener("mousedown", function(e){{
      var o = document.getElementById(sid+"_im_outer");
      if(!o || !o.contains(e.target)) return;
      if(e.target.tagName === "BUTTON" || e.target.tagName === "IMG") return;
      dragging = true;
      lastX = e.clientX;
      lastY = e.clientY;
      o.style.cursor = "grabbing";
    }});

    document.addEventListener("mousemove", function(e){{
      if(!dragging) return;
      _pendingPanDX += e.clientX - lastX;
      _pendingPanDY += e.clientY - lastY;
      lastX = e.clientX;
      lastY = e.clientY;
      _scheduleFrame();
    }});

    document.addEventListener("mouseup", function(){{
      if(!dragging) return;
      dragging = false;
      var o = document.getElementById(sid+"_im_outer");
      if(o) o.style.cursor = "grab";
    }});
  }})();

  /* ── Zoom molette — RAF-locked ── */
  (function(){{
    document.addEventListener("wheel", function(e){{
      var outer = document.getElementById(sid+"_im_outer");
      if(!outer || !outer.contains(e.target)) return;
      e.preventDefault();
      var rect = outer.getBoundingClientRect();
      /* Toujours écraser l'origine vers la position courante du curseur */
      _pendingZoomOriginX = e.clientX - rect.left;
      _pendingZoomOriginY = e.clientY - rect.top;
      /* Facteurs s'accumulent multiplicativement entre deux RAF */
      _pendingZoomFactor *= (e.deltaY < 0 ? 1.12 : 0.89);
      _sliderNeedsUpdate = true;
      _scheduleFrame();
    }}, {{passive: false}});
  }})();

  /* ── Touch pinch + pan — RAF-locked ── */
  (function(){{
    var lastDist = 0, lastTX = 0, lastTY = 0, tDragging = false;

    document.addEventListener("touchstart", function(e){{
      var outer = document.getElementById(sid+"_im_outer");
      if(!outer || !outer.contains(e.target)) return;
      if(e.touches.length === 2){{
        lastDist = Math.hypot(
          e.touches[0].clientX - e.touches[1].clientX,
          e.touches[0].clientY - e.touches[1].clientY
        );
        tDragging = false;
      }} else {{
        lastTX = e.touches[0].clientX;
        lastTY = e.touches[0].clientY;
        tDragging = true;
      }}
    }}, {{passive: true}});

    document.addEventListener("touchmove", function(e){{
      var outer = document.getElementById(sid+"_im_outer");
      if(!outer || !outer.contains(e.target)) return;
      e.preventDefault();
      if(e.touches.length === 2){{
        var dist = Math.hypot(
          e.touches[0].clientX - e.touches[1].clientX,
          e.touches[0].clientY - e.touches[1].clientY
        );
        var rect = outer.getBoundingClientRect();
        _pendingZoomOriginX = ((e.touches[0].clientX + e.touches[1].clientX) / 2) - rect.left;
        _pendingZoomOriginY = ((e.touches[0].clientY + e.touches[1].clientY) / 2) - rect.top;
        _pendingZoomFactor *= dist / lastDist;
        lastDist = dist;
        _sliderNeedsUpdate = true;
        _scheduleFrame();
      }} else if(tDragging){{
        _pendingPanDX += e.touches[0].clientX - lastTX;
        _pendingPanDY += e.touches[0].clientY - lastTY;
        lastTX = e.touches[0].clientX;
        lastTY = e.touches[0].clientY;
        _scheduleFrame();
      }}
    }}, {{passive: false}});

    document.addEventListener("touchend", function(){{
      tDragging = false;
    }}, {{passive: true}});
  }})();

  /* ─────────────────────────────────────────────
     Toggle vue carrousel / image map
  ───────────────────────────────────────────── */
  window[sid+"_setView"] = function(view){{
    currentView = view;
    var pc   = document.getElementById(sid+"_panel_carousel");
    var pm   = document.getElementById(sid+"_panel_imgmap");
    var tb_c = document.getElementById(sid+"_tab_carousel");
    var tb_m = document.getElementById(sid+"_tab_imgmap");
    var tb2    = document.getElementById(sid+"_toolbar2");
    var wCol   = document.getElementById(sid+"_wafer_col");
    var mainEl = document.getElementById(sid+"_main");

    if(view === "carousel"){{
      pc.style.display = "flex";
      pm.style.display = "none";
      tb_c.style.background = "rgba(10,36,99,0.08)"; tb_c.style.color = "#0A2463";
      tb_m.style.background = "transparent";          tb_m.style.color = "#888";
      if(tb2) tb2.style.display = "flex";
      if(mainEl) mainEl.style.gridTemplateColumns = waferVisible ? "40% 1fr" : "0px 1fr";
      if(wCol){{ wCol.style.opacity = waferVisible?"1":"0"; wCol.style.pointerEvents=waferVisible?"":"none"; }}
      var sep = document.getElementById(sid+"_led_sep");
      var lbl = document.getElementById(sid+"_led_lbl");
      var pills = document.getElementById(sid+"_led_pills");
      if(sep) sep.style.display = "";
      if(lbl) lbl.style.display = "";
      if(pills) pills.style.display = "flex";
    }} else {{
      pc.style.display = "none";
      pm.style.display = "flex";
      tb_c.style.background = "transparent";          tb_c.style.color = "#888";
      tb_m.style.background = "rgba(10,36,99,0.08)"; tb_m.style.color = "#0A2463";
      if(tb2) tb2.style.display = "flex";
      if(mainEl) mainEl.style.gridTemplateColumns = waferVisible ? "40% 1fr" : "0px 1fr";
      if(wCol){{ wCol.style.opacity=waferVisible?"1":"0"; wCol.style.pointerEvents=waferVisible?"":"none"; }}
      var sep = document.getElementById(sid+"_led_sep");
      var lbl = document.getElementById(sid+"_led_lbl");
      var pills = document.getElementById(sid+"_led_pills");
      if(sep) sep.style.display = "none";
      if(lbl) lbl.style.display = "none";
      if(pills) pills.style.display = "none";
      requestAnimationFrame(function(){{
        buildLedCheckboxes(currentWafer);
        drawImgMap(currentWafer);
      }});
    }}
  }};

  /* ─────────────────────────────────────────────
     Panel LED — toggle + checkboxes
  ───────────────────────────────────────────── */
  window[sid+"_toggleLedPanel"] = function(){{
    ledPanelOpen = !ledPanelOpen;
    var panel = document.getElementById(sid+"_led_panel");
    var btn   = document.getElementById(sid+"_led_toggle");
    if(ledPanelOpen){{
      panel.style.width = "140px";
      panel.style.borderRightWidth = "0.5px";
      if(btn) btn.innerHTML = "LEDs &#9650;";
    }} else {{
      panel.style.width = "0";
      panel.style.borderRightWidth = "0";
      if(btn) btn.innerHTML = "LEDs &#9660;";
    }}
  }};

  window[sid+"_selectAllLeds"] = function(val){{
    var boxes = document.getElementById(sid+"_led_checkboxes");
    if(!boxes) return;
    boxes.querySelectorAll("input[type=checkbox]").forEach(function(cb){{
      cb.checked = val;
      if(val) activeLeds.add(cb.value);
      else    activeLeds.delete(cb.value);
    }});
    requestAnimationFrame(function(){{ drawImgMap(currentWafer); }});
  }};

  function buildLedCheckboxes(waferName){{
    var fields = ALL[waferName] || {{}};
    var ledSet = {{}};
    Object.values(fields).forEach(function(f){{ ledSet[f.led] = true; }});
    var leds = Object.keys(ledSet).sort();

    activeLeds = new Set(leds.length > 0 ? [leds[0]] : []);

    var container = document.getElementById(sid+"_led_checkboxes");
    if(!container) return;
    container.innerHTML = "";
    leds.forEach(function(led){{
      var row = document.createElement("label");
      row.style.cssText =
        "display:flex;align-items:center;gap:5px;padding:3px 2px;"+
        "cursor:pointer;border-radius:3px;"+
        "font-family:'IBM Plex Mono',monospace;font-size:9px;color:#0A2463;"+
        "white-space:nowrap;overflow:hidden;";
      row.title = led;
      row.addEventListener("mouseenter",function(){{ this.style.background="rgba(10,36,99,0.06)"; }});
      row.addEventListener("mouseleave",function(){{ this.style.background=""; }});

      var cb = document.createElement("input");
      cb.type = "checkbox"; cb.value = led; cb.checked = (led === leds[0]);
      cb.style.cssText = "accent-color:#0A2463;cursor:pointer;flex-shrink:0;";
      cb.addEventListener("change", function(){{
        if(this.checked) activeLeds.add(led);
        else             activeLeds.delete(led);
        requestAnimationFrame(function(){{ drawImgMap(currentWafer); }});
      }});

      var txt = document.createElement("span");
      var short = led.length > 14 ? led.slice(0,13)+"…" : led;
      txt.textContent = short;
      txt.style.cssText = "overflow:hidden;text-overflow:ellipsis;";

      row.appendChild(cb);
      row.appendChild(txt);
      container.appendChild(row);
    }});
  }}

  /* ─────────────────────────────────────────────
     Image number global (vue image map)
  ───────────────────────────────────────────── */
  function collectImgNums(waferName){{
    var fields  = ALL[waferName] || {{}};
    var numSet  = {{}};
    Object.values(fields).forEach(function(f){{
      var imgs = activeType==="all" ? getActiveImages(f)
                 : (f.by_type[activeType]?f.by_type[activeType].images:[]);
      imgs.forEach(function(img){{ if(img.imgnum) numSet[img.imgnum] = true; }});
    }});
    allImgNums = Object.keys(numSet).sort(function(a,b){{
      var na = parseFloat(a), nb = parseFloat(b);
      return isNaN(na)||isNaN(nb) ? a.localeCompare(b) : na-nb;
    }});
    return allImgNums;
  }}

  function buildImgNumBar(){{
    var bar  = document.getElementById(sid+"_imgnum_bar");
    var btns = document.getElementById(sid+"_global_imgnum_btns");
    var sl   = document.getElementById(sid+"_global_imgnum_slider");
    var lbl  = document.getElementById(sid+"_global_imgnum_lbl");
    if(!bar||!btns||!sl) return;

    if(allImgNums.length <= 1){{ bar.style.display = "none"; return; }}
    bar.style.display = "flex";

    sl.min = 0; sl.max = allImgNums.length-1; sl.value = globalImgNum;

    btns.innerHTML = "";
    allImgNums.forEach(function(num, i){{
      var btn = document.createElement("button");
      btn.textContent = num;
      btn.dataset.idx = i;
      btn.style.cssText =
        "height:20px;min-width:20px;padding:0 5px;border-radius:3px;"+
        "border:0.5px solid rgba(212,175,55,.3);cursor:pointer;"+
        "font-family:'IBM Plex Mono',monospace;font-size:9px;"+
        "transition:background .1s,color .1s;"+
        (i===globalImgNum
          ? "background:#D4AF37;color:#0A0E1A;border-color:#D4AF37;"
          : "background:transparent;color:rgba(212,175,55,.7);");
      btn.addEventListener("click",(function(idx){{ return function(){{
        window[sid+"_globalImgSet"](idx);
      }}; }})(i));
      btns.appendChild(btn);
    }});
    if(lbl) lbl.textContent = (globalImgNum+1)+"/"+allImgNums.length;
  }}

  function refreshImgNumBar(){{
    var btns = document.getElementById(sid+"_global_imgnum_btns");
    var sl   = document.getElementById(sid+"_global_imgnum_slider");
    var lbl  = document.getElementById(sid+"_global_imgnum_lbl");
    if(btns) btns.querySelectorAll("button").forEach(function(btn){{
      var i = parseInt(btn.dataset.idx);
      if(i===globalImgNum){{
        btn.style.background="#D4AF37"; btn.style.color="#0A0E1A";
        btn.style.borderColor="#D4AF37";
      }} else {{
        btn.style.background="transparent"; btn.style.color="rgba(212,175,55,.7)";
        btn.style.borderColor="rgba(212,175,55,.3)";
      }}
    }});
    if(sl) sl.value = globalImgNum;
    if(lbl) lbl.textContent = (globalImgNum+1)+"/"+allImgNums.length;
  }}

  function applyGlobalImgNum(){{
    var targetNum = allImgNums[globalImgNum];
    imCellRegistry.forEach(function(entry){{
      var idx = 0;
      for(var i=0; i<entry.images.length; i++){{
        if(entry.images[i].imgnum === targetNum){{ idx=i; break; }}
      }}
      entry.setCellImg(idx);
    }});
    refreshImgNumBar();
  }}

  window[sid+"_globalImgSet"] = function(idx){{
    globalImgNum = Math.max(0, Math.min(allImgNums.length-1, idx));
    applyGlobalImgNum();
  }};

  window[sid+"_globalImgStep"] = function(dir){{
    window[sid+"_globalImgSet"](globalImgNum + dir);
  }};

  /* ─────────────────────────────────────────────
     Vue image map
  ───────────────────────────────────────────── */
  function drawImgMap(waferName){{
    var outer = document.getElementById(sid+"_im_outer");
    if(!outer) return;
    var W = outer.offsetWidth || 600;
    var H = outer.offsetHeight || 400;
    if(W < 10 || H < 10) return;

    var fields = ALL[waferName] || {{}};

    imBaseScale = Math.min((W-20)/(2*WR), (H-20)/(2*WR));

    if(imPanX===0 && imPanY===0){{ imPanX=W/2; imPanY=H/2; }}

    var totalFields = Object.keys(fields).length;
    var totalImgs = Object.values(fields).reduce(function(s,f){{
      return s + (activeType==="all" ? f.n : (f.by_type[activeType]?f.by_type[activeType].n:0));
    }}, 0);
    var badge = document.getElementById(sid+"_im_badge");
    if(badge) badge.textContent = totalFields+" champs · "+totalImgs+" images";

    var svg = document.getElementById(sid+"_im_svg");
    svg.style.width  = (2*WR*imBaseScale+40)+"px";
    svg.style.height = (2*WR*imBaseScale+40)+"px";
    svg.setAttribute("viewBox",
      (-WR*imBaseScale-20)+" "+(-WR*imBaseScale-20)+" "+
      (2*WR*imBaseScale+40)+" "+(2*WR*imBaseScale+40));

    var wc = document.getElementById(sid+"_im_wc");
    wc.setAttribute("cx","0"); wc.setAttribute("cy","0");
    wc.setAttribute("r", WR*imBaseScale);

    var flatY_mm  = WR*0.92;
    var flatY_svg = flatY_mm*imBaseScale;
    var halfX_svg = Math.sqrt(Math.max(0,WR*WR-flatY_mm*flatY_mm))*imBaseScale;
    var ifl = document.getElementById(sid+"_im_flat");
    ifl.setAttribute("x1",-halfX_svg); ifl.setAttribute("y1",flatY_svg);
    ifl.setAttribute("x2", halfX_svg); ifl.setAttribute("y2",flatY_svg);

    svg.style.left = (-WR*imBaseScale-20)+"px";
    svg.style.top  = (-WR*imBaseScale-20)+"px";

    document.getElementById(sid+"_im_borders").innerHTML = "";
    document.getElementById(sid+"_im_cells").innerHTML = "";
    var bg    = document.getElementById(sid+"_im_borders");
    var cells = document.getElementById(sid+"_im_cells");

    var imScale = imBaseScale;

    imCellRegistry = [];

    Object.values(fields).forEach(function(f){{
      if(activeLeds !== null && !activeLeds.has(f.led)) return;

      var images = activeType==="all"
        ? getActiveImages(f)
        : (f.by_type[activeType]?f.by_type[activeType].images:[]);
      var n = images.length;

      var px = (f.x-0.5)*FW*imScale - FW*imScale/2;
      var py = -(f.y-0.5)*FH*imScale - FH*imScale/2;
      var pw = Math.max(2, Math.floor(FW*imScale));
      var ph = Math.max(2, Math.floor(FH*imScale));

      var br = document.createElementNS("http://www.w3.org/2000/svg","rect");
      br.setAttribute("x",px); br.setAttribute("y",py);
      br.setAttribute("width",pw); br.setAttribute("height",ph);
      br.setAttribute("fill","none");
      br.setAttribute("stroke", n>0 ? "rgba(10,36,99,0.3)" : "rgba(10,36,99,0.1)");
      br.setAttribute("stroke-width","0.5");
      bg.appendChild(br);

      var cell = document.createElement("div");
      cell.style.cssText =
        "position:absolute;left:"+px+"px;top:"+py+"px;"+
        "width:"+pw+"px;height:"+ph+"px;overflow:hidden;box-sizing:border-box;"+
        "background:"+(n>0?"#0A0E1A":"rgba(10,36,99,0.03)")+";"+
        "cursor:"+(n>0?"pointer":"default")+";"+
        "transition:box-shadow .12s;";

      if(n > 0){{
        var cellIdx = 0;

        var im = document.createElement("img");
        im.setAttribute("loading","lazy");
        /* Lazy src : posé via dataset, chargé par IntersectionObserver */
        im.dataset.lazySrc = images[0].src;
        im.style.cssText =
          "position:absolute;inset:0;width:100%;height:100%;"+
          "object-fit:cover;display:block;transition:opacity .15s;";
        cell.appendChild(im);

        /* Observer lazy loading */
        if(window[sid+"_io"]) window[sid+"_io"].observe(im);

        function setCellImg(idx){{
          cellIdx = (idx + n) % n;
          var newSrc = images[cellIdx].src;
          if(im.dataset.lazySrc !== undefined && !im.src){{
            /* Pas encore chargée : mettre à jour lazySrc */
            im.dataset.lazySrc = newSrc;
          }} else {{
            im.src = newSrc;
          }}
        }}

        imCellRegistry.push({{ setCellImg: setCellImg, images: images }});

        if(n > 1){{
          var arrowStyle =
            "position:absolute;top:50%;transform:translateY(-50%);"+
            "width:"+Math.max(12,Math.min(18,pw*0.22))+"px;"+
            "height:"+Math.max(12,Math.min(18,pw*0.22))+"px;"+
            "border-radius:50%;border:none;"+
            "background:rgba(10,18,40,0.55);color:#fff;"+
            "display:flex;align-items:center;justify-content:center;"+
            "cursor:pointer;z-index:5;opacity:0;transition:opacity .12s;"+
            "font-size:"+Math.max(8,Math.min(12,pw*0.16))+"px;line-height:1;padding:0;";

          var btnL = document.createElement("button");
          btnL.style.cssText = arrowStyle+"left:1px;";
          btnL.innerHTML = "&#8249;";
          btnL.addEventListener("click", (function(){{ return function(e){{
            e.stopPropagation();
            setCellImg(cellIdx - 1);
          }}; }})());

          var btnR = document.createElement("button");
          btnR.style.cssText = arrowStyle+"right:1px;";
          btnR.innerHTML = "&#8250;";
          btnR.addEventListener("click", (function(){{ return function(e){{
            e.stopPropagation();
            setCellImg(cellIdx + 1);
          }}; }})());

          cell.appendChild(btnL);
          cell.appendChild(btnR);

          cell.addEventListener("mouseenter", function(){{
            btnL.style.opacity = "1";
            btnR.style.opacity = "1";
            cell.style.boxShadow = "inset 0 0 0 1.5px #D4AF37";
            cell.style.zIndex = "10";
          }});
          cell.addEventListener("mouseleave", function(){{
            btnL.style.opacity = "0";
            btnR.style.opacity = "0";
            cell.style.boxShadow = "";
            cell.style.zIndex = "";
          }});

          var tStartX = 0;
          cell.addEventListener("touchstart", function(e){{
            tStartX = e.touches[0].clientX;
          }}, {{passive:true}});
          cell.addEventListener("touchend", function(e){{
            var dx = e.changedTouches[0].clientX - tStartX;
            if(Math.abs(dx) > pw * 0.25){{
              setCellImg(cellIdx + (dx < 0 ? 1 : -1));
            }}
          }}, {{passive:true}});

        }} else {{
          cell.addEventListener("mouseenter", function(){{
            cell.style.boxShadow = "inset 0 0 0 1.5px #D4AF37";
            cell.style.zIndex = "10";
          }});
          cell.addEventListener("mouseleave", function(){{
            cell.style.boxShadow = "";
            cell.style.zIndex = "";
          }});
        }}

        cell.addEventListener("click", (function(field, imgs){{
          return function(){{
            currentField  = field;
            currentImages = imgs;
            imgIdx = cellIdx;
            window[sid+"_setView"]("carousel");
            document.getElementById(sid+"_fields").querySelectorAll("rect").forEach(function(r){{
              r.setAttribute("stroke","rgba(10,36,99,0.2)");
              r.setAttribute("stroke-width","0.5");
            }});
            document.getElementById(sid+"_field_lbl").textContent =
              field.led || ("Champ ("+field.x+", "+field.y+")");
            document.getElementById(sid+"_field_sub").textContent =
              "X="+field.x+" Y="+field.y+" · "+imgs.length+" image"+(imgs.length>1?"s":"");
            buildImgNumButtons();
            showImage();
          }};
        }})(f, images));

      }} else {{
        cell.style.background = "rgba(10,36,99,0.03)";
      }}

      cells.appendChild(cell);
    }});

    collectImgNums(waferName);
    buildImgNumBar();
    if(allImgNums.length > 1) applyGlobalImgNum();

    imApplyTransform();
  }}

  /* ─────────────────────────────────────────────
     IntersectionObserver — lazy loading images
  ───────────────────────────────────────────── */
  (function(){{
    var outer = document.getElementById(sid+"_im_outer");
    window[sid+"_io"] = new IntersectionObserver(function(entries){{
      entries.forEach(function(e){{
        if(e.isIntersecting && e.target.dataset.lazySrc){{
          e.target.src = e.target.dataset.lazySrc;
          delete e.target.dataset.lazySrc;
          window[sid+"_io"].unobserve(e.target);
        }}
      }});
    }}, {{ root: outer, rootMargin: "120px" }});
  }})();

  /* ─────────────────────────────────────────────
     Init
  ───────────────────────────────────────────── */
  if(currentWafer){{
    buildLedPills(currentWafer);
    drawFields(currentWafer);
    updateBadge(currentWafer);
  }}

}})();
</script>
"""

    def _hover_fields_js(self) -> str:
        return ""