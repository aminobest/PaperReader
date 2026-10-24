// US-06 node inspector & editing · US-09 notes · US-10 chat. Side-panel views driven by the Workspace.
import { api, confirmDialog, dialog, errorToast, toast, waitJob } from './api.js';
import { debounce, esc, renderMarkdown, timeAgo } from './util.mjs';

// ---- US-06 -----------------------------------------------------------------------------------
export class NodePanel {
  constructor(ws, el) {
    this.ws = ws;
    this.el = el;
    this.busy = new Map();
    this.editing = false;
    el.addEventListener('click', (e) => this._click(e));
  }

  get node() { return this.ws.selected.length === 1 ? this.ws.mm.byId.get(this.ws.selected[0]) : null; }

  path(n) {
    const out = [];
    for (let cur = n; cur; cur = cur.parent_id ? this.ws.mm.byId.get(cur.parent_id) : null) out.unshift(cur);
    return out;
  }

  render() {
    this.editing = false;
    const ws = this.ws;
    if (!ws.map) { this.el.innerHTML = '<div class="empty">No mind map yet.</div>'; return; }
    if (ws.selected.length > 1) {
      const ns = ws.selected.map((id) => ws.mm.byId.get(id)).filter(Boolean);
      this.el.innerHTML = `<h3>${ns.length} nodes selected</h3><ul class="plain">${ns.map((n) => `<li>${esc(n.title)}</li>`).join('')}</ul>
        <button class="btn primary" data-a="chat">💬 Chat about these</button>`;
      return;
    }
    const n = this.node;
    if (!n) {
      const r = ws.map.report || {};
      const papers = ws.session.papers.filter((p) => ws.map.paper_ids.includes(p.id)).map((p) => esc(p.title)).join(', ');
      this.el.innerHTML = `<h3>${esc(ws.map.title || 'Untitled map')}</h3>
        <p class="muted small">Papers: ${papers || '—'}</p>
        ${r.nodes ? `<p class="muted small">${r.nodes} nodes · ${r.quotes_verified} verified quotes${r.quotes_dropped ? ` · ${r.quotes_dropped} unverifiable dropped` : ''}${r.fix_rounds ? ` · ${r.fix_rounds} fix round(s)` : ''}</p>` : ''}
        <div class="actions"><button class="btn" data-a="rename-map">Rename map</button><button class="btn danger" data-a="delete-map">Delete map</button></div>
        <div class="tips"><b>Tips</b><ul>
          <li>Tap a node to light up its evidence in the paper.</li>
          <li>Select text in the paper to see related nodes, highlight it, or ask the AI.</li>
          <li>Use <b>Depth</b> to go from the big picture to the details.</li>
          <li>Keyboard: Tab child · Enter sibling · F2 edit · Del delete · Space fold · arrows move.</li></ul></div>`;
      return;
    }
    const quotes = ws.nodeQuotes([n.id]);
    const links = (ws.map.links || []).filter((l) => l.source_id === n.id || l.target_id === n.id);
    const busy = this.busy.get(n.id);
    const crumbs = this.path(n).slice(0, -1).map((p) => `<button class="crumb" data-sel="${p.id}">${esc(p.title)}</button>`).join('<span>›</span>');
    this.el.innerHTML = `<div class="crumbs">${crumbs}</div>
      <h3 class="node-title">${esc(n.title)} <span class="kind kind-${n.kind}">${esc(n.kind)}</span></h3>
      <p class="explain">${esc(n.explanation) || '<span class="muted">No explanation yet.</span>'}</p>
      ${busy ? `<div class="busy"><span class="spinner"></span>${esc(busy)}</div>` : ''}
      <div class="actions">
        <button class="btn" data-a="edit">✏️ Edit</button><button class="btn" data-a="child">＋ Child</button>
        <button class="btn" data-a="expand" ${busy ? 'disabled' : ''}>🔍 Go deeper (AI)</button>
        <button class="btn" data-a="reground" ${busy ? 'disabled' : ''}>🎯 Re-find evidence (AI)</button>
        <button class="btn" data-a="chat">💬 Chat</button><button class="btn" data-a="note">📝 Note</button>
        <button class="btn" data-a="link">🔗 Link to…</button>
        ${n.parent_id ? '<button class="btn danger" data-a="delete">🗑 Delete</button>' : ''}
      </div>
      <h4>Evidence in the paper <span class="muted">(${quotes.length})</span></h4>
      ${quotes.length ? quotes.map((q) => `<div class="quote" data-quote="${q.id}"><span class="pg">${esc(this._paperLabel(q.paper_id))} p.${q.page}</span>“${esc(q.text)}”<button class="x" data-del-quote="${q.id}" aria-label="Remove quote">×</button></div>`).join('')
        : '<p class="muted small">No quotes. Select a passage in the paper and choose “Link to node”, or use “Re-find evidence”.</p>'}
      ${links.length ? `<h4>Relations</h4>${links.map((l) => {
        const other = ws.mm.byId.get(l.source_id === n.id ? l.target_id : l.source_id);
        const dir = l.source_id === n.id ? '→' : '←';
        return `<div class="link-row"><span>${dir} <i>${esc(l.label || 'related to')}</i> <button class="crumb" data-sel="${other?.id}">${esc(other?.title || '?')}</button></span>
          <span><button class="x" data-edit-link="${l.id}" aria-label="Rename relation">✎</button><button class="x" data-del-link="${l.id}" aria-label="Delete relation">×</button></span></div>`;
      }).join('')}` : ''}`;
  }

