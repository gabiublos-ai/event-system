/* Radar de Eventos BR — front-end sem build.
 * Os dados vêm de data/events.json, gerado diariamente pelo robô (scraper/).
 * Para personalizar: edite CONFIG e THEME_ICONS abaixo. */
const CONFIG = {
  repo: "gabiublos-ai/event-system", // usado no botão "Sugerir evento"
  dataUrl: "data/events.json",
  // contorno dos estados no mapa (opcional; se não carregar, o mapa segue só com as cidades)
  statesGeoJson: "https://cdn.jsdelivr.net/gh/codeforgermany/click_that_hood@main/public/data/brazil-states.geojson",
};

/* Ícones de linha dos temas (Lucide, licença ISC) */
const THEME_ICONS = {
  all: '<rect x="3" y="3" width="7" height="7" rx="1.5"/><rect x="14" y="3" width="7" height="7" rx="1.5"/><rect x="3" y="14" width="7" height="7" rx="1.5"/><rect x="14" y="14" width="7" height="7" rx="1.5"/>',
  ia: '<rect x="5" y="5" width="14" height="14" rx="2"/><rect x="9" y="9" width="6" height="6" rx="1"/><path d="M9 2v3M15 2v3M9 19v3M15 19v3M19 9h3M19 15h3M2 9h3M2 15h3"/>',
  startups: '<path d="M4.5 16.5c-1.5 1.26-2 5-2 5s3.74-.5 5-2c.71-.84.7-2.13-.09-2.91a2.18 2.18 0 0 0-2.91-.09z"/><path d="m12 15-3-3a22 22 0 0 1 2-3.95A12.88 12.88 0 0 1 22 2c0 2.72-.78 7.5-6 11a22.35 22.35 0 0 1-4 2z"/><path d="M9 12H4s.55-3.03 2-4c1.62-1.08 5 0 5 0M12 15v5s3.03-.55 4-2c1.08-1.62 0-5 0-5"/>',
  aceleradoras: '<path d="M13 2 3 14h9l-1 8 10-12h-9l1-8z"/>',
  escolas_negocio: '<path d="M22 10 12 5 2 10l10 5 10-5z"/><path d="M6 12v5c3 3 9 3 12 0v-5M22 10v6"/>',
  demo_day: '<path d="m3 11 18-5v12L3 14v-3z"/><path d="M11.6 16.8a3 3 0 1 1-5.8-1.6"/>',
  fintech: '<rect x="2" y="5" width="20" height="14" rx="2"/><path d="M2 10h20M6 15h4"/>',
  healthtech: '<path d="M19 14c1.49-1.46 3-3.21 3-5.5A5.5 5.5 0 0 0 16.5 3c-1.76 0-3 .5-4.5 2-1.5-1.5-2.74-2-4.5-2A5.5 5.5 0 0 0 2 8.5c0 2.3 1.5 4.05 3 5.5l7 7z"/><path d="M3.22 12H9.5l.5-1 2 4.5 2-7 1.5 3.5h5.27"/>',
  cripto: '<circle cx="8" cy="8" r="6"/><path d="M18.09 10.37A6 6 0 1 1 10.34 18M7 6h1v4M16.71 13.88l.7.71-2.82 2.82"/>',
  bitcoin: '<path d="M11.77 19.09c4.92.87 6.14-6.03 1.21-6.9m-1.21 6.9-5.91-1.04m5.91 1.04-.35 1.97m1.56-8.86c4.93.87 6.14-6.03 1.22-6.9m-1.22 6.9-3.94-.7m5.16-6.2L8.29 4.26m5.91 1.04.35-1.97M7.48 20.36l3.13-17.72"/>',
  foodtech: '<path d="M11 20A7 7 0 0 1 9.8 6.1C15.5 5 17 4.48 19 2c1 2 2 4.18 2 8 0 5.5-4.78 10-10 10z"/><path d="M2 21c0-3 1.85-5.36 5.08-6C9.5 14.52 12 13 13 12"/>',
};
const PIN = '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 22s7-6.1 7-12a7 7 0 1 0-14 0c0 5.9 7 12 7 12z"/><circle cx="12" cy="10" r="2.5"/></svg>';
const PAID = "Pago (valor no site)";

const MONTHS = ["jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez"];
const MONTHS_FULL = ["janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho", "agosto", "setembro", "outubro", "novembro", "dezembro"];
const REGIONS = {
  Norte: ["AC", "AP", "AM", "PA", "RO", "RR", "TO"],
  Nordeste: ["AL", "BA", "CE", "MA", "PB", "PE", "PI", "RN", "SE"],
  "Centro-Oeste": ["DF", "GO", "MT", "MS"],
  Sudeste: ["ES", "MG", "RJ", "SP"],
  Sul: ["PR", "RS", "SC"],
};
const FORMAT_LABEL = { presencial: "Presencial", hibrido: "Híbrido", online: "Online" };

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
  q: "", themesOn: new Set(), type: "", uf: "", city: "", period: "upcoming", from: "", to: "", format: "",
  favOf: "", onlyNew: false, view: "cards",
  team: { status: "off", members: [] },
  favs: new Set(store.get("favs", [])),
  calMonth: null,
  map: null, mapView: null, statesGeo: null,
};
const todayISO = new Date(Date.now() - new Date().getTimezoneOffset() * 60000).toISOString().slice(0, 10);

/* ---------- init ---------- */
init();
async function init() {
  applyTheme(store.get("theme", null));
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
  window.Team?.init(onTeam);
}

/* ---------- equipe: login por convite e favoritos por pessoa ---------- */
const initials = (n) => String(n || "?").trim().split(/\s+/).slice(0, 2).map((w) => w[0]).join("").toUpperCase();
const signedIn = () => state.team.status === "in";
const membersWhoFav = (id) => signedIn() ? state.team.members.filter((m) => m.favs.includes(id)) : [];

