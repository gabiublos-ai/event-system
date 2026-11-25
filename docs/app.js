/* Radar de Eventos BR — front-end sem dependências.
 * Os dados vêm de data/events.json, gerado diariamente pelo robô (scraper/).
 * Para personalizar: edite CONFIG abaixo. */
const CONFIG = {
  repo: "gabiublos-ai/event-system", // usado no botão "Sugerir evento"
  dataUrl: "data/events.json",
};

const MONTHS = ["jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez"];
const MONTHS_FULL = ["janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho", "agosto", "setembro", "outubro", "novembro", "dezembro"];
const REGIONS = {
  Norte: ["AC", "AP", "AM", "PA", "RO", "RR", "TO"],
  Nordeste: ["AL", "BA", "CE", "MA", "PB", "PE", "PI", "RN", "SE"],
  "Centro-Oeste": ["DF", "GO", "MT", "MS"],
  Sudeste: ["ES", "MG", "RJ", "SP"],
  Sul: ["PR", "RS", "SC"],
};
const TILE_LAYOUT = [
  [null, "RR", null, "AP", null, null, null],
  [null, "AM", "PA", "MA", "CE", "RN", null],
  ["AC", "RO", "TO", "PI", "PE", "PB", null],
  [null, "MT", "GO", "BA", "SE", "AL", null],
  [null, "MS", "DF", "MG", "ES", null, null],
  [null, "PR", "SP", "RJ", null, null, null],
  [null, "SC", null, null, null, null, null],
  [null, "RS", null, null, null, null, null],
];
const FORMAT_LABEL = { presencial: "Presencial", hibrido: "Híbrido", online: "Online" };
const REC_LABEL = { anual: "Anual", semestral: "Semestral", trimestral: "Trimestral", mensal: "Mensal", ocasional: "Ocasional" };

const $ = (s, el = document) => el.querySelector(s);
const $$ = (s, el = document) => [...el.querySelectorAll(s)];
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const strip = (s) => String(s ?? "").normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase();
const store = {
  get(k, d) { try { return JSON.parse(localStorage.getItem(k)) ?? d; } catch { return d; } },
  set(k, v) { try { localStorage.setItem(k, JSON.stringify(v)); } catch { /* modo privado */ } },
};

const state = {
  all: [], meta: {}, themes: {}, states: {},
  q: "", themesOn: new Set(), uf: "", period: "upcoming", format: "", rec: "", sort: "date",
  fav: false, onlyNew: false, view: "cards",
  favs: new Set(store.get("favs", [])),
  calMonth: null,
};
const todayISO = new Date(Date.now() - new Date().getTimezoneOffset() * 60000).toISOString().slice(0, 10);

/* ---------- init ---------- */
init();
async function init() {
  applyTheme(store.get("theme", matchMedia("(prefers-color-scheme: light)").matches ? "light" : "dark"));
  $("#suggestBtn").href = `https://github.com/${CONFIG.repo}/issues/new?template=sugerir-evento.yml`;
  try {
    const res = await fetch(`${CONFIG.dataUrl}?v=${Date.now()}`);
    const data = await res.json();
    state.all = data.events || [];
    state.meta = data.meta || {};
    state.themes = state.meta.themes || {};
    state.states = state.meta.states || {};
  } catch (e) {
    $("#view").innerHTML = `<div class="empty"><b>Não foi possível carregar os eventos.</b>Abra o site por um servidor (ex.: GitHub Pages) — veja o README.</div>`;
    return;
  }
  readHash();
  buildControls();
  bind();
  render();
}

function applyTheme(t) {
  document.documentElement.dataset.theme = t;
  store.set("theme", t);
  const b = document.getElementById("themeToggle");
  if (b) b.textContent = t === "dark" ? "☀" : "☾";
}

/* ---------- controls ---------- */
function buildControls() {
  const up = state.meta.updated_at ? new Date(state.meta.updated_at) : null;
  $("#updated").textContent = up ? `Atualizado em ${up.toLocaleDateString("pt-BR")} às ${up.toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit" })}` : "";

  const sel = $("#fState");
  for (const [reg, ufs] of Object.entries(REGIONS)) {
    const og = document.createElement("optgroup");
    og.label = reg;
    og.innerHTML = `<option value="R:${reg}">Toda a região ${reg}</option>` +
      ufs.map((uf) => `<option value="${uf}">${esc(state.states[uf] || uf)} (${uf})</option>`).join("");
    sel.append(og);
  }
  sel.insertAdjacentHTML("beforeend", `<option value="ONLINE">Somente online</option>`);
  sel.value = state.uf;
  $("#fPeriod").value = state.period;
  $("#fFormat").value = state.format;
  $("#fRec").value = state.rec;
  $("#fSort").value = state.sort;
  $("#q").value = state.q;
  $("#fFav").checked = state.fav;
  $("#fNew").checked = state.onlyNew;
  setView(state.view, false);
}

