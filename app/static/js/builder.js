"use strict";
/**
 * builder.js — Report Builder (vanilla JS, zéro dépendance).
 *
 * État en mémoire (`state`) = la config compilée par l'API :
 *   { meta:{title,subtitle,author}, main_dataset, pages:[...] }
 * Une page (= un onglet du builder) est soit :
 *   basique : { name, layout:"basic", blocks:[{type,params}, ...] }
 *   grille  : { name, layout:"grid",  rows:[{ncols, cells:[{type,params}|null, ...]}] }
 */

// ── État global ──────────────────────────────────────────────────────────
const state = {
  meta: { title: "Rapport", subtitle: "", author: "" },
  main_dataset: "",
  datasets: [],       // [{key, rows, columns:[{name,dtype}]}]
  registry: {},        // {category: [{name,category,description,usable,unusable_reason,params:[...]}]}
  pages: [{ name: "Page 1", layout: "basic", blocks: [] }],
  activePage: 0,
  reportId: null,
  reportName: "",
};

let libraryTarget = null;   // callback(blockType) appelé quand on choisit un bloc dans la modale

// ── Helpers API ──────────────────────────────────────────────────────────
async function api(method, url, body) {
  const opts = { method, headers: {} };
  if (body !== undefined) {
    opts.headers["Content-Type"] = "application/json";
    opts.body = JSON.stringify(body);
  }
  const res = await fetch(url, opts);
  if (!res.ok) {
    let msg = res.statusText;
    try { const j = await res.json(); msg = j.detail || msg; } catch (e) { /* not json */ }
    throw new Error(msg);
  }
  const ct = res.headers.get("content-type") || "";
  if (ct.includes("application/json")) return res.json();
  return res.text();
}

function toast(msg, isError) {
  const el = document.getElementById("toast");
  el.textContent = msg;
  el.className = "bld-toast" + (isError ? " error" : "");
  el.hidden = false;
  clearTimeout(toast._t);
  toast._t = setTimeout(() => { el.hidden = true; }, isError ? 6000 : 3000);
}

function currentDatasetColumns() {
  const ds = state.datasets.find(d => d.key === state.main_dataset);
  return ds ? ds.columns.map(c => c.name) : [];
}

function findBlockSpec(type) {
  for (const cat of Object.values(state.registry)) {
    const found = cat.find(b => b.name === type);
    if (found) return found;
  }
  return null;
}

function defaultParamsFor(spec) {
  const params = {};
  for (const p of spec.params) {
    if (p.kind === "kpi_list") { params[p.name] = []; continue; }
    if (p.required) {
      params[p.name] = p.kind === "column" || p.kind === "dataset_ref" ? "" : (p.kind === "bool" ? false : "");
    }
    // les params optionnels sans valeur ne sont pas envoyés -> le bloc garde son défaut
  }
  return params;
}

// ── Chargement initial ───────────────────────────────────────────────────
async function init() {
  bindHeaderEvents();
  bindModalCloseEvents();
  try {
    state.registry = await api("GET", "/api/blocks");
  } catch (e) { toast("Impossible de charger la bibliothèque de blocs : " + e.message, true); }
  await refreshDatasets();
  renderAll();
}

async function refreshDatasets(selectKey) {
  try {
    state.datasets = await api("GET", "/api/datasets");
  } catch (e) { toast("Impossible de charger les datasets : " + e.message, true); return; }
  const sel = document.getElementById("f-dataset");
  sel.innerHTML = '<option value="">— Choisir un dataset —</option>' +
    state.datasets.map(d => `<option value="${escapeHtml(d.key)}">${escapeHtml(d.key)} (${d.rows} lignes)</option>`).join("");
  if (selectKey) state.main_dataset = selectKey;
  if (state.main_dataset && state.datasets.some(d => d.key === state.main_dataset)) {
    sel.value = state.main_dataset;
  } else if (state.datasets.length && !state.main_dataset) {
    state.main_dataset = state.datasets[0].key;
    sel.value = state.main_dataset;
  }
}

function escapeHtml(s) {
  return String(s ?? "").replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}

