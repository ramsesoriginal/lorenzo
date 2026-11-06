/// <reference types="vitest/config" />
import { getViteConfig } from 'astro/config';

// The web shell's tests render the real Astro components (the container API) and drive them in jsdom,
// so a change to the markup that breaks bindShell fails here and not in an app.
export default getViteConfig({
  test: {
    exclude: ['**/node_modules/**'],
  },
});
