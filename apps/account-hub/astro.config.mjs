// @ts-check
import { defineConfig } from 'astro/config';

// Static output only, per ADR 0004 — no server-side rendering at request
// time, ever.
export default defineConfig({
  output: 'static',
  // /overview and /characters became one page (ADR 0179). A static build turns
  // each entry into a page that forwards, so bookmarks and old links still work.
  redirects: {
    '/overview': '/campaigns',
    '/characters': '/campaigns',
  },
  // Fixed, non-default port: apps/inventory-web already owns Astro's
  // default 4321, and both apps need to run concurrently in local dev.
  server: { port: 4322 },
});