// ── Header : dataset / meta / actions ────────────────────────────────────
function bindHeaderEvents() {
  document.getElementById("f-title").addEventListener("input", e => state.meta.title = e.target.value);
  document.getElementById("f-subtitle").addEventListener("input", e => state.meta.subtitle = e.target.value);
  document.getElementById("f-author").addEventListener("input", e => state.meta.author = e.target.value);
  document.getElementById("f-title").value = state.meta.title;

  document.getElementById("f-dataset").addEventListener("change", e => {
    state.main_dataset = e.target.value;
    renderAll(); // les <select> de colonnes doivent se rafraîchir
  });

  document.getElementById("btn-upload").addEventListener("click", () => document.getElementById("f-upload-file").click());
  document.getElementById("f-upload-file").addEventListener("change", async e => {
    const file = e.target.files[0];
    if (!file) return;
    const fd = new FormData();
    fd.append("file", file);
    try {
      const res = await fetch("/api/datasets", { method: "POST", body: fd });
      if (!res.ok) { const j = await res.json().catch(() => ({})); throw new Error(j.detail || res.statusText); }
      const { key } = await res.json();
      await refreshDatasets(key);
      renderAll();
      toast(`Dataset "${key}" chargé.`);
    } catch (err) {
      toast("Upload échoué : " + err.message, true);
    } finally {
      e.target.value = "";
    }
  });

  document.getElementById("btn-preview").addEventListener("click", onPreview);
  document.getElementById("btn-save").addEventListener("click", onOpenSaveModal);
  document.getElementById("btn-load").addEventListener("click", onOpenLoadModal);
  document.getElementById("btn-export").addEventListener("click", onExport);

  document.getElementById("save-confirm").addEventListener("click", onConfirmSave);
}

function bindModalCloseEvents() {
  document.querySelectorAll("[data-close-modal]").forEach(btn => {
    btn.addEventListener("click", () => btn.closest(".bld-modal-overlay").hidden = true);
  });
  document.querySelectorAll(".bld-modal-overlay").forEach(ov => {
    ov.addEventListener("click", e => { if (e.target === ov) ov.hidden = true; });
  });
}

function buildConfig() {
  return {
    meta: { ...state.meta },
    main_dataset: state.main_dataset,
    pages: state.pages.map(p => {
      if (p.layout === "grid") {
        return { name: p.name, layout: "grid", rows: p.rows.map(r => ({ ncols: r.ncols, cells: r.cells.slice(0, r.ncols) })) };
      }
      return { name: p.name, layout: "basic", blocks: p.blocks };
    }),
  };
}

async function onPreview() {
  if (!state.main_dataset) { toast("Choisis d'abord un dataset.", true); return; }
  try {
    const html = await api("POST", "/api/reports/preview", buildConfig());
    const blob = new Blob([html], { type: "text/html" });
    const url = URL.createObjectURL(blob);
    window.open(url, "_blank");
    setTimeout(() => URL.revokeObjectURL(url), 30000);
  } catch (e) {
    toast("Aperçu impossible : " + e.message, true);
  }
}

function onOpenSaveModal() {
  document.getElementById("save-name").value = state.reportName || state.meta.title || "";
  document.getElementById("modal-save").hidden = false;
}

async function onConfirmSave() {
  const name = document.getElementById("save-name").value.trim();
  if (!name) { toast("Donne un nom au rapport.", true); return; }
  try {
    const { id } = await api("POST", "/api/reports", {
      id: state.reportId, name, config: buildConfig(),
    });
    state.reportId = id;
    state.reportName = name;
    document.getElementById("modal-save").hidden = true;
    toast(`Rapport "${name}" enregistré.`);
  } catch (e) {
    toast("Échec de l'enregistrement : " + e.message, true);
  }
}

