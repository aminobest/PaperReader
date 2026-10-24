// US-07 — workspace orchestrator: map ↔ paper traceability, layers, uploads, responsive panes (US-12).
import { api, confirmDialog, dialog, errorToast, h, toast, waitJob } from './api.js';
import { overlappingQuotes } from './geometry.mjs';
import { defaultLayout, dragSplitter, foldFlags, gridFor, layoutMode, resetSplitter, sanitizeLayout } from './layout.mjs';
import { MindMap } from './mindmap.js';
import { ANN_COLORS, colorDots, PdfView } from './pdfview.js';
import { ChatPanel, NodePanel, NotesPanel } from './panels.js';
import { esc } from './util.mjs';

export class Workspace {
  constructor(root, sessionId, app) {
    this.root = root;
    this.sid = sessionId;
    this.app = app;
    this.selected = [];
    this.layers = JSON.parse(localStorage.getItem('pr.layers') || '{"map":true,"chat":true,"ann":true}');
    this.annotations = new Map(); // paperId -> list
    this.chatQuotes = [];
    this.activeChatId = null;
    this.map = null;
  }

  async init() {
    [this.config, this.session, this.chatQuotes, this.prefs] = await Promise.all([
      api('/config'), api(`/sessions/${this.sid}`), api(`/sessions/${this.sid}/quotes`), api('/prefs')]);
    this.root.innerHTML = this._skeleton();
    this.$('.ws').style.setProperty('--chat', this.config.chat_color);
    this.mm = new MindMap(this.$('.mm-host'), {
      onSelect: (id, add) => this.selectNodes(id ? (add ? toggleIn(this.selected, id) : [id]) : []),
      onToggle: (id, collapsed) => this.toggleFold(id, collapsed),
      onUnfold: (id) => this._persistFold(() => api(`/nodes/${id}`, { method: 'PATCH', body: { collapsed: false } })),
      onOpen: (id) => { this.selectNodes([id]); this.showSide('node'); this.nodePanel.edit(); },
      onKey: (action, id) => this.nodePanel.keyAction(action, id),
    });
    this.pdf = new PdfView(this.$('.pdf-host'), {
      onSelection: (sel) => this.onPaperSelection(sel),
      onTapHits: (hits, xy) => this.onTapHits(hits, xy),
    });
    this.nodePanel = new NodePanel(this, this.$('[data-panel=node]'));
    this.notesPanel = new NotesPanel(this, this.$('[data-panel=notes]'));
    this.chatPanel = new ChatPanel(this, this.$('[data-panel=chat]'));
    this._bindChrome();
    this._applyMode();
    window.addEventListener('resize', () => this._applyMode());
    this.renderPapers();
    this.renderMaps();
    const firstPaper = this.session.papers[0]?.id || null;
    await this.showPaper(firstPaper);
    const m = this.session.maps.filter((x) => x.status === 'ready').at(-1) || this.session.maps.at(-1);
    if (m) await this.loadMap(m.id); else this.renderMapEmpty();
    this.notesPanel.load();
    this.chatPanel.load();
    this.nodePanel.render();
  }

  $(sel) { return this.root.querySelector(sel); }

