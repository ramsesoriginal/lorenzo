import { defineConfig } from '@playwright/test';

// Not part of CI's default gate yet (mise.toml's test-e2e task is hidden) —
// see ADR 0071. `webServer` starts the real dev server so tests exercise
// actual rendered pages, not a mock.
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
