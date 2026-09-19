// @ts-check
import { defineConfig } from 'astro/config';

// Static output only, per ADR 0004 — no server-side rendering at request
// time, ever.
export default defineConfig({
  output: 'static',
  build: {
    // Flat `page.html` files, not `page/index.html` directories. Directory
    // output makes Cloudflare Pages 308-redirect a bare `/auth/redirect`
    // request to `/auth/redirect/` before this app's own JS ever runs -
    // @authgear/web's finishAuthentication() then reconstructs the token
    // exchange's redirect_uri from the now-slash-suffixed window.location,
    // which no longer exact-matches the no-slash URI registered in
    // Authgear, and the token exchange 400s with "invalid redirect URI".
    // Flat files sidestep the redirect entirely (confirmed against a real
    // deploy) - every static host in use here serves `foo.html` for `/foo`
    // with no redirect.
    format: 'file',
  },
  // Fixed, non-default port: apps/inventory-web already owns Astro's
  // default 4321, and both apps need to run concurrently in local dev.
  server: { port: 4322 },
});