function renderChips(baseList) {
  const counts = {};
  for (const e of baseList) for (const t of e.themes || []) counts[t] = (counts[t] || 0) + 1;
  $("#themeChips").innerHTML = Object.entries(state.themes).map(([k, t]) =>
    `<button class="chip ${state.themesOn.has(k) ? "on" : ""}" data-theme="${k}" style="--c:${t.color}" aria-pressed="${state.themesOn.has(k)}">
      ${t.emoji} ${esc(t.label)} <span class="n">${counts[k] || 0}</span></button>`).join("");
}

function bind() {
  let tmr;
  $("#q").addEventListener("input", (e) => { clearTimeout(tmr); tmr = setTimeout(() => { state.q = e.target.value; render(); }, 120); });
  const map = { fState: "uf", fPeriod: "period", fFormat: "format", fRec: "rec", fSort: "sort" };
  for (const [id, key] of Object.entries(map)) $("#" + id).addEventListener("change", (e) => { state[key] = e.target.value; render(); });
  $("#fFav").addEventListener("change", (e) => { state.fav = e.target.checked; render(); });
  $("#fNew").addEventListener("change", (e) => { state.onlyNew = e.target.checked; render(); });
  $("#themeChips").addEventListener("click", (e) => {
    const b = e.target.closest(".chip"); if (!b) return;
    const k = b.dataset.theme;
    state.themesOn.has(k) ? state.themesOn.delete(k) : state.themesOn.add(k);
    render();
  });
  $$(".tab").forEach((t) => t.addEventListener("click", () => setView(t.dataset.view)));
  $("#clearBtn").addEventListener("click", clearFilters);
  $("#csvBtn").addEventListener("click", () => exportCSV(filtered()));
  $("#icsBtn").addEventListener("click", () => download("eventos.ics", toICS(filtered().filter((e) => e.start_date)), "text/calendar"));
  $("#themeToggle").addEventListener("click", () => applyTheme(document.documentElement.dataset.theme === "dark" ? "light" : "dark"));
  document.addEventListener("keydown", (e) => {
    if (e.key === "/" && document.activeElement.tagName !== "INPUT") { e.preventDefault(); $("#q").focus(); }
  });
  $("#view").addEventListener("click", onViewClick);
  $("#modal").addEventListener("click", (e) => { if (e.target.id === "modal" || e.target.closest(".close")) $("#modal").close(); });
  window.addEventListener("hashchange", () => { readHash(); buildControlsLight(); render(false); });
}

function buildControlsLight() {
  $("#fState").value = state.uf; $("#fPeriod").value = state.period; $("#fFormat").value = state.format;
  $("#fRec").value = state.rec; $("#fSort").value = state.sort; $("#q").value = state.q;
}

function clearFilters() {
  Object.assign(state, { q: "", uf: "", period: "upcoming", format: "", rec: "", sort: "date", fav: false, onlyNew: false });
  state.themesOn.clear();
  buildControlsLight(); $("#fFav").checked = false; $("#fNew").checked = false;
  render();
}

function setView(v, rerender = true) {
  state.view = v;
  $$(".tab").forEach((t) => t.classList.toggle("active", t.dataset.view === v));
  if (rerender) render();
}

/* ---------- URL hash (filtros compartilháveis) ---------- */
function writeHash() {
  const p = new URLSearchParams();
  if (state.q) p.set("q", state.q);
  if (state.themesOn.size) p.set("t", [...state.themesOn].join(","));
  if (state.uf) p.set("uf", state.uf);
  if (state.period !== "upcoming") p.set("p", state.period);
  if (state.format) p.set("f", state.format);
  if (state.rec) p.set("r", state.rec);
  if (state.view !== "cards") p.set("v", state.view);
  const h = p.toString();
  history.replaceState(null, "", h ? "#" + h : location.pathname);
}
function readHash() {
  const p = new URLSearchParams(location.hash.slice(1));
  state.q = p.get("q") || "";
  state.themesOn = new Set((p.get("t") || "").split(",").filter(Boolean));
  state.uf = p.get("uf") || "";
  state.period = p.get("p") || "upcoming";
  state.format = p.get("f") || "";
  state.rec = p.get("r") || "";
  state.view = p.get("v") || state.view;
}