  _skeleton() {
    return `<div class="ws">
      <header class="ws-top">
        <a class="btn ghost icon" href="#/" aria-label="All sessions">‹</a>
        <button class="ws-title" data-act="rename-session" title="Rename session">${esc(this.session.name)}</button>
        <div class="ws-top-actions">
          <select class="map-select" aria-label="Mind map"></select>
          <button class="btn" data-act="new-map">＋ Map</button>
          <label class="btn">＋ Paper<input type="file" accept="application/pdf,.pdf" multiple hidden data-upload></label>
          <button class="btn ghost icon layout-btn" data-act="layout" aria-label="Layout" title="Layout">▦</button>
          <button class="btn ghost icon side-toggle" data-act="toggle-side" aria-label="Side panel">☰</button>
        </div>
      </header>
      <main class="ws-main">
        <section class="pane pane-map" data-pane="map">
          <div class="pane-bar">
            <div class="seg depth" role="group" aria-label="Depth"></div>
            <span class="spacer"></span>
            <button class="btn ghost icon" data-act="zoom-out" aria-label="Zoom out">−</button>
            <button class="btn ghost icon" data-act="fit" aria-label="Fit map">⤢</button>
            <button class="btn ghost icon" data-act="zoom-in" aria-label="Zoom in">＋</button>
          </div>
          <div class="mm-host"></div>
          <div class="map-status"></div>
          <div class="node-chip" hidden></div>
        </section>
        <div class="split" data-split="sa" title="Drag to resize · double-click to reset"></div>
        <section class="pane pane-paper" data-pane="paper">
          <div class="pane-bar">
            <select class="paper-select" aria-label="Paper"></select>
            <button class="btn ghost icon" data-act="paper-menu" aria-label="Paper actions">⋯</button>
            <span class="spacer"></span>
            <div class="seg layers" role="group" aria-label="Layers">
              <button data-layer="map" style="--lc:${this.config.map_color}" title="Map quotes">Map</button>
              <button data-layer="chat" style="--lc:${this.config.chat_color}" title="Chat quotes">AI</button>
              <button data-layer="ann" style="--lc:#eab308" title="My highlights">Mine</button>
            </div>
            <button class="btn ghost icon" data-act="pdf-zoom-out" aria-label="Zoom out paper">−</button>
            <button class="btn ghost icon" data-act="pdf-zoom-in" aria-label="Zoom in paper">＋</button>
          </div>
          <div class="pdf-host"></div>
        </section>
        <div class="split" data-split="sb" title="Drag to resize · double-click to reset"></div>
        <aside class="pane pane-side" data-pane="side">
          <div class="tabs" role="tablist">
            <button data-side="node" class="on">Node</button><button data-side="notes">Notes</button><button data-side="chat">Chat</button>
          </div>
          <div class="side-body">
            <div data-panel="node"></div><div data-panel="notes" hidden></div><div data-panel="chat" hidden></div>
          </div>
        </aside>
      </main>
      <nav class="ws-tabs">
        <button data-tab="map" class="on">Map</button><button data-tab="paper">Paper</button>
        <button data-tab="node">Node</button><button data-tab="notes">Notes</button><button data-tab="chat">Chat</button>
      </nav>
      <div class="sel-bar" hidden></div>
      <div class="popover" hidden></div>
    </div>`;
  }

  // ---- responsive (US-12) ------------------------------------------------------------------
  _applyMode() {
    const ws = this.$('.ws');
    const mode = layoutMode(window.innerWidth);
    const changed = ws.dataset.mode !== mode;
    ws.dataset.mode = mode;
    if (!ws.dataset.tab) ws.dataset.tab = 'map';
    if (changed || !this.layout) this.layout = mode === 'phone' ? null : sanitizeLayout(this.prefs?.[`layout.${mode}`], mode);
    this._applyLayout();
    if (changed && this.mm) requestAnimationFrame(() => this.mm.fit());
  }

  // ---- US-13 user layout ---------------------------------------------------------------------
  _applyLayout() {
    const ws = this.$('.ws');
    const main = this.$('.ws-main');
    if (!this.layout) {
      ws.dataset.layout = 'tabs';
      main.style.gridTemplateAreas = main.style.gridTemplateColumns = main.style.gridTemplateRows = '';
      return;
    }
    const g = gridFor(this.layout);
    if (this.layout.side === 'drawer' && ws.dataset.layout !== 'drawer') ws.classList.remove('side-open');
    ws.dataset.layout = this.layout.side;
    main.style.gridTemplateAreas = g.areas;
    main.style.gridTemplateColumns = g.columns;
    main.style.gridTemplateRows = g.rows;
  }

  async _saveLayout() {
    const key = `layout.${this.$('.ws').dataset.mode}`;
    this.prefs = { ...this.prefs, [key]: this.layout };
    try { await api(`/prefs/${key}`, { method: 'PUT', body: this.layout }); } catch (e) { errorToast(e); }
  }

  _afterLayout() {
    this._applyLayout();
    requestAnimationFrame(() => this.mm.fit());
  }

  setLayout(patch) {
    this.layout = { ...this.layout, ...patch };
    this._afterLayout();
    this._saveLayout();
  }

