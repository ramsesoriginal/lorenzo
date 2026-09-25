import { defineConfig, devices } from '@playwright/test';
import { API_URL, AUTHGEAR_URL, SITE_URL } from './tests/e2e/support/env.ts';

// End-to-end tests (ADR 0114): the built site, the real apps/api on a fresh database, and a
// fake Authgear, all started here. Locally, servers already running are reused.
const CI = Boolean(process.env.CI);

export default defineConfig({
  testDir: './tests/e2e',
  fullyParallel: true,
  forbidOnly: CI,
  reporter: CI ? [['list'], ['html', { open: 'never' }]] : 'list',
  use: {
    ...devices['Desktop Chrome'],
    // An installed browser instead of Playwright's own download, e.g. `msedge` or `chrome`.
    channel: process.env.E2E_BROWSER_CHANNEL || undefined,
    baseURL: SITE_URL,
    trace: 'retain-on-failure',
  },
  webServer: [
    {
      command: 'node tests/e2e/support/fake-authgear.ts',
      url: `${AUTHGEAR_URL}/.well-known/openid-configuration`,
      reuseExistingServer: !CI,
    },
    {
      command: 'node tests/e2e/support/api-server.ts',
      url: `${API_URL}/healthz`,
      reuseExistingServer: !CI,
      timeout: 300_000,
    },
    {
      command: 'node tests/e2e/support/site-server.ts',
      url: SITE_URL,
      reuseExistingServer: !CI,
      timeout: 300_000,
    },
  ],
});
