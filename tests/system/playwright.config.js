// CR-01 — system tests run against a fresh local server using the real LLM (small fixture = few tokens).
const { defineConfig } = require('@playwright/test');

module.exports = defineConfig({
  testDir: './specs',
  workers: 1,
  timeout: 6 * 60 * 1000,
  expect: { timeout: 15000 },
  reporter: [['list']],
  use: { baseURL: 'http://127.0.0.1:7420', trace: 'retain-on-failure' },
  webServer: { command: './start-server.sh', url: 'http://127.0.0.1:7420/api/health', reuseExistingServer: false, timeout: 60000 },
});