  async resetLayout() {
    const mode = this.$('.ws').dataset.mode;
    this.layout = defaultLayout(mode);
    delete this.prefs[`layout.${mode}`];
    this._afterLayout();
    try { await api(`/prefs/layout.${mode}`, { method: 'DELETE' }); } catch (e) { errorToast(e); }
  }

  layoutMenu(anchor) {
    const pop = this.$('.popover');
    const tablet = this.$('.ws').dataset.mode === 'tablet';
    const pos = [['right', 'Right'], ['left', 'Left'], ['bottom', 'Bottom (footer)'], ...(tablet ? [['drawer', 'Drawer']] : [])];
    pop.innerHTML = `<div class="layout-menu"><b>Notes · Chat · Node panel</b>
      <div class="seg wrap">${pos.map(([v, l]) => `<button data-lay-side="${v}" class="${this.layout.side === v ? 'on' : ''}">${l}</button>`).join('')}</div>
      <button class="pop-row" data-lay="swap">⇄ Swap map and paper</button>
      <button class="pop-row" data-lay="reset">↺ Reset layout</button>
      <p class="muted small">Drag the dividers to resize; double-click a divider to reset it.</p></div>`;
    pop.hidden = false;
    const r = anchor.getBoundingClientRect();
    Object.assign(pop.style, { left: `${Math.max(8, Math.min(window.innerWidth - 300, r.right - 290))}px`, top: `${r.bottom + 6}px` });
    pop.onclick = (e) => {
      const b = e.target.closest('[data-lay-side],[data-lay]');
      if (!b) return;
      if (b.dataset.laySide) this.setLayout({ side: b.dataset.laySide });
      else if (b.dataset.lay === 'swap') this.setLayout({ swap: !this.layout.swap });
      else this.resetLayout();
      pop.hidden = true;
    };
    const away = (e) => { if (!pop.contains(e.target) && e.target !== anchor) { pop.hidden = true; document.removeEventListener('pointerdown', away, true); } };
    setTimeout(() => document.addEventListener('pointerdown', away, true), 0);
  }

  showTab(tab) {
    const ws = this.$('.ws');
    if (['node', 'notes', 'chat'].includes(tab)) { this.showSide(tab); ws.dataset.tab = 'side'; } else ws.dataset.tab = tab;
    for (const b of this.root.querySelectorAll('.ws-tabs button')) b.classList.toggle('on', b.dataset.tab === tab);
    if (tab === 'map') requestAnimationFrame(() => this.mm.reveal(this.selected[0]));
  }

  showSide(name) {
    for (const b of this.root.querySelectorAll('[data-side]')) b.classList.toggle('on', b.dataset.side === name);
    for (const p of this.root.querySelectorAll('[data-panel]')) p.hidden = p.dataset.panel !== name;
    this.$('.ws').classList.add('side-open');
    if (layoutMode(window.innerWidth) === 'phone') {
      this.$('.ws').dataset.tab = 'side';
      for (const b of this.root.querySelectorAll('.ws-tabs button')) b.classList.toggle('on', b.dataset.tab === name);
    }
  }

  _bindChrome() {
    const ws = this.$('.ws');
    ws.addEventListener('click', (e) => {
      const b = e.target.closest('[data-act],[data-side],[data-tab],[data-layer],[data-depth]');
      if (!b) return;
      if (b.dataset.side) return this.showSide(b.dataset.side);
      if (b.dataset.tab) return this.showTab(b.dataset.tab);
      if (b.dataset.layer) return this.toggleLayer(b.dataset.layer);
      if (b.dataset.depth) return this.fold(b.dataset.depth);
      const act = b.dataset.act;
      const fns = {
        'rename-session': () => this.renameSession(),
        'new-map': () => this.newMap(),
        'toggle-side': () => ws.classList.toggle('side-open'),
        layout: () => this.layoutMenu(b),
        'zoom-in': () => this.mm.zoom(1.25), 'zoom-out': () => this.mm.zoom(0.8), fit: () => this.mm.fit(),
        'pdf-zoom-in': () => this.pdf.setZoom(this.pdf.zoomFactor * 1.2), 'pdf-zoom-out': () => this.pdf.setZoom(this.pdf.zoomFactor / 1.2),
        'paper-menu': () => this.paperMenu(),
        'open-node': () => this.showTab('node'), 'open-paper': () => this.showTab('paper'),
      };
      fns[act]?.();
    });
    this.$('.map-select').onchange = (e) => this.loadMap(e.target.value);
    this.$('.paper-select').onchange = (e) => this.showPaper(e.target.value);
    this.$('[data-upload]').onchange = (e) => this.upload([...e.target.files]).finally(() => { e.target.value = ''; });
    this.$('.pane-paper').addEventListener('dragover', (e) => e.preventDefault());
    this.$('.pane-paper').addEventListener('drop', (e) => { e.preventDefault(); this.upload([...e.dataTransfer.files]); });
    for (const s of this.root.querySelectorAll('.split')) this._bindSplit(s);
    for (const b of this.root.querySelectorAll('[data-layer]')) b.classList.toggle('on', !!this.layers[b.dataset.layer]);
  }

