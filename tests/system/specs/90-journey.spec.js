// CR-03 — the owner's whole reading workflow on a real arXiv paper with the real LLM.
// Runs only with JOURNEY=1 (scripts/ci.sh --journey). Screenshots go to .tmp/journey/ for UX review.
const { test, expect } = require('@playwright/test');
const fs = require('fs');
const path = require('path');
const { login, newSession, selectText, clickCenter } = require('../helpers');

const ARXIV_ID = '1706.03762'; // "Attention Is All You Need", 15 pages
const PDF = path.resolve(__dirname, `../../fixtures/arxiv/${ARXIV_ID}.pdf`);
const SHOTS = path.resolve(__dirname, '../../../.tmp/journey');

test.skip(!process.env.JOURNEY, 'journey runs on demand: scripts/ci.sh --journey');
test.describe.configure({ mode: 'serial', timeout: 15 * 60 * 1000 });

let page;
let step = 0;
const shot = async (name) => page.screenshot({ path: `${SHOTS}/${String(++step).padStart(2, '0')}-${name}.png` });

test.beforeAll(async ({ browser }) => {
  fs.mkdirSync(SHOTS, { recursive: true });
  if (!fs.existsSync(PDF)) {
    fs.mkdirSync(path.dirname(PDF), { recursive: true });
    const res = await fetch(`https://arxiv.org/pdf/${ARXIV_ID}`, { headers: { 'User-Agent': 'PaperReader-journey-test' } });
    fs.writeFileSync(PDF, Buffer.from(await res.arrayBuffer()));
  }
  page = await browser.newPage({ viewport: { width: 1440, height: 900 } });
});
test.afterAll(async () => { await page.close(); });

test('AT-C03.1 AT-03.5 journey: sign in, session, upload the arXiv paper (title from its heading)', async () => {
  await login(page);
  if (process.env.JOURNEY_MODEL) {  // e.g. a cheaper model of the presets; default = the model set in Admin
    const r = await page.request.put('/api/admin/settings', { data: { model: process.env.JOURNEY_MODEL } });
    expect(r.ok()).toBeTruthy();
  }
  console.log('journey model:', (await (await page.request.get('/api/config')).json()).model);
  await newSession(page, 'Transformers — reading');
  await page.setInputFiles('[data-upload]', PDF);
  await expect(page.locator('.paper-select option')).toHaveCount(1);
  await expect(page.locator('.pdf-page')).toHaveCount(15, { timeout: 30000 });
  await expect(page.locator('.paper-select')).toContainText('Attention Is All You Need'); // AT-03.5
  await expect(page.locator('.pdf-page[data-page="1"] .textLayer span').first()).toBeAttached({ timeout: 30000 });
  await shot('uploaded');
});

test('AT-C03.1 AT-05.5 journey: AI builds the mind map (≥ 3 levels); every quote is real text', async () => {
  await page.click('[data-act=new-map]');
  await page.click('.modal button[type=submit]');
  const ready = page.locator('.toast.ok', { hasText: 'Map ready' });
  await expect(ready).toBeVisible({ timeout: 12 * 60 * 1000 });
  console.log('map report:', await ready.textContent());
  await expect(page.locator('.mm-node.d0')).toBeVisible();
  await shot('map-big-picture');
  const map = await page.evaluate(async () => {
    const s = await (await fetch(`/api/sessions/${location.hash.split('/')[2]}`)).json();
    return (await fetch(`/api/maps/${s.maps[0].id}`)).json();
  });
  console.log(`nodes=${map.nodes.length} links=${map.links.length} quotes=${map.quotes.length} report=${JSON.stringify(map.report)}`);
  expect(map.nodes.length).toBeGreaterThan(15);
  expect(map.report.depth).toBeGreaterThanOrEqual(3); // AT-05.5 high level → tiny details
  expect(map.quotes.length).toBeGreaterThan(10);
  expect(map.nodes.some((n) => n.kind === 'background' || n.kind === 'definition')).toBeTruthy();
  for (const q of map.quotes) expect(q.rects.length).toBeGreaterThan(0);
});

test('AT-C03.1 journey: depth from big picture to details; node → paper evidence', async () => {
  await page.click('[data-depth=all]');
  await expect(page.locator('.mm-node.d3').first()).toBeVisible();
  await page.click('[data-depth="1"]');
  await page.locator('.mm-node.d1 .mm-toggle').first().click();
  await expect(page.locator('.mm-node.d2').first()).toBeVisible();
  const deep = page.locator('.mm-node.d2:has(.mm-badge)').first();
  await deep.click();
  await expect(page.locator('.hl-map.strong').first()).toBeInViewport({ timeout: 8000 });
  await expect(page.locator('.quote').first()).toBeVisible();
  await shot('node-to-paper');
});