async function onOpenLoadModal() {
  document.getElementById("modal-open").hidden = false;
  const list = document.getElementById("open-list");
  list.innerHTML = '<div class="bld-field-hint">Chargement…</div>';
  try {
    const reports = await api("GET", "/api/reports");
    if (!reports.length) { list.innerHTML = '<div class="bld-field-hint">Aucun rapport enregistré.</div>'; return; }
    list.innerHTML = "";
    for (const r of reports) {
      const row = document.createElement("div");
      row.className = "bld-open-item";
      row.innerHTML = `
        <div>
          <div class="bld-open-item-name">${escapeHtml(r.name)}</div>
          <div class="bld-open-item-meta">${escapeHtml(r.title || "")} · ${escapeHtml(r.updated_at || "")}</div>
        </div>
        <div class="bld-open-item-spacer"></div>
        <button class="bld-btn bld-btn-sm bld-btn-danger" data-del="${r.id}">Supprimer</button>
      `;
      row.addEventListener("click", (e) => {
        if (e.target.closest("[data-del]")) return;
        loadReport(r.id);
      });
      row.querySelector("[data-del]").addEventListener("click", async (e) => {
        e.stopPropagation();
        if (!confirm(`Supprimer "${r.name}" ?`)) return;
        try { await api("DELETE", `/api/reports/${r.id}`); onOpenLoadModal(); }
        catch (err) { toast("Suppression échouée : " + err.message, true); }
      });
      list.appendChild(row);
    }
  } catch (e) {
    list.innerHTML = `<div class="bld-field-error">${escapeHtml(e.message)}</div>`;
  }
}

async function loadReport(id) {
  try {
    const cfg = await api("GET", `/api/reports/${id}`);
    const bm = cfg._meta_builder || {};
    state.reportId = id;
    state.reportName = bm.name || id;
    state.meta = cfg.meta || { title: "Rapport", subtitle: "", author: "" };
    state.main_dataset = cfg.main_dataset || "";
    state.pages = (cfg.pages || []).map(p => normalizePage(p));
    if (!state.pages.length) state.pages = [{ name: "Page 1", layout: "basic", blocks: [] }];
    state.activePage = 0;
    document.getElementById("f-title").value = state.meta.title || "";
    document.getElementById("f-subtitle").value = state.meta.subtitle || "";
    document.getElementById("f-author").value = state.meta.author || "";
    document.getElementById("modal-open").hidden = true;
    renderAll();
    toast(`Rapport "${state.reportName}" chargé.`);
  } catch (e) {
    toast("Chargement échoué : " + e.message, true);
  }
}

function normalizePage(p) {
  if (p.layout === "grid") {
    return { name: p.name || "Page", layout: "grid", rows: (p.rows || []).map(r => ({ ncols: r.ncols || (r.cells || []).length || 1, cells: r.cells || [] })) };
  }
  return { name: p.name || "Page", layout: "basic", blocks: p.blocks || [] };
}

async function onExport() {
  if (!state.reportId) {
    toast("Enregistre d'abord le rapport avant d'exporter.", true);
    onOpenSaveModal();
    return;
  }
  try {
    // Sauvegarde silencieuse de l'état courant sous le même id avant export
    await api("POST", "/api/reports", { id: state.reportId, name: state.reportName, config: buildConfig() });
    const res = await fetch(`/api/reports/${state.reportId}/generate`, { method: "POST" });
    if (!res.ok) { const j = await res.json().catch(() => ({})); throw new Error(j.detail || res.statusText); }
    const blob = await res.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url; a.download = `${state.reportId}.html`;
    document.body.appendChild(a); a.click(); a.remove();
    setTimeout(() => URL.revokeObjectURL(url), 10000);
  } catch (e) {
    toast("Export échoué : " + e.message, true);
  }
}

// ── Rendu : onglets + canvas ──────────────────────────────────────────────
function renderAll() {
  renderTabs();
  renderCanvas();
}

function renderTabs() {
  const nav = document.getElementById("page-tabs");
  nav.innerHTML = "";
  state.pages.forEach((page, i) => {
    const tab = document.createElement("div");
    tab.className = "bld-tab" + (i === state.activePage ? " active" : "");
    tab.innerHTML = `
      <input class="bld-tab-name" value="${escapeHtml(page.name)}" size="${Math.max(4, page.name.length)}">
      <span class="bld-tab-del" title="Supprimer l'onglet">✕</span>
    `;
    tab.addEventListener("click", (e) => {
      if (e.target.closest(".bld-tab-del") || e.target.tagName === "INPUT") return;
      state.activePage = i; renderAll();
    });
    tab.querySelector("input").addEventListener("input", e => { page.name = e.target.value; });
    tab.querySelector("input").addEventListener("click", e => e.stopPropagation());
    tab.querySelector(".bld-tab-del").addEventListener("click", (e) => {
      e.stopPropagation();
      if (state.pages.length === 1) { toast("Il doit rester au moins un onglet.", true); return; }
      if (!confirm(`Supprimer l'onglet "${page.name}" ?`)) return;
      state.pages.splice(i, 1);
      if (state.activePage >= state.pages.length) state.activePage = state.pages.length - 1;
      renderAll();
    });
    nav.appendChild(tab);
  });
  const add = document.createElement("div");
  add.className = "bld-tab-add";
  add.textContent = "+";
  add.title = "Ajouter un onglet";
  add.addEventListener("click", () => {
    state.pages.push({ name: `Page ${state.pages.length + 1}`, layout: "basic", blocks: [] });
    state.activePage = state.pages.length - 1;
    renderAll();
  });
  nav.appendChild(add);
}