  /** AT-13.1 — drag a divider (mouse, pen or finger); AT-13.4 — double-click resets it. */
  _bindSplit(el) {
    const which = el.dataset.split;
    el.addEventListener('pointerdown', (e) => {
      if (!this.layout) return;
      e.preventDefault();
      el.setPointerCapture(e.pointerId);
      el.classList.add('dragging');
      const main = this.$('.ws-main').getBoundingClientRect();
      const a = this.$('.pane-map').getBoundingClientRect(), b = this.$('.pane-paper').getBoundingClientRect();
      const panes = { left: Math.min(a.left, b.left), width: Math.max(a.right, b.right) - Math.min(a.left, b.left) };
      const move = (ev) => { this.layout = dragSplitter(this.layout, which, { x: ev.clientX, y: ev.clientY }, panes, main); this._applyLayout(); };
      const up = () => {
        el.classList.remove('dragging');
        el.removeEventListener('pointermove', move); el.removeEventListener('pointerup', up); el.removeEventListener('pointercancel', up);
        this.mm.fit();
        this._saveLayout();
      };
      el.addEventListener('pointermove', move); el.addEventListener('pointerup', up); el.addEventListener('pointercancel', up);
    });
    el.addEventListener('dblclick', () => {
      if (!this.layout) return;
      this.layout = resetSplitter(this.layout, which, this.$('.ws').dataset.mode);
      this._afterLayout();
      this._saveLayout();
    });
  }

  // ---- session & papers ------------------------------------------------------------------
  async renameSession() {
    const v = await dialog({ title: 'Rename session', fields: [{ name: 'name', label: 'Name', value: this.session.name }] });
    if (!v) return;
    try { this.session = { ...this.session, ...(await api(`/sessions/${this.sid}`, { method: 'PATCH', body: v })) }; this.$('.ws-title').textContent = this.session.name; } catch (e) { errorToast(e); }
  }

  renderPapers() {
    const sel = this.$('.paper-select');
    sel.innerHTML = this.session.papers.length
      ? this.session.papers.map((p) => `<option value="${p.id}">${esc(p.title)} · ${p.page_count}p</option>`).join('')
      : '<option value="">No papers</option>';
    if (this.pdf.paperId) sel.value = this.pdf.paperId;
  }

  async upload(files) {
    files = files.filter((f) => f.name.toLowerCase().endsWith('.pdf') || f.type === 'application/pdf');
    if (!files.length) return toast('Choose PDF files', 'error');
    const form = new FormData();
    for (const f of files) form.append('files', f);
    toast(`Uploading ${files.length} paper(s)…`);
    try {
      const created = await api(`/sessions/${this.sid}/papers`, { method: 'POST', form });
      this.session.papers.push(...created);
      this.renderPapers();
      await this.showPaper(created[0].id);
      toast('Uploaded. Create a mind map with “＋ Map”.', 'ok');
    } catch (e) { errorToast(e); }
  }

  async showPaper(paperId) {
    if (!paperId) { await this.pdf.load(null); return; }
    this.$('.paper-select').value = paperId;
    try {
      await this.pdf.load(paperId);
      if (!this.annotations.has(paperId)) this.annotations.set(paperId, await api(`/papers/${paperId}/annotations`));
      this.refreshOverlays();
    } catch (e) { errorToast(e); }
  }

