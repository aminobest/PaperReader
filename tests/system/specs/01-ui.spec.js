// System tests without LLM calls: shell, sessions, papers, annotations, notes, manual map editing, admin, devices.
const { test, expect } = require('@playwright/test');
const { login, newSession, uploadFixture, selectText, clickCenter } = require('../helpers');

test('AT-01.2 unauthenticated: API 401 and login screen; AT-C02.1 health', async ({ page, request }) => {
  expect((await request.get('/api/sessions')).status()).toBe(401);
  expect(await (await request.get('/api/health')).json()).toEqual({ status: 'ok' });
  await page.goto('/');
  await expect(page.locator('button:has-text("Sign in")')).toBeVisible();
});

test('AT-01.4 login lands on sessions; logout returns to login', async ({ page }) => {
  await page.goto('/');
  await page.fill('input[name=username]', 'test');
  await page.fill('input[name=password]', 'wrong-password');
  await page.click('button:has-text("Sign in")');
  await expect(page.locator('.error-text')).toBeVisible();
  await login(page);
  await page.click('[data-a=logout]');
  await expect(page.locator('button:has-text("Sign in")')).toBeVisible();
});

test('AT-02.1 create session (blank rejected); AT-02.2 rename and delete', async ({ page }) => {
  await login(page);
  await page.click('.new-session button');
  await expect(page.locator('.toast.error')).toBeVisible();
  await newSession(page, 'Session A');
  await page.click('a[aria-label="All sessions"]');
  const card = page.locator('.session-card', { hasText: 'Session A' });
  await expect(card).toBeVisible();
  await card.locator('[aria-label="Rename session"]').click();
  await page.fill('.modal input[name=name]', 'Session B');
  await page.click('.modal button[type=submit]');
  const renamed = page.locator('.session-card', { hasText: 'Session B' });
  await expect(renamed).toBeVisible();
  await renamed.locator('[aria-label="Delete session"]').click();
  await page.click('.modal button[type=submit]');
  await expect(renamed).toHaveCount(0);
});

test.describe('workspace without AI', () => {
  test.beforeEach(async ({ page }) => {
    await login(page);
    await newSession(page, `WS ${Date.now()}`);
    await uploadFixture(page);
  });

  test('AT-03.1 upload; AT-03.3 pages render with a selectable text layer', async ({ page }) => {
    await expect(page.locator('.pdf-page')).toHaveCount(2);
    await expect(page.locator('.pdf-page[data-page="1"] canvas')).toBeVisible();
    await selectText(page, 'Short texts');
    expect(await page.evaluate(() => getSelection().toString())).toContain('Short texts');
  });

  test('AT-08.1 highlight a selection in a color; AT-08.2 recolor, comment, delete', async ({ page }) => {
    await selectText(page, 'Short texts');
    await page.click('.sel-bar [data-color=yellow]');
    const hl = page.locator('.hl-ann').first();
    await expect(hl).toBeVisible();
    await page.evaluate(() => getSelection().removeAllRanges());
    await clickCenter(page, hl);
    await expect(page.locator('.popover')).toBeVisible();
    await page.click('.popover [data-color=pink]');
    await expect(page.locator('.popover .dot.on[data-color=pink]')).toBeVisible();
    await page.fill('.popover textarea', 'key claim');
    await page.click('.popover [data-ann-save]');
    await page.reload();
    await expect(page.locator('.hl-ann')).toHaveCount(1, { timeout: 20000 });
    expect(await page.locator('.hl-ann').first().evaluate((e) => e.style.getPropertyValue('--hc'))).toBe('#f9a8d4');
    await clickCenter(page, page.locator('.hl-ann').first());
    await expect(page.locator('.popover textarea')).toHaveValue('key claim');
    await page.click('.popover [data-ann-del]');
    await expect(page.locator('.hl-ann')).toHaveCount(0);
  });

  test('AT-09.1 notes: create, autosave, persist after reload, delete', async ({ page }) => {
    await page.click('[data-side=notes]');
    await page.click('[data-n=new]');
    await page.fill('.note-body', 'My takeaway\nThe gate filters noise.');
    await expect(page.locator('.save-state')).toHaveText('Saved', { timeout: 5000 });
    await page.reload();
    await page.click('[data-side=notes]');
    const item = page.locator('.note-item', { hasText: 'My takeaway' });
    await expect(item).toBeVisible();
    await item.click();
    await page.click('[data-n=delete]');
    await page.click('.modal button[type=submit]');
    await expect(page.locator('.note-item', { hasText: 'My takeaway' })).toHaveCount(0);
  });

  test('AT-06.1 manual map: add child, edit, move, delete; AT-06.5 depth, fold, fit, zoom', async ({ page }) => {
    await page.click('[data-act=new-map]');
    await page.fill('.modal input[name=title]', 'My map');
    await page.uncheck('.modal input[name=generate]');
    await page.click('.modal button[type=submit]');
    const root = page.locator('.mm-node.d0');
    await expect(root).toContainText('My map');
    const addChild = async (parent, title) => {
      await parent.click();
      await page.click('[data-a=child]');
      await page.fill('.modal input[name=title]', title);
      await page.uncheck('.modal input[name=ground]'); // no AI in this spec (AT-06.7 opt-out)
      await page.click('.modal button[type=submit]');
      await expect(page.locator('.mm-node', { hasText: title })).toBeVisible();
    };
    await addChild(root, 'Branch');
    await addChild(page.locator('.mm-node', { hasText: 'Branch' }), 'Leaf');
    await addChild(root, 'Other');
    await page.locator('.mm-node', { hasText: 'Leaf' }).click();
    await page.click('[data-a=edit]');
    await page.fill('.node-form input[name=title]', 'Leaf edited');
    await page.uncheck('.node-form input[name=reground]');
    await page.selectOption('.node-form select[name=parent_id]', { label: 'My map › Other' });
    await page.click('.node-form button.primary');
    await expect(page.locator('.mm-node', { hasText: 'Leaf edited' })).toBeVisible();
    await expect(page.locator('.crumbs')).toContainText('Other');
    // depth: 1 level hides the leaf, All shows it again
    await page.click('[data-depth="1"]');
    await expect(page.locator('.mm-node', { hasText: 'Leaf edited' })).toHaveCount(0);
    await page.click('[data-depth=all]');
    await expect(page.locator('.mm-node', { hasText: 'Leaf edited' })).toBeVisible();
    await page.locator('.mm-node', { hasText: 'Other' }).locator('.mm-toggle').click();
    await expect(page.locator('.mm-node', { hasText: 'Leaf edited' })).toHaveCount(0);
    const before = await page.locator('.mm-world').evaluate((e) => e.style.transform);
    await page.click('[data-act=zoom-in]');
    expect(await page.locator('.mm-world').evaluate((e) => e.style.transform)).not.toBe(before);
    await page.click('[data-act=fit]');
    await page.locator('.mm-node', { hasText: 'Branch' }).click();
    await page.click('[data-a=delete]');
    await page.click('.modal button[type=submit]');
    await expect(page.locator('.mm-node', { hasText: 'Branch' })).toHaveCount(0);
  });
});

