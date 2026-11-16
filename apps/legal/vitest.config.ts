import { defineConfig } from 'vitest/config';

export default defineConfig({
  test: {
    // No end-to-end suite yet.
    exclude: ['**/node_modules/**'],
  },
});