  _paperLabel(pid) {
    const ps = this.ws.session.papers;
    return ps.length > 1 ? `P${ps.findIndex((p) => p.id === pid) + 1}` : '';
  }

  async _click(e) {
    const t = e.target.closest('button,[data-quote]');
    if (!t) return;
    const ws = this.ws, n = this.node;
    try {
      if (t.dataset.sel) return ws.selectNodes([t.dataset.sel]);
      if (t.dataset.delQuote) { await api(`/quotes/${t.dataset.delQuote}`, { method: 'DELETE' }); return ws.loadMap(ws.map.id, { keepView: true }); }
      if (t.dataset.delLink) { await api(`/links/${t.dataset.delLink}`, { method: 'DELETE' }); return ws.loadMap(ws.map.id, { keepView: true }); }
      if (t.dataset.editLink) {
        const l = ws.map.links.find((x) => x.id === t.dataset.editLink);
        const v = await dialog({ title: 'Relation label', fields: [{ name: 'label', label: 'Label', value: l.label }] });
        if (v) { await api(`/links/${l.id}`, { method: 'PATCH', body: v }); await ws.loadMap(ws.map.id, { keepView: true }); }
        return;
      }
      if (t.dataset.quote) { const q = ws.map.quotes.find((x) => x.id === t.dataset.quote); if (q) { await ws.goToQuote(q); if (window.innerWidth < 700) ws.showTab('paper'); } return; }
      const a = t.dataset.a;
      if (a === 'rename-map') {
        const v = await dialog({ title: 'Rename map', fields: [{ name: 'title', label: 'Title', value: ws.map.title }] });
        if (v) { await api(`/maps/${ws.map.id}`, { method: 'PATCH', body: v }); await ws.reloadSessionMaps(); await ws.loadMap(ws.map.id, { keepView: true }); }
      } else if (a === 'delete-map') {
        if (!(await confirmDialog('Delete map?', `“${ws.map.title}” and its nodes, quotes and relations will be deleted. Notes are kept.`))) return;
        await api(`/maps/${ws.map.id}`, { method: 'DELETE' });
        ws.map = null;
        await ws.reloadSessionMaps();
        await ws.loadMap(ws.session.maps.at(-1)?.id || null);
      } else if (a === 'edit') this.edit();
      else if (a === 'child') await this.addNode(n.id);
      else if (a === 'delete') await this.remove(n);
      else if (a === 'expand') await this.runJob(n, 'expand', 'Going deeper…');
      else if (a === 'reground') await this.runJob(n, 'reground', 'Finding evidence…');
      else if (a === 'chat') await ws.chatPanel.start({ node_ids: ws.selected });
      else if (a === 'note') await ws.notesPanel.create('');
      else if (a === 'link') await this.link(n);
    } catch (err) { errorToast(err); }
  }

