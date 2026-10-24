// US-06 — interactive mind map: HTML nodes + SVG edges, pan / wheel / pinch zoom, collapse, depth, keyboard.
import { esc } from './util.mjs';
import { bounds, branchOf, childrenIndex, fitTransform, layoutTree, maxDepth, visibleNodes } from './layout.mjs';

const BRANCH_COLORS = ['#2563eb', '#16a34a', '#db2777', '#ea580c', '#7c3aed', '#0891b2', '#ca8a04', '#dc2626'];

export class MindMap {
  constructor(root, handlers) {
    this.root = root;
    this.on = handlers; // onSelect(id, additive), onToggle(id, collapsed), onOpen(id), onKey(action, id)
    this.map = null;
    this.selected = new Set();
    this.related = new Set();
    this.depth = Infinity;
    this.t = { s: 1, tx: 0, ty: 0 };
    this.pointers = new Map();
    root.classList.add('mm');
    root.tabIndex = 0;
    root.innerHTML = '<div class="mm-world"><svg class="mm-edges"></svg><div class="mm-nodes"></div></div>';
    this.world = root.querySelector('.mm-world');
    this.svg = root.querySelector('.mm-edges');
    this.layer = root.querySelector('.mm-nodes');
    this._bindGestures();
    root.addEventListener('keydown', (e) => this._key(e));
  }

  setMap(map, { keepView = false } = {}) {
    const firstLoad = !this.map || this.map.id !== map?.id;
    this.map = map;
    this.byId = new Map((map?.nodes || []).map((n) => [n.id, n]));
    this.quoteCount = new Map();
    for (const q of map?.quotes || []) this.quoteCount.set(q.node_id, (this.quoteCount.get(q.node_id) || 0) + 1);
    for (const id of [...this.selected]) if (!this.byId.has(id)) this.selected.delete(id);
    this.render();
    if (firstLoad || !keepView) this.fit();
  }

  maxDepth() { return this.map ? maxDepth(this.map.nodes) : 0; }

  setSelected(ids) { this.selected = new Set(ids); this._paintState(); }

  setRelated(ids) { this.ensureVisible(ids); this.related = new Set(ids); this._paintState(); if (ids.length) this.reveal(ids[0]); }

  /** Unfold ancestors so the given nodes are on screen (traceability from the paper). */
  ensureVisible(ids) {
    if (!this.map || !ids.length) return;
    const folded = [];
    for (const id of ids) {
      for (let p = this.byId.get(this.byId.get(id)?.parent_id); p; p = this.byId.get(p.parent_id)) {
        if (p.collapsed) folded.push(p.id);
      }
    }
    for (const id of new Set(folded)) { this.byId.get(id).collapsed = 0; this.on.onUnfold(id); }
    if (folded.length) this.render();
  }

  render() {
    const nodes = this.map?.nodes || [];
    const vis = visibleNodes(nodes, this.depth);
    const kids = childrenIndex(nodes);
    const branch = branchOf(nodes);
    const top = kids.get(null)?.[0];
    const branchColor = new Map((kids.get(top?.id) || []).map((n, i) => [n.id, BRANCH_COLORS[i % BRANCH_COLORS.length]]));
    this.layer.innerHTML = nodes.filter((n) => vis.has(n.id)).map((n) => {
      const d = vis.get(n.id);
      const nKids = (kids.get(n.id) || []).length;
      const hidden = nKids && n.collapsed;
      const color = d === 0 ? '#111827' : branchColor.get(branch.get(n.id)) || '#64748b';
      const q = this.quoteCount.get(n.id) || 0;
      return `<div class="mm-node d${Math.min(d, 3)} kind-${n.kind}" data-id="${n.id}" style="--c:${color}" title="${esc(n.explanation)}">
        <span class="mm-kind">${esc(n.kind)}</span><div class="mm-title">${esc(n.title)}</div>
        ${q ? `<span class="mm-badge" title="${q} supporting quote(s)">❝${q}</span>` : ''}
        ${nKids ? `<button class="mm-toggle" data-toggle="${n.id}" aria-label="${hidden ? 'expand' : 'collapse'}">${hidden ? `+${nKids}` : '−'}</button>` : ''}
      </div>`;
    }).join('');
    this.sizes = new Map();
    for (const el of this.layer.children) this.sizes.set(el.dataset.id, { w: el.offsetWidth, h: el.offsetHeight });
    this.pos = layoutTree(nodes, this.sizes, this.depth);
    for (const el of this.layer.children) {
      const p = this.pos.get(el.dataset.id), s = this.sizes.get(el.dataset.id);
      el.style.transform = `translate(${p.x - s.w / 2}px, ${p.y - s.h / 2}px)`;
      el.classList.toggle('left', p.side < 0);
    }
    this._drawEdges(nodes, vis, branch, branchColor);
    this._paintState();
  }