  async paperMenu() {
    const p = this.session.papers.find((x) => x.id === this.pdf.paperId);
    if (!p) return;
    const v = await dialog({ title: 'Paper', fields: [{ name: 'title', label: 'Title', value: p.title }, { name: 'delete', type: 'checkbox', label: 'Delete this paper (its highlights and map quotes are removed)' }] });
    if (!v) return;
    try {
      if (v.delete) {
        if (!(await confirmDialog('Delete paper?', p.title))) return;
        await api(`/papers/${p.id}`, { method: 'DELETE' });
        this.session.papers = this.session.papers.filter((x) => x.id !== p.id);
        this.pdf.docs.delete(p.id); this.pdf.paperId = null;
        this.renderPapers();
        await this.showPaper(this.session.papers[0]?.id || null);
        if (this.map) await this.loadMap(this.map.id);
      } else {
        Object.assign(p, await api(`/papers/${p.id}`, { method: 'PATCH', body: { title: v.title } }));
        this.renderPapers();
      }
    } catch (e) { errorToast(e); }
  }

  // ---- maps ------------------------------------------------------------------------------
  renderMaps() {
    const sel = this.$('.map-select');
    sel.innerHTML = this.session.maps.length
      ? this.session.maps.map((m) => `<option value="${m.id}">${esc(m.title || 'Untitled map')}${m.status !== 'ready' ? ` (${m.status})` : ''}</option>`).join('')
      : '<option value="">No maps</option>';
    if (this.map) sel.value = this.map.id;
  }

  renderMapEmpty() {
    this.$('.map-status').innerHTML = this.session.papers.length
      ? '<div class="empty">Create a mind map with <b>＋ Map</b> — pick one paper or several.</div>'
      : '<div class="empty">Upload a paper with <b>＋ Paper</b> to begin.</div>';
  }

  async newMap() {
    if (!this.session.papers.length) return toast('Upload a paper first', 'error');
    const v = await dialog({
      title: 'New mind map', ok: 'Create',
      fields: [
        { name: 'paper_ids', type: 'checks', label: 'Papers', options: this.session.papers.map((p) => ({ value: p.id, label: p.title })), value: [this.pdf.paperId || this.session.papers[0].id] },
        { name: 'title', label: 'Title (optional)', placeholder: 'The AI proposes one' },
        { name: 'generate', type: 'checkbox', label: 'Build it with AI (takes 1–3 min)', value: true },
      ],
    });
    if (!v) return;
    try {
      const { map, job } = await api(`/sessions/${this.sid}/maps`, { method: 'POST', body: v });
      this.session.maps.push(map);
      this.renderMaps();
      await this.loadMap(map.id);
      if (job) this.trackMapJob(map.id, job);
    } catch (e) { errorToast(e); }
  }

  async trackMapJob(mapId, job) {
    try {
      const done = await waitJob(job, (j, s) => this._mapProgress(mapId, `Building the mind map… ${s}s`));
      const r = done.report || {};
      toast(`Map ready: ${r.nodes} nodes, ${r.quotes_verified} verified quotes${r.quotes_dropped ? `, ${r.quotes_dropped} unverifiable dropped` : ''}.`, 'ok', 6000);
    } catch (e) { errorToast(e); }
    await this.reloadSessionMaps();
    if (this.map?.id === mapId) await this.loadMap(mapId);
  }

  _mapProgress(mapId, text) {
    if (this.map?.id === mapId) this.$('.map-status').innerHTML = `<div class="busy"><span class="spinner"></span>${esc(text)}</div>`;
  }

  async reloadSessionMaps() {
    this.session.maps = (await api(`/sessions/${this.sid}`)).maps;
    this.renderMaps();
  }