function onTeam(t) {
  state.team = t;
  if (t.status === "in") {
    const me = t.members.find((m) => m.uid === t.me.uid);
    state.favs = new Set(me ? me.favs : state.favs);
  }
  renderGate();
  const chip = $("#userChip");
  chip.hidden = t.status !== "in";
  if (t.status === "in") chip.innerHTML = `<span class="avatar">${esc(initials(t.me.name))}</span><span class="uname">${esc(t.me.name.split(" ")[0])}</span>`;
  $("#inviteBtn").hidden = !(t.status === "in" && t.admin) && t.status !== "off";
  renderFavSelect();
  if (t.status === "in" || t.status === "off") render(false);
}

function renderFavSelect() {
  const sel = $("#fFavOf");
  let opts = `<option value="">Todos os eventos</option><option value="me">★ Meus favoritos</option>`;
  if (signedIn()) {
    const others = state.team.members.filter((m) => m.uid !== state.team.me.uid);
    if (others.length) {
      opts += `<option value="any">★ Favoritos de toda a equipe</option><optgroup label="Favoritos de…">` +
        others.map((m) => `<option value="${esc(m.uid)}">${esc(m.name)} (${m.favs.length})</option>`).join("") + `</optgroup>`;
    }
  }
  sel.innerHTML = opts;
  if (![...sel.options].some((o) => o.value === state.favOf)) state.favOf = state.favOf && !signedIn() ? state.favOf : "";
  sel.value = state.favOf;
}

function renderGate() {
  const t = state.team, gate = $("#gate"), card = $("#gateCard");
  const show = Team.enabled && t.status !== "in";
  gate.hidden = !show;
  document.body.classList.toggle("locked", show);
  if (!show) return;
  const brand = `<div class="gate-brand"><span class="brand-mark"><svg viewBox="0 0 24 24"><circle cx="12" cy="12" r="2.2"/><path d="M16.2 7.8a6 6 0 0 1 0 8.4M7.8 16.2a6 6 0 0 1 0-8.4M19 5a10 10 0 0 1 0 14M5 19A10 10 0 0 1 5 5"/></svg></span><b>Radar de Eventos BR</b></div>`;
  const form = (label, btn, id) => `<form id="${id}" class="gate-form">
      <label for="gateEmail">${label}</label>
      <input id="gateEmail" type="email" required autocomplete="email" placeholder="seu@email.com">
      <button class="btn primary" type="submit">${btn}</button>
      <p class="gate-msg" id="gateMsg" role="status">${esc(t.error || "")}</p></form>`;
  if (t.status === "loading") card.innerHTML = `${brand}<p class="gate-sub">Conectando…</p>`;
  else if (t.status === "needEmail") card.innerHTML = `${brand}<h2>Confirme seu e-mail</h2><p class="gate-sub">Para concluir o acesso neste aparelho, digite o e-mail em que você recebeu o convite.</p>${form("E-mail", "Entrar", "gateConfirm")}`;
  else if (t.status === "notInvited") card.innerHTML = `${brand}<h2>Acesso não liberado</h2><p class="gate-sub">O e-mail <b>${esc(t.me?.email || "")}</b> ainda não foi convidado. Peça um convite a quem administra o radar.</p><button class="btn" id="gateOut" type="button">Entrar com outro e-mail</button>`;
  else if (t.status === "error") card.innerHTML = `${brand}<h2>Não foi possível entrar</h2><p class="gate-sub">${esc(t.error)}</p><button class="btn" type="button" onclick="location.reload()">Tentar de novo</button>`;
  else card.innerHTML = `${brand}<h2>Acesso por convite</h2><p class="gate-sub">Digite seu e-mail e enviaremos um link de acesso, sem senha.</p>${form("E-mail", "Receber link de acesso", "gateLogin")}`;
  $("#gateLogin")?.addEventListener("submit", async (ev) => {
    ev.preventDefault();
    const email = $("#gateEmail").value, msg = $("#gateMsg");
    msg.textContent = "Enviando…";
    try { await Team.requestLink(email); msg.textContent = `Pronto! Enviamos um link para ${email}. Abra o e-mail neste aparelho para entrar (veja também o spam).`; }
    catch (e) { msg.textContent = "Não foi possível enviar o link. Confira o e-mail e tente de novo."; }
  });
  $("#gateConfirm")?.addEventListener("submit", async (ev) => { ev.preventDefault(); $("#gateMsg").textContent = "Entrando…"; await Team.completeLink($("#gateEmail").value); });
  $("#gateOut")?.addEventListener("click", () => Team.signOut());
}

async function toggleFav(id) {
  const on = !state.favs.has(id);
  on ? state.favs.add(id) : state.favs.delete(id);
  if (signedIn()) {
    const me = state.team.members.find((m) => m.uid === state.team.me.uid);
    if (me) me.favs = on ? [...me.favs, id] : me.favs.filter((x) => x !== id);
    Team.setFav(id, on).catch(() => alertToast("Não foi possível salvar o favorito. Tente de novo."));
  } else store.set("favs", [...state.favs]);
}

function alertToast(text) {
  let t = $("#toast");
  if (!t) { t = document.createElement("div"); t.id = "toast"; t.className = "toast"; t.setAttribute("role", "status"); document.body.append(t); }
  t.textContent = text; t.classList.add("show");
  clearTimeout(alertToast.tm); alertToast.tm = setTimeout(() => t.classList.remove("show"), 3500);
}

