// US-06 / US-12 — pure layout helpers (no DOM): bilateral mind-map tree layout, depth filter, device mode.

export const H_GAP = 56;
export const V_GAP = 14;

/** AT-12.5 — layout mode from viewport width. */
export function layoutMode(width) {
  if (width >= 1100) return 'desktop';
  if (width >= 700) return 'tablet';
  return 'phone';
}

export function childrenIndex(nodes) {
  const byParent = new Map();
  for (const n of nodes) {
    const k = n.parent_id ?? null;
    if (!byParent.has(k)) byParent.set(k, []);
    byParent.get(k).push(n);
  }
  for (const list of byParent.values()) list.sort((a, b) => a.position - b.position || (a.created_at || '').localeCompare(b.created_at || ''));
  return byParent;
}

/** AT-06.5 — ids visible given collapsed flags and a depth limit (root = depth 0). */
export function visibleNodes(nodes, depthLimit = Infinity) {
  const kids = childrenIndex(nodes);
  const root = (kids.get(null) || [])[0];
  const out = new Map(); // id -> depth
  if (!root) return out;
  const stack = [[root, 0]];
  while (stack.length) {
    const [n, d] = stack.pop();
    out.set(n.id, d);
    if (n.collapsed || d >= depthLimit) continue;
    for (const c of kids.get(n.id) || []) stack.push([c, d + 1]);
  }
  return out;
}

export function maxDepth(nodes) {
  let m = 0;
  for (const d of visibleNodes(nodes.map((n) => ({ ...n, collapsed: 0 }))).values()) m = Math.max(m, d);
  return m;
}

/** Map each node to its top-level branch id (for branch colors). */
export function branchOf(nodes) {
  const byId = new Map(nodes.map((n) => [n.id, n]));
  const out = new Map();
  for (const n of nodes) {
    let cur = n;
    while (cur && cur.parent_id && byId.get(cur.parent_id)?.parent_id) cur = byId.get(cur.parent_id);
    out.set(n.id, cur && cur.parent_id ? cur.id : null);
  }
  return out;
}

/**
 * Bilateral tidy layout: root at (0,0); first-level branches balanced left/right by subtree height.
 * sizes: Map id -> {w,h}. Returns Map id -> {x, y, side} where (x,y) is the node centre.
 */
export function layoutTree(nodes, sizes, depthLimit = Infinity) {
  const vis = visibleNodes(nodes, depthLimit);
  const kids = childrenIndex(nodes.filter((n) => vis.has(n.id)));
  const root = (kids.get(null) || [])[0];
  const pos = new Map();
  if (!root) return pos;
  const size = (id) => sizes.get(id) || { w: 120, h: 36 };
  const heightMemo = new Map();
  const height = (n) => {
    if (heightMemo.has(n.id)) return heightMemo.get(n.id);
    const cs = kids.get(n.id) || [];
    const sum = cs.reduce((a, c) => a + height(c), 0) + Math.max(0, cs.length - 1) * V_GAP;
    const h = Math.max(size(n.id).h, sum);
    heightMemo.set(n.id, h);
    return h;
  };
  const place = (n, x, y, side) => {
    pos.set(n.id, { x, y, side });
    const cs = kids.get(n.id) || [];
    const total = cs.reduce((a, c) => a + height(c), 0) + Math.max(0, cs.length - 1) * V_GAP;
    let top = y - total / 2;
    for (const c of cs) {
      const h = height(c);
      const cx = x + side * (size(n.id).w / 2 + H_GAP + size(c.id).w / 2);
      place(c, cx, top + h / 2, side);
      top += h + V_GAP;
    }
  };
  pos.set(root.id, { x: 0, y: 0, side: 0 });
  const right = [], left = [];
  let hr = 0, hl = 0;
  for (const c of kids.get(root.id) || []) {
    if (hr <= hl) { right.push(c); hr += height(c) + V_GAP; } else { left.push(c); hl += height(c) + V_GAP; }
  }
  for (const [list, side] of [[right, 1], [left, -1]]) {
    const total = list.reduce((a, c) => a + height(c), 0) + Math.max(0, list.length - 1) * V_GAP;
    let top = -total / 2;
    for (const c of list) {
      const h = height(c);
      place(c, side * (size(root.id).w / 2 + H_GAP + size(c.id).w / 2), top + h / 2, side);
      top += h + V_GAP;
    }
  }
  return pos;
}

/** Bounding box of laid-out nodes: {x0,y0,x1,y1}. */
export function bounds(pos, sizes) {
  let x0 = Infinity, y0 = Infinity, x1 = -Infinity, y1 = -Infinity;
  for (const [id, p] of pos) {
    const s = sizes.get(id) || { w: 120, h: 36 };
    x0 = Math.min(x0, p.x - s.w / 2); x1 = Math.max(x1, p.x + s.w / 2);
    y0 = Math.min(y0, p.y - s.h / 2); y1 = Math.max(y1, p.y + s.h / 2);
  }
  return Number.isFinite(x0) ? { x0, y0, x1, y1 } : { x0: 0, y0: 0, x1: 0, y1: 0 };
}

