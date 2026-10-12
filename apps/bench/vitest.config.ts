import { fileURLToPath } from 'node:url';
import { defineConfig } from 'vitest/config';

export default defineConfig({
  resolve: {
    alias: [
      {
        // The atlas is a file the bundler emits; unit tests only need an address for it.
        find: /^@lorenzo\/brand\/icons\.svg\?url$/,
        replacement: fileURLToPath(new URL('./tests/stubs/sprite-url.ts', import.meta.url)),
      },
    ],
  },
  test: {
    // tests/e2e/** is Playwright's, not Vitest's - see ADR 0114.
    exclude: ['**/node_modules/**', 'tests/e2e/**'],
  },
});
