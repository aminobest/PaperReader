// Shared helpers for system specs.
const { expect } = require('@playwright/test');
const path = require('path');

const FIXTURE = path.resolve(__dirname, '../fixtures/tiny_paper.pdf');

async function login(page, username = 'test', password = 'test123456789') {
  await page.goto('/');
  await page.fill('input[name=username]', username);
  await page.fill('input[name=password]', password);
  await page.click('button:has-text("Sign in")');
  await expect(page.locator('.new-session')).toBeVisible();
}

async function newSession(page, name) {
  await page.fill('.new-session input', name);
  await page.click('.new-session button');
  await expect(page.locator('.ws-title')).toHaveText(name);
}

async function uploadFixture(page) {
  await page.setInputFiles('[data-upload]', FIXTURE);
  await expect(page.locator('.paper-select')).toContainText('Gated Memory Networks');
  await expect(page.locator('.pdf-page[data-page="1"] .textLayer span').first()).toBeAttached({ timeout: 20000 });
}

/** Select the text of the first text-layer span containing `needle` (like a user drag-select). */
async function selectText(page, needle) {
  await page.evaluate((n) => {
    const span = [...document.querySelectorAll('.textLayer span')].find((s) => s.textContent.includes(n));
    if (!span) throw new Error(`no span contains ${n}`);
    const r = document.createRange();
    r.selectNodeContents(span);
    const sel = getSelection();
    sel.removeAllRanges();
    sel.addRange(r);
  }, needle);
  await expect(page.locator('.sel-bar')).toBeVisible();
}

async function clickCenter(page, locator) {
  const b = await locator.boundingBox();
  await page.mouse.click(b.x + b.width / 2, b.y + b.height / 2);
}

module.exports = { login, newSession, uploadFixture, selectText, clickCenter, FIXTURE };
