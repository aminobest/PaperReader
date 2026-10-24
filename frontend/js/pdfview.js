// US-03 viewer · US-07 traceability overlays · US-08 annotation capture. pdf.js with lazy page rendering.
import * as pdfjsLib from '/vendor/pdfjs/pdf.min.mjs';
import { hitTest, normalizeRects } from './geometry.mjs';
import { esc } from './util.mjs';

pdfjsLib.GlobalWorkerOptions.workerSrc = '/vendor/pdfjs/pdf.worker.min.mjs';

export const ANN_COLORS = { yellow: '#fde047', green: '#86efac', blue: '#93c5fd', pink: '#f9a8d4', orange: '#fdba74', red: '#fca5a5' };

export class PdfView {
  constructor(root, handlers) {
    this.root = root;
    this.on = handlers; // onSelection(sel|null), onTapHits(hits, point, clientXY), onScale()
    this.docs = new Map();
    this.paperId = null;
    this.zoomFactor = 1;
    this.items = []; // overlay items: {id, type:'ann'|'map'|'chat', page, rects, color, strong, ...}
    root.classList.add('pdf-scroll');
    this.pagesEl = document.createElement('div');
    this.pagesEl.className = 'pdf-pages';
    root.append(this.pagesEl);
    this.observer = new IntersectionObserver((entries) => {
      for (const en of entries) if (en.isIntersecting) this._renderPage(Number(en.target.dataset.page));
    }, { root, rootMargin: '600px 0px' });
    this._bindSelection();
    new ResizeObserver(() => this._maybeRelayout()).observe(root);
  }

  async load(paperId) {
    if (this.paperId === paperId) return;
    this.paperId = paperId;
    this.pagesEl.innerHTML = '<div class="pdf-loading">Loading paper…</div>';
    if (!paperId) { this.pagesEl.innerHTML = '<div class="empty">No paper yet. Upload a PDF with “＋ Paper”.</div>'; return; }
    let entry = this.docs.get(paperId);
    if (!entry) {
      const doc = await pdfjsLib.getDocument({ url: `/api/papers/${paperId}/file`, withCredentials: true }).promise;
      const sizes = [];
      for (let i = 1; i <= doc.numPages; i++) {
        const vp = (await doc.getPage(i)).getViewport({ scale: 1 });
        sizes.push({ w: vp.width, h: vp.height });
      }
      entry = { doc, sizes };
      this.docs.set(paperId, entry);
    }
    if (this.paperId !== paperId) return;
    this.entry = entry;
    this._layout();
  }

  _baseScale() {
    const w = Math.max(...this.entry.sizes.map((s) => s.w));
    return Math.max(0.3, (this.root.clientWidth - 24) / w);
  }

  _layout() {
    this.observer.disconnect();
    this.scale = this._baseScale() * this.zoomFactor;
    this.lastWidth = this.root.clientWidth;
    this.pagesEl.innerHTML = this.entry.sizes.map((s, i) => `<div class="pdf-page" data-page="${i + 1}"
        style="width:${Math.floor(s.w * this.scale)}px;height:${Math.floor(s.h * this.scale)}px;--scale-factor:${this.scale}">
        <div class="hl-layer"></div><div class="pdf-pno">${i + 1}</div></div>`).join('');
    this.rendered = new Set();
    for (const el of this.pagesEl.children) this.observer.observe(el);
    this._paintOverlays();
  }

  _maybeRelayout() {
    if (!this.entry || Math.abs(this.root.clientWidth - this.lastWidth) < 30) return;
    clearTimeout(this._rt);
    this._rt = setTimeout(() => this._keepPosition(() => this._layout()), 150);
  }

  _keepPosition(fn) {
    const ratio = this.root.scrollTop / Math.max(1, this.root.scrollHeight);
    fn();
    this.root.scrollTop = ratio * this.root.scrollHeight;
  }

  setZoom(f) {
    this.zoomFactor = Math.max(0.5, Math.min(4, f));
    if (this.entry) this._keepPosition(() => this._layout());
  }

  pageEl(page) { return this.pagesEl.querySelector(`.pdf-page[data-page="${page}"]`); }