function renderCanvas() {
  const canvas = document.getElementById("canvas");
  canvas.innerHTML = "";
  const page = state.pages[state.activePage];
  if (!page) return;

  const toggle = document.createElement("div");
  toggle.className = "bld-layout-toggle";
  toggle.innerHTML = `
    <button data-mode="basic" class="${page.layout === "basic" ? "active" : ""}">Basique</button>
    <button data-mode="grid"  class="${page.layout === "grid"  ? "active" : ""}">Grille</button>
  `;
  toggle.querySelectorAll("button").forEach(btn => {
    btn.addEventListener("click", () => {
      const mode = btn.dataset.mode;
      if (mode === page.layout) return;
      if (mode === "grid") { page.layout = "grid"; page.rows = page.rows || []; }
      else { page.layout = "basic"; page.blocks = page.blocks || []; }
      renderCanvas();
    });
  });
  canvas.appendChild(toggle);

  if (page.layout === "grid") renderGridPage(canvas, page);
  else renderBasicPage(canvas, page);
}

function renderBasicPage(canvas, page) {
  page.blocks.forEach((blockCfg, idx) => {
    canvas.appendChild(renderBlockCard(blockCfg, {
      onRemove: () => { page.blocks.splice(idx, 1); renderCanvas(); },
      onMoveUp: idx > 0 ? () => { swap(page.blocks, idx, idx - 1); renderCanvas(); } : null,
      onMoveDown: idx < page.blocks.length - 1 ? () => { swap(page.blocks, idx, idx + 1); renderCanvas(); } : null,
    }));
  });
  const addBtn = document.createElement("button");
  addBtn.className = "bld-add-block-btn";
  addBtn.textContent = "+ Ajouter un bloc";
  addBtn.addEventListener("click", () => openLibrary((type) => {
    const spec = findBlockSpec(type);
    page.blocks.push({ type, params: defaultParamsFor(spec) });
    renderCanvas();
  }));
  canvas.appendChild(addBtn);
}

