// @ts-check
import { defineConfig } from 'astro/config';

// Static output only, per ADR 0004 — no server-side rendering at request
// time, ever.
export default defineConfig({
  output: 'static',
  // The browser tests build a second copy with sign-in configured, beside the plain one.
  outDir: process.env.BENCH_OUT_DIR || './dist',
  vite: {
    server: {
      // WSL2 on a /mnt/ drive doesn't deliver file-change events - poll instead.
      watch: process.cwd().startsWith('/mnt/') ? { usePolling: true, interval: 300 } : undefined,
    },
  },
});