/** Zoom/pan that fits a box into a viewport (with padding), clamped to [minS, maxS]. */
export function fitTransform(box, vw, vh, pad = 24, minS = 0.2, maxS = 1.4) {
  const bw = Math.max(1, box.x1 - box.x0), bh = Math.max(1, box.y1 - box.y0);
  const s = Math.max(minS, Math.min(maxS, Math.min((vw - 2 * pad) / bw, (vh - 2 * pad) / bh)));
  return { s, tx: vw / 2 - s * (box.x0 + bw / 2), ty: vh / 2 - s * (box.y0 + bh / 2) };
}

// ---- US-13 — user layout: side panel position, map/paper order, pane sizes ------------------------
export const SIDE_POSITIONS = ['right', 'left', 'bottom', 'drawer'];
const SPLIT = '6px';
const clamp = (v, lo, hi) => Math.max(lo, Math.min(hi, v));

/** AT-13.5 — defaults per device class (tablet keeps the US-12 drawer). */
export function defaultLayout(mode) {
  return { side: mode === 'tablet' ? 'drawer' : 'right', swap: false, share: 0.5, sideW: 360, sideH: 300 };
}

/** AT-13.5 — any stored value is coerced into a valid layout; garbage falls back to defaults. */
export function sanitizeLayout(raw, mode) {
  const d = defaultLayout(mode);
  if (!raw || typeof raw !== 'object') return d;
  const num = (v, lo, hi, def) => (Number.isFinite(v) ? clamp(v, lo, hi) : def);
  return {
    side: SIDE_POSITIONS.includes(raw.side) ? raw.side : d.side,
    swap: raw.swap === true,
    share: num(raw.share, 0.15, 0.85, d.share),
    sideW: num(raw.sideW, 240, 900, d.sideW),
    sideH: num(raw.sideH, 120, 900, d.sideH),
  };
}

/** AT-13.2 / AT-13.3 — CSS grid for a layout. Areas: map, paper, side, sa (map|paper splitter), sb (side splitter). */
export function gridFor(p) {
  const [a, b] = p.swap ? ['paper', 'map'] : ['map', 'paper'];
  const first = p.swap ? 1 - p.share : p.share;
  const panes = `minmax(0, ${first}fr) ${SPLIT} minmax(0, ${1 - first}fr)`;
  if (p.side === 'left') return { areas: `"side sb ${a} sa ${b}"`, columns: `${p.sideW}px ${SPLIT} ${panes}`, rows: 'minmax(0, 1fr)' };
  if (p.side === 'bottom') {
    return { areas: `"${a} sa ${b}" "sb sb sb" "side side side"`, columns: panes, rows: `minmax(0, 1fr) ${SPLIT} ${p.sideH}px` };
  }
  if (p.side === 'drawer') return { areas: `"${a} sa ${b}"`, columns: panes, rows: 'minmax(0, 1fr)' };
  return { areas: `"${a} sa ${b} sb side"`, columns: `${panes} ${SPLIT} ${p.sideW}px`, rows: 'minmax(0, 1fr)' };
}

/**
 * AT-13.1 — new layout after dragging a splitter to pointer (x, y).
 * panes: bounding box spanning both map and paper; main: bounding box of the whole workspace body.
 */
export function dragSplitter(p, which, pointer, panes, main) {
  if (which === 'sa') {
    const first = clamp((pointer.x - panes.left) / Math.max(1, panes.width), 0.15, 0.85);
    return { ...p, share: p.swap ? 1 - first : first };
  }
  if (p.side === 'bottom') return { ...p, sideH: clamp(main.bottom - pointer.y, 120, Math.max(120, main.height - 160)) };
  const w = p.side === 'left' ? pointer.x - main.left : main.right - pointer.x;
  return { ...p, sideW: clamp(w, 240, Math.max(240, Math.min(900, main.width - 360))) };
}

/** AT-13.4 — double-click on a splitter resets only the size it controls. */
export function resetSplitter(p, which, mode) {
  const d = defaultLayout(mode);
  return which === 'sa' ? { ...p, share: d.share } : { ...p, sideW: d.sideW, sideH: d.sideH };
}

/** AT-06.5 — collapsed flag per node so exactly `depth` levels below the root show (null = all). Mirrors domain.mindmap.fold_flags. */
export function foldFlags(nodes, depth) {
  const kids = childrenIndex(nodes);
  const out = new Map();
  const stack = (kids.get(null) || []).map((n) => [n, 0]);
  while (stack.length) {
    const [n, d] = stack.pop();
    out.set(n.id, depth != null && d >= depth && (kids.get(n.id) || []).length > 0);
    for (const c of kids.get(n.id) || []) stack.push([c, d + 1]);
  }
  return out;
}