function renderGridPage(canvas, page) {
  page.rows = page.rows || [];
  page.rows.forEach((row, rIdx) => {
    const rowEl = document.createElement("div");
    rowEl.className = "bld-row";

    const head = document.createElement("div");
    head.className = "bld-row-head";
    head.innerHTML = `
      <label>Ligne ${rIdx + 1} —</label>
      <select class="bld-select-ncols">
        ${[1, 2, 3, 4].map(n => `<option value="${n}" ${n === row.ncols ? "selected" : ""}>${n} colonne${n > 1 ? "s" : ""}</option>`).join("")}
      </select>
      <span class="bld-block-headspacer"></span>
      <button class="bld-block-headbtn danger" data-del-row title="Supprimer la ligne">✕</button>
    `;
    head.querySelector(".bld-select-ncols").addEventListener("change", (e) => {
      const n = parseInt(e.target.value, 10);
      row.ncols = n;
      const cells = row.cells || [];
      while (cells.length < n) cells.push(null);
      row.cells = cells.slice(0, Math.max(n, cells.length));
      renderCanvas();
    });
    head.querySelector("[data-del-row]").addEventListener("click", () => {
      if (!confirm("Supprimer cette ligne ?")) return;
      page.rows.splice(rIdx, 1);
      renderCanvas();
    });
    rowEl.appendChild(head);

    const cellsEl = document.createElement("div");
    cellsEl.className = "bld-row-cells";
    cellsEl.style.gridTemplateColumns = `repeat(${row.ncols}, 1fr)`;
    row.cells = row.cells || [];
    while (row.cells.length < row.ncols) row.cells.push(null);

    for (let c = 0; c < row.ncols; c++) {
      const cellWrap = document.createElement("div");
      cellWrap.className = "bld-row-cell";
      const cellCfg = row.cells[c];
      if (cellCfg) {
        cellWrap.appendChild(renderBlockCard(cellCfg, {
          onRemove: () => { row.cells[c] = null; renderCanvas(); },
        }));
      } else {
        const addBtn = document.createElement("button");
        addBtn.className = "bld-add-block-btn";
        addBtn.textContent = "+ ajouter";
        addBtn.addEventListener("click", () => openLibrary((type) => {
          const spec = findBlockSpec(type);
          row.cells[c] = { type, params: defaultParamsFor(spec) };
          renderCanvas();
        }));
        cellWrap.appendChild(addBtn);
      }
      cellsEl.appendChild(cellWrap);
    }
    rowEl.appendChild(cellsEl);
    canvas.appendChild(rowEl);
  });

  const addRowBtn = document.createElement("button");
  addRowBtn.className = "bld-add-block-btn";
  addRowBtn.textContent = "+ Ajouter une ligne";
  addRowBtn.addEventListener("click", () => {
    page.rows.push({ ncols: 2, cells: [null, null] });
    renderCanvas();
  });
  canvas.appendChild(addRowBtn);
}

function swap(arr, i, j) { const t = arr[i]; arr[i] = arr[j]; arr[j] = t; }

// ── Carte de bloc + formulaire de paramètres ─────────────────────────────
function renderBlockCard(blockCfg, { onRemove, onMoveUp, onMoveDown }) {
  const spec = findBlockSpec(blockCfg.type);
  const card = document.createElement("div");
  card.className = "bld-block-card";

  const head = document.createElement("div");
  head.className = "bld-block-head";
  head.innerHTML = `
    <span class="bld-block-dot"></span>
    <span class="bld-block-type">${escapeHtml(blockCfg.type)}</span>
    <span class="bld-block-cat">${escapeHtml(spec ? spec.category : "?")}</span>
    <span class="bld-block-headspacer"></span>
    ${onMoveUp ? '<button class="bld-block-headbtn" data-up title="Monter">↑</button>' : ""}
    ${onMoveDown ? '<button class="bld-block-headbtn" data-down title="Descendre">↓</button>' : ""}
    <button class="bld-block-headbtn danger" data-remove title="Retirer">✕</button>
  `;
  const body = document.createElement("div");
  body.className = "bld-block-body";
  if (spec) body.appendChild(renderParamForm(spec, blockCfg.params));
  else body.innerHTML = `<div class="bld-field-error">Bloc inconnu du registre : ${escapeHtml(blockCfg.type)}</div>`;

  head.addEventListener("click", (e) => {
    if (e.target.closest("button")) return;
    body.classList.toggle("open");
  });
  if (onMoveUp) head.querySelector("[data-up]").addEventListener("click", (e) => { e.stopPropagation(); onMoveUp(); });
  if (onMoveDown) head.querySelector("[data-down]").addEventListener("click", (e) => { e.stopPropagation(); onMoveDown(); });
  head.querySelector("[data-remove]").addEventListener("click", (e) => { e.stopPropagation(); onRemove(); });

  card.appendChild(head);
  card.appendChild(body);
  // Un bloc fraîchement ajouté s'ouvre directement pour configuration
  if (!blockCfg._seen) { blockCfg._seen = true; body.classList.add("open"); }
  return card;
}

function renderParamForm(spec, params) {
  const wrap = document.createElement("div");
  wrap.style.display = "flex";
  wrap.style.flexDirection = "column";
  wrap.style.gap = "10px";

  if (!spec.params.length) {
    const p = document.createElement("div");
    p.className = "bld-field-hint";
    p.textContent = "Ce bloc n'a pas de paramètre à configurer.";
    wrap.appendChild(p);
    return wrap;
  }

  for (const p of spec.params) {
    wrap.appendChild(renderField(p, params));
  }
  return wrap;
}

