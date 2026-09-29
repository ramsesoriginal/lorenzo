import { defineConfig } from '@playwright/test';
import { API_URL, AUTHGEAR_URL, SITE_URL } from '../inventory-web/tests/e2e/support/env';
// Reuse the established real API + fake Authgear launchers (ADR 0114).
// Run separately from inventory-web: this stack uses the same local ports.
export default defineConfig({
  testDir: './tests',
  testMatch: ['e2e/**/*.spec.ts', 'real-api/**/*.spec.ts'],
  fullyParallel: true,
  use: {
    baseURL: SITE_URL,
    channel: process.env.E2E_BROWSER_CHANNEL || undefined,
    trace: 'retain-on-failure',
  },
  webServer: [
    {
      command: 'node tests/e2e/support/fake-authgear.ts',
      cwd: '../inventory-web',
      url: `${AUTHGEAR_URL}/.well-known/openid-configuration`,
      timeout: 300_000,
    },
    {
      command: 'node tests/e2e/support/api-server.ts',
      cwd: '../inventory-web',
      url: `${API_URL}/healthz`,
      timeout: 300_000,
      env: { E2E_DATABASE: 'lorenzo_account_hub_e2e' },
    },
    { command: 'node tests/real-api/site-server.ts', url: SITE_URL, timeout: 300_000 },
  ],
});