/* Convites (só administradores) */
async function openInvite() {
  if (!Team.enabled) {
    $("#modalBody").innerHTML = `<button class="btn ghost sm icon close" aria-label="Fechar">✕</button>
      <h2>Convidar pessoas</h2>
      <p class="desc">Para convidar pessoas com acesso nominal e favoritos individuais, falta ligar o login do radar (Firebase, gratuito).
      O passo a passo está no README do repositório, na seção “Acesso por convite”.</p>`;
    $("#modal").showModal(); return;
  }
  $("#modalBody").innerHTML = `<button class="btn ghost sm icon close" aria-label="Fechar">✕</button>
    <h2>Convidar pessoa</h2>
    <p class="desc">A pessoa recebe um e-mail com o link de acesso ao radar. Cada um entra com o próprio e-mail e marca os seus favoritos.</p>
    <form id="inviteForm" class="invite-form">
      <label class="field"><span>Nome</span><input id="invName" required placeholder="Nome da pessoa" autocomplete="off"></label>
      <label class="field"><span>E-mail</span><input id="invEmail" type="email" required placeholder="pessoa@empresa.com" autocomplete="off"></label>
      <button class="btn primary" type="submit">Enviar convite</button>
    </form>
    <p class="gate-msg" id="invMsg" role="status"></p>
    <h3 class="inv-title">Pessoas com acesso</h3>
    <div id="invList" class="inv-list"><p class="hint">Carregando…</p></div>`;
  $("#modal").showModal();
  const load = async () => {
    try {
      const list = await Team.listInvites();
      const joined = new Set(state.team.members.map((m) => (m.email || "").toLowerCase()));
      $("#invList").innerHTML = list.length ? list.map((i) => `<div class="inv-row">
          <span class="avatar">${esc(initials(i.name))}</span>
          <span class="inv-who"><b>${esc(i.name)}</b><small>${esc(i.email)}</small></span>
          <span class="inv-status ${joined.has(i.email) ? "ok" : ""}">${joined.has(i.email) ? "Ativo" : "Convite enviado"}</span>
          <a class="btn ghost sm" href="${mailtoInvite(i)}" title="Abrir uma mensagem no seu e-mail">Lembrar</a>
          <button class="btn ghost sm" data-revoke="${esc(i.email)}" type="button">Remover</button></div>`).join("")
        : `<p class="hint">Ninguém convidado ainda.</p>`;
    } catch { $("#invList").innerHTML = `<p class="hint">Não foi possível carregar a lista.</p>`; }
  };
  load();
  $("#inviteForm").addEventListener("submit", async (ev) => {
    ev.preventDefault();
    const name = $("#invName").value.trim(), email = $("#invEmail").value.trim();
    $("#invMsg").textContent = "Enviando convite…";
    try {
      await Team.invite(name, email);
      $("#invMsg").innerHTML = `Convite enviado para <b>${esc(email)}</b>. Quer mandar uma mensagem pessoal também? <a href="${mailtoInvite({ name, email })}">Abrir no meu e-mail</a>`;
      ev.target.reset(); load();
    } catch (e) { $("#invMsg").textContent = "Não foi possível enviar o convite: " + (e.message || e); }
  });
  $("#invList").addEventListener("click", async (ev) => {
    const b = ev.target.closest("[data-revoke]"); if (!b) return;
    if (b.dataset.confirm !== "1") { b.dataset.confirm = "1"; b.textContent = "Confirmar remoção"; return; }
    await Team.revoke(b.dataset.revoke).catch(() => {}); load();
  });
}
function mailtoInvite(i) {
  const first = String(i.name || "").split(" ")[0];
  const body = `Oi ${first}!\n\nTe convidei para o Radar de Eventos BR, com os eventos de IA, startups, fintech, health tech, cripto e mais em todo o Brasil.\n\nVocê vai receber um e-mail com o link de acesso. Se não chegar, entre em ${Team.siteUrl()} e digite este e-mail (${i.email}) para receber o link.\n\nLá você pode marcar seus eventos favoritos e ver os da equipe.`;
  return `mailto:${encodeURIComponent(i.email)}?subject=${encodeURIComponent("Convite: Radar de Eventos BR")}&body=${encodeURIComponent(body)}`;
}

function openUserMenu() {
  const t = state.team;
  $("#modalBody").innerHTML = `<button class="btn ghost sm icon close" aria-label="Fechar">✕</button>
    <div class="me-head"><span class="avatar lg">${esc(initials(t.me.name))}</span><div><h2>${esc(t.me.name)}</h2><p class="desc">${esc(t.me.email)}${t.admin ? " · administrador(a)" : ""}</p></div></div>
    <p class="desc">Você tem <b>${state.favs.size}</b> evento(s) favorito(s). A equipe tem ${t.members.length} pessoa(s) com acesso.</p>
    <div class="actions">
      <button class="btn" id="seeMine" type="button">★ Ver meus favoritos</button>
      ${t.members.length > 1 ? `<button class="btn" id="seeTeam" type="button">Ver favoritos da equipe</button>` : ""}
      <button class="btn" id="logout" type="button">Sair</button>
    </div>`;
  $("#modal").showModal();
  $("#seeMine").addEventListener("click", () => { state.favOf = "me"; $("#fFavOf").value = "me"; $("#modal").close(); render(); });
  $("#seeTeam")?.addEventListener("click", () => { state.favOf = "any"; $("#fFavOf").value = "any"; $("#modal").close(); render(); });
  $("#logout").addEventListener("click", async () => { $("#modal").close(); await Team.signOut(); });
}