function renderField(p, params) {
  const field = document.createElement("div");
  field.className = "bld-field";
  const label = document.createElement("label");
  label.className = "bld-label";
  label.innerHTML = p.name + (p.required ? '<span class="req">*</span>' : "");
  field.appendChild(label);

  const columns = currentDatasetColumns();
  const setVal = (v) => { params[p.name] = v; };
  const curVal = params[p.name];

  let input;
  switch (p.kind) {
    case "bool": {
      const row = document.createElement("div");
      row.className = "bld-field-row bld-field-check";
      input = document.createElement("input");
      input.type = "checkbox";
      input.checked = curVal !== undefined ? !!curVal : !!p.default;
      input.addEventListener("change", () => setVal(input.checked));
      row.appendChild(input);
      field.replaceChildren(row);
      row.prepend(label);
      return field;
    }
    case "column": {
      input = document.createElement("select");
      input.className = "bld-select";
      input.innerHTML = '<option value="">—</option>' + columns.map(c => `<option value="${escapeHtml(c)}">${escapeHtml(c)}</option>`).join("");
      input.value = curVal || "";
      input.addEventListener("change", () => setVal(input.value));
      break;
    }
    case "dataset_ref": {
      input = document.createElement("select");
      input.className = "bld-select";
      input.innerHTML = '<option value="">—</option>' + state.datasets.map(d => `<option value="${escapeHtml(d.key)}">${escapeHtml(d.key)}</option>`).join("");
      input.value = curVal || "";
      input.addEventListener("change", () => setVal(input.value));
      break;
    }
    case "column_multi": {
      input = document.createElement("input");
      input.className = "bld-input";
      input.type = "text";
      input.placeholder = "col1, col2, …";
      input.value = Array.isArray(curVal) ? curVal.join(", ") : (curVal || "");
      input.addEventListener("input", () => {
        const list = input.value.split(",").map(s => s.trim()).filter(Boolean);
        setVal(list.length ? list : undefined);
      });
      const hint = document.createElement("div");
      hint.className = "bld-field-hint";
      hint.textContent = columns.length ? `Colonnes disponibles : ${columns.join(", ")}` : "";
      field.appendChild(input);
      field.appendChild(hint);
      return field;
    }
    case "range": {
      const row = document.createElement("div");
      row.className = "bld-field-row";
      const lo = document.createElement("input"); lo.className = "bld-input"; lo.type = "number"; lo.placeholder = "min";
      const hi = document.createElement("input"); hi.className = "bld-input"; hi.type = "number"; hi.placeholder = "max";
      if (Array.isArray(curVal)) { lo.value = curVal[0] ?? ""; hi.value = curVal[1] ?? ""; }
      const update = () => {
        if (lo.value === "" && hi.value === "") { setVal(undefined); return; }
        setVal([lo.value === "" ? null : Number(lo.value), hi.value === "" ? null : Number(hi.value)]);
      };
      lo.addEventListener("input", update); hi.addEventListener("input", update);
      row.appendChild(lo); row.appendChild(hi);
      field.appendChild(row);
      return field;
    }
    case "int":
    case "float": {
      input = document.createElement("input");
      input.className = "bld-input";
      input.type = "number";
      if (p.kind === "float") input.step = "any";
      input.value = curVal !== undefined ? curVal : (p.default ?? "");
      input.addEventListener("input", () => setVal(input.value === "" ? undefined : Number(input.value)));
      break;
    }
    case "kpi_list": {
      field.appendChild(renderKpiListField(curVal || [], setVal));
      return field;
    }
    case "json": {
      input = document.createElement("textarea");
      const initial = curVal !== undefined ? curVal : p.default;
      input.value = typeof initial === "string" ? initial : (initial !== undefined && initial !== null ? JSON.stringify(initial, null, 2) : "");
      input.placeholder = "JSON (ex: [\"a\", \"b\"] ou {\"x\": 1})";
      const err = document.createElement("div");
      err.className = "bld-field-error";
      input.addEventListener("input", () => {
        const raw = input.value.trim();
        if (!raw) { setVal(undefined); err.textContent = ""; return; }
        try { setVal(JSON.parse(raw)); err.textContent = ""; }
        catch (e) { setVal(raw); err.textContent = "JSON invalide — la valeur brute sera envoyée telle quelle."; }
      });
      field.appendChild(input);
      field.appendChild(err);
      return field;
    }
    default: {
      input = document.createElement("input");
      input.className = "bld-input";
      input.type = "text";
      input.value = curVal !== undefined ? curVal : (p.default ?? "");
      input.addEventListener("input", () => setVal(input.value === "" ? undefined : input.value));
    }
  }
  field.appendChild(input);
  return field;
}

