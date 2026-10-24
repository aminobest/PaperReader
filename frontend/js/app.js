// US-01 login · US-02 sessions list · router. Entry point of the PWA.
import { api, ApiError, confirmDialog, dialog, errorToast } from './api.js';
import { esc, timeAgo } from './util.mjs';
import { Workspace } from './workspace.js';

const root = document.getElementById('app');
let me = null;

window.addEventListener('pr:unauthorized', () => { me = null; showLogin(); });
window.addEventListener('hashchange', route);

async function boot() {
  try { me = await api('/auth/me'); } catch (e) { if (!(e instanceof ApiError && e.status === 401)) errorToast(e); }
  if (!me) return showLogin();
  route();
}

function showLogin() {
  root.innerHTML = `<div class="login"><form class="card">
      <h1>📄 PaperReader</h1><p class="muted">Understand papers fast — every idea traced to the text.</p>
      <label>Username<input name="username" autocomplete="username" autocapitalize="none" required></label>
      <label>Password<input name="password" type="password" autocomplete="current-password" required></label>
      <p class="error-text" hidden></p>
      <button class="btn primary big">Sign in</button></form></div>`;
  const form = root.querySelector('form');
  form.onsubmit = async (e) => {
    e.preventDefault();
    try {
      me = await api('/auth/login', { method: 'POST', body: { username: form.username.value, password: form.password.value } });
      route();
    } catch (err) {
      const p = form.querySelector('.error-text');
      p.hidden = false; p.textContent = err.message;
    }
  };
}

async function route() {
  if (!me) return showLogin();
  const hash = location.hash || '#/';
  if (location.pathname === '/admin' || hash.startsWith('#/admin')) {
    const { renderAdmin } = await import('./admin.js');
    return renderAdmin(root, me);
  }
  const m = hash.match(/^#\/s\/(\w+)/);
  if (m) {
    const ws = new Workspace(root, m[1], { me });
    try { await ws.init(); } catch (e) { errorToast(e); location.hash = '#/'; }
    return;
  }
  return renderSessions();
}

async function renderSessions() {
  let sessions = [];
  try { sessions = await api('/sessions'); } catch (e) { return errorToast(e); }
  root.innerHTML = `<div class="page">
    <header class="page-top"><h1>📄 PaperReader</h1><span class="spacer"></span>
      ${me.role === 'admin' ? '<a class="btn ghost" href="/admin">Admin</a>' : ''}
      <button class="btn ghost" data-a="logout">Sign out (${esc(me.username)})</button></header>
    <form class="new-session"><input name="name" placeholder="New session name, e.g. “Transformers reading group”" aria-label="Session name">
      <button class="btn primary">Create session</button></form>
    <div class="sessions">${sessions.length ? sessions.map((s) => `<div class="session-card" data-id="${s.id}">
        <a href="#/s/${s.id}" class="session-open"><b>${esc(s.name)}</b><span class="muted small">${s.paper_count} paper(s) · ${timeAgo(s.updated_at)}</span></a>
        <button class="x" data-rename="${s.id}" aria-label="Rename session">✎</button><button class="x" data-del="${s.id}" aria-label="Delete session">×</button></div>`).join('')
      : '<div class="empty">No sessions yet. Create one, then upload one or more papers.</div>'}</div></div>`;
  const form = root.querySelector('.new-session');
  form.onsubmit = async (e) => {
    e.preventDefault();
    try {
      const s = await api('/sessions', { method: 'POST', body: { name: form.name.value } });
      location.hash = `#/s/${s.id}`;
    } catch (err) { errorToast(err); }
  };
  root.querySelector('.page').onclick = async (e) => {
    const t = e.target.closest('[data-a],[data-rename],[data-del]');
    if (!t) return;
    try {
      if (t.dataset.a === 'logout') { await api('/auth/logout', { method: 'POST' }); me = null; return showLogin(); }
      const s = sessions.find((x) => x.id === (t.dataset.rename || t.dataset.del));
      if (t.dataset.rename) {
        const v = await dialog({ title: 'Rename session', fields: [{ name: 'name', label: 'Name', value: s.name }] });
        if (v) { await api(`/sessions/${s.id}`, { method: 'PATCH', body: v }); renderSessions(); }
      }
      if (t.dataset.del && await confirmDialog('Delete session?', `“${s.name}” with all its papers, maps, notes and chats will be deleted.`)) {
        await api(`/sessions/${s.id}`, { method: 'DELETE' });
        renderSessions();
      }
    } catch (err) { errorToast(err); }
  };
}

boot();
