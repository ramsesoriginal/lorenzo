import { defineConfig } from 'vitest/config';

export default defineConfig({
  test: {
    // tests/e2e/** is Playwright's, not Vitest's - see ADR 0114.
    exclude: ['**/node_modules/**', 'tests/e2e/**'],
  },
});