  _anchor(id, towardsX) {
    const p = this.pos.get(id), s = this.sizes.get(id);
    return { x: p.x + (towardsX >= p.x ? s.w / 2 : -s.w / 2), y: p.y };
  }

  _drawEdges(nodes, vis, branch, branchColor) {
    const paths = [];
    for (const n of nodes) {
      if (!n.parent_id || !this.pos.has(n.id) || !this.pos.has(n.parent_id)) continue;
      const c = this.pos.get(n.id);
      const a = this._anchor(n.parent_id, c.x), b = this._anchor(n.id, this.pos.get(n.parent_id).x);
      const mx = (a.x + b.x) / 2;
      const d = vis.get(n.id);
      const color = branchColor.get(branch.get(n.id)) || '#94a3b8';
      paths.push(`<path d="M${a.x},${a.y} C${mx},${a.y} ${mx},${b.y} ${b.x},${b.y}" stroke="${color}" stroke-width="${Math.max(1.5, 5 - d)}" fill="none" opacity=".75"/>`);
    }
    for (const l of this.map?.links || []) {
      if (!this.pos.has(l.source_id) || !this.pos.has(l.target_id)) continue;
      const a = this.pos.get(l.source_id), b = this.pos.get(l.target_id);
      const mx = (a.x + b.x) / 2, my = Math.min(a.y, b.y) - 40 - Math.abs(a.x - b.x) * 0.08;
      paths.push(`<path class="mm-link" data-link="${l.id}" d="M${a.x},${a.y} Q${mx},${my} ${b.x},${b.y}" fill="none"/>`);
      if (l.label) paths.push(`<text class="mm-link-label" x="${mx}" y="${(a.y + b.y) / 4 + my / 2}" text-anchor="middle">${esc(l.label)}</text>`);
    }
    const box = bounds(this.pos, this.sizes);
    const pad = 200;
    this.svg.setAttribute('viewBox', `${box.x0 - pad} ${box.y0 - pad} ${box.x1 - box.x0 + 2 * pad} ${box.y1 - box.y0 + 2 * pad}`);
    Object.assign(this.svg.style, { left: `${box.x0 - pad}px`, top: `${box.y0 - pad}px`, width: `${box.x1 - box.x0 + 2 * pad}px`, height: `${box.y1 - box.y0 + 2 * pad}px` });
    this.svg.innerHTML = paths.join('');
  }

  _paintState() {
    for (const el of this.layer.children) {
      el.classList.toggle('selected', this.selected.has(el.dataset.id));
      el.classList.toggle('related', this.related.has(el.dataset.id));
    }
  }

  // ---- view transform ---------------------------------------------------------------
  _apply() { this.world.style.transform = `translate(${this.t.tx}px, ${this.t.ty}px) scale(${this.t.s})`; }

  fit() {
    if (!this.pos?.size) return;
    const r = this.root.getBoundingClientRect();
    this.t = fitTransform(bounds(this.pos, this.sizes), r.width || 600, r.height || 400);
    this._apply();
  }

  zoom(factor, cx, cy) {
    const r = this.root.getBoundingClientRect();
    cx ??= r.width / 2; cy ??= r.height / 2;
    const s = Math.max(0.15, Math.min(3, this.t.s * factor));
    this.t.tx = cx - (cx - this.t.tx) * (s / this.t.s);
    this.t.ty = cy - (cy - this.t.ty) * (s / this.t.s);
    this.t.s = s;
    this._apply();
  }

  /** Make sure a node is visible (expand ancestors past the depth limit is not forced; just pan). */
  reveal(id) {
    const p = this.pos?.get(id);
    if (!p) return;
    const r = this.root.getBoundingClientRect();
    const x = p.x * this.t.s + this.t.tx, y = p.y * this.t.s + this.t.ty;
    if (x < 40 || x > r.width - 40 || y < 40 || y > r.height - 40) {
      this.t.tx += r.width / 2 - x; this.t.ty += r.height / 2 - y;
      this.world.style.transition = 'transform .25s';
      this._apply();
      setTimeout(() => { this.world.style.transition = ''; }, 300);
    }
  }

