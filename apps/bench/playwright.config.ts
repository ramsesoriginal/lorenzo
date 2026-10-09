import { defineConfig, devices } from '@playwright/test';

// Browser tests of the built static page; no API is involved yet (ADR 0210).
export default defineConfig({
  testDir: './tests/e2e',
  fullyParallel: true,
  forbidOnly: Boolean(process.env.CI),
  reporter: 'list',
  use: {
    ...devices['Desktop Chrome'],
    viewport: { width: 1440, height: 900 },
    baseURL: 'http://localhost:4331',
    channel: process.env.E2E_BROWSER_CHANNEL || undefined,
    launchOptions: { executablePath: process.env.E2E_CHROMIUM || undefined },
  },
  webServer: {
    command: 'pnpm run build && pnpm exec astro preview --port 4331',
    url: 'http://localhost:4331',
    reuseExistingServer: !process.env.CI,
    timeout: 120_000,
  },
});