  edit() {
    const n = this.node;
    if (!n) return;
    const ws = this.ws;
    const descendants = new Set([n.id]);
    let grew = true;
    while (grew) { grew = false; for (const x of ws.map.nodes) if (x.parent_id && descendants.has(x.parent_id) && !descendants.has(x.id)) { descendants.add(x.id); grew = true; } }
    const parents = ws.map.nodes.filter((x) => !descendants.has(x.id));
    this.editing = true;
    this.el.innerHTML = `<form class="node-form">
      <label>Title<input name="title" value="${esc(n.title)}" required></label>
      <label>Kind<select name="kind">${ws.config.kinds.map((k) => `<option ${k === n.kind ? 'selected' : ''}>${k}</option>`).join('')}</select></label>
      <label>Explanation<textarea name="explanation" rows="6">${esc(n.explanation)}</textarea></label>
      ${n.parent_id ? `<label>Parent (move)<select name="parent_id">${parents.map((p) => `<option value="${p.id}" ${p.id === n.parent_id ? 'selected' : ''}>${esc(this.path(p).map((x) => x.title).join(' › '))}</option>`).join('')}</select></label>` : ''}
      <label class="check"><input type="checkbox" name="reground" checked> Re-derive the evidence with AI if the title or explanation changed</label>
      <div class="actions"><button type="button" class="btn ghost" data-cancel>Cancel</button><button class="btn primary">Save</button></div></form>`;
    const form = this.el.querySelector('form');
    form.querySelector('[data-cancel]').onclick = () => this.render();
    form.onsubmit = async (e) => {
      e.preventDefault();
      const f = form.elements;
      const body = { title: f.title.value, kind: f.kind.value, explanation: f.explanation.value };
      if (f.parent_id) body.parent_id = f.parent_id.value;
      if (!f.reground.checked) body.reground = false;
      const res = await ws.patchNode(n.id, body);
      if (res?.job) await this.trackJob(n, res.job, 'reground', 'Finding evidence…');
    };
    form.elements.title.focus();
  }

  async addNode(parentId) {
    const v = await dialog({ title: 'New node', fields: [{ name: 'title', label: 'Title' }, { name: 'explanation', type: 'textarea', label: 'Explanation (optional)', rows: 3 },
      { name: 'ground', type: 'checkbox', label: 'Find its evidence in the paper with AI', value: true }] });
    if (!v) return;
    const node = await api(`/maps/${this.ws.map.id}/nodes`, { method: 'POST', body: { parent_id: parentId, ...v } });
    const parent = this.ws.mm.byId.get(parentId);
    if (parent?.collapsed) await api(`/nodes/${parentId}`, { method: 'PATCH', body: { collapsed: false } });
    await this.ws.loadMap(this.ws.map.id, { keepView: true });
    this.ws.selectNodes([node.id], { jump: false });
    if (node.job) await this.trackJob(node, node.job, 'reground', 'Finding evidence…');
  }

  async remove(n) {
    const kids = this.ws.map.nodes.filter((x) => x.parent_id === n.id).length;
    if (!(await confirmDialog('Delete node?', `“${n.title}”${kids ? ' and everything under it' : ''} will be deleted. Linked notes are kept.`))) return;
    await api(`/nodes/${n.id}`, { method: 'DELETE' });
    this.ws.selected = n.parent_id ? [n.parent_id] : [];
    await this.ws.loadMap(this.ws.map.id, { keepView: true });
    this.ws.selectNodes(this.ws.selected, { jump: false });
  }

  async link(n) {
    const others = this.ws.map.nodes.filter((x) => x.id !== n.id);
    const v = await dialog({ title: `Relate “${n.title}” to…`, fields: [
      { name: 'target_id', type: 'select', label: 'Node', options: others.map((o) => ({ value: o.id, label: this.path(o).map((x) => x.title).join(' › ') })) },
      { name: 'label', label: 'Relation', placeholder: 'e.g. is evidence for' }] });
    if (!v) return;
    await api(`/maps/${this.ws.map.id}/links`, { method: 'POST', body: { source_id: n.id, ...v } });
    await this.ws.loadMap(this.ws.map.id, { keepView: true });
  }

