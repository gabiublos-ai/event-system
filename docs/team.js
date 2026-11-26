/* Acesso por convite + favoritos por pessoa (Firebase Authentication + Firestore).
 *
 * Só liga se docs/firebase-config.js tiver a configuração do projeto Firebase.
 * Sem ela, o site funciona como antes (favoritos guardados só no navegador).
 *
 * Dados no Firestore:
 *   admins/{email}   -> quem pode convidar (criado à mão no console do Firebase)
 *   invites/{email}  -> { name, email, invitedBy, invitedAt }  (lista de quem tem acesso)
 *   users/{uid}      -> { name, email, favs: [ids], updatedAt } (favoritos de cada pessoa)
 * Regras de segurança: firestore.rules (na raiz do repositório).
 */
window.Team = (() => {
  // guarda o endereço original: o link do e-mail traz o código de acesso na URL
  const START_HREF = location.href;
  const V = "13.4.0"; // versão do SDK do Firebase (a mesma indicada no console)
  const cfg = window.FIREBASE_CONFIG;
  const enabled = !!(cfg && cfg.apiKey && cfg.projectId);
  const EMAIL_KEY = "radar_email_login";
  let A, F, auth, db, unsubUsers = null;
  let onChange = () => {};
  const st = { status: enabled ? "loading" : "off", me: null, admin: false, members: [], error: "" };
  const emit = () => onChange({ ...st });
  const lower = (s) => String(s || "").trim().toLowerCase();
  const siteUrl = () => location.origin + location.pathname;
  const toIso = (ts) => (ts && typeof ts.toDate === "function" ? ts.toDate().toISOString() : null);

  async function init(cb) {
    onChange = cb || onChange;
    if (!enabled) { emit(); return; }
    try {
      const [app, a, f] = await Promise.all([
        import(`https://www.gstatic.com/firebasejs/${V}/firebase-app.js`),
        import(`https://www.gstatic.com/firebasejs/${V}/firebase-auth.js`),
        import(`https://www.gstatic.com/firebasejs/${V}/firebase-firestore.js`),
      ]);
      A = a; F = f;
      const fbApp = app.initializeApp(cfg);
      auth = A.getAuth(fbApp);
      auth.languageCode = "pt";
      db = F.getFirestore(fbApp);
    } catch (e) {
      st.status = "error"; st.error = "Não foi possível conectar ao serviço de login."; emit(); return;
    }
    // chegou pelo link do e-mail?
    // mantém a pessoa conectada neste navegador depois do primeiro acesso
    try { await A.setPersistence(auth, A.browserLocalPersistence); } catch { /* usa o padrão */ }
    if (A.isSignInWithEmailLink(auth, START_HREF)) {
      let email = null;
      try { email = localStorage.getItem(EMAIL_KEY); } catch { /* sem storage */ }
      if (email) await completeLink(email);
      else { st.status = "needEmail"; emit(); }
    }
    A.onAuthStateChanged(auth, (user) => { onAuth(user).catch((e) => { st.status = "error"; st.error = String(e.message || e); emit(); }); });
  }

  async function completeLink(email) {
    try {
      await A.signInWithEmailLink(auth, lower(email), START_HREF);
      try { localStorage.removeItem(EMAIL_KEY); } catch { /* ok */ }
      history.replaceState(null, "", siteUrl() + location.hash);
    } catch (e) {
      st.status = "signedOut";
      st.error = "Este link de acesso expirou ou já foi usado. Peça um novo abaixo.";
      emit();
    }
  }

  async function onAuth(user) {
    if (unsubUsers) { unsubUsers(); unsubUsers = null; }
    if (!user) { if (st.status !== "needEmail") st.status = "signedOut"; st.me = null; st.members = []; st.admin = false; emit(); return; }
    const email = lower(user.email);
    const [adm, inv] = await Promise.all([
      F.getDoc(F.doc(db, "admins", email)).catch(() => null),
      F.getDoc(F.doc(db, "invites", email)).catch(() => null),
    ]);
    st.admin = !!(adm && adm.exists());
    if (!st.admin && !(inv && inv.exists())) { st.status = "notInvited"; st.me = { email }; emit(); return; }
    const name = (inv && inv.exists() && inv.data().name) || (adm && adm.exists() && adm.data().name) || email.split("@")[0];
    st.me = { uid: user.uid, email, name };
    // primeiro acesso: leva os favoritos que já estavam neste navegador
    let local = [];
    try { local = JSON.parse(localStorage.getItem("favs") || "[]"); } catch { /* ok */ }
    // registra o acesso (aba Admin: último acesso e número de acessos)
    const data = { name, email, updatedAt: F.serverTimestamp(), lastSeen: F.serverTimestamp(), visits: F.increment(1) };
    if (local.length) data.favs = F.arrayUnion(...local);
    await F.setDoc(F.doc(db, "users", user.uid), data, { merge: true });
    unsubUsers = F.onSnapshot(F.collection(db, "users"), (snap) => {
      st.members = snap.docs.map((d) => {
        const x = d.data();
        return { uid: d.id, ...x, favs: x.favs || [], lastSeen: toIso(x.lastSeen), visits: x.visits || 0 };
      })
        .sort((a, b) => (a.name || "").localeCompare(b.name || "", "pt-BR"));
      st.status = "in"; emit();
    }, (e) => { st.status = "error"; st.error = String(e.message || e); emit(); });
  }

  async function requestLink(email) {
    email = lower(email);
    await A.sendSignInLinkToEmail(auth, email, { url: siteUrl(), handleCodeInApp: true });
    try { localStorage.setItem(EMAIL_KEY, email); } catch { /* ok */ }
  }

  async function setFav(id, on) {
    if (!st.me?.uid) return;
    await F.setDoc(F.doc(db, "users", st.me.uid), { favs: on ? F.arrayUnion(id) : F.arrayRemove(id), updatedAt: F.serverTimestamp() }, { merge: true });
  }

  async function invite(name, email) {
    email = lower(email);
    await F.setDoc(F.doc(db, "invites", email), { name: name.trim(), email, invitedBy: st.me.email, invitedAt: F.serverTimestamp() });
    // o próprio Firebase envia o e-mail com o link de acesso
    await A.sendSignInLinkToEmail(auth, email, { url: siteUrl(), handleCodeInApp: true });
  }

  async function listAdmins() {
    // a lista de administradores não é pública; o próprio admin sabe que é admin
    return st.admin ? [st.me.email] : [];
  }

  async function revoke(email) { await F.deleteDoc(F.doc(db, "invites", lower(email))); }

  async function listInvites() {
    const snap = await F.getDocs(F.collection(db, "invites"));
    return snap.docs.map((d) => ({ ...d.data(), invitedAt: toIso(d.data().invitedAt) })).sort((a, b) => (a.name || "").localeCompare(b.name || "", "pt-BR"));
  }

  async function signOut() { await A.signOut(auth); }

  return { enabled, init, completeLink, requestLink, setFav, invite, revoke, listInvites, listAdmins, signOut, siteUrl, state: () => ({ ...st }) };
})();
