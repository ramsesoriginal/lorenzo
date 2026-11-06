# Lorenzo Social

The relationships between the entries of a library: who knows whom, which way each tie goes, what it
holds (a standing, a Concordance) and who may see it. A static Astro app in plain TypeScript, on the
shared page frame and brand ([ADR 0408](../../docs/adr/0408-lorenzo-social-the-app.md),
[RFC 0049](../../docs/rfcs/0049-lorenzo-social-relationships-and-social-webs.md)). Every read and write
goes through [`apps/api`](../api); the app holds no durable private cache and no secret.

## What it does

- Libraries first, then **Relationships**: a searchable list of what the person may see, and for those
  who write relationships (Owners, Organizers, Authors and GMs) a form that makes one from two ends,
  a direction, an optional type and an audience (restricted unless opened).
- One relationship's page: the sentence that says it, what it is of, what it holds, and the changes a
  writer may make (swap the ends, one way or both, who may see it, delete).
- A relationship is shown only with both ends visible to the reader; the API decides, the page only
  words what it is told.

## Running it

```bash
cp .env.example .env     # an Authgear SPA client of its own, see docs/operations/social-setup.md
mise run //apps/social:dev   # http://127.0.0.1:4329
```

The API has to allow the app's origin in `CORS_ALLOWED_ORIGINS`.

## Checks

`mise run //apps/social:lint` is Biome, `astro check` and Prettier for `.astro`; `:test` is Vitest (the
words a page uses, and the stylesheet's tokens-only rule); `:test-e2e` is Playwright against the real
API and a fake Authgear, with ports and a database of its own: a GM making a relationship, a player
seeing only what they may, axe in light and dark, and the phone width.

## Hosting

[docs/operations/social-setup.md](../../docs/operations/social-setup.md).