/* ---------- filtering ---------- */
function addDays(iso, n) { const d = new Date(iso + "T12:00:00"); d.setDate(d.getDate() + n); return d.toISOString().slice(0, 10); }

function baseFiltered() {
  const q = strip(state.q).trim();
  return state.all.filter((e) => {
    const end = e.end_date || e.start_date;
    if (state.period === "tbd") { if (e.start_date) return false; }
    else if (state.period !== "all") {
      if (end && end < todayISO) return false;
      if (["30", "90", "180"].includes(state.period)) {
        if (!e.start_date || e.start_date > addDays(todayISO, +state.period)) return false;
      }
    }
    if (state.uf) {
      if (state.uf === "ONLINE") { if (e.format !== "online") return false; }
      else if (state.uf.startsWith("R:")) { if (!REGIONS[state.uf.slice(2)].includes(e.state)) return false; }
      else if (e.state !== state.uf) return false;
    }
    if (state.format && e.format !== state.format) return false;
    if (state.rec === "rec" && (!e.recurrence || e.recurrence === "ocasional")) return false;
    if (state.rec === "ocasional" && e.recurrence && e.recurrence !== "ocasional") return false;
    if (state.fav && !state.favs.has(e.id)) return false;
    if (state.onlyNew && !e.is_new) return false;
    if (q) {
      const hay = strip([e.name, e.description, e.city, e.state, e.organizer, e.venue, ...(e.themes || []).map((t) => state.themes[t]?.label)].join(" "));
      if (!q.split(/\s+/).every((w) => hay.includes(w))) return false;
    }
    return true;
  });
}
function filtered(base = baseFiltered()) {
  let list = state.themesOn.size ? base.filter((e) => (e.themes || []).some((t) => state.themesOn.has(t))) : base;
  const by = {
    date: (a, b) => (a.start_date || "9999").localeCompare(b.start_date || "9999") || a.name.localeCompare(b.name),
    new: (a, b) => (b.first_seen || "").localeCompare(a.first_seen || "") || (a.start_date || "9999").localeCompare(b.start_date || "9999"),
    name: (a, b) => a.name.localeCompare(b.name, "pt-BR"),
  }[state.sort];
  return [...list].sort(by);
}

/* ---------- render ---------- */
function render(updateHash = true) {
  const base = baseFiltered();
  const list = filtered(base);
  renderChips(base);
  renderStats();
  $("#count").textContent = `${list.length} evento${list.length === 1 ? "" : "s"}`;
  const v = $("#view");
  if (!list.length && state.view !== "map" && state.view !== "calendar") {
    v.innerHTML = `<div class="empty"><b>Nenhum evento encontrado</b>Tente remover alguns filtros ou ampliar o período.</div>`;
  } else {
    ({ cards: renderCards, list: renderList, calendar: renderCalendar, map: renderMap })[state.view](v, list);
  }
  if (updateHash) writeHash();
}

function renderStats() {
  const up = state.all.filter((e) => !(e.end_date || e.start_date) || (e.end_date || e.start_date) >= todayISO);
  const next30 = up.filter((e) => e.start_date && e.start_date <= addDays(todayISO, 30)).length;
  const ufs = new Set(up.map((e) => e.state).filter(Boolean)).size;
  const news = up.filter((e) => e.is_new).length;
  $("#stats").innerHTML = [
    [up.length, "eventos no radar"], [next30, "nos próximos 30 dias"], [`${ufs}/27`, "estados com eventos"], [news, "novos nesta semana"],
  ].map(([b, s]) => `<div class="stat"><b>${b}</b><span>${s}</span></div>`).join("");
}

