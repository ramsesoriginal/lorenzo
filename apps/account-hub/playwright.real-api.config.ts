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
      // Public repositories are off by default (ADR 0290): Studio's visibility switch is tested on a
      // deployment that has them, and it is shown only to an Owner of a repository.
      // A repository holds at most 50 entries here (ADR 0298), so a spec can reach the limit with a
      // handful of requests; no other spec comes near it.
      // Its specs release the same repository again and again within seconds, so releases are not held
      // apart (ADR 0301); studio-release-cooldown.spec.ts runs once more with the API's own default.
      env: {
        E2E_DATABASE: 'lorenzo_account_hub_e2e',
        PUBLIC_REPOSITORIES_ENABLED: 'true',
        // Where a storefront's Report link goes (ADR 0299).
        REPORT_ADDRESS: 'reports@example.test',
        REPOSITORY_MAX_ENTRIES: '50',
        RELEASE_COOLDOWN_SECONDS: process.env.E2E_RELEASE_COOLDOWN_SECONDS ?? '0',
      },
    },
    { command: 'node tests/real-api/site-server.ts', url: SITE_URL, timeout: 300_000 },
  ],
});