test('AT-11.2 admin settings; AT-11.3 prompt edit, placeholder validation, reset', async ({ page }) => {
  await login(page);
  await page.goto('/admin');
  await expect(page.locator('h1', { hasText: 'Admin' })).toBeVisible();
  const model = page.locator('input[name=model]');
  const original = await model.inputValue();
  await model.fill('openai/gpt-6-luna');
  await page.click('.settings button');
  await expect(page.locator('.toast.ok')).toBeVisible();
  await page.reload();
  await expect(page.locator('input[name=model]')).toHaveValue('openai/gpt-6-luna');
  await page.fill('input[name=model]', original);
  await page.click('.settings button');
  const chat = page.locator('details.prompt[data-key=chat]');
  await chat.locator('summary').click();
  await chat.locator('textarea').fill('missing placeholders');
  await chat.locator('[data-save]').click();
  await expect(page.locator('.toast.error')).toContainText('placeholder');
  await chat.locator('[data-reset]').click();
  await expect(chat.locator('textarea')).toHaveValue(/\{\{context\}\}/);
});

test.describe('devices', () => {
  const open = async (page) => {
    await login(page);
    await newSession(page, `Device ${Date.now()}`);
  };

  test('AT-12.1 desktop shows map, paper and side panel together', async ({ page }) => {
    await page.setViewportSize({ width: 1440, height: 900 });
    await open(page);
    for (const sel of ['.pane-map', '.pane-paper', '.pane-side']) await expect(page.locator(sel)).toBeInViewport();
    await expect(page.locator('.split[data-split=sa]')).toBeVisible();
    await expect(page.locator('.ws-tabs')).toBeHidden();
  });

  test('AT-12.2 tablet splits map and paper; side panel is a drawer', async ({ page }) => {
    await page.setViewportSize({ width: 1024, height: 768 });
    await open(page);
    await expect(page.locator('.pane-map')).toBeInViewport();
    await expect(page.locator('.pane-paper')).toBeInViewport();
    await expect(page.locator('.pane-side')).not.toBeInViewport();
    await page.click('[data-act=toggle-side]');
    await expect(page.locator('.pane-side')).toBeInViewport();
  });

  test('AT-12.3 phone shows one pane at a time with a tab bar', async ({ page }) => {
    await page.setViewportSize({ width: 390, height: 844 });
    await open(page);
    await expect(page.locator('.ws-tabs')).toBeVisible();
    await expect(page.locator('.pane-map')).toBeVisible();
    await expect(page.locator('.pane-paper')).toBeHidden();
    await page.click('.ws-tabs [data-tab=paper]');
    await expect(page.locator('.pane-paper')).toBeVisible();
    await expect(page.locator('.pane-map')).toBeHidden();
    await page.click('.ws-tabs [data-tab=notes]');
    await expect(page.locator('[data-panel=notes]')).toBeVisible();
  });
});
