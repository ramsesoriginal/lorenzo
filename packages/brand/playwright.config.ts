import { defineConfig, devices } from '@playwright/test';

// Browser checks of the web interface parts (docs/design/web, RFC 0050, slice UI-A): the preview
// pages are served as they are, by a static server with no dependency, and driven in Chromium.
// There is no API, no database and no build.
const CI = Boolean(process.env.CI);
const PORT = Number(process.env.BRAND_E2E_PORT || 4381);

export default defineConfig({
  testDir: './tests/e2e',
  fullyParallel: true,
  forbidOnly: CI,
  retries: CI ? 1 : 0,
  reporter: CI ? [['list'], ['html', { open: 'never' }]] : 'list',
  use: {
    ...devices['Desktop Chrome'],
    viewport: { width: 1280, height: 900 },
    channel: process.env.E2E_BROWSER_CHANNEL || undefined,
    baseURL: `http://127.0.0.1:${PORT}`,
    trace: 'retain-on-first-failure',
  },
  webServer: {
    command: 'node tests/e2e/server.mjs',
    url: `http://127.0.0.1:${PORT}/preview/index.html`,
    env: { BRAND_E2E_PORT: String(PORT) },
    reuseExistingServer: !CI,
  },
});
