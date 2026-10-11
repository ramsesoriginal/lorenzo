# The hub's browser tests against the real API

These run the built site against the real `apps/api` on a fresh database and a fake Authgear, through
inventory-web's launchers ([ADR 0114](../../../../docs/adr/0114-inventory-web-end-to-end-tests.md),
[ADR 0136](../../../../docs/adr/0136-account-hub-client-and-tenant-slug.md)). They share their ports with
inventory-web's, so run one stack at a time. Locally, with Postgres from `infra/docker-compose.yml`:

```bash
E2E_POSTGRES_URL=postgres://lorenzo:lorenzo@127.0.0.1:55432/postgres pnpm run test:real-api
```

## What CI runs

CI runs `pnpm run test:real-api:ci` ([ADR 0196](../../../../docs/adr/0196-shelf-the-repositories-list-and-page.md)): the logged-out
smoke tests in `tests/e2e` and every spec in this folder, listed in that script. The pages were reworked
into `data-*` hooks and shared components after the first specs were written, and the stale ones have
since been repaired against them one file at a time (#505), so none is left out.

A new spec goes into `test:real-api:ci` in the same change that adds it. Find things the way the pages
are built: by their `data-*` hooks and by role and name, through the helpers in `support.ts`
(`signIn`, `openLibrary` for a library open on `/tenants`, `campaignCard`, `seatFor`). Do not delete a
spec to make a run green: if a behaviour has gone, say so in the spec and adapt it.

Notes on what the repaired specs rely on:

- `/tenants` opens one library at a time, the one `?tenant=<slug>` names (`openLibrary`); a campaign's
  people and invite links are on tabs of its card, and a library's "Leave" is on the Admins tab.
- The hub caches what it reads for the next page (`lib/cache.ts`), so a test that makes a page ask the
  API again (an unreachable API, an expired session) empties `sessionStorage` first.
- An account that may create and has no library gets the create form on `/tenants`, not an empty page;
  the link to `/setup` is in the header and on `/` and `/campaigns`.
