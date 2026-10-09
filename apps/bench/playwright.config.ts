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
  webServer: [
    {
      // Sign-in not configured: the plain page. Builds both copies, one after the other (two
      // builds at once trip over each other's cache), then serves this one.
      command: [
        'BENCH_OUT_DIR=./dist pnpm run build',
        'BENCH_OUT_DIR=./dist-auth PUBLIC_AUTHGEAR_ENDPOINT=http://authgear.test PUBLIC_AUTHGEAR_CLIENT_ID=bench-test-client pnpm exec astro build',
        'touch dist-auth/.ready',
        'BENCH_OUT_DIR=./dist pnpm exec astro preview --ignore-lock --port 4331',
      ].join(' && '),
      url: 'http://localhost:4331',
      reuseExistingServer: !process.env.CI,
      timeout: 120_000,
    },
    {
      // Sign-in configured against an Authgear that does not exist: the tests answer its
      // requests. Waits for the build above.
      command:
        "sh -c 'until [ -f dist-auth/.ready ]; do sleep 1; done; BENCH_OUT_DIR=./dist-auth pnpm exec astro preview --ignore-lock --port 4332'",
      url: 'http://localhost:4332',
      reuseExistingServer: !process.env.CI,
      timeout: 120_000,
    },
  ],
});
