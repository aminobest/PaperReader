// System tests with the REAL LLM (OpenRouter, model from Admin) on the 2-page fixture — kept to 3 AI calls.
const { test, expect } = require('@playwright/test');
const { login, newSession, uploadFixture, selectText, clickCenter } = require('../helpers');

test.describe.configure({ mode: 'serial' });

let page;
test.beforeAll(async ({ browser }) => {
  page = await browser.newPage({ viewport: { width: 1440, height: 900 } });
  await login(page);
  await newSession(page, 'AI session');
  await uploadFixture(page);
});
test.afterAll(async () => { await page.close(); });

test('AT-05.3 AT-14.1 AT-14.2 AT-14.3 generate contextual, explained evidence with the map', async () => {
  await page.click('[data-act=new-map]');
  await page.click('.modal button[type=submit]');
  await expect(page.locator('.map-status .busy')).toBeVisible();
  await expect(page.locator('.toast.ok', { hasText: 'Map ready' })).toBeVisible({ timeout: 5 * 60 * 1000 });
  await expect(page.locator('.mm-node.d0')).toBeVisible();
  expect(await page.locator('.mm-node').count()).toBeGreaterThan(4);
  await page.click('[data-depth=all]');
  await expect(page.locator('.mm-badge').first()).toBeVisible();
  const evidence = await page.evaluate(async () => {
    const sid = location.hash.match(/^#\/s\/(\w+)/)?.[1];
    const session = await fetch(`/api/sessions/${sid}`).then((r) => r.json());
    const map = await fetch(`/api/maps/${session.maps.at(-1).id}`).then((r) => r.json());
    return map.quotes;
  });
  expect(evidence.length).toBeGreaterThan(0);
  for (const q of evidence) expect(q.text.trim().length).toBeGreaterThan(0);
  const logs = await page.request.get('/api/admin/logs?limit=50').then((r) => r.json());
  const generation = logs.find((l) => l.kind === 'map_generate');
  const quotePrompt = generation.messages[1].content;
  expect(quotePrompt).toContain('no fixed target or maximum');
  expect(quotePrompt.toLowerCase()).toContain('not keyword matching');
  expect(quotePrompt).not.toContain('1-2 non-redundant passages');
});

test('AT-04.5 every map-quote highlight lies on real text of the paper', async () => {
  await page.locator('.pdf-scroll').evaluate((e) => e.scrollTo(0, e.scrollHeight));
  await expect(page.locator('.pdf-page[data-page="2"] .textLayer span').first()).toBeAttached();
  await page.locator('.pdf-scroll').evaluate((e) => e.scrollTo(0, 0));
  const result = await page.evaluate(() => {
    const out = { total: 0, onText: 0 };
    for (const hl of document.querySelectorAll('.hl-map')) {
      out.total++;
      const page = hl.closest('.pdf-page');
      const hb = hl.getBoundingClientRect();
      const spans = [...page.querySelectorAll('.textLayer span')].map((s) => s.getBoundingClientRect());
      if (spans.some((s) => s.left < hb.right && hb.left < s.right && s.top < hb.bottom && hb.top < s.bottom)) out.onText++;
    }
    return out;
  });
  expect(result.total).toBeGreaterThan(0);
  expect(result.onText).toBe(result.total);
});

test('AT-07.1 selecting a node highlights its quotes and scrolls the paper to them', async () => {
  await page.locator('.pdf-scroll').evaluate((e) => e.scrollTo(0, e.scrollHeight));
  const node = page.locator('.mm-node:has(.mm-badge)').last();
  await node.click();
  await expect(node).toHaveClass(/selected/);
  const strong = page.locator('.hl-map.strong');
  await expect(strong.first()).toBeAttached();
  await expect(strong.first()).toBeInViewport({ timeout: 5000 });
  expect(await page.locator('.quote').count()).toBeGreaterThan(0);
});

test('AT-07.4 layer toggles hide and show map quotes', async () => {
  await page.click('[data-layer=map]');
  await expect(page.locator('.hl-map')).toHaveCount(0);
  await page.click('[data-layer=map]');
  await expect(page.locator('.hl-map').first()).toBeAttached();
});

test('AT-07.3 tapping a quote highlight selects its node', async () => {
  await page.locator('.mm').click({ position: { x: 5, y: 5 } }); // clear selection
  await expect(page.locator('.mm-node.selected')).toHaveCount(0);
  const hl = page.locator('.hl-map').first();
  await hl.scrollIntoViewIfNeeded();
  await clickCenter(page, hl);
  const popover = page.locator('.popover:not([hidden]) [data-node]');
  if (await popover.count()) await popover.first().click();
  await expect(page.locator('.mm-node.selected').first()).toBeVisible();
});

test('AT-07.2 selecting text in the paper lights up the related nodes', async () => {
  const quoteText = await page.locator('.hl-map').first().evaluate((hl) => {
    const page = hl.closest('.pdf-page');
    const hb = hl.getBoundingClientRect();
    const span = [...page.querySelectorAll('.textLayer span')].find((s) => {
      const r = s.getBoundingClientRect();
      return r.left < hb.right && hb.left < r.right && r.top < hb.bottom && hb.top < r.bottom && s.textContent.trim().length > 8;
    });
    return span.textContent.trim().slice(0, 12);
  });
  await selectText(page, quoteText);
  await expect(page.locator('.mm-node.related').first()).toBeVisible();
  await expect(page.locator('.sel-bar [data-sel=related]')).toBeVisible();
  await page.evaluate(() => getSelection().removeAllRanges());
});

test('AT-06.3 "Go deeper" asks the AI and appends grounded child nodes', async () => {
  const before = await page.locator('.mm-node').count();
  await page.locator('.mm-node.d1').first().click();
  await page.click('[data-a=expand]');
  await expect(page.locator('.toast.ok', { hasText: 'Added' })).toBeVisible({ timeout: 4 * 60 * 1000 });
  await page.click('[data-depth=all]');
  await expect.poll(() => page.locator('.mm-node').count()).toBeGreaterThan(before);
});

test('AT-06.7 a new node gets its evidence from the AI automatically', async () => {
  await page.locator('.mm-node.d0').click();
  await page.click('[data-a=child]');
  await page.fill('.modal input[name=title]', 'Accuracy on TREC');
  await page.fill('.modal textarea[name=explanation]', 'GMN reaches 88.4 percent on the TREC question dataset.');
  await page.click('.modal button[type=submit]');
  await expect(page.locator('.toast.ok', { hasText: 'verified quotes' })).toBeVisible({ timeout: 4 * 60 * 1000 });
  await expect(page.locator('.mm-node', { hasText: 'Accuracy on TREC' }).locator('.mm-badge')).toBeVisible();
  await expect(page.locator('.quote').first()).toContainText('88.4');
});

test('AT-10.1 chat about a node; AT-10.3 answer quotes shown in the AI-trace color, citations jump to them', async () => {
  await page.locator('.mm-node.d1').first().click();
  await page.click('[data-a=chat]');
  await expect(page.locator('.chat-ctx .chip')).toBeVisible();
  await page.fill('.composer textarea', 'Explain this to a beginner in 2-3 sentences and cite the paper.');
  await page.click('.composer button');
  await expect(page.locator('.msg.assistant').last()).not.toContainText('Thinking', { timeout: 4 * 60 * 1000 });
  const cite = page.locator('.msg.assistant .cite').first();
  await expect(cite).toBeVisible();
  await cite.click();
  const chatHl = page.locator('.hl-chat.strong').first();
  await expect(chatHl).toBeInViewport({ timeout: 5000 });
  const color = await page.evaluate(() => fetch('/api/config').then((r) => r.json()).then((c) => c.chat_color));
  expect(await chatHl.evaluate((e) => e.style.getPropertyValue('--hc'))).toBe(color);
});

test('AT-10.5 deleting a message removes its evidence from the paper', async () => {
  await expect(page.locator('.hl-chat').first()).toBeAttached();
  await page.locator('.msg.user .msg-del').first().click({ force: true });
  await page.click('.modal button[type=submit]');
  await expect(page.locator('.msg')).toHaveCount(0);
  await expect(page.locator('.hl-chat')).toHaveCount(0);
  await page.click('[data-c=back]');
  await expect(page.locator('.chat-item')).toHaveCount(1);
});
