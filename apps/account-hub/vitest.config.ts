import { defineConfig } from 'vitest/config';

export default defineConfig({
  test: {
    // tests/e2e/** and tests/real-api/** are Playwright's, not Vitest's - see ADR 0071.
    exclude: ['**/node_modules/**', 'tests/e2e/**', 'tests/real-api/**'],
  },
});