function renderKpiListField(kpis, setVal) {
  const wrap = document.createElement("div");
  wrap.style.display = "flex";
  wrap.style.flexDirection = "column";
  wrap.style.gap = "6px";

  const list = [...kpis];
  const redraw = () => {
    wrap.innerHTML = "";
    const header = document.createElement("div");
    header.className = "bld-kpi-row";
    header.innerHTML = ["Label", "Valeur", "Unité", "Delta", "Sous-titre", ""]
      .map(h => `<span class="bld-field-hint">${h}</span>`).join("");
    wrap.appendChild(header);

    list.forEach((kpi, i) => {
      const row = document.createElement("div");
      row.className = "bld-kpi-row";
      const mk = (key, ph) => {
        const inp = document.createElement("input");
        inp.className = "bld-input"; inp.placeholder = ph || "";
        inp.value = kpi[key] ?? "";
        inp.addEventListener("input", () => { kpi[key] = inp.value; setVal(list); });
        return inp;
      };
      row.appendChild(mk("label", "LEDs"));
      row.appendChild(mk("value", "600"));
      row.appendChild(mk("unit", "%"));
      row.appendChild(mk("delta", "+5%"));
      row.appendChild(mk("subtitle", ""));
      const del = document.createElement("button");
      del.className = "bld-block-headbtn danger"; del.textContent = "✕";
      del.addEventListener("click", () => { list.splice(i, 1); setVal(list); redraw(); });
      row.appendChild(del);
      wrap.appendChild(row);
    });

    const add = document.createElement("button");
    add.className = "bld-btn bld-btn-sm bld-kpi-add";
    add.textContent = "+ Ajouter un KPI";
    add.addEventListener("click", () => { list.push({ label: "", value: "" }); setVal(list); redraw(); });
    wrap.appendChild(add);
  };
  redraw();
  return wrap;
}

// ── Modale bibliothèque de blocs ─────────────────────────────────────────
function openLibrary(onPick) {
  libraryTarget = onPick;
  document.getElementById("lib-search").value = "";
  renderLibraryList("");
  document.getElementById("modal-library").hidden = false;
  document.getElementById("lib-search").focus();
}

document.addEventListener("DOMContentLoaded", () => {
  document.getElementById("lib-search").addEventListener("input", (e) => renderLibraryList(e.target.value));
});

function renderLibraryList(filter) {
  const container = document.getElementById("lib-list");
  container.innerHTML = "";
  const f = filter.trim().toLowerCase();

  for (const [category, blocks] of Object.entries(state.registry)) {
    const matching = blocks.filter(b => !f || b.name.toLowerCase().includes(f) || (b.description || "").toLowerCase().includes(f));
    if (!matching.length) continue;

    const label = document.createElement("div");
    label.className = "bld-lib-cat-label";
    label.textContent = category;
    container.appendChild(label);

    const grid = document.createElement("div");
    grid.className = "bld-lib-grid";
    for (const b of matching) {
      const item = document.createElement("div");
      item.className = "bld-lib-item" + (b.usable ? "" : " disabled");
      item.title = b.usable ? "" : (b.unusable_reason || "Non supporté dans le builder");
      item.innerHTML = `
        <div class="bld-lib-item-name">${escapeHtml(b.name)}</div>
        <div class="bld-lib-item-desc">${escapeHtml(b.description || "")}</div>
      `;
      if (b.usable) {
        item.addEventListener("click", () => {
          document.getElementById("modal-library").hidden = true;
          if (libraryTarget) libraryTarget(b.name);
        });
      }
      grid.appendChild(item);
    }
    container.appendChild(grid);
  }

  if (!container.children.length) {
    container.innerHTML = '<div class="bld-field-hint">Aucun bloc ne correspond à la recherche.</div>';
  }
}

init();
