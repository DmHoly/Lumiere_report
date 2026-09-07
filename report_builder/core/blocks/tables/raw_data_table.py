"""
raw_data_table_block.py — RawDataTableBlock pour LUMIÈRE Report Engine.

Affiche les données scalaires du DataStore sous forme de tableau interactif,
avec filtres à la Excel, coloration par colonne, gestion des colonnes visibles
et export CSV.

Usage
-----
# Données depuis le store (toutes les clés → dropdown automatique)
report.data.register("main", df)
report.data.register("yield", df_yield)
report.add(RawDataTableBlock())               # lit toutes les clés du store

# Données depuis une clé spécifique
report.add(RawDataTableBlock(data="main"))

# Avec options
report.add(RawDataTableBlock(
    title="Données brutes",
    hidden_cols_default=["kpi_id", "file_path"],   # colonnes masquées par défaut
    color_enabled_default=False,                   # coloration désactivée par défaut
))
"""
from __future__ import annotations

import html as _h
import json
from typing import Union

import numpy as np
import pandas as pd

from ..._helpers import Block, _safe_json, _is_vector_col
from ..data.data_mixin import DataMixin, DataArg


# ─────────────────────────────────────────────────────────────────────────────
#  Helper
# ─────────────────────────────────────────────────────────────────────────────

def _df_scalar_records(df: pd.DataFrame) -> tuple[list[str], list[dict]]:
    """
    Retourne (cols_scalaires, records) en excluant les colonnes vectorielles.
    Les valeurs NaN/Inf sont remplacées par None.
    """
    scalar_cols = [c for c in df.columns if not _is_vector_col(df[c])]
    records = []
    for _, row in df.iterrows():
        rec: dict = {}
        for col in scalar_cols:
            v = row[col]
            if isinstance(v, float) and (np.isnan(v) or np.isinf(v)):
                rec[col] = None
            else:
                rec[col] = _safe_json(v)
        records.append(rec)
    return scalar_cols, records


# ─────────────────────────────────────────────────────────────────────────────
#  Block
# ─────────────────────────────────────────────────────────────────────────────