test('AT-C03.1 journey: paper → nodes, colored highlight with comment', async () => {
  const hl = page.locator('.hl-map.strong').first();
  const words = await hl.evaluate((h) => {
    const hb = h.getBoundingClientRect();
    const span = [...h.closest('.pdf-page').querySelectorAll('.textLayer span')].find((s) => {
      const r = s.getBoundingClientRect();
      return r.left < hb.right && hb.left < r.right && r.top < hb.bottom && hb.top < r.bottom && s.textContent.trim().length > 10;
    });
    return span.textContent.trim().slice(0, 14);
  });
  await page.locator('.mm').click({ position: { x: 5, y: 5 } });
  await selectText(page, words);
  await expect(page.locator('.mm-node.related').first()).toBeVisible();
  await shot('paper-to-nodes');
  await page.click('.sel-bar [data-color=green]');
  await expect(page.locator('.hl-ann').first()).toBeAttached();
  await page.evaluate(() => getSelection().removeAllRanges());
  await clickCenter(page, page.locator('.hl-ann').first());
  await page.fill('.popover textarea', 'Core claim — re-read');
  await page.click('.popover [data-ann-save]');
});

test('AT-C03.1 journey: note linked to a node', async () => {
  await page.locator('.mm-node.selected, .mm-node.d1').first().click();
  await page.click('[data-a=note]');
  await page.fill('.note-body', 'Self-attention = every token looks at every other token.\nWhy it beats RNNs: parallel + short paths.');
  await expect(page.locator('.save-state')).toHaveText('Saved', { timeout: 5000 });
  await expect(page.locator('[data-panel=notes] .chip')).toBeVisible();
});

test('AT-C03.1 journey: chat with grounded citations in the AI-trace color', async () => {
  await page.click('[data-side=node]');
  await page.locator('.mm-node.selected').first().click();
  await page.click('[data-a=chat]');
  await page.fill('.composer textarea', 'I have no ML background. Explain this simply with an everyday analogy, and cite the paper.');
  await page.click('.composer button');
  await expect(page.locator('.msg.assistant').last()).not.toContainText('Thinking', { timeout: 5 * 60 * 1000 });
  await expect(page.locator('.msg.assistant .cite').first()).toBeVisible();
  await page.locator('.msg.assistant .cite').first().click();
  await expect(page.locator('.hl-chat.strong').first()).toBeInViewport({ timeout: 8000 });
  console.log('chat answer:', (await page.locator('.msg.assistant').last().textContent()).slice(0, 400));
  await shot('chat-citations');
});

test('AT-C03.1 journey: go deeper on a node', async () => {
  await page.click('[data-side=node]');
  const target = page.locator('.mm-node.d1').first();
  await target.click();
  const before = await page.locator('.mm-node').count();
  await page.click('[data-a=expand]');
  await expect(page.locator('.toast.ok', { hasText: 'Added' })).toBeVisible({ timeout: 5 * 60 * 1000 });
  await expect.poll(() => page.locator('.mm-node').count()).toBeGreaterThan(before);
});

test('AT-C03.1 AT-06.7 journey: edit a node → evidence re-derived; add a relation', async () => {
  const node = page.locator('.mm-node.d2').first();
  await node.click();
  await page.click('[data-a=edit]');
  await page.fill('.node-form textarea[name=explanation]', 'In my words: the model weighs how much each word should look at every other word.');
  const logsBefore = (await (await page.request.get('/api/admin/logs')).json()).filter((l) => l.kind === 'node_reground').length;
  await page.click('.node-form button.primary');
  await expect(page.locator('[data-panel=node] .busy')).toBeVisible();
  await expect(page.locator('[data-panel=node] .busy')).toBeHidden({ timeout: 5 * 60 * 1000 });
  const logsAfter = (await (await page.request.get('/api/admin/logs')).json()).filter((l) => l.kind === 'node_reground').length;
  expect(logsAfter).toBeGreaterThan(logsBefore); // AT-06.7: evidence re-derived automatically
  await page.click('[data-a=link]');
  await page.selectOption('.modal select[name=target_id]', { index: 1 });
  await page.fill('.modal input[name=label]', 'motivates');
  await page.click('.modal button[type=submit]');
  await expect(page.locator('.link-row', { hasText: 'motivates' })).toBeVisible();
});

test('AT-C03.1 journey: notes as footer, reload keeps everything', async () => {
  await page.click('[data-act=layout]');
  await page.click('.layout-menu [data-lay-side]:has-text("Bottom")');
  await page.click('[data-side=notes]');
  await shot('footer-layout');
  await page.reload();
  await expect(page.locator('.ws')).toHaveAttribute('data-layout', 'bottom');
  await expect(page.locator('.mm-node.d0')).toBeVisible();
  await page.click('[data-side=notes]');
  await expect(page.locator('.note-item', { hasText: 'Self-attention' })).toBeVisible();
  await expect(page.locator('.hl-ann').first()).toBeAttached({ timeout: 20000 });
  await page.click('[data-side=chat]');
  await expect(page.locator('.chat-item')).toHaveCount(1);
});

test('AT-C03.1 journey: same session on the phone', async () => {
  await page.setViewportSize({ width: 430, height: 932 });
  await expect(page.locator('.ws-tabs')).toBeVisible();
  await page.click('.ws-tabs [data-tab=map]');
  await page.locator('.mm-node.d1').first().click();
  await expect(page.locator('.node-chip')).toBeVisible();
  await shot('phone-map');
  await page.click('.node-chip [data-act=open-paper]');
  await expect(page.locator('.pane-paper')).toBeVisible();
  await shot('phone-paper');
});
