import { defineConfig } from '@playwright/test';

// For running these specs on the dev server, see ADR 0071 (mise.toml's test-e2e task is
// hidden). CI runs them through playwright.real-api.config.ts (`test:real-api:ci`). `webServer`
// starts the real dev server so tests exercise actual rendered pages, not a mock.
export default defineConfig({
  testDir: './tests/e2e',
  fullyParallel: true,
  webServer: {
    command: 'pnpm run dev',
    url: 'http://localhost:4322',
    reuseExistingServer: !process.env.CI,
  },
  use: {
    baseURL: 'http://localhost:4322',
  },
});