function dateParts(e) {
  if (!e.start_date) {
    return { d: "?", m: e.typical_month ? MONTHS[e.typical_month - 1] : "a conf.", tbd: true };
  }
  const [, mm, dd] = e.start_date.split("-");
  return { d: +dd, m: MONTHS[+mm - 1] };
}
function fmtRange(e) {
  if (!e.start_date) {
    return e.typical_month ? `Data a confirmar · costuma ocorrer em ${MONTHS_FULL[e.typical_month - 1]}` : "Data a confirmar";
  }
  const f = (iso) => new Date(iso + "T12:00:00").toLocaleDateString("pt-BR", { day: "2-digit", month: "short", year: "numeric" });
  return e.end_date && e.end_date !== e.start_date ? `${f(e.start_date)} – ${f(e.end_date)}` : f(e.start_date);
}
const place = (e) => e.format === "online" && !e.city ? "Online" : [e.city, e.state].filter(Boolean).join(" – ") || "Local a confirmar";
const pills = (e) => (e.themes || []).map((t) => state.themes[t] ? `<span class="pill" style="--c:${state.themes[t].color}">${state.themes[t].emoji} ${esc(state.themes[t].label)}</span>` : "").join("");
const starBtn = (e) => `<button class="star ${state.favs.has(e.id) ? "on" : ""}" data-star="${e.id}" title="Favoritar" aria-label="Favoritar">${state.favs.has(e.id) ? "★" : "☆"}</button>`;

function renderCards(v, list) {
  v.innerHTML = `<div class="grid">${list.map((e) => {
    const dp = dateParts(e);
    const rec = e.recurrence && e.recurrence !== "ocasional";
    return `<article class="card" data-id="${e.id}">
      ${starBtn(e)}
      <div class="card-top">
        <div class="datebox ${dp.tbd ? "tbd" : ""}"><div class="d">${dp.d}</div><div class="m">${dp.m}</div></div>
        <div style="min-width:0;padding-right:22px">
          <h3>${esc(e.name)}</h3>
          <div class="meta"><span>📍 ${esc(place(e))}</span><span>${FORMAT_LABEL[e.format] || ""}</span></div>
        </div>
      </div>
      <div class="badges">
        ${e.is_new ? `<span class="badge new">Novo</span>` : ""}
        ${rec ? `<span class="badge rec">↻ ${REC_LABEL[e.recurrence] || "Recorrente"}</span>` : ""}
        ${!e.start_date ? `<span class="badge">Data a confirmar</span>` : ""}
      </div>
      ${e.description ? `<p class="desc">${esc(e.description)}</p>` : ""}
      <div class="pills">${pills(e)}</div>
    </article>`;
  }).join("")}</div>`;
}

function renderList(v, list) {
  let last = "";
  const rows = list.map((e) => {
    const key = e.start_date ? e.start_date.slice(0, 7) : "tbd";
    let sep = "";
    if (key !== last && state.sort === "date") {
      last = key;
      sep = `<div class="month-sep">${key === "tbd" ? "Data a confirmar" : `${MONTHS_FULL[+key.slice(5) - 1]} ${key.slice(0, 4)}`}</div>`;
    }
    const when = e.start_date ? new Date(e.start_date + "T12:00:00").toLocaleDateString("pt-BR", { day: "2-digit", month: "short" }) : "A confirmar";
    return `${sep}<div class="row" data-id="${e.id}">
      <div class="when">${when}</div>
      <div style="min-width:0"><div class="t">${esc(e.name)}</div><div class="sub2">${(e.themes || []).map((t) => state.themes[t]?.emoji || "").join(" ")} ${esc(e.organizer || e.description || "")}</div></div>
      <div class="where">📍 ${esc(place(e))}</div>
      <div class="fmt">${FORMAT_LABEL[e.format] || ""}${e.recurrence && e.recurrence !== "ocasional" ? " · ↻" : ""}</div>
      ${starBtn(e)}
    </div>`;
  }).join("");
  v.innerHTML = `<div class="list">${rows}</div>`;
}