  async loadMap(mapId, opts = {}) {
    if (!mapId) { this.map = null; this.mm.setMap({ nodes: [], links: [], quotes: [] }); this.renderMapEmpty(); this.refreshOverlays(); this.nodePanel.render(); return; }
    const seq = this._mapSeq = (this._mapSeq || 0) + 1;
    let map;
    try { map = await api(`/maps/${mapId}`); } catch (e) { return errorToast(e); }
    if (seq !== this._mapSeq) return; // a newer load or local change won the race
    this.map = map;
    this.$('.map-select').value = mapId;
    this.$('.map-status').innerHTML = this.map.status === 'failed'
      ? `<div class="empty error">Generation failed: ${esc(this.map.error || '')}<br>Delete this map and try again (maybe another model in Admin).</div>`
      : '';
    if (this.map.status === 'generating') {
      this._mapProgress(mapId, 'Building the mind map…');
      clearTimeout(this._poll);
      this._poll = setTimeout(async () => { await this.reloadSessionMaps(); if (this.map?.id === mapId) this.loadMap(mapId); }, 4000);
    }
    this.mm.setMap(this.map, opts);
    this.selected = this.selected.filter((id) => this.mm.byId.has(id));
    this.mm.setSelected(this.selected);
    this.renderDepth();
    this.refreshOverlays();
    this.nodePanel.render();
  }

  renderDepth() {
    const max = this.mm.maxDepth();
    const levels = [];
    for (let d = 1; d < Math.min(max, 5); d++) levels.push(d);
    this.$('.depth').innerHTML = `<span class="muted small">Depth</span>${levels.map((d) => `<button data-depth="${d}" title="Show ${d} level(s) below the centre">${d}</button>`).join('')}<button data-depth="all">All</button>`;
  }

  /** AT-06.5 — show the map down to a depth (persisted as fold state). */
  async fold(depth) {
    const d = depth === 'all' ? null : Number(depth);
    const flags = foldFlags(this.map.nodes, d);
    for (const n of this.map.nodes) n.collapsed = flags.get(n.id) ? 1 : 0;
    this._mapSeq = (this._mapSeq || 0) + 1; // responses already in flight are now stale
    this.mm.setMap(this.map);
    await this._persistFold(() => api(`/maps/${this.map.id}/fold`, { method: 'POST', body: { depth: d } }));
  }

  /** Fold writes are queued so the server applies them in the order the user made them. */
  _persistFold(write) {
    this._foldQueue = (this._foldQueue || Promise.resolve()).then(write).catch(async (e) => {
      errorToast(e);
      await this.loadMap(this.map.id, { keepView: true });
    });
    return this._foldQueue;
  }

  /** Fold/unfold one branch: instant on screen, persisted in the background. */
  async toggleFold(id, collapsed) {
    const n = this.mm.byId.get(id);
    if (!n) return;
    n.collapsed = collapsed ? 1 : 0;
    this._mapSeq = (this._mapSeq || 0) + 1;
    this.mm.render();
    await this._persistFold(() => api(`/nodes/${id}`, { method: 'PATCH', body: { collapsed } }));
  }

  async patchNode(id, body, { reload = true } = {}) {
    try {
      const res = await api(`/nodes/${id}`, { method: 'PATCH', body });
      if (reload) await this.loadMap(this.map.id, { keepView: true });
      return res;
    } catch (e) { errorToast(e); return null; }
  }

  // ---- traceability (US-07) ----------------------------------------------------------------
  nodeQuotes(ids) { return (this.map?.quotes || []).filter((q) => ids.includes(q.node_id)); }

  /** AT-07.1 — select nodes, highlight their quotes, jump to the first one. */
  selectNodes(ids, { jump = true } = {}) {
    this.selected = ids;
    this.mm.ensureVisible(ids);
    this.mm.setSelected(ids);
    this.mm.setRelated([]);
    this.refreshOverlays();
    this.nodePanel.render();
    this.notesPanel.renderFilter();
    this._renderChip();
    const first = this.nodeQuotes(ids)[0];
    if (jump && first) this.goToQuote(first);
  }

  async goToQuote(q, { flash = true } = {}) {
    if (q.paper_id !== this.pdf.paperId) await this.showPaper(q.paper_id);
    this.pdf.scrollTo(q.page, q.rects[0]);
    if (flash) setTimeout(() => this.pdf.flash(q.id), 350);
  }

