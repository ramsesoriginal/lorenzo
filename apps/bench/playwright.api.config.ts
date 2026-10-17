import { defineConfig, devices } from '@playwright/test';
import { API_URL, AUTHGEAR_URL, SITE_URL } from '../beings/tests/e2e/support/env.ts';

// Reuse the existing fake Authgear/API launchers, as account-hub does for inventory-web.
export default defineConfig({
  testDir: './tests/real-api',
  fullyParallel: false,
  forbidOnly: Boolean(process.env.CI),
  reporter: 'list',
  use: {
    ...devices['Desktop Chrome'],
    baseURL: SITE_URL,
    viewport: { width: 1440, height: 900 },
    trace: 'retain-on-failure',
  },
  webServer: [
    {
      command: 'node ../beings/tests/e2e/support/fake-authgear.ts',
      url: `${AUTHGEAR_URL}/.well-known/openid-configuration`,
      reuseExistingServer: process.env.E2E_REUSE_SERVERS === '1',
      timeout: 120_000,
    },
    {
      command: 'node ../beings/tests/e2e/support/api-server.ts',
      env: { E2E_DATABASE: 'lorenzo_bench_e2e' },
      url: `${API_URL}/healthz`,
      reuseExistingServer: process.env.E2E_REUSE_SERVERS === '1',
      timeout: 120_000,
    },
    {
      command: 'node tests/real-api/site-server.ts',
      url: SITE_URL,
      reuseExistingServer: process.env.E2E_REUSE_SERVERS === '1',
      timeout: 120_000,
    },
  ],
});