function applyTheme(t) {
  if (t) document.documentElement.dataset.theme = t; else delete document.documentElement.dataset.theme;
  const dark = t ? t === "dark" : matchMedia("(prefers-color-scheme: dark)").matches;
  $("#themeToggle").textContent = dark ? "☀" : "☾";
}
const isDark = () => (document.documentElement.dataset.theme || (matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light")) === "dark";

/* ---------- controles ---------- */
function buildControls() {
  const up = state.meta.updated_at ? new Date(state.meta.updated_at) : null;
  if (up) $("#updated").textContent = `Atualizado em ${up.toLocaleDateString("pt-BR")} às ${up.toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit" })}`;

  const sel = $("#fState");
  for (const [reg, ufs] of Object.entries(REGIONS)) {
    const og = document.createElement("optgroup");
    og.label = reg;
    og.innerHTML = `<option value="R:${reg}">Toda a região ${reg}</option>` +
      ufs.map((uf) => `<option value="${uf}">${esc(state.states[uf] || uf)} (${uf})</option>`).join("");
    sel.append(og);
  }
  sel.insertAdjacentHTML("beforeend", `<option value="ONLINE">Somente online</option>`);
  buildControlsLight();
  $("#fNew").checked = state.onlyNew;
  setView(state.view, false);
}

function buildControlsLight() {
  $("#fState").value = state.uf; $("#fPeriod").value = state.period; $("#fFormat").value = state.format;
  $("#fFrom").value = state.from; $("#fTo").value = state.to; $("#q").value = state.q;
  const off = state.period === "tbd";
  $("#fFrom").disabled = $("#fTo").disabled = off;
  $(".daterange").classList.toggle("disabled", off);
}

/* Categoria: menu com contagem (respeita os outros filtros) */
function renderTypeSelect() {
  const tc = {};
  for (const e of baseFiltered("type")) tc[e.type || "evento"] = (tc[e.type || "evento"] || 0) + 1;
  const total = Object.values(tc).reduce((a, b) => a + b, 0);
  const types = state.meta.types || {};
  const opts = Object.entries(types).filter(([k]) => tc[k] || state.type === k)
    .sort((a, b) => a[1].label.localeCompare(b[1].label, "pt-BR"))
    .map(([k, t]) => `<option value="${k}">${esc(t.label)} (${tc[k] || 0})</option>`).join("");
  $("#fType").innerHTML = `<option value="">Todas (${total})</option>${opts}`;
  $("#fType").value = state.type;
}

/* Explore nossos temas: cards com ícone */
function renderThemeCards() {
  const counts = {};
  const base = baseFiltered("themes");
  for (const e of base) for (const t of e.themes || []) counts[t] = (counts[t] || 0) + 1;
  const icon = (k) => `<svg viewBox="0 0 24 24" aria-hidden="true">${THEME_ICONS[k] || THEME_ICONS.all}</svg>`;
  const card = (k, label, n, on, color) =>
    `<button class="theme-card ${on ? "on" : ""} ${n ? "" : "empty"}" data-theme="${k}" style="--c:${color}" aria-pressed="${on}" type="button">
      ${icon(k)}<span class="t-label">${esc(label)}</span><span class="t-count">${n} evento${n === 1 ? "" : "s"}</span></button>`;
  $("#themeChips").innerHTML = card("all", "Todos os temas", base.length, !state.themesOn.size, "var(--accent)") +
    Object.entries(state.themes).map(([k, t]) => card(k, t.label, counts[k] || 0, state.themesOn.has(k), t.color)).join("");
  updateCarouselNav();
}
function updateCarouselNav() {
  const row = $("#themeChips");
  $(".car-nav.prev").hidden = row.scrollLeft < 8;
  $(".car-nav.next").hidden = row.scrollLeft + row.clientWidth >= row.scrollWidth - 8;
}

function bind() {
  let tmr;
  $("#q").addEventListener("input", (e) => { clearTimeout(tmr); tmr = setTimeout(() => { state.q = e.target.value; render(); }, 120); });
  $("#fState").addEventListener("change", (e) => { state.uf = e.target.value; state.city = ""; state.mapView = null; render(); });
  $("#fFormat").addEventListener("change", (e) => { state.format = e.target.value; render(); });
  $("#fType").addEventListener("change", (e) => { state.type = e.target.value; render(); });
  $("#fPeriod").addEventListener("change", (e) => {
    state.period = e.target.value; state.calMonth = null;
    applyPeriod(); buildControlsLight();
    if (state.period === "custom") { try { $("#fFrom").showPicker(); } catch { $("#fFrom").focus(); } }
    render();
  });
  for (const id of ["fFrom", "fTo"]) $("#" + id).addEventListener("change", () => {
    state.from = $("#fFrom").value; state.to = $("#fTo").value; state.calMonth = null;
    if (state.from && state.to && state.to < state.from) { state.to = state.from; $("#fTo").value = state.to; }
    state.period = state.from || state.to ? "custom" : "upcoming";
    if (state.period === "upcoming") applyPeriod();
    $("#fPeriod").value = state.period;
    render();
  });
  $("#fFavOf").addEventListener("change", (e) => { state.favOf = e.target.value; render(); });
  $("#inviteBtn").addEventListener("click", openInvite);
  $("#userChip").addEventListener("click", openUserMenu);
  $("#fNew").addEventListener("change", (e) => { state.onlyNew = e.target.checked; render(); });
  $("#themeChips").addEventListener("click", (e) => {
    const b = e.target.closest(".theme-card"); if (!b) return;
    const k = b.dataset.theme;
    if (k === "all") state.themesOn.clear();
    else state.themesOn.has(k) ? state.themesOn.delete(k) : state.themesOn.add(k);
    render();
  });
  $("#themeChips").addEventListener("scroll", updateCarouselNav, { passive: true });
  window.addEventListener("resize", updateCarouselNav);
  $(".car-nav.prev").addEventListener("click", () => $("#themeChips").scrollBy({ left: -400 }));
  $(".car-nav.next").addEventListener("click", () => $("#themeChips").scrollBy({ left: 400 }));
  $("#allThemes").addEventListener("click", () => { state.themesOn.clear(); render(); });
  $$(".tab").forEach((t) => t.addEventListener("click", () => setView(t.dataset.view)));
  $("#clearBtn").addEventListener("click", clearFilters);
  $("#csvBtn").addEventListener("click", () => exportCSV(filtered()));
  $("#icsBtn").addEventListener("click", () => download("eventos.ics", toICS(filtered().filter((e) => e.start_date)), "text/calendar"));
  $("#themeToggle").addEventListener("click", () => {
    const t = isDark() ? "light" : "dark";
    store.set("theme", t); applyTheme(t);
    if (state.view === "map") render(false);
  });
  document.addEventListener("keydown", (e) => {
    if (e.key === "/" && !["INPUT", "SELECT", "TEXTAREA"].includes(document.activeElement.tagName)) { e.preventDefault(); $("#q").focus(); }
  });
  $("#view").addEventListener("click", onViewClick);
  $("#modal").addEventListener("click", (e) => { if (e.target.id === "modal" || e.target.closest(".close")) $("#modal").close(); });
  window.addEventListener("hashchange", () => { readHash(); buildControlsLight(); render(false); });
}

/* Atalhos de período preenchem as datas de início/fim */
function applyPeriod() {
  const p = state.period;
  if (p === "custom") return;
  if (p === "tbd" || p === "all") { state.from = ""; state.to = ""; return; }
  state.from = todayISO;
  state.to = p === "upcoming" ? "" : addDays(todayISO, +p);
}

function clearFilters() {
  Object.assign(state, { q: "", type: "", uf: "", city: "", period: "upcoming", format: "", favOf: "", onlyNew: false, mapView: null, calMonth: null });
  state.themesOn.clear(); applyPeriod();
  buildControlsLight(); $("#fFavOf").value = ""; $("#fNew").checked = false;
  render();
}

function setView(v, rerender = true) {
  state.view = v;
  $$(".tab").forEach((t) => { t.classList.toggle("active", t.dataset.view === v); t.setAttribute("aria-selected", t.dataset.view === v); });
  if (rerender) render();
}

/* ---------- filtros na URL (link compartilhável) ---------- */
function writeHash() {
  const p = new URLSearchParams();
  if (state.q) p.set("q", state.q);
  if (state.themesOn.size) p.set("t", [...state.themesOn].join(","));
  if (state.type) p.set("c", state.type);
  if (state.uf) p.set("uf", state.uf);
  if (state.city) p.set("cidade", state.city);
  if (state.period !== "upcoming") p.set("p", state.period);
  if (state.period === "custom") { if (state.from) p.set("de", state.from); if (state.to) p.set("ate", state.to); }
  if (state.format) p.set("f", state.format);
  if (state.view !== "cards") p.set("v", state.view);
  const h = p.toString();
  history.replaceState(null, "", h ? "#" + h : location.pathname);
}
function readHash() {
  const p = new URLSearchParams(location.hash.slice(1));
  state.q = p.get("q") || "";
  state.themesOn = new Set((p.get("t") || "").split(",").filter(Boolean));
  state.type = p.get("c") || "";
  state.uf = p.get("uf") || "";
  state.city = p.get("cidade") || "";
  state.period = p.get("p") || "upcoming";
  state.from = p.get("de") || ""; state.to = p.get("ate") || "";
  applyPeriod();
  state.format = p.get("f") || "";
  state.view = p.get("v") || state.view;
}

/* ---------- filtragem ---------- */
function addDays(iso, n) { const d = new Date(iso + "T12:00:00"); d.setDate(d.getDate() + n); return d.toISOString().slice(0, 10); }

/* skip: "themes" | "type" ignora esse filtro (usado para as contagens) */
function baseFiltered(skip = "") {
  const q = strip(state.q).trim();
  return state.all.filter((e) => {
    const end = e.end_date || e.start_date;
    if (state.period === "tbd") { if (e.start_date) return false; }
    else if (state.period !== "all" || state.from || state.to) {
      if (!e.start_date) { if (state.to || state.period === "custom") return false; }
      else {
        // datas escolhidas: o evento precisa começar no período; atalhos: vale o que ainda está acontecendo
        const ref = state.period === "custom" ? e.start_date : end;
        if (state.from && ref < state.from) return false;
        if (state.to && e.start_date > state.to) return false;
      }
    }
    if (state.uf) {
      if (state.uf === "ONLINE") { if (e.format !== "online") return false; }
      else if (state.uf.startsWith("R:")) { if (!REGIONS[state.uf.slice(2)].includes(e.state)) return false; }
      else if (e.state !== state.uf) return false;
    }
    if (state.city && `${strip(e.city || "")}|${e.state}` !== state.city) return false;
    if (state.format && e.format !== state.format) return false;
    if (skip !== "type" && state.type && (e.type || "evento") !== state.type) return false;
    if (skip !== "themes" && state.themesOn.size && !(e.themes || []).some((t) => state.themesOn.has(t))) return false;
    if (state.favOf === "me" && !state.favs.has(e.id)) return false;
    if (state.favOf === "any" && !membersWhoFav(e.id).length) return false;
    if (state.favOf && !["me", "any"].includes(state.favOf)) {
      const m = state.team.members.find((x) => x.uid === state.favOf);
      if (!m || !m.favs.includes(e.id)) return false;
    }
    if (state.onlyNew && !e.is_new) return false;
    if (q) {
      const hay = strip([e.name, typeLabel(e), e.description, e.city, e.state, e.organizer, e.venue, ...(e.themes || []).map((t) => state.themes[t]?.label)].join(" "));
      if (!q.split(/\s+/).every((w) => hay.includes(w))) return false;
    }
    return true;
  });
}
function filtered() {
  return baseFiltered().sort((a, b) =>
    (a.start_date || "9999").localeCompare(b.start_date || "9999") || a.name.localeCompare(b.name, "pt-BR"));
}

/* ---------- render ---------- */
function render(updateHash = true) {
  const list = filtered();
  renderThemeCards();
  renderTypeSelect();
  renderStats();
  $("#count").textContent = `${list.length} evento${list.length === 1 ? "" : "s"}${state.city ? ` na cidade selecionada no mapa` : ""}`;
  const v = $("#view");
  if (state.view !== "map" && state.map) { state.map.remove(); state.map = null; }
  if (!list.length && !["map", "calendar"].includes(state.view)) {
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
  const free = up.filter((e) => e.price === "Gratuito").length;
  $("#stats").innerHTML = [
    [up.length, "eventos no radar"], [next30, "nos próximos 30 dias"], [`${ufs}/27`, "estados com eventos"], [free, "eventos gratuitos"],
  ].map(([b, s]) => `<div class="stat"><dt>${s}</dt><dd>${b}</dd></div>`).join("");
}

function dateParts(e) {
  if (!e.start_date) return { d: "?", m: e.typical_month ? MONTHS[e.typical_month - 1] : "a conf.", tbd: true };
  const [, mm, dd] = e.start_date.split("-");
  return { d: +dd, m: MONTHS[+mm - 1] };
}
function fmtRange(e) {
  if (!e.start_date) return e.typical_month ? `Data a confirmar · costuma ocorrer em ${MONTHS_FULL[e.typical_month - 1]}` : "Data a confirmar";
  const f = (iso) => new Date(iso + "T12:00:00").toLocaleDateString("pt-BR", { day: "2-digit", month: "short", year: "numeric" });
  return e.end_date && e.end_date !== e.start_date ? `${f(e.start_date)} – ${f(e.end_date)}` : f(e.start_date);
}
const place = (e) => e.format === "online" && !e.city ? "Online" : [e.city, e.state].filter(Boolean).join(" – ") || "Local a confirmar";
const pills = (e) => (e.themes || []).map((t) => state.themes[t] ? `<span class="pill" style="--c:${state.themes[t].color}">${esc(state.themes[t].label)}</span>` : "").join("");
const typeInfo = (e) => (state.meta.types || {})[e.type || "evento"] || { label: "Evento", icon: "📅" };
const typeLabel = (e, icon = false) => (icon ? typeInfo(e).icon + " " : "") + typeInfo(e).label;

/* Resumo curto: descrição do evento ou, sem ela, um resumo montado com o que se sabe */
function summaryOf(e) {
  const d = (e.summary || e.description || "").trim();
  if (d.length >= 40) return d;
  const temas = (e.themes || []).map((t) => state.themes[t]?.label).filter(Boolean);
  const onde = e.format === "online" ? "online" : e.city ? `em ${e.city}${e.state ? " – " + e.state : ""}` : "";
  const quem = e.organizer ? `, organizado por ${e.organizer}` : "";
  const base = `${typeInfo(e).label} sobre ${temas.length ? temas.join(", ") : "inovação"} ${onde}${quem}.`;
  return (d ? d + " " : "") + base.replace(/\s+/g, " ").replace(" .", ".");
}
const priceText = (e) => !e.price ? "Valor no site" : e.price === PAID ? "Pago · ver valor no site" : e.price;
const priceTag = (e) => `<span class="price ${e.price === "Gratuito" ? "free" : e.price && e.price !== PAID ? "" : "unknown"}">${esc(priceText(e))}</span>`;
const starBtn = (e) => `<button class="star ${state.favs.has(e.id) ? "on" : ""}" data-star="${e.id}" title="${state.favs.has(e.id) ? "Remover dos favoritos" : "Favoritar"}" aria-label="Favoritar" aria-pressed="${state.favs.has(e.id)}">${state.favs.has(e.id) ? "★" : "☆"}</button>`;
/* bolinhas com as iniciais de quem da equipe favoritou */
function favFaces(e) {
  const ms = membersWhoFav(e.id);
  if (!ms.length) return "";
  const names = ms.map((m) => m.name).join(", ");
  return `<span class="faces" title="Favoritado por: ${esc(names)}">${ms.slice(0, 4).map((m) => `<span class="avatar sm">${esc(initials(m.name))}</span>`).join("")}${ms.length > 4 ? `<span class="avatar sm more">+${ms.length - 4}</span>` : ""}</span>`;
}

function renderCards(v, list) {
  v.innerHTML = `<div class="grid">${list.map((e) => {
    const dp = dateParts(e);
    return `<article class="card" data-id="${e.id}">
      ${starBtn(e)}
      <div class="card-top">
        <div class="datebox ${dp.tbd ? "tbd" : ""}"><div class="d">${dp.d}</div><div class="m">${dp.m}</div></div>
        <div class="top-meta">
          <span class="cat">${typeInfo(e).icon} ${esc(typeInfo(e).label)}</span>
          ${e.is_new ? `<span class="badge new">Novo</span>` : ""}
          ${!e.start_date ? `<span class="badge soft">Data a confirmar</span>` : ""}
          ${e.start_date && e.date_confirmed === false ? `<span class="badge soft" title="Data identificada automaticamente — confirme no site">Data estimada</span>` : ""}
        </div>
      </div>
      <h3>${esc(e.name)}</h3>
      <div class="where">${PIN}<span>${esc(place(e))} · ${FORMAT_LABEL[e.format] || ""}</span></div>
      <p class="desc">${esc(summaryOf(e))}</p>
      <div class="card-foot"><div class="pills">${pills(e)}</div>${favFaces(e)}${priceTag(e)}</div>
    </article>`;
  }).join("")}</div>`;
}

function renderList(v, list) {
  let last = "";
  const rows = list.map((e) => {
    const key = e.start_date ? e.start_date.slice(0, 7) : "tbd";
    let sep = "";
    if (key !== last) {
      last = key;
      sep = `<div class="month-sep">${key === "tbd" ? "Data a confirmar" : `${MONTHS_FULL[+key.slice(5) - 1]} ${key.slice(0, 4)}`}</div>`;
    }
    const when = e.start_date ? new Date(e.start_date + "T12:00:00").toLocaleDateString("pt-BR", { day: "2-digit", month: "short" }) : "A confirmar";
    return `${sep}<div class="row" data-id="${e.id}">
      <div class="when">${when}</div>
      <div style="min-width:0"><div class="t">${esc(e.name)}</div><div class="sub2">${esc(summaryOf(e))}</div></div>
      <div class="where">${esc(place(e))}</div>
      <div class="fmt">${typeInfo(e).icon} ${esc(typeInfo(e).label)}</div>
      ${priceTag(e)}
      ${starBtn(e)}
    </div>`;
  }).join("");
  v.innerHTML = `<div class="list">${rows}</div>`;
}

function renderCalendar(v, list) {
  if (!state.calMonth) {
    const firstUp = list.find((e) => e.start_date && e.start_date >= (state.from || todayISO)) || list.find((e) => e.start_date);
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
    ${tbd ? `<p class="cal-note">+ ${tbd} evento(s) recorrente(s) que costumam ocorrer em ${MONTHS_FULL[m - 1]}, com data a confirmar.</p>` : ""}`;
}

/* ---------- Mapa (Leaflet + OpenStreetMap/CARTO) ---------- */
function renderMap(v, list) {
  if (!window.L) {
    v.innerHTML = `<div class="empty"><b>Carregando o mapa…</b>Se não aparecer, verifique sua conexão.</div>`;
    setTimeout(() => state.view === "map" && render(false), 600);
    return;
  }
  // agrupa por cidade
  const groups = {};
  let online = 0;
  for (const e of list) {
    if (e.lat == null || e.lon == null) { if (e.format === "online") online++; continue; }
    const k = `${strip(e.city || "")}|${e.state}`;
    const g = (groups[k] ||= { key: k, city: e.city || `${state.states[e.state] || e.state} (local a confirmar)`, uf: e.state, lat: e.lat, lon: e.lon, events: [] });
    if (e.city && /[^\x00-\x7F]/.test(e.city) && !/[^\x00-\x7F]/.test(g.city)) g.city = e.city; // prefere o nome com acento
    g.events.push(e);
  }
  const gl = Object.values(groups).sort((a, b) => b.events.length - a.events.length);

  if (state.map) { state.mapView = { c: state.map.getCenter(), z: state.map.getZoom() }; state.map.remove(); state.map = null; }
  v.innerHTML = `<div class="map-wrap">
      <div id="leafmap" role="region" aria-label="Mapa do Brasil com os eventos"></div>
      <aside class="map-side">
        <h3>${gl.length} cidade${gl.length === 1 ? "" : "s"} com eventos</h3>
        <p class="hint">Clique numa bolha ou cidade para ver os eventos.${online ? ` ${online} evento(s) online não aparecem no mapa.` : ""}</p>
        ${state.city ? `<button class="btn sm" data-clearcity="1" style="width:100%;margin-bottom:8px">Ver todas as cidades</button>` : ""}
        ${gl.map((g) => `<button class="city-row" data-city="${esc(g.key)}"><span>${esc(g.city)}<small>${esc(state.states[g.uf] || g.uf)}</small></span><b>${g.events.length}</b></button>`).join("") || `<p class="hint">Nenhum evento com local para os filtros atuais.</p>`}
      </aside>
    </div>`;

  const map = L.map("leafmap", { zoomControl: true, scrollWheelZoom: true, minZoom: 3, maxBounds: [[-40, -90], [12, -25]] });
  state.map = map;
  L.tileLayer(`https://{s}.basemaps.cartocdn.com/${isDark() ? "dark_all" : "light_all"}/{z}/{x}/{y}{r}.png`, {
    attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> &copy; <a href="https://carto.com/attributions">CARTO</a>',
    subdomains: "abcd", maxZoom: 18,
  }).addTo(map);
  if (state.mapView) map.setView(state.mapView.c, state.mapView.z);
  else map.fitBounds([[-33.8, -73.99], [5.3, -34.8]]);

  drawStates(map, list);

  const max = Math.max(1, ...gl.map((g) => g.events.length));
  state.mapGroups = groups;
  for (const g of gl) {
    const n = g.events.length;
    const size = Math.round(26 + 34 * Math.sqrt(n / max));
    const icon = L.divIcon({ className: "", html: `<div class="bubble" style="width:${size}px;height:${size}px;font-size:${size > 40 ? 14 : 12}px">${n}</div>`, iconSize: [size, size] });
    const mk = L.marker([g.lat, g.lon], { icon, title: `${g.city}: ${n} evento(s)`, riseOnHover: true }).addTo(map);
    mk.bindPopup(() => popupHtml(g), { maxWidth: 300 });
    g.marker = mk;
  }
}

function popupHtml(g) {
  const items = [...g.events].sort((a, b) => (a.start_date || "9999").localeCompare(b.start_date || "9999"));
  return `<div class="pop"><h4>${esc(g.city)} – ${esc(g.uf)} · ${items.length} evento${items.length === 1 ? "" : "s"}</h4>
    <ul>${items.slice(0, 30).map((e) => `<li data-pop="${e.id}"><span>${e.start_date ? e.start_date.slice(8, 10) + "/" + e.start_date.slice(5, 7) : "a conf."}</span>${esc(e.name)}</li>`).join("")}</ul>
    ${items.length > 30 ? `<p style="margin:6px 0 0;color:#777">+ ${items.length - 30} eventos</p>` : ""}
    <button class="pop-filter" data-popcity="${esc(g.key)}">Ver só os eventos desta cidade</button></div>`;
}

async function drawStates(map, list) {
  try {
    if (!state.statesGeo) state.statesGeo = await (await fetch(CONFIG.statesGeoJson)).json();
  } catch { return; }
  if (state.map !== map) return;
  const byUf = {};
  for (const e of list) if (e.state) byUf[e.state] = (byUf[e.state] || 0) + 1;
  const max = Math.max(1, ...Object.values(byUf));
  const nameToUf = Object.fromEntries(Object.entries(state.states).map(([uf, n]) => [strip(n), uf]));
  // aceita qualquer formato de propriedades: sigla ("SP") ou nome do estado
  const ufOf = (f) => {
    const vals = Object.values(f.properties || {}).filter((x) => typeof x === "string");
    for (const x of vals) if (/^[A-Za-z]{2}$/.test(x) && state.states[x.toUpperCase()]) return x.toUpperCase();
    for (const x of vals) if (nameToUf[strip(x)]) return nameToUf[strip(x)];
    return null;
  };
  const accent = getComputedStyle(document.documentElement).getPropertyValue("--accent").trim() || "#5a45e6";
  L.geoJSON(state.statesGeo, {
    style: (f) => {
      const n = byUf[ufOf(f)] || 0;
      return { color: accent, weight: 1, opacity: .45, fillColor: accent, fillOpacity: n ? .06 + .22 * (n / max) : 0 };
    },
    onEachFeature: (f, layer) => {
      const uf = ufOf(f);
      if (!uf) return;
      layer.bindTooltip(`${state.states[uf] || uf}: ${byUf[uf] || 0} evento(s)`, { sticky: true });
      layer.on("click", () => { state.uf = uf; state.city = ""; state.mapView = null; $("#fState").value = uf; render(); });
    },
  }).addTo(map).bringToBack();
}

/* ---------- interações ---------- */
function onViewClick(ev) {
  const star = ev.target.closest("[data-star]");
  if (star) {
    ev.stopPropagation();
    toggleFav(star.dataset.star);
    render(false);
    return;
  }
  const cal = ev.target.closest("[data-cal]");
  if (cal) {
    const [y, m] = state.calMonth.split("-").map(Number);
    const d = new Date(y, m - 1 + +cal.dataset.cal, 1);
    state.calMonth = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}`;
    render();
    return;
  }
  const pop = ev.target.closest("[data-pop]");
  if (pop) { openModal(state.all.find((x) => x.id === pop.dataset.pop)); return; }
  const popCity = ev.target.closest("[data-popcity]");
  if (popCity) { state.city = popCity.dataset.popcity; setView("cards"); return; }
  if (ev.target.closest("[data-clearcity]")) { state.city = ""; state.mapView = null; render(); return; }
  const cityRow = ev.target.closest("[data-city]");
  if (cityRow && state.map) {
    const g = state.mapGroups?.[cityRow.dataset.city];
    if (g) { state.map.setView([g.lat, g.lon], Math.max(state.map.getZoom(), 9)); g.marker.openPopup(); }
    return;
  }
  const item = ev.target.closest("[data-id]");
  if (item) openModal(state.all.find((x) => x.id === item.dataset.id));
}

function openModal(e) {
  if (!e) return;
  const rows = [
    ["Quando", fmtRange(e) + (e.start_date && e.date_confirmed === false ? " (estimada — confirme no site)" : "")],
    ["Onde", [e.venue, place(e)].filter(Boolean).join(" · ")],
    ["Categoria", typeLabel(e, true)],
    ["Formato", FORMAT_LABEL[e.format]],
    ["Valor", priceText(e)],
    ["Organização", e.organizer],
    ["Favoritado por", membersWhoFav(e.id).map((m) => m.name).join(", ")],
    ["Fontes", (e.sources || [e.source]).join(", ")],
  ].filter(([, v]) => v);
  $("#modalBody").innerHTML = `
    <button class="btn ghost sm icon close" aria-label="Fechar">✕</button>
    <div class="pills">${pills(e)}</div>
    <h2>${esc(e.name)}</h2>
    <p class="desc">${esc(e.description && e.description.length >= 40 ? e.description : summaryOf(e))}</p>
    <dl class="kv">${rows.map(([k, v]) => `<dt>${k}</dt><dd>${esc(v)}</dd>`).join("")}</dl>
    <div class="actions">
      ${e.url ? `<a class="btn primary" href="${esc(e.url)}" target="_blank" rel="noopener">Ver no site do evento ↗</a>` : ""}
      ${e.start_date ? `<a class="btn" href="${gcalUrl(e)}" target="_blank" rel="noopener">Adicionar ao Google Agenda</a>
      <button class="btn" id="oneIcs" type="button">Baixar .ics</button>` : ""}
      <button class="btn" id="favModal" type="button">${state.favs.has(e.id) ? "★ Favorito" : "☆ Favoritar"}</button>
    </div>`;
  $("#oneIcs")?.addEventListener("click", () => download(`${e.id}.ics`, toICS([e]), "text/calendar"));
  $("#favModal").addEventListener("click", () => {
    toggleFav(e.id); if (state.view !== "map") render(false); openModal(e);
  });
  if (!$("#modal").open) $("#modal").showModal();
}

/* ---------- exportações ---------- */
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
  const cols = ["name", "type", "price", "start_date", "end_date", "city", "state", "region", "venue", "format", "themes", "organizer", "url", "description"];
  const head = ["Nome", "Categoria", "Valor", "Início", "Fim", "Cidade", "UF", "Região", "Local", "Formato", "Temas", "Organização", "Link", "Descrição"];
  const rows = list.map((e) => ({ ...e, type: typeLabel(e), price: priceText(e) }));
  const q = (v) => `"${String(Array.isArray(v) ? v.map((t) => state.themes[t]?.label || t).join(" | ") : v ?? "").replace(/"/g, '""')}"`;
  download("eventos.csv", "﻿" + [head.join(";"), ...rows.map((e) => cols.map((c) => q(e[c])).join(";"))].join("\n"), "text/csv");
}
function download(name, content, type) {
  const a = document.createElement("a");
  a.href = URL.createObjectURL(new Blob([content], { type }));
  a.download = name; a.click();
  setTimeout(() => URL.revokeObjectURL(a.href), 1000);
}