  _renderChip() {
    const chip = this.$('.node-chip');
    const n = this.selected.length === 1 && this.mm.byId.get(this.selected[0]);
    chip.hidden = !n;
    if (n) {
      const q = this.nodeQuotes([n.id]).length;
      chip.innerHTML = `<b>${esc(n.title)}</b><span class="muted">❝${q}</span><button class="btn small" data-act="open-paper">Paper</button><button class="btn small primary" data-act="open-node">Details</button>`;
    }
  }

  toggleLayer(name) {
    this.layers[name] = !this.layers[name];
    localStorage.setItem('pr.layers', JSON.stringify(this.layers));
    for (const b of this.root.querySelectorAll('[data-layer]')) b.classList.toggle('on', !!this.layers[b.dataset.layer]);
    this.refreshOverlays();
  }

  refreshOverlays() {
    const items = [];
    const sel = new Set(this.selected);
    if (this.layers.map) {
      for (const q of this.map?.quotes || []) items.push({ ...q, type: 'map', color: this.config.map_color, strong: sel.has(q.node_id) });
    }
    if (this.layers.chat) {
      for (const q of this.chatQuotes) items.push({ ...q, type: 'chat', color: this.config.chat_color, strong: q.chat_id === this.activeChatId });
    }
    if (this.layers.ann) {
      for (const a of this.annotations.get(this.pdf.paperId) || []) items.push({ ...a, type: 'ann', color: ANN_COLORS[a.color], strong: true });
    }
    this.pdf.setItems(items);
  }

  async refreshChatQuotes() {
    this.chatQuotes = await api(`/sessions/${this.sid}/quotes`);
    this.refreshOverlays();
  }

  /** AT-07.2 — a passage selected in the paper lights up the nodes whose quotes overlap it. */
  onPaperSelection(sel) {
    const bar = this.$('.sel-bar');
    if (!sel) {
      if (!bar.matches(':hover') && !bar.contains(document.activeElement)) { bar.hidden = true; this.mm.setRelated([]); }
      return;
    }
    this.lastSelection = sel;
    const quotes = this.map?.quotes || [];
    const related = [...new Set(sel.parts.flatMap((p) => overlappingQuotes(p, quotes)).map((q) => q.node_id))];
    this.mm.setRelated(related);
    const one = this.selected.length === 1 ? this.mm.byId.get(this.selected[0]) : null;
    bar.innerHTML = `<div class="dots">${colorDots()}</div>
      <button class="btn small" data-sel="ask">Ask AI</button>
      <button class="btn small" data-sel="note">Note</button>
      ${one ? `<button class="btn small" data-sel="link" title="Add this passage as evidence of “${esc(one.title)}”">Link to node</button>` : ''}
      ${related.length ? `<button class="btn small primary" data-sel="related">${related.length} node${related.length > 1 ? 's' : ''}</button>` : ''}`;
    bar.hidden = false;
    const x = Math.min(window.innerWidth - bar.offsetWidth - 8, Math.max(8, sel.anchor.x - bar.offsetWidth / 2));
    const y = Math.min(window.innerHeight - bar.offsetHeight - 8, sel.anchor.y + 14);
    Object.assign(bar.style, { left: `${x}px`, top: `${y}px` });
    bar.onpointerdown = (e) => e.preventDefault(); // keep the text selection alive
    bar.onclick = (e) => this._selAction(e, related);
  }

  async _selAction(e, related) {
    const b = e.target.closest('[data-color],[data-sel]');
    if (!b) return;
    const sel = this.lastSelection;
    this.$('.sel-bar').hidden = true;
    try {
      if (b.dataset.color) {
        for (const part of sel.parts) {
          const a = await api(`/papers/${part.paperId}/annotations`, { method: 'POST', body: { page: part.page, rects: part.rects, color: b.dataset.color, text: sel.text } });
          this.annotations.get(part.paperId).push(a);
        }
        window.getSelection().removeAllRanges();
        this.refreshOverlays();
      } else if (b.dataset.sel === 'related') {
        this.selectNodes(related, { jump: false });
        this.mm.reveal(related[0]);
        if (layoutMode(window.innerWidth) === 'phone') this.showTab('map');
      } else if (b.dataset.sel === 'ask') {
        await this.chatPanel.start({ passage: sel.text, node_ids: this.selected, paper_ids: [sel.paperId] });
      } else if (b.dataset.sel === 'note') {
        await this.notesPanel.create(`> ${sel.text} (p.${sel.page})\n\n`);
      } else if (b.dataset.sel === 'link') {
        const nid = this.selected[0];
        await api(`/nodes/${nid}/quotes`, { method: 'POST', body: { paper_id: sel.paperId, page: sel.page, text: sel.text } });
        window.getSelection().removeAllRanges();
        await this.loadMap(this.map.id, { keepView: true });
        toast('Passage linked as evidence', 'ok');
      }
    } catch (err) { errorToast(err); }
  }

