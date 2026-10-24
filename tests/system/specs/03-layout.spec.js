// US-13 — resizable, rearrangeable workspace (no AI).
const { test, expect } = require('@playwright/test');
const { login, newSession } = require('../helpers');

const box = (page, sel) => page.locator(sel).boundingBox();

async function openWorkspace(page, size) {
  await page.setViewportSize(size);
  await login(page);
  await page.request.delete('/api/prefs/layout.desktop');
  await page.request.delete('/api/prefs/layout.tablet');
  await newSession(page, `Layout ${Date.now()}`);
}

async function drag(page, sel, dx, dy) {
  const b = await box(page, sel);
  const x = b.x + b.width / 2, y = b.y + b.height / 2;
  await page.mouse.move(x, y);
  await page.mouse.down();
  await page.mouse.move(x + dx / 2, y + dy / 2);
  await page.mouse.move(x + dx, y + dy);
  await page.mouse.up();
}

async function chooseSide(page, label) {
  await page.click('[data-act=layout]');
  await page.click(`.layout-menu [data-lay-side]:has-text("${label}")`);
}

test('AT-13.1 drag dividers to resize; sizes survive a reload', async ({ page }) => {
  await openWorkspace(page, { width: 1440, height: 900 });
  const map0 = (await box(page, '.pane-map')).width, side0 = (await box(page, '.pane-side')).width;
  await drag(page, '.split[data-split=sa]', -200, 0);
  await drag(page, '.split[data-split=sb]', -140, 0);
  const map1 = (await box(page, '.pane-map')).width, side1 = (await box(page, '.pane-side')).width;
  expect(map1).toBeLessThan(map0 - 150);
  expect(side1).toBeGreaterThan(side0 + 100);
  await expect.poll(async () => (await (await page.request.get('/api/prefs')).json())['layout.desktop']?.sideW).toBeGreaterThan(450);
  await page.reload();
  await expect(page.locator('.pane-side')).toBeVisible();
  expect(Math.abs((await box(page, '.pane-map')).width - map1)).toBeLessThan(4);
  expect(Math.abs((await box(page, '.pane-side')).width - side1)).toBeLessThan(4);
});

test('AT-13.2 side panel as footer, left, right; AT-13.3 swap map and paper; AT-13.4 reset', async ({ page }) => {
  await openWorkspace(page, { width: 1440, height: 900 });
  await chooseSide(page, 'Bottom');
  const side = await box(page, '.pane-side'), map = await box(page, '.pane-map');
  expect(side.y).toBeGreaterThan(map.y + map.height - 2);
  expect(side.width).toBeGreaterThan(1300);
  await page.click('[data-side=notes]');
  await expect(page.locator('[data-panel=notes]')).toBeVisible();
  await drag(page, '.split[data-split=sb]', 0, -100); // taller footer
  expect((await box(page, '.pane-side')).height).toBeGreaterThan(side.height + 80);

  await chooseSide(page, 'Left');
  expect((await box(page, '.pane-side')).x).toBeLessThan((await box(page, '.pane-map')).x);

  await page.click('[data-act=layout]');
  await page.click('.layout-menu [data-lay=swap]');
  expect((await box(page, '.pane-paper')).x).toBeLessThan((await box(page, '.pane-map')).x);
  await page.reload();
  await expect(page.locator('.pane-map')).toBeVisible();
  expect((await box(page, '.pane-paper')).x).toBeLessThan((await box(page, '.pane-map')).x);

  await page.click('[data-act=layout]');
  await page.click('.layout-menu [data-lay=reset]');
  const m = await box(page, '.pane-map'), p = await box(page, '.pane-paper'), s = await box(page, '.pane-side');
  expect(m.x).toBeLessThan(p.x);
  expect(p.x).toBeLessThan(s.x);
  expect(Math.abs(s.width - 360)).toBeLessThan(3);
});

test('AT-13.4 double-click a divider resets only that size', async ({ page }) => {
  await openWorkspace(page, { width: 1440, height: 900 });
  await drag(page, '.split[data-split=sa]', -200, 0);
  await drag(page, '.split[data-split=sb]', -150, 0);
  const side = (await box(page, '.pane-side')).width;
  await page.dblclick('.split[data-split=sa]');
  const m = await box(page, '.pane-map'), p = await box(page, '.pane-paper');
  expect(Math.abs(m.width - p.width)).toBeLessThan(3);
  expect(Math.abs((await box(page, '.pane-side')).width - side)).toBeLessThan(3);
});

test('AT-13.5 layout is per device class; phone keeps tabs', async ({ page }) => {
  await openWorkspace(page, { width: 1440, height: 900 });
  await chooseSide(page, 'Bottom');
  await expect.poll(async () => (await (await page.request.get('/api/prefs')).json())['layout.desktop']?.side).toBe('bottom');
  await page.setViewportSize({ width: 1024, height: 768 }); // iPad landscape
  await expect(page.locator('.ws')).toHaveAttribute('data-layout', 'drawer');
  await chooseSide(page, 'Bottom');
  await expect(page.locator('.pane-side')).toBeInViewport();
  await page.setViewportSize({ width: 390, height: 844 }); // iPhone
  await expect(page.locator('.ws-tabs')).toBeVisible();
  await expect(page.locator('[data-act=layout]')).toBeHidden();
  await expect(page.locator('.pane-paper')).toBeHidden();
  await page.setViewportSize({ width: 1440, height: 900 });
  await expect(page.locator('.ws')).toHaveAttribute('data-layout', 'bottom');
});
