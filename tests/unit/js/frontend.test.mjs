// Unit tests for pure frontend modules (node --test): US-06 layout, US-07 geometry, US-12 mode, US-10 markdown.
import assert from 'node:assert/strict';
import { test } from 'node:test';
import { hitTest, mergeLines, normalizeRects, overlappingQuotes } from '../../../frontend/js/geometry.mjs';
import { bounds, fitTransform, layoutMode, layoutTree, visibleNodes } from '../../../frontend/js/layout.mjs';
import { renderMarkdown } from '../../../frontend/js/util.mjs';

const nodes = [
  { id: 'r', parent_id: null, position: 0, collapsed: 0 },
  { id: 'a', parent_id: 'r', position: 0, collapsed: 0 },
  { id: 'b', parent_id: 'r', position: 1, collapsed: 0 },
  { id: 'a1', parent_id: 'a', position: 0, collapsed: 0 },
  { id: 'a2', parent_id: 'a', position: 1, collapsed: 0 },
];

test('AT-12.5 layout mode by viewport width', () => {
  assert.equal(layoutMode(1440), 'desktop');
  assert.equal(layoutMode(1100), 'desktop');
  assert.equal(layoutMode(1024), 'tablet');
  assert.equal(layoutMode(700), 'tablet');
  assert.equal(layoutMode(430), 'phone');
});

test('AT-06.5 collapsed nodes hide their subtree; depth limit applies', () => {
  assert.deepEqual([...visibleNodes(nodes).keys()].sort(), ['a', 'a1', 'a2', 'b', 'r']);
  const folded = nodes.map((n) => (n.id === 'a' ? { ...n, collapsed: 1 } : n));
  assert.deepEqual([...visibleNodes(folded).keys()].sort(), ['a', 'b', 'r']);
  assert.deepEqual([...visibleNodes(nodes, 1).keys()].sort(), ['a', 'b', 'r']);
});

test('AT-06.5 bilateral layout: root centred, branches on both sides, children ordered, fit inside viewport', () => {
  const sizes = new Map(nodes.map((n) => [n.id, { w: 100, h: 30 }]));
  const pos = layoutTree(nodes, sizes);
  assert.deepEqual(pos.get('r'), { x: 0, y: 0, side: 0 });
  assert.equal(Math.sign(pos.get('a').x), 1);
  assert.equal(Math.sign(pos.get('b').x), -1);
  assert.ok(pos.get('a1').y < pos.get('a2').y);
  assert.ok(pos.get('a1').x > pos.get('a').x);
  const t = fitTransform(bounds(pos, sizes), 800, 600);
  const box = bounds(pos, sizes);
  assert.ok(box.x0 * t.s + t.tx >= 0 && box.x1 * t.s + t.tx <= 800);
});

test('AT-07.2 selection overlapping a quote finds the quote (same paper and page only)', () => {
  const quotes = [
    { id: 'q1', node_id: 'n1', paper_id: 'p', page: 1, rects: [[0.1, 0.1, 0.5, 0.12]] },
    { id: 'q2', node_id: 'n2', paper_id: 'p', page: 2, rects: [[0.1, 0.1, 0.5, 0.12]] },
    { id: 'q3', node_id: 'n3', paper_id: 'p', page: 1, rects: [[0.1, 0.5, 0.5, 0.52]] },
  ];
  const hits = overlappingQuotes({ paperId: 'p', page: 1, rects: [[0.3, 0.105, 0.6, 0.115]] }, quotes);
  assert.deepEqual(hits.map((q) => q.id), ['q1']);
});

test('AT-07.2 client rects are normalised to the page and merged per line', () => {
  const page = { left: 100, top: 50, right: 300, bottom: 450, width: 200, height: 400 };
  const r = normalizeRects([
    { left: 120, right: 160, top: 90, bottom: 100, width: 40, height: 10 },
    { left: 160, right: 200, top: 90, bottom: 100, width: 40, height: 10 },
    { left: 120, right: 140, top: 110, bottom: 120, width: 20, height: 10 },
    { left: 0, right: 5, top: 0, bottom: 1, width: 5, height: 1 },
  ], page);
  assert.equal(r.length, 2);
  assert.deepEqual(r[0], [0.1, 0.1, 0.5, 0.125]);
  assert.equal(mergeLines([]).length, 0);
});

test('AT-07.2 hit test finds overlay items under a tapped point', () => {
  const items = [{ id: 'x', rects: [[0.1, 0.1, 0.2, 0.2]] }, { id: 'y', rects: [[0.5, 0.5, 0.6, 0.6]] }];
  assert.deepEqual(hitTest({ x: 0.15, y: 0.15 }, items).map((i) => i.id), ['x']);
});

test('AT-10.2 linked citations render as clickable chips; HTML is escaped', () => {
  const html = renderMarkdown('**Gate** <b>x</b> [[q:abc123|1]]\n- item');
  assert.ok(html.includes('<button class="cite" data-quote="abc123">1</button>'));
  assert.ok(html.includes('&lt;b&gt;') && html.includes('<strong>Gate</strong>') && html.includes('<li>item</li>'));
});