  /** AT-07.3 — tapping a highlight selects its node(s), opens its chat, or edits an annotation. */
  onTapHits(hits, xy) {
    const pop = this.$('.popover');
    pop.hidden = true;
    if (!hits.length) return;
    const nodeIds = [...new Set(hits.filter((x) => x.type === 'map').map((x) => x.node_id))];
    const anns = hits.filter((x) => x.type === 'ann');
    const chats = [...new Set(hits.filter((x) => x.type === 'chat').map((x) => x.chat_id))];
    if (nodeIds.length && !anns.length && !chats.length) {
      this.selectNodes(nodeIds, { jump: false });
      this.mm.reveal(nodeIds[0]);
      return;
    }
    const nodeBtns = nodeIds.map((id) => `<button class="pop-row" data-node="${id}">◉ ${esc(this.mm.byId.get(id)?.title || 'node')}</button>`).join('');
    const chatBtns = chats.map((id) => `<button class="pop-row" data-chat="${id}">💬 ${esc(this.chatPanel.title(id))}</button>`).join('');
    const annRows = anns.map((a) => `<div class="pop-ann" data-ann="${a.id}"><div class="dots">${colorDots(a.color)}</div>
        <textarea rows="2" placeholder="Comment…">${esc(a.comment)}</textarea>
        <div class="row"><button class="btn small" data-ann-save>Save</button><button class="btn small danger" data-ann-del>Delete</button></div></div>`).join('');
    pop.innerHTML = annRows + nodeBtns + chatBtns;
    pop.hidden = false;
    Object.assign(pop.style, { left: `${Math.min(window.innerWidth - 300, Math.max(8, xy.x - 140))}px`, top: `${Math.min(window.innerHeight - pop.offsetHeight - 8, xy.y + 12)}px` });
    pop.onclick = async (e) => {
      const t = e.target;
      try {
        if (t.closest('[data-node]')) { pop.hidden = true; const id = t.closest('[data-node]').dataset.node; this.selectNodes([id], { jump: false }); this.mm.reveal(id); return; }
        if (t.closest('[data-chat]')) { pop.hidden = true; return this.chatPanel.open(t.closest('[data-chat]').dataset.chat); }
        const row = t.closest('[data-ann]');
        if (!row) return;
        const id = row.dataset.ann;
        const list = this.annotations.get(this.pdf.paperId);
        const i = list.findIndex((a) => a.id === id);
        if (t.dataset.color) { list[i] = await api(`/annotations/${id}`, { method: 'PATCH', body: { color: t.dataset.color } }); row.querySelector('.dots').innerHTML = colorDots(list[i].color); }
        if (t.matches('[data-ann-save]')) { list[i] = await api(`/annotations/${id}`, { method: 'PATCH', body: { comment: row.querySelector('textarea').value } }); pop.hidden = true; toast('Saved', 'ok'); }
        if (t.matches('[data-ann-del]')) { await api(`/annotations/${id}`, { method: 'DELETE' }); list.splice(i, 1); pop.hidden = true; }
        this.refreshOverlays();
      } catch (err) { errorToast(err); }
    };
    const away = (e) => { if (!pop.contains(e.target)) { pop.hidden = true; document.removeEventListener('pointerdown', away, true); } };
    setTimeout(() => document.addEventListener('pointerdown', away, true), 0);
  }
}

function toggleIn(list, id) {
  return list.includes(id) ? list.filter((x) => x !== id) : [...list, id];
}