class RawDataTableBlock(Block):
    """
    Tableau de données brutes interactif.

    Paramètres
    ----------
    data : str | pd.DataFrame | None
        - None      → lit toutes les clés du store (dropdown si plusieurs)
        - str       → lit uniquement cette clé du store
        - DataFrame → données locales (une seule clé "__local__")
    title : str
        Titre du bloc.
    hidden_cols_default : list[str]
        Colonnes masquées par défaut (l'utilisateur peut les réactiver).
    color_enabled_default : bool
        Coloration par colonne activée ou non par défaut.
    page_size : int
        Nombre de lignes par page (défaut 50).
    num : str
        Numéro/label optionnel affiché dans le titre.
    """

    needs_plotly = False
    needs_marked = False

    def __init__(
        self,
        data: Union[str, pd.DataFrame, None] = None,
        title: str = "Raw Data",
        hidden_cols_default: list[str] | None = None,
        color_enabled_default: bool = False,
        page_size: int = 50,
        num: str = "",
    ):
        self._data_arg = data
        self.title = title
        self.hidden_cols_default = hidden_cols_default or []
        self.color_enabled_default = color_enabled_default
        self.page_size = page_size
        self.num = num
        self._id = f"rdt_{id(self)}"

    # ── Résolution des métadonnées (colonnes uniquement pour path store) ──────

    def _collect_cols(self, store) -> tuple[dict[str, list[str]], dict | None]:
        """
        Retourne (cols_by_key, inline_rows_or_None).

        - df local  : inline_rows = {key: [records]}  (sérialisation nécessaire)
        - clé store : inline_rows = None  (JS lira window.__DATA_STORE__)
        """
        cols_by_key: dict[str, list[str]] = {}
        inline_rows: dict | None = None

        if isinstance(self._data_arg, pd.DataFrame):
            scalar_cols, recs = _df_scalar_records(self._data_arg)
            cols_by_key["__local__"] = scalar_cols
            inline_rows = {"__local__": recs}

        elif isinstance(self._data_arg, str):
            if store is None:
                raise RuntimeError(
                    f"RawDataTableBlock references key {self._data_arg!r} "
                    f"but no DataStore was provided."
                )
            df = store.resolve(self._data_arg)
            cols_by_key[self._data_arg] = [c for c in df.columns if not _is_vector_col(df[c])]

        else:
            # None → toutes les clés du store
            if store is None:
                return {}, None
            for key in store.keys():
                df = store.resolve(key)
                cols_by_key[key] = [c for c in df.columns if not _is_vector_col(df[c])]

        return cols_by_key, inline_rows

    # ── Render ────────────────────────────────────────────────────────────────

    def render(self, store=None) -> str:
        sid = self._id
        cols_by_key, inline_rows = self._collect_cols(store)

        if not cols_by_key:
            return (
                f'<div class="rdt-empty" style="padding:2rem;text-align:center;'
                f'color:var(--slate-400);font-family:var(--fm);">'
                f'Aucune donnée disponible dans le DataStore.</div>'
            )

        cols_json   = json.dumps(cols_by_key)
        # inline_rows = None pour le path store (zéro copie)
        inline_json = json.dumps(inline_rows) if inline_rows is not None else "null"
        hidden_json = json.dumps(self.hidden_cols_default)
        color_default = "true" if self.color_enabled_default else "false"
        page_size = self.page_size
        keys_list = list(cols_by_key.keys())
        first_key = json.dumps(keys_list[0]) if keys_list else '""'
        title_h = _h.escape(self.title)
        num_h = _h.escape(self.num)

        return f"""
<!-- RawDataTableBlock [{sid}] -->
<div class="rdt-wrap" id="{sid}">

  {self._css()}

  <!-- ── Header ── -->
  <div class="rdt-header">
    <div class="rdt-title-row">
      {"<span class='rdt-num'>" + num_h + "</span>" if num_h else ""}
      <span class="rdt-title">{title_h}</span>
      <span class="rdt-badge" id="{sid}-badge">—</span>
    </div>
    <div class="rdt-toolbar">

      <!-- Dropdown dataset (si plusieurs clés) -->
      <div class="rdt-tool-group" id="{sid}-ds-group">
        <label class="rdt-label">Dataset</label>
        <select class="rdt-select" id="{sid}-ds-select"></select>
      </div>

      <!-- Filtre global -->
      <div class="rdt-tool-group">
        <label class="rdt-label">Recherche</label>
        <div class="rdt-search-wrap">
          <span class="rdt-search-icon">⌕</span>
          <input class="rdt-input" id="{sid}-search" type="text" placeholder="Filtrer toutes les colonnes…">
        </div>
      </div>

      <!-- Toggle coloration -->
      <div class="rdt-tool-group">
        <label class="rdt-label">Coloration</label>
        <button class="rdt-toggle-btn" id="{sid}-color-btn" data-active="{str(self.color_enabled_default).lower()}">
          <span class="rdt-toggle-track"><span class="rdt-toggle-thumb"></span></span>
          <span class="rdt-toggle-label" id="{sid}-color-lbl">
            {"On" if self.color_enabled_default else "Off"}
          </span>
        </button>
      </div>

      <!-- Bouton colonnes -->
      <div class="rdt-tool-group">
        <label class="rdt-label">&nbsp;</label>
        <button class="rdt-btn rdt-btn-secondary" id="{sid}-col-btn">
          ⚙ Colonnes
        </button>
      </div>

      <!-- Export CSV -->
      <div class="rdt-tool-group">
        <label class="rdt-label">&nbsp;</label>
        <button class="rdt-btn rdt-btn-primary" id="{sid}-csv-btn">
          ↓ CSV
        </button>
      </div>

    </div>
  </div>

  <!-- ── Table container ── -->
  <div class="rdt-table-wrap" id="{sid}-table-wrap">
    <table class="rdt-table" id="{sid}-table">
      <thead id="{sid}-thead"></thead>
      <tbody id="{sid}-tbody"></tbody>
    </table>
  </div>

  <!-- ── Pagination ── -->
  <div class="rdt-pagination" id="{sid}-pagination">
    <button class="rdt-page-btn" id="{sid}-prev">‹ Préc.</button>
    <span class="rdt-page-info" id="{sid}-page-info"></span>
    <button class="rdt-page-btn" id="{sid}-next">Suiv. ›</button>
  </div>

  <!-- ── Modal colonnes ── -->
  <div class="rdt-modal-overlay" id="{sid}-modal-overlay">
    <div class="rdt-modal">
      <div class="rdt-modal-header">
        <span class="rdt-modal-title">Gérer les colonnes</span>
        <button class="rdt-modal-close" id="{sid}-modal-close">✕</button>
      </div>
      <div class="rdt-modal-body">
        <div class="rdt-modal-actions">
          <button class="rdt-btn rdt-btn-xs" id="{sid}-col-all">Tout afficher</button>
          <button class="rdt-btn rdt-btn-xs" id="{sid}-col-none">Tout masquer</button>
          <button class="rdt-btn rdt-btn-xs" id="{sid}-col-reset">Réinitialiser</button>
        </div>
        <div class="rdt-col-list" id="{sid}-col-list"></div>
      </div>
    </div>
  </div>

</div>

<script>
(function() {{
  var sid      = "{sid}";
  var COLS     = {cols_json};
  var INLINE   = {inline_json};
  var HIDDEN_DEFAULT = {hidden_json};
  var PAGE_SIZE = {page_size};
  var colorEnabled = {color_default};

  // Accès aux lignes : df local (INLINE) ou store global
  function getRows(key) {{
    if (INLINE && INLINE[key]) return INLINE[key];
    return (window.__DATA_STORE__ || {{}})[key] || [];
  }}

  // ── State ──
  var allKeys  = Object.keys(COLS);
  var curKey   = {first_key};
  var curCols  = [];
  var colTypes = {{}};       // col → "num" | "str"
  var hiddenCols = new Set(HIDDEN_DEFAULT);
  var filters  = {{}};       // col → {{value, op}}
  var globalFilter = "";
  var sortCol  = null;
  var sortAsc  = true;
  var page     = 0;
  var filteredRows = [];

  // ── DOM refs ──
  var el = function(id) {{ return document.getElementById(sid + "-" + id); }};
  var tbody   = document.getElementById(sid + "-tbody");
  var thead   = document.getElementById(sid + "-thead");

  // ── Dataset selector ──
  var dsGroup  = document.getElementById(sid + "-ds-group");
  var dsSelect = document.getElementById(sid + "-ds-select");

  if (allKeys.length <= 1) {{
    dsGroup.style.display = "none";
  }} else {{
    allKeys.forEach(function(k) {{
      var opt = document.createElement("option");
      opt.value = k; opt.textContent = k;
      dsSelect.appendChild(opt);
    }});
    dsSelect.value = curKey;
    dsSelect.addEventListener("change", function() {{
      curKey = dsSelect.value;
      hiddenCols = new Set(HIDDEN_DEFAULT);
      filters = {{}};
      globalFilter = "";
      sortCol = null; sortAsc = true; page = 0;
      el("search").value = "";
      load();
    }});
  }}

  // ── Détection des types de colonnes (fait une seule fois au load) ──
  function detectColTypes() {{
    colTypes = {{}};
    var sample = getRows(curKey).slice(0, 50);
    curCols.forEach(function(c) {{
      var isNum = sample.some(function(row) {{ return typeof row[c] === "number"; }});
      colTypes[c] = isNum ? "num" : "str";
    }});
  }}

  // ── Load dataset ──
  function load() {{
    curCols = COLS[curKey];
    detectColTypes();
    renderThead();   // thead rendu une seule fois
    applyFilter();
    renderColModal();
  }}

  // ── Coloration heatmap par colonne ──
  function colMinMax() {{
    var mm = {{}};
    var rows = getRows(curKey);
    curCols.forEach(function(c) {{
      if (colTypes[c] !== "num") return;
      var nums = rows.map(function(r) {{ return r[c]; }}).filter(function(v) {{ return typeof v === "number"; }});
      if (nums.length > 1) {{
        mm[c] = {{ min: Math.min.apply(null, nums), max: Math.max.apply(null, nums) }};
      }}
    }});
    return mm;
  }}

  function heatColor(v, min, max) {{
    if (min === max) return "";
    var t = (v - min) / (max - min);
    var r = Math.round(13  + t * (201 - 13));
    var g = Math.round(27  + t * (168 - 27));
    var b = Math.round(62  + t * (76  - 62));
    return "rgba(" + r + "," + g + "," + b + ",0.18)";
  }}

  // ── Rendu du thead (STABLE — ne recrée pas les inputs à chaque render) ──
  // Les inputs de filtre sont créés une seule fois ; leur valeur est lue
  // directement dans les listeners → pas de problème de listener perdu.
  function renderThead() {{
    thead.innerHTML = "";

    var visCols = curCols.filter(function(c) {{ return !hiddenCols.has(c); }});

    // Row 1 : labels + tri
    var tr1 = document.createElement("tr");
    tr1.id = sid + "-thead-labels";
    visCols.forEach(function(c) {{
      var th = document.createElement("th");
      th.className = "rdt-th";
      th.dataset.col = c;
      var inner = document.createElement("div");
      inner.className = "rdt-th-inner";
      var lbl = document.createElement("span");
      lbl.className = "rdt-th-label";
      lbl.textContent = c;
      inner.appendChild(lbl);
      var arrow = document.createElement("span");
      arrow.className = "rdt-sort-arrow";
      arrow.id = sid + "-arrow-" + c.replace(/[^a-z0-9]/gi, "_");
      inner.appendChild(arrow);
      th.appendChild(inner);
      th.addEventListener("click", function() {{
        if (sortCol === c) {{ sortAsc = !sortAsc; }} else {{ sortCol = c; sortAsc = true; }}
        updateSortArrows();
        applyFilter();
      }});
      tr1.appendChild(th);
    }});
    thead.appendChild(tr1);

    // Row 2 : filtres par colonne
    // Les inputs sont créés une seule fois ici.
    // Ils survivent aux appels de renderTbody() car thead n'est pas retouché.
    var tr2 = document.createElement("tr");
    tr2.className = "rdt-filter-row";
    visCols.forEach(function(c) {{
      var td = document.createElement("th");
      td.className = "rdt-th rdt-th-filter";

      if (colTypes[c] === "num") {{
        var wrap = document.createElement("div");
        wrap.className = "rdt-filter-num";

        var opSel = document.createElement("select");
        opSel.className = "rdt-filter-op";
        opSel.id = sid + "-fop-" + c.replace(/[^a-z0-9]/gi, "_");
        ["=",">",">=","<","<=","!="].forEach(function(op) {{
          var o = document.createElement("option");
          o.value = op; o.textContent = op;
          opSel.appendChild(o);
        }});

        var inp = document.createElement("input");
        inp.className = "rdt-filter-inp";
        inp.type = "number";
        inp.placeholder = "val";
        inp.id = sid + "-finp-" + c.replace(/[^a-z0-9]/gi, "_");

        // Listener unique, lit directement les valeurs courantes des inputs
        (function(col, opEl, inpEl) {{
          function upd() {{
            var v = inpEl.value;
            if (v === "" || v === null) {{
              delete filters[col];
            }} else {{
              filters[col] = {{ op: opEl.value, value: parseFloat(v) }};
            }}
            page = 0;
            applyFilter();
          }}
          opEl.addEventListener("change", upd);
          inpEl.addEventListener("input",  upd);
        }})(c, opSel, inp);

        wrap.appendChild(opSel);
        wrap.appendChild(inp);
        td.appendChild(wrap);
      }} else {{
        var inp2 = document.createElement("input");
        inp2.className = "rdt-filter-inp rdt-filter-str";
        inp2.type = "text";
        inp2.placeholder = "contient…";
        inp2.id = sid + "-finp-" + c.replace(/[^a-z0-9]/gi, "_");

        (function(col, inpEl) {{
          inpEl.addEventListener("input", function() {{
            var v = inpEl.value;
            if (!v) {{ delete filters[col]; }}
            else {{ filters[col] = {{ op: "contains", value: v }}; }}
            page = 0;
            applyFilter();
          }});
        }})(c, inp2);

        td.appendChild(inp2);
      }}

      tr2.appendChild(td);
    }});
    thead.appendChild(tr2);
  }}

  // Met à jour uniquement les flèches de tri sans recréer le thead
  function updateSortArrows() {{
    curCols.forEach(function(c) {{
      var arrowId = sid + "-arrow-" + c.replace(/[^a-z0-9]/gi, "_");
      var arrow = document.getElementById(arrowId);
      if (!arrow) return;
      if (sortCol === c) {{
        arrow.textContent = sortAsc ? " ▲" : " ▼";
      }} else {{
        arrow.textContent = "";
      }}
    }});
  }}

  // ── Filtrage global + par colonne ──
  function applyFilter() {{
    var rows = getRows(curKey);
    var gf = globalFilter.toLowerCase();

    filteredRows = rows.filter(function(row) {{
      // filtre global
      if (gf) {{
        var match = false;
        curCols.forEach(function(c) {{
          if (!hiddenCols.has(c)) {{
            var v = row[c];
            if (v !== null && v !== undefined && String(v).toLowerCase().indexOf(gf) !== -1) match = true;
          }}
        }});
        if (!match) return false;
      }}
      // filtres par colonne
      for (var col in filters) {{
        var f = filters[col];
        if (f.value === "" || f.value === null || f.value === undefined) continue;
        var cell = row[col];
        var fv = f.value;
        if (f.op === "contains") {{
          if (cell === null || cell === undefined) return false;
          if (String(cell).toLowerCase().indexOf(String(fv).toLowerCase()) === -1) return false;
        }} else {{
          var num = parseFloat(cell);
          var fnum = parseFloat(fv);
          if (isNaN(num) || isNaN(fnum)) return false;
          if (f.op === "="  && num !== fnum) return false;
          if (f.op === ">"  && num <= fnum)  return false;
          if (f.op === ">=" && num <  fnum)  return false;
          if (f.op === "<"  && num >= fnum)  return false;
          if (f.op === "<=" && num >  fnum)  return false;
          if (f.op === "!=" && num === fnum) return false;
        }}
      }}
      return true;
    }});

    // tri
    if (sortCol !== null) {{
      var sc = sortCol;
      filteredRows.sort(function(a, b) {{
        var av = a[sc], bv = b[sc];
        if (av === null || av === undefined) av = "";
        if (bv === null || bv === undefined) bv = "";
        var n = typeof av === "number" && typeof bv === "number";
        var cmp = n ? (av - bv) : String(av).localeCompare(String(bv));
        return sortAsc ? cmp : -cmp;
      }});
    }}

    page = 0;
    renderTbody();
  }}

  // ── Rendu tbody uniquement (thead intact) ──
  function renderTbody() {{
    var visCols = curCols.filter(function(c) {{ return !hiddenCols.has(c); }});
    var mm = colorEnabled ? colMinMax() : {{}};
    var total = filteredRows.length;
    var pages = Math.ceil(total / PAGE_SIZE) || 1;
    if (page >= pages) page = pages - 1;
    var start = page * PAGE_SIZE;
    var slice = filteredRows.slice(start, start + PAGE_SIZE);

    // Badge
    document.getElementById(sid + "-badge").textContent =
      total + " ligne" + (total > 1 ? "s" : "") +
      (total < getRows(curKey).length ? " (filtré)" : "");

    // Tbody
    tbody.innerHTML = "";
    if (slice.length === 0) {{
      var emptyTr = document.createElement("tr");
      var emptyTd = document.createElement("td");
      emptyTd.colSpan = visCols.length;
      emptyTd.className = "rdt-empty-row";
      emptyTd.textContent = "Aucune donnée ne correspond aux filtres.";
      emptyTr.appendChild(emptyTd);
      tbody.appendChild(emptyTr);
    }} else {{
      slice.forEach(function(row, ri) {{
        var tr = document.createElement("tr");
        tr.className = (ri % 2 === 0) ? "rdt-row-even" : "rdt-row-odd";
        visCols.forEach(function(c) {{
          var td = document.createElement("td");
          td.className = "rdt-td";
          var v = row[c];
          if (v === null || v === undefined) {{
            td.textContent = "";
            td.classList.add("rdt-null");
          }} else {{
            td.textContent = typeof v === "number"
              ? (Number.isInteger(v) ? v : v.toPrecision(5))
              : v;
            if (colorEnabled && mm[c] && typeof v === "number") {{
              td.style.background = heatColor(v, mm[c].min, mm[c].max);
            }}
          }}
          tr.appendChild(td);
        }});
        tbody.appendChild(tr);
      }});
    }}

    // Pagination
    var pi = document.getElementById(sid + "-page-info");
    pi.textContent = "Page " + (page + 1) + " / " + pages + " · " +
      (start + 1) + "–" + Math.min(start + PAGE_SIZE, total) + " sur " + total;
    el("prev").disabled = page === 0;
    el("next").disabled = page >= pages - 1;
  }}

  // ── Coloration toggle ──
  el("color-btn").addEventListener("click", function() {{
    colorEnabled = !colorEnabled;
    this.dataset.active = colorEnabled ? "true" : "false";
    el("color-lbl").textContent = colorEnabled ? "On" : "Off";
    renderTbody();
  }});

  // ── Recherche globale ──
  el("search").addEventListener("input", function() {{
    globalFilter = this.value;
    page = 0;
    applyFilter();
  }});

  // ── Pagination ──
  el("prev").addEventListener("click", function() {{
    if (page > 0) {{ page--; renderTbody(); }}
  }});
  el("next").addEventListener("click", function() {{
    var pages = Math.ceil(filteredRows.length / PAGE_SIZE);
    if (page < pages - 1) {{ page++; renderTbody(); }}
  }});

  // ── Export CSV ──
  el("csv-btn").addEventListener("click", function() {{
    var visCols = curCols.filter(function(c) {{ return !hiddenCols.has(c); }});
    var rows = filteredRows;
    var lines = [visCols.map(function(c) {{ return JSON.stringify(c); }}).join(",")];
    rows.forEach(function(row) {{
      lines.push(visCols.map(function(c) {{
        var v = row[c];
        if (v === null || v === undefined) return "";
        if (typeof v === "string") return JSON.stringify(v);
        return v;
      }}).join(","));
    }});
    var blob = new Blob([lines.join("\\n")], {{ type: "text/csv;charset=utf-8;" }});
    var url = URL.createObjectURL(blob);
    var a = document.createElement("a");
    a.href = url; a.download = curKey + ".csv"; a.click();
    URL.revokeObjectURL(url);
  }});

  // ── Modal colonnes ──
  el("col-btn").addEventListener("click", function() {{
    el("modal-overlay").classList.add("rdt-modal-open");
  }});
  el("modal-close").addEventListener("click", closeModal);
  el("modal-overlay").addEventListener("click", function(e) {{
    if (e.target === el("modal-overlay")) closeModal();
  }});
  function closeModal() {{
    el("modal-overlay").classList.remove("rdt-modal-open");
  }}

  function renderColModal() {{
    var list = el("col-list");
    list.innerHTML = "";
    curCols.forEach(function(c) {{
      var item = document.createElement("label");
      item.className = "rdt-col-item";
      var cb = document.createElement("input");
      cb.type = "checkbox";
      cb.checked = !hiddenCols.has(c);
      (function(col, checkbox) {{
        checkbox.addEventListener("change", function() {{
          if (checkbox.checked) {{ hiddenCols.delete(col); }}
          else {{ hiddenCols.add(col); }}
          // Reconstruire le thead complet (colonnes visibles ont changé)
          filters = {{}};
          page = 0;
          renderThead();
          applyFilter();
        }});
      }})(c, cb);
      var lbl = document.createElement("span");
      lbl.textContent = c;
      item.appendChild(cb);
      item.appendChild(lbl);
      list.appendChild(item);
    }});
  }}

  el("col-all").addEventListener("click", function() {{
    hiddenCols.clear();
    filters = {{}};
    renderColModal(); renderThead(); page = 0; applyFilter();
  }});
  el("col-none").addEventListener("click", function() {{
    curCols.forEach(function(c) {{ hiddenCols.add(c); }});
    filters = {{}};
    renderColModal(); renderThead(); page = 0; applyFilter();
  }});
  el("col-reset").addEventListener("click", function() {{
    hiddenCols = new Set(HIDDEN_DEFAULT);
    filters = {{}};
    renderColModal(); renderThead(); page = 0; applyFilter();
  }});

  // ── Init ──
  load();
}})();
</script>
"""

    # ── CSS (embarqué une fois par bloc) ─────────────────────────────────────

    def _css(self) -> str:
        return """<style>
/* ══════════════════════════════════════════════════════
   RawDataTableBlock — LUMIÈRE Report Engine
══════════════════════════════════════════════════════ */

/* Wrap principal */
.rdt-wrap {
  font-family: var(--fd, 'DM Sans', sans-serif);
  background: var(--surface, #fff);
  border: 1px solid var(--border, #e2e6f0);
  border-radius: var(--radius, 8px);
  overflow: hidden;
  box-shadow: var(--shadow, 0 1px 3px rgba(13,27,62,.08));
}

/* Header */
.rdt-header {
  padding: 14px 18px 12px;
  border-bottom: 1px solid var(--border, #e2e6f0);
  background: var(--slate-50, #f8f9fc);
}

.rdt-title-row {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 12px;
}

.rdt-num {
  font-family: var(--fm, monospace);
  font-size: 11px;
  color: var(--slate-400, #8892aa);
  background: var(--slate-100, #eef0f6);
  border-radius: 4px;
  padding: 2px 7px;
}

.rdt-title {
  font-family: var(--fm, monospace);
  font-size: 13px;
  font-weight: 500;
  color: var(--navy, #0d1b3e);
  letter-spacing: .02em;
}

.rdt-badge {
  font-family: var(--fm, monospace);
  font-size: 10px;
  color: var(--slate-400, #8892aa);
  background: var(--slate-100, #eef0f6);
  border-radius: 10px;
  padding: 2px 9px;
  margin-left: auto;
}

/* Toolbar */
.rdt-toolbar {
  display: flex;
  align-items: flex-end;
  flex-wrap: wrap;
  gap: 12px;
}

.rdt-tool-group {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.rdt-label {
  font-size: 10px;
  font-family: var(--fm, monospace);
  color: var(--slate-400, #8892aa);
  text-transform: uppercase;
  letter-spacing: .06em;
}

.rdt-select {
  height: 30px;
  padding: 0 28px 0 9px;
  border: 1px solid var(--border, #e2e6f0);
  border-radius: 5px;
  background: var(--surface, #fff);
  font-family: var(--fm, monospace);
  font-size: 12px;
  color: var(--navy, #0d1b3e);
  cursor: pointer;
  appearance: none;
  background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='10' height='6'%3E%3Cpath d='M0 0l5 6 5-6z' fill='%238892aa'/%3E%3C/svg%3E");
  background-repeat: no-repeat;
  background-position: right 8px center;
}

.rdt-search-wrap {
  position: relative;
}
.rdt-search-icon {
  position: absolute;
  left: 8px;
  top: 50%;
  transform: translateY(-50%);
  color: var(--slate-400, #8892aa);
  font-size: 14px;
  pointer-events: none;
}
.rdt-input {
  height: 30px;
  width: 220px;
  padding: 0 9px 0 28px;
  border: 1px solid var(--border, #e2e6f0);
  border-radius: 5px;
  font-family: var(--fm, monospace);
  font-size: 12px;
  color: var(--navy, #0d1b3e);
  background: var(--surface, #fff);
  outline: none;
  transition: border-color .15s;
}
.rdt-input:focus { border-color: var(--gold, #c9a84c); }

/* Toggle coloration */
.rdt-toggle-btn {
  display: flex;
  align-items: center;
  gap: 7px;
  background: none;
  border: none;
  cursor: pointer;
  padding: 0;
}
.rdt-toggle-track {
  width: 36px;
  height: 20px;
  background: var(--slate-200, #d8dce8);
  border-radius: 10px;
  position: relative;
  transition: background .2s;
}
.rdt-toggle-btn[data-active="true"] .rdt-toggle-track {
  background: var(--gold, #c9a84c);
}
.rdt-toggle-thumb {
  position: absolute;
  left: 2px;
  top: 2px;
  width: 16px;
  height: 16px;
  background: #fff;
  border-radius: 50%;
  transition: transform .2s;
  box-shadow: 0 1px 3px rgba(0,0,0,.2);
}
.rdt-toggle-btn[data-active="true"] .rdt-toggle-thumb {
  transform: translateX(16px);
}
.rdt-toggle-label {
  font-family: var(--fm, monospace);
  font-size: 11px;
  color: var(--slate-600, #4a5568);
  min-width: 20px;
}

/* Boutons */
.rdt-btn {
  height: 30px;
  padding: 0 13px;
  border-radius: 5px;
  font-family: var(--fm, monospace);
  font-size: 11px;
  font-weight: 500;
  letter-spacing: .03em;
  cursor: pointer;
  border: none;
  white-space: nowrap;
  transition: opacity .15s, transform .1s;
}
.rdt-btn:hover { opacity: .85; transform: translateY(-1px); }
.rdt-btn-primary {
  background: var(--navy, #0d1b3e);
  color: var(--gold-l, #e8c97a);
}
.rdt-btn-secondary {
  background: var(--slate-100, #eef0f6);
  color: var(--navy, #0d1b3e);
  border: 1px solid var(--border, #e2e6f0);
}
.rdt-btn-xs {
  height: 24px;
  padding: 0 9px;
  font-size: 10px;
  background: var(--slate-100, #eef0f6);
  color: var(--navy, #0d1b3e);
  border: 1px solid var(--border, #e2e6f0);
}

/* Table container */
.rdt-table-wrap {
  overflow-x: auto;
  max-height: 520px;
  overflow-y: auto;
}

.rdt-table {
  width: 100%;
  border-collapse: collapse;
  font-family: var(--fm, monospace);
  font-size: 11.5px;
}

/* Thead sticky */
.rdt-table thead {
  position: sticky;
  top: 0;
  z-index: 10;
}

.rdt-th {
  background: var(--navy, #0d1b3e);
  color: var(--slate-100, #eef0f6);
  padding: 8px 10px;
  text-align: left;
  white-space: nowrap;
  cursor: pointer;
  border-right: 1px solid var(--navy-l, #1a2f6a);
  user-select: none;
  font-size: 11px;
  font-weight: 500;
  letter-spacing: .03em;
}
.rdt-th:hover { background: var(--navy-l, #1a2f6a); }
.rdt-th-inner {
  display: flex;
  align-items: center;
  gap: 4px;
}
.rdt-sort-arrow { color: var(--gold, #c9a84c); }

/* Filtre row */
.rdt-th-filter {
  background: var(--navy-d, #0a1530);
  padding: 5px 6px;
  cursor: default;
}
.rdt-th-filter:hover { background: var(--navy-d, #0a1530); }

.rdt-filter-num {
  display: flex;
  gap: 3px;
}
.rdt-filter-op {
  width: 44px;
  height: 22px;
  font-size: 10px;
  font-family: var(--fm, monospace);
  border: 1px solid var(--navy-l, #1a2f6a);
  background: var(--navy-m, #122052);
  color: var(--slate-100, #eef0f6);
  border-radius: 3px;
  padding: 0 2px;
}
.rdt-filter-inp {
  height: 22px;
  padding: 0 5px;
  font-size: 10px;
  font-family: var(--fm, monospace);
  border: 1px solid var(--navy-l, #1a2f6a);
  background: var(--navy-m, #122052);
  color: var(--slate-100, #eef0f6);
  border-radius: 3px;
  outline: none;
  min-width: 0;
}
.rdt-filter-str { width: 100%; }
.rdt-filter-inp:focus { border-color: var(--gold, #c9a84c); }
/* Fix number input arrows */
.rdt-filter-inp[type=number] { width: 70px; -moz-appearance: textfield; }
.rdt-filter-inp[type=number]::-webkit-inner-spin-button { opacity: .4; }

/* Tbody */
.rdt-td {
  padding: 5px 10px;
  border-bottom: 1px solid var(--slate-100, #eef0f6);
  border-right: 1px solid var(--slate-100, #eef0f6);
  white-space: nowrap;
  color: var(--text, #0d1b3e);
  font-size: 11.5px;
  transition: background .15s;
}
.rdt-row-even { background: var(--surface, #fff); }
.rdt-row-odd  { background: var(--slate-50, #f8f9fc); }
.rdt-row-even:hover td, .rdt-row-odd:hover td {
  background: rgba(201,168,76,.08) !important;
}
.rdt-null { color: var(--slate-400, #8892aa); }

.rdt-empty-row {
  text-align: center;
  padding: 40px;
  color: var(--slate-400, #8892aa);
  font-family: var(--fm, monospace);
  font-size: 12px;
}

/* Pagination */
.rdt-pagination {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 16px;
  padding: 10px 18px;
  border-top: 1px solid var(--border, #e2e6f0);
  background: var(--slate-50, #f8f9fc);
}
.rdt-page-btn {
  height: 28px;
  padding: 0 12px;
  border-radius: 5px;
  border: 1px solid var(--border, #e2e6f0);
  background: var(--surface, #fff);
  font-family: var(--fm, monospace);
  font-size: 11px;
  cursor: pointer;
  color: var(--navy, #0d1b3e);
  transition: background .15s;
}
.rdt-page-btn:hover:not(:disabled) { background: var(--slate-100, #eef0f6); }
.rdt-page-btn:disabled { opacity: .35; cursor: default; }
.rdt-page-info {
  font-family: var(--fm, monospace);
  font-size: 11px;
  color: var(--slate-400, #8892aa);
}

/* Modal */
.rdt-modal-overlay {
  display: none;
  position: fixed;
  inset: 0;
  background: rgba(10,12,18,.6);
  z-index: 99000;
  align-items: center;
  justify-content: center;
  backdrop-filter: blur(3px);
}
.rdt-modal-overlay.rdt-modal-open {
  display: flex;
}
.rdt-modal {
  background: var(--surface, #fff);
  border: 1px solid var(--border, #e2e6f0);
  border-radius: 10px;
  width: min(440px, 90vw);
  max-height: 80vh;
  display: flex;
  flex-direction: column;
  box-shadow: 0 20px 60px rgba(13,27,62,.25);
}
.rdt-modal-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 14px 18px;
  border-bottom: 1px solid var(--border, #e2e6f0);
  background: var(--navy, #0d1b3e);
  border-radius: 10px 10px 0 0;
}
.rdt-modal-title {
  font-family: var(--fm, monospace);
  font-size: 12px;
  font-weight: 500;
  color: var(--gold-l, #e8c97a);
  letter-spacing: .04em;
}
.rdt-modal-close {
  background: none;
  border: none;
  color: var(--slate-400, #8892aa);
  font-size: 16px;
  cursor: pointer;
  line-height: 1;
  padding: 2px;
}
.rdt-modal-close:hover { color: #fff; }
.rdt-modal-body {
  padding: 14px 18px;
  overflow-y: auto;
  flex: 1;
}
.rdt-modal-actions {
  display: flex;
  gap: 8px;
  margin-bottom: 12px;
  flex-wrap: wrap;
}
.rdt-col-list {
  display: flex;
  flex-direction: column;
  gap: 2px;
}
.rdt-col-item {
  display: flex;
  align-items: center;
  gap: 9px;
  padding: 6px 8px;
  border-radius: 5px;
  cursor: pointer;
  font-family: var(--fm, monospace);
  font-size: 11.5px;
  color: var(--navy, #0d1b3e);
  transition: background .12s;
}
.rdt-col-item:hover { background: var(--slate-50, #f8f9fc); }
.rdt-col-item input[type=checkbox] {
  accent-color: var(--gold, #c9a84c);
  width: 14px;
  height: 14px;
  cursor: pointer;
  flex-shrink: 0;
}
</style>"""