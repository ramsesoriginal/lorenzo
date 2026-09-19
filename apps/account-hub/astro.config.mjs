// @ts-check
import { defineConfig } from 'astro/config';

// Static output only, per ADR 0004 — no server-side rendering at request
// time, ever.
export default defineConfig({
  output: 'static',
  // Fixed, non-default port: apps/inventory-web already owns Astro's
  // default 4321, and both apps need to run concurrently in local dev.
  server: { port: 4322 },
});