  async runJob(n, kind, label) {
    const job = await api(`/nodes/${n.id}/${kind}`, { method: 'POST' });
    await this.trackJob(n, job, kind, label);
  }

  async trackJob(n, job, kind, label) {
    this.busy.set(n.id, label);
    if (this.node?.id === n.id) this.render();
    try {
      const done = await waitJob(job, (j, s) => { this.busy.set(n.id, `${label} ${s}s`); if (this.node?.id === n.id && !this.editing) this.render(); });
      const r = done.report || {};
      toast(kind === 'expand' ? `Added ${r.nodes} nodes · ${r.quotes_verified} verified quotes` : (r.note || `${r.quotes_verified} verified quotes`), 'ok', 5000);
    } catch (e) { errorToast(e); }
    this.busy.delete(n.id);
    await this.ws.loadMap(this.ws.map.id, { keepView: true });
    if (this.ws.selected.includes(n.id)) this.ws.selectNodes(this.ws.selected);
  }

  async keyAction(action, id) {
    const n = this.ws.mm.byId.get(id);
    try {
      if (action === 'add-child') await this.addNode(id);
      if (action === 'add-sibling') await this.addNode(n.parent_id);
      if (action === 'delete') await this.remove(n);
    } catch (e) { errorToast(e); }
  }
}

// ---- US-09 -------------------------------------------------------------------------------------
export class NotesPanel {
  constructor(ws, el) {
    this.ws = ws;
    this.el = el;
    this.notes = [];
    this.onlyNode = false;
    this.current = null;
    el.addEventListener('click', (e) => this._click(e));
  }

  async load() {
    try { this.notes = await api(`/sessions/${this.ws.sid}/notes`); } catch (e) { return errorToast(e); }
    if (!this.current) this.renderList();
  }

  renderFilter() { if (!this.current) this.renderList(); }

  renderList() {
    this.current = null;
    const nid = this.ws.selected.length === 1 ? this.ws.selected[0] : null;
    const list = this.onlyNode && nid ? this.notes.filter((n) => n.node_id === nid) : this.notes;
    this.el.innerHTML = `<div class="panel-head"><button class="btn primary" data-n="new">＋ Note</button>
        ${nid ? `<label class="check small"><input type="checkbox" data-n="filter" ${this.onlyNode ? 'checked' : ''}> Only this node</label>` : ''}</div>
      ${list.length ? list.map((n) => `<button class="note-item" data-open="${n.id}"><b>${esc(n.title)}</b>
        <span class="muted small">${n.node_id ? `◉ ${esc(this.ws.mm.byId.get(n.node_id)?.title || 'node in another map')} · ` : ''}${timeAgo(n.updated_at)}</span>
        <span class="snippet">${esc(n.body.slice(0, 140))}</span></button>`).join('') : '<div class="empty">No notes yet.</div>'}`;
  }

  async create(body) {
    const node_id = this.ws.selected.length === 1 ? this.ws.selected[0] : null;
    const note = await api(`/sessions/${this.ws.sid}/notes`, { method: 'POST', body: { body, node_id } });
    this.notes.unshift(note);
    this.ws.showSide('notes');
    this.openEditor(note);
  }

  openEditor(note) {
    this.current = note;
    const node = note.node_id && this.ws.mm.byId.get(note.node_id);
    this.el.innerHTML = `<div class="panel-head"><button class="btn ghost" data-n="back">‹ Notes</button><span class="muted small save-state">Saved</span>
        <button class="btn danger small" data-n="delete">Delete</button></div>
      ${note.node_id ? `<div class="chip">◉ <button class="crumb" data-n="goto">${esc(node?.title || 'node')}</button><button class="x" data-n="unlink" aria-label="Unlink">×</button></div>` : ''}
      <textarea class="note-body" placeholder="Write your understanding… (first line = title)">${esc(note.body)}</textarea>`;
    const ta = this.el.querySelector('.note-body');
    const state = this.el.querySelector('.save-state');
    const save = debounce(async () => {
      try {
        const upd = await api(`/notes/${note.id}`, { method: 'PATCH', body: { body: ta.value } });
        Object.assign(note, upd);
        state.textContent = 'Saved';
      } catch (e) { state.textContent = 'Not saved!'; errorToast(e); }
    }, 600);
    this._flush = () => save.flush();
    ta.addEventListener('input', () => { state.textContent = 'Saving…'; save(); });
    ta.addEventListener('blur', () => { if (state.textContent !== 'Saved') save.flush(); });
    ta.focus();
    ta.setSelectionRange(ta.value.length, ta.value.length);
  }