function renderCalendar(v, list) {
  if (!state.calMonth) {
    const firstUp = list.find((e) => e.start_date && e.start_date >= todayISO);
    state.calMonth = (firstUp ? firstUp.start_date : todayISO).slice(0, 7);
  }
  const [y, m] = state.calMonth.split("-").map(Number);
  const first = new Date(y, m - 1, 1);
  const start = new Date(first); start.setDate(1 - first.getDay());
  const byDay = {};
  for (const e of list) {
    if (!e.start_date) continue;
    let d = e.start_date; const end = e.end_date || e.start_date; let guard = 0;
    while (d <= end && guard++ < 31) { (byDay[d] ||= []).push(e); d = addDays(d, 1); }
  }
  let cells = "";
  for (let i = 0; i < 42; i++) {
    const d = new Date(start); d.setDate(start.getDate() + i);
    const iso = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
    const evs = byDay[iso] || [];
    cells += `<div class="cell ${d.getMonth() !== m - 1 ? "out" : ""} ${iso === todayISO ? "today" : ""}">
      <span class="num">${d.getDate()}</span>
      ${evs.slice(0, 3).map((e) => `<div class="ev" data-id="${e.id}" title="${esc(e.name)}" style="--c:${state.themes[e.themes?.[0]]?.color || "var(--accent)"}">${esc(e.name)}</div>`).join("")}
      ${evs.length > 3 ? `<span class="more">+${evs.length - 3} mais</span>` : ""}
    </div>`;
  }
  const tbd = list.filter((e) => !e.start_date && e.typical_month === m).length;
  v.innerHTML = `<div class="cal-head">
      <button class="btn ghost sm" data-cal="-1">‹ Anterior</button>
      <h2>${MONTHS_FULL[m - 1]} ${y}</h2>
      <button class="btn ghost sm" data-cal="1">Próximo ›</button>
    </div>
    <div class="cal">${["dom", "seg", "ter", "qua", "qui", "sex", "sáb"].map((d) => `<div class="dow">${d}</div>`).join("")}${cells}</div>
    ${tbd ? `<p class="count" style="margin-top:12px">+ ${tbd} evento(s) recorrente(s) que costumam ocorrer em ${MONTHS_FULL[m - 1]}, com data a confirmar — veja na Lista com o período “Data a confirmar”.</p>` : ""}`;
}

function renderMap(v, list) {
  const counts = {};
  for (const e of list) if (e.state) counts[e.state] = (counts[e.state] || 0) + 1;
  const max = Math.max(1, ...Object.values(counts));
  const tiles = TILE_LAYOUT.flat().map((uf) => {
    if (!uf) return `<div class="tile empty"></div>`;
    const n = counts[uf] || 0;
    const pct = n ? 15 + Math.round((n / max) * 85) : 4;
    const color = `color-mix(in srgb, var(--accent) ${pct}%, transparent)`;
    return `<div class="tile ${state.uf === uf ? "sel" : ""}" data-uf="${uf}" title="${esc(state.states[uf] || uf)}: ${n} evento(s)" style="background:${color}">
      <div>${uf}<small>${n}</small></div></div>`;
  }).join("");
  const ranking = Object.entries(counts).sort((a, b) => b[1] - a[1]);
  const online = list.filter((e) => e.format === "online").length;
  v.innerHTML = `<div class="map-wrap">
    <div><div class="tilemap">${tiles}</div>
      <div class="legend"><span>menos</span><div class="bar"></div><span>mais eventos</span></div>
      <p class="count" style="margin-top:8px">Clique em um estado para filtrar. ${online ? `${online} evento(s) online.` : ""}</p></div>
    <div class="rank"><h3>Ranking por estado</h3>
      ${ranking.map(([uf, n]) => `<div class="rank-row" data-uf="${uf}"><span>${esc(state.states[uf] || uf)}</span><div class="b" style="width:${(n / max) * 100}%"></div><b>${n}</b></div>`).join("") || `<p class="count">Sem eventos com estado para os filtros atuais.</p>`}
    </div></div>`;
}