  _bindGestures() {
    const el = this.root;
    let moved = false, last = null, pinch = null, downTarget = null;
    el.addEventListener('pointerdown', (e) => {
      if (e.target.closest('button')) return;
      downTarget = e.target;
      this.pointers.set(e.pointerId, { x: e.clientX, y: e.clientY });
      moved = false; last = { x: e.clientX, y: e.clientY };
      if (this.pointers.size === 2) {
        const [p1, p2] = [...this.pointers.values()];
        pinch = { d: Math.hypot(p1.x - p2.x, p1.y - p2.y), s: this.t.s };
      }
    });
    el.addEventListener('pointermove', (e) => {
      if (!this.pointers.has(e.pointerId)) return;
      this.pointers.set(e.pointerId, { x: e.clientX, y: e.clientY });
      if (this.pointers.size === 2 && pinch) {
        const [p1, p2] = [...this.pointers.values()];
        const r = el.getBoundingClientRect();
        const d = Math.hypot(p1.x - p2.x, p1.y - p2.y);
        this.zoom((pinch.s * d / pinch.d) / this.t.s, (p1.x + p2.x) / 2 - r.left, (p1.y + p2.y) / 2 - r.top);
        moved = true;
        return;
      }
      const dx = e.clientX - last.x, dy = e.clientY - last.y;
      if (!moved && Math.abs(dx) + Math.abs(dy) > 3) {
        moved = true;
        try { el.setPointerCapture(e.pointerId); } catch { /* pointer already gone */ }
      }
      if (moved) { this.t.tx += dx; this.t.ty += dy; this._apply(); }
      last = { x: e.clientX, y: e.clientY };
    });
    const up = (e) => {
      const wasTap = !moved && this.pointers.size === 1;
      this.pointers.delete(e.pointerId);
      if (this.pointers.size < 2) pinch = null;
      if (wasTap && e.type === 'pointerup') this._tap(e, downTarget);
    };
    el.addEventListener('pointerup', up);
    el.addEventListener('pointercancel', up);
    el.addEventListener('click', (e) => {
      const t = e.target.closest('[data-toggle]');
      if (t) { const n = this.byId.get(t.dataset.toggle); this.on.onToggle(n.id, !n.collapsed); }
    });
    el.addEventListener('dblclick', (e) => {
      const n = e.target.closest('.mm-node');
      if (n) this.on.onOpen(n.dataset.id);
    });
    el.addEventListener('wheel', (e) => {
      e.preventDefault();
      const r = el.getBoundingClientRect();
      if (e.ctrlKey || e.metaKey) this.zoom(Math.exp(-e.deltaY * 0.01), e.clientX - r.left, e.clientY - r.top);
      else { this.t.tx -= e.deltaX; this.t.ty -= e.deltaY; this._apply(); }
    }, { passive: false });
    // Safari trackpad pinch
    let gs = 1;
    el.addEventListener('gesturestart', (e) => { e.preventDefault(); gs = 1; });
    el.addEventListener('gesturechange', (e) => { e.preventDefault(); this.zoom(e.scale / gs); gs = e.scale; });
  }

  _tap(e, target) {
    const n = (target || e.target).closest?.('.mm-node');
    if (n) { this.root.focus({ preventScroll: true }); this.on.onSelect(n.dataset.id, e.shiftKey || e.metaKey || e.ctrlKey); }
    else this.on.onSelect(null, false);
  }

  // ---- keyboard (desktop mind-map conventions) ------------------------------------------
  _key(e) {
    if (e.target !== this.root) return;
    const id = [...this.selected][0];
    const n = id && this.byId.get(id);
    const kids = childrenIndex(this.map?.nodes || []);
    const go = (target) => { if (target) { e.preventDefault(); this.on.onSelect(target.id, false); this.reveal(target.id); } };
    switch (e.key) {
      case 'Tab': if (n) { e.preventDefault(); this.on.onKey('add-child', id); } break;
      case 'Enter': if (n) { e.preventDefault(); this.on.onKey(n.parent_id ? 'add-sibling' : 'add-child', id); } break;
      case 'Delete': case 'Backspace': if (n?.parent_id) { e.preventDefault(); this.on.onKey('delete', id); } break;
      case 'F2': case 'e': if (n) { e.preventDefault(); this.on.onOpen(id); } break;
      case ' ': if (n) { e.preventDefault(); this.on.onToggle(id, !n.collapsed); } break;
      case 'f': e.preventDefault(); this.fit(); break;
      case 'ArrowLeft': case 'ArrowRight': {
        if (!n) { go(kids.get(null)?.[0]); break; }
        const side = this.pos.get(id)?.side || (e.key === 'ArrowRight' ? 1 : -1);
        const outward = (e.key === 'ArrowRight') === (side >= 0);
        if (outward) go((kids.get(id) || []).find((c) => this.pos.has(c.id)) || null);
        else go(n.parent_id ? this.byId.get(n.parent_id) : null);
        break;
      }
      case 'ArrowUp': case 'ArrowDown': {
        if (!n?.parent_id) break;
        const sibs = (kids.get(n.parent_id) || []).filter((c) => this.pos.has(c.id) && Math.sign(this.pos.get(c.id).side) === Math.sign(this.pos.get(id).side));
        const i = sibs.findIndex((c) => c.id === id);
        go(sibs[i + (e.key === 'ArrowDown' ? 1 : -1)]);
        break;
      }
      default:
    }
  }
}
