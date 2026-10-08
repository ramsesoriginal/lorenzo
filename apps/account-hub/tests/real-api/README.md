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
smoke tests in `tests/e2e`, `tests/real-api/shelf.spec.ts`, `tests/real-api/copy.spec.ts`, `tests/real-api/studio.spec.ts` and `tests/real-api/updates.spec.ts` ([ADR 0201](../../../../docs/adr/0201-shelf-the-copy-wizard.md), [ADR 0202](../../../../docs/adr/0202-studio-my-repositories.md), [ADR 0203](../../../../docs/adr/0203-shelf-the-update-inbox.md)). Those are the tests known to match the pages
as they are today.

## What is not run in CI, and why

The other specs in this folder were written against the pages as they were before the hub's pages were
reworked: they look for elements that have since become `data-*` hooks (`#tenant-list`, `#repository-list`,
`#account-signed-in`) and for headings and controls the pages no longer have. `signIn` in `support.ts` has
been brought up to date; the specs have not. Run on their own they fail on those selectors, not on
behaviour. They stay here, so that what each one checks is not lost, and are repaired one file at a time
(each repaired spec is added to `test:real-api:ci`), tracked in #505. Do not delete one to make a run green.

The specs not run in CI: `admin-basics`, `being-handoff`, `campaigns`, `errors`, `exits`, `invite-links`,
`repositories` (what is left of it, about `/beings` and the pages of playing: the rest became
`studio.spec.ts`, ADR 0202), `self-service`, `setup` and `tenant-slug`.