  async _click(e) {
    const t = e.target.closest('[data-n],[data-open]');
    if (!t) return;
    try {
      if (t.dataset.open) return this.openEditor(this.notes.find((n) => n.id === t.dataset.open));
      const a = t.dataset.n;
      if (a === 'new') await this.create('');
      if (a === 'filter') { this.onlyNode = t.checked; this.renderList(); }
      if (a === 'back') { const s = this.el.querySelector('.save-state'); if (s && s.textContent !== 'Saved') this._flush?.(); this.renderList(); }
      if (a === 'goto') this.ws.selectNodes([this.current.node_id]);
      if (a === 'unlink') { Object.assign(this.current, await api(`/notes/${this.current.id}`, { method: 'PATCH', body: { unlink: true } })); this.openEditor(this.current); }
      if (a === 'delete') {
        if (!(await confirmDialog('Delete note?', this.current.title))) return;
        await api(`/notes/${this.current.id}`, { method: 'DELETE' });
        this.notes = this.notes.filter((n) => n.id !== this.current.id);
        this.renderList();
      }
    } catch (err) { errorToast(err); }
  }
}

// ---- US-10 ----------------------------------------------------------------------------------------
export class ChatPanel {
  constructor(ws, el) {
    this.ws = ws;
    this.el = el;
    this.chats = [];
    this.chat = null;
    this.pending = null;
    el.addEventListener('click', (e) => this._click(e));
  }

  title(id) { return this.chats.find((c) => c.id === id)?.title || 'chat'; }

  async load() {
    try { this.chats = await api(`/sessions/${this.ws.sid}/chats`); } catch (e) { return errorToast(e); }
    if (!this.chat) this.renderList();
  }

  renderList() {
    this.chat = null;
    this.ws.activeChatId = null;
    this.ws.refreshOverlays();
    const sel = this.ws.selected.length;
    this.el.innerHTML = `<div class="panel-head"><button class="btn primary" data-c="new">＋ ${sel ? `Chat about ${sel === 1 ? 'this node' : `${sel} nodes`}` : 'Chat about the paper'}</button></div>
      ${this.chats.length ? this.chats.map((c) => `<div class="chat-item"><button class="note-item" data-open="${c.id}"><b>${esc(c.title)}</b><span class="muted small">${timeAgo(c.updated_at)}</span></button>
        <button class="x" data-rename="${c.id}" aria-label="Rename chat">✎</button><button class="x" data-del="${c.id}" aria-label="Delete chat">×</button></div>`).join('')
        : '<div class="empty">Select a node (or text in the paper) and start a chat to understand it.</div>'}`;
  }

  async start(body) {
    const chat = await api(`/sessions/${this.ws.sid}/chats`, { method: 'POST', body: { map_id: this.ws.map?.id || null, node_ids: [], ...body } });
    this.chats.unshift(chat);
    this.ws.showSide('chat');
    await this.open(chat.id);
  }

  async open(id) {
    this.chat = await api(`/chats/${id}`);
    this.ws.activeChatId = id;
    this.ws.refreshOverlays();
    this.ws.showSide('chat');
    this.render();
  }