  async _renderPage(pno) {
    if (this.rendered.has(pno)) return;
    this.rendered.add(pno);
    const el = this.pageEl(pno);
    const page = await this.entry.doc.getPage(pno);
    const vp = page.getViewport({ scale: this.scale });
    const dpr = Math.min(window.devicePixelRatio || 1, 3);
    const canvas = document.createElement('canvas');
    canvas.width = Math.floor(vp.width * dpr); canvas.height = Math.floor(vp.height * dpr);
    canvas.style.width = `${Math.floor(vp.width)}px`; canvas.style.height = `${Math.floor(vp.height)}px`;
    const text = document.createElement('div');
    text.className = 'textLayer';
    el.prepend(canvas);
    el.append(text);
    await page.render({ canvasContext: canvas.getContext('2d'), viewport: vp, transform: dpr !== 1 ? [dpr, 0, 0, dpr, 0, 0] : null }).promise;
    await new pdfjsLib.TextLayer({ textContentSource: page.streamTextContent(), container: text, viewport: vp }).render();
    el.classList.add('ready');
  }

  // ---- overlays ----------------------------------------------------------------------------
  setItems(items) { this.items = items; this._paintOverlays(); }

  _paintOverlays() {
    if (!this.entry) return;
    const byPage = new Map();
    for (const it of this.items) {
      if (it.paper_id !== this.paperId) continue;
      if (!byPage.has(it.page)) byPage.set(it.page, []);
      byPage.get(it.page).push(it);
    }
    for (const el of this.pagesEl.children) {
      const layer = el.querySelector('.hl-layer');
      const list = byPage.get(Number(el.dataset.page)) || [];
      layer.innerHTML = list.flatMap((it) => it.rects.map((r) => `<div class="hl hl-${it.type}${it.strong ? ' strong' : ''}" data-item="${it.id}"
        style="left:${r[0] * 100}%;top:${r[1] * 100}%;width:${(r[2] - r[0]) * 100}%;height:${(r[3] - r[1]) * 100}%;--hc:${it.color}"></div>`)).join('');
    }
  }

  /** AT-07.1 — scroll so the given rect is visible near the top third. */
  scrollTo(page, rect) {
    const el = this.pageEl(page);
    if (!el) return;
    const y = el.offsetTop + (rect ? rect[1] * el.offsetHeight : 0) - this.root.clientHeight / 3;
    this.root.scrollTo({ top: Math.max(0, y), behavior: 'smooth' });
  }

  flash(itemId) {
    for (const d of this.pagesEl.querySelectorAll(`.hl[data-item="${itemId}"]`)) {
      d.classList.remove('flash'); void d.offsetWidth; d.classList.add('flash');
    }
  }

  // ---- selection & taps ----------------------------------------------------------------------
  currentSelection() {
    const sel = window.getSelection();
    if (!sel || sel.isCollapsed || !sel.rangeCount) return null;
    const range = sel.getRangeAt(0);
    if (!this.pagesEl.contains(range.commonAncestorContainer)) return null;
    const text = sel.toString().replace(/\s+/g, ' ').trim();
    if (!text) return null;
    const rects = [...range.getClientRects()];
    const parts = [];
    for (const el of this.pagesEl.children) {
      const box = el.getBoundingClientRect();
      const r = normalizeRects(rects.filter((cr) => cr.top < box.bottom && cr.bottom > box.top), box);
      if (r.length) parts.push({ paperId: this.paperId, page: Number(el.dataset.page), rects: r });
    }
    if (!parts.length) return null;
    const last = rects[rects.length - 1];
    return { text, parts, paperId: this.paperId, page: parts[0].page, rects: parts[0].rects, anchor: { x: last.right, y: last.bottom } };
  }

  _bindSelection() {
    let t;
    const fire = () => { clearTimeout(t); t = setTimeout(() => this.on.onSelection(this.currentSelection()), 120); };
    document.addEventListener('selectionchange', fire);
    let down = null;
    this.root.addEventListener('pointerdown', (e) => { down = { x: e.clientX, y: e.clientY }; });
    this.root.addEventListener('pointerup', (e) => {
      if (!down || Math.hypot(e.clientX - down.x, e.clientY - down.y) > 6) return;
      const sel = window.getSelection();
      if (sel && !sel.isCollapsed) return;
      const pageEl = e.target.closest('.pdf-page');
      if (!pageEl) return;
      const box = pageEl.getBoundingClientRect();
      const point = { x: (e.clientX - box.left) / box.width, y: (e.clientY - box.top) / box.height };
      const page = Number(pageEl.dataset.page);
      const hits = hitTest(point, this.items.filter((it) => it.paper_id === this.paperId && it.page === page && !it.hidden));
      this.on.onTapHits(hits, { x: e.clientX, y: e.clientY });
    });
  }
}

export function colorDots(selected) {
  return Object.entries(ANN_COLORS).map(([name, hex]) => `<button class="dot${name === selected ? ' on' : ''}" data-color="${name}" style="--dot:${hex}" aria-label="${esc(name)} highlight" title="${esc(name)}"></button>`).join('');
}
