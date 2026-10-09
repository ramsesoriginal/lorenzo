// @ts-check
import { defineConfig } from 'astro/config';

// Static output only, per ADR 0004 — no server-side rendering at request
// time, ever.
export default defineConfig({
  output: 'static',
  vite: {
    server: {
      // WSL2 on a /mnt/ drive doesn't deliver file-change events - poll instead.
      watch: process.cwd().startsWith('/mnt/') ? { usePolling: true, interval: 300 } : undefined,
    },
  },
});