  render() {
    const c = this.chat;
    const ctxNodes = c.node_ids.map((id) => this.ws.mm.byId.get(id)?.title).filter(Boolean);
    this.el.innerHTML = `<div class="panel-head"><button class="btn ghost" data-c="back">‹ Chats</button><b class="grow">${esc(c.title)}</b></div>
      <div class="chat-ctx">${ctxNodes.map((t) => `<span class="chip">◉ ${esc(t)}</span>`).join('')}${c.passage ? `<blockquote>${esc(c.passage)}</blockquote>` : ''}</div>
      <div class="msgs">${c.messages.map((m) => this._msg(m)).join('')}${this.pending === c.id ? '<div class="msg assistant"><span class="spinner"></span> Thinking… (answers are checked against the paper)</div>' : ''}
        ${!c.messages.length && this.pending !== c.id ? '<div class="muted small">Ask anything — e.g. “Explain this like I’m new to the field”, “Why does this matter?”, “Give me an example”.</div>' : ''}</div>
      <form class="composer"><textarea name="q" rows="2" placeholder="Ask about this…" ${this.pending ? 'disabled' : ''}></textarea><button class="btn primary" ${this.pending ? 'disabled' : ''}>Send</button></form>`;
    const form = this.el.querySelector('form');
    const ta = form.elements.q;
    ta.addEventListener('keydown', (e) => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); form.requestSubmit(); } });
    form.onsubmit = (e) => { e.preventDefault(); this.send(ta.value); };
    const msgs = this.el.querySelector('.msgs');
    msgs.scrollTop = msgs.scrollHeight;
    if (!this.pending) ta.focus({ preventScroll: true });
  }

  _msg(m) {
    const del = m.id ? `<button class="x msg-del" data-del-msg="${m.id}" aria-label="Delete message" title="Delete">×</button>` : '';
    if (m.role === 'user') return `<div class="msg user">${del}${esc(m.content)}</div>`;
    const r = m.report || {};
    return `<div class="msg assistant">${del}${renderMarkdown(m.content)}${r.quotes_dropped ? `<div class="muted small">${r.quotes_dropped} citation(s) could not be verified in the paper and were removed.</div>` : ''}</div>`;
  }

  async send(text) {
    text = text.trim();
    if (!text || this.pending) return;
    const c = this.chat;
    c.messages.push({ role: 'user', content: text });
    this.pending = c.id;
    this.render();
    try {
      const job = await api(`/chats/${c.id}/messages`, { method: 'POST', body: { content: text } });
      await waitJob(job);
    } catch (e) { errorToast(e); }
    this.pending = null;
    if (this.chat?.id === c.id) await this.open(c.id);
    await this.ws.refreshChatQuotes();
  }

  async _click(e) {
    const t = e.target.closest('[data-c],[data-open],[data-del],[data-rename],[data-del-msg],.cite');
    if (!t) return;
    try {
      if (t.dataset.delMsg) {
        const m = this.chat.messages.find((x) => x.id === t.dataset.delMsg);
        const msg = m.role === 'user' ? 'This question and its answer will be deleted.' : 'This answer and its highlighted evidence will be deleted.';
        if (!(await confirmDialog('Delete message?', msg))) return;
        await api(`/messages/${m.id}`, { method: 'DELETE' });
        await this.open(this.chat.id);
        await this.ws.refreshChatQuotes();
        return;
      }
      if (t.classList.contains('cite')) {
        const q = this.chat.quotes.find((x) => x.id === t.dataset.quote);
        if (q) { await this.ws.goToQuote(q); if (window.innerWidth < 700) this.ws.showTab('paper'); }
        return;
      }
      if (t.dataset.open) return this.open(t.dataset.open);
      if (t.dataset.del) {
        if (!(await confirmDialog('Delete chat?', this.title(t.dataset.del)))) return;
        await api(`/chats/${t.dataset.del}`, { method: 'DELETE' });
        this.chats = this.chats.filter((c) => c.id !== t.dataset.del);
        await this.ws.refreshChatQuotes();
        return this.renderList();
      }
      if (t.dataset.rename) {
        const c = this.chats.find((x) => x.id === t.dataset.rename);
        const v = await dialog({ title: 'Rename chat', fields: [{ name: 'title', label: 'Title', value: c.title }] });
        if (v) { Object.assign(c, await api(`/chats/${c.id}`, { method: 'PATCH', body: v })); this.renderList(); }
        return;
      }
      if (t.dataset.c === 'new') await this.start({ node_ids: this.ws.selected });
      if (t.dataset.c === 'back') { await this.load(); this.renderList(); }
    } catch (err) { errorToast(err); }
  }
}