/* ---------- interactions ---------- */
function onViewClick(e) {
  const star = e.target.closest("[data-star]");
  if (star) {
    e.stopPropagation();
    const id = star.dataset.star;
    state.favs.has(id) ? state.favs.delete(id) : state.favs.add(id);
    store.set("favs", [...state.favs]);
    render();
    return;
  }
  const cal = e.target.closest("[data-cal]");
  if (cal) {
    const [y, m] = state.calMonth.split("-").map(Number);
    const d = new Date(y, m - 1 + +cal.dataset.cal, 1);
    state.calMonth = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}`;
    render();
    return;
  }
  const tile = e.target.closest("[data-uf]");
  if (tile) {
    state.uf = state.uf === tile.dataset.uf ? "" : tile.dataset.uf;
    $("#fState").value = state.uf;
    render();
    return;
  }
  const item = e.target.closest("[data-id]");
  if (item) openModal(state.all.find((x) => x.id === item.dataset.id));
}

function openModal(e) {
  if (!e) return;
  const rows = [
    ["Quando", fmtRange(e)],
    ["Onde", [e.venue, place(e)].filter(Boolean).join(" · ")],
    ["Formato", FORMAT_LABEL[e.format]],
    ["Recorrência", REC_LABEL[e.recurrence] || "Ocasional"],
    ["Organização", e.organizer],
    ["Preço", e.price],
    ["Fontes", (e.sources || [e.source]).join(", ")],
  ].filter(([, v]) => v);
  $("#modalBody").innerHTML = `
    <button class="btn ghost sm icon close" aria-label="Fechar">✕</button>
    <div class="pills">${pills(e)}</div>
    <h2>${esc(e.name)}</h2>
    ${e.description ? `<p class="desc" style="-webkit-line-clamp:unset">${esc(e.description)}</p>` : ""}
    <dl class="kv">${rows.map(([k, v]) => `<dt>${k}</dt><dd>${esc(v)}</dd>`).join("")}</dl>
    <div class="actions">
      ${e.url ? `<a class="btn primary" href="${esc(e.url)}" target="_blank" rel="noopener">Site do evento ↗</a>` : ""}
      ${e.start_date ? `<a class="btn" href="${gcalUrl(e)}" target="_blank" rel="noopener">＋ Google Agenda</a>
      <button class="btn" id="oneIcs">⤓ .ics</button>` : ""}
      <button class="btn" id="favModal">${state.favs.has(e.id) ? "★ Favorito" : "☆ Favoritar"}</button>
    </div>`;
  $("#oneIcs")?.addEventListener("click", () => download(`${e.id}.ics`, toICS([e]), "text/calendar"));
  $("#favModal").addEventListener("click", () => {
    state.favs.has(e.id) ? state.favs.delete(e.id) : state.favs.add(e.id);
    store.set("favs", [...state.favs]); render(); openModal(e);
  });
  if (!$("#modal").open) $("#modal").showModal();
}

/* ---------- exports ---------- */
const ymd = (iso) => iso.replaceAll("-", "");
function gcalUrl(e) {
  const end = addDays(e.end_date || e.start_date, 1);
  const p = new URLSearchParams({
    action: "TEMPLATE", text: e.name, dates: `${ymd(e.start_date)}/${ymd(end)}`,
    details: `${e.description || ""}\n\n${e.url || ""}`, location: [e.venue, e.city, e.state].filter(Boolean).join(", "),
  });
  return `https://calendar.google.com/calendar/render?${p}`;
}
function toICS(list) {
  const t = (s) => String(s || "").replace(/[\\;,]/g, (c) => "\\" + c).replace(/\n/g, "\\n");
  const stamp = new Date().toISOString().replace(/[-:]/g, "").slice(0, 15) + "Z";
  const body = list.map((e) => [
    "BEGIN:VEVENT", `UID:${e.id}@radar-eventos-br`, `DTSTAMP:${stamp}`,
    `DTSTART;VALUE=DATE:${ymd(e.start_date)}`, `DTEND;VALUE=DATE:${ymd(addDays(e.end_date || e.start_date, 1))}`,
    `SUMMARY:${t(e.name)}`, `DESCRIPTION:${t((e.description || "") + "\n" + (e.url || ""))}`,
    `LOCATION:${t([e.venue, e.city, e.state].filter(Boolean).join(", "))}`, e.url ? `URL:${e.url}` : "", "END:VEVENT",
  ].filter(Boolean).join("\r\n")).join("\r\n");
  return `BEGIN:VCALENDAR\r\nVERSION:2.0\r\nPRODID:-//Radar de Eventos BR//PT-BR\r\nCALSCALE:GREGORIAN\r\n${body}\r\nEND:VCALENDAR\r\n`;
}
function exportCSV(list) {
  const cols = ["name", "start_date", "end_date", "city", "state", "region", "venue", "format", "recurrence", "themes", "organizer", "url", "description"];
  const q = (v) => `"${String(Array.isArray(v) ? v.map((t) => state.themes[t]?.label || t).join(" | ") : v ?? "").replace(/"/g, '""')}"`;
  download("eventos.csv", "﻿" + [cols.join(";"), ...list.map((e) => cols.map((c) => q(e[c])).join(";"))].join("\n"), "text/csv");
}
function download(name, content, type) {
  const a = document.createElement("a");
  a.href = URL.createObjectURL(new Blob([content], { type }));
  a.download = name; a.click();
  setTimeout(() => URL.revokeObjectURL(a.href), 1000);
}
