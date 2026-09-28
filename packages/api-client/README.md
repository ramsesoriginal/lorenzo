# @lorenzo/api-client

The typed client for [`apps/api`](../../apps/api) that [`apps/loot-bot`](../../apps/loot-bot) and [`apps/inventory-web`](../../apps/inventory-web) share. See [ADR 0122](../../docs/adr/0122-api-client-package.md) for why it exists and what it deliberately leaves out.

## What's in it

- `paths`, `components`, and `Schema<Name>`: the types generated from `apps/api`'s OpenAPI schema, in `src/schema.d.ts`.
- `createLorenzoClient({ baseUrl, getAccessToken?, fetch? })`: an [`openapi-fetch`](https://openapi-ts.dev/openapi-fetch/) client. With `getAccessToken`, every request carries the token, and a request without one is refused before it's sent. Without it, pass `Authorization` per request.
- `LorenzoApiError`, `toLorenzoApiError()`, and `unwrap()`: one error type for every failed call, carrying the API's own message and the whole problem body.
- `fetchAllPages()`, `MAX_PAGE_SIZE`, `Page<T>`: paging (ADR 0020).
- `etagOf()`: a response's `ETag`, for a later `If-Match` (ADR 0042).

What it doesn't hold: rules (the API decides what's allowed), app-shaped data, and presentation.

```ts
import { createLorenzoClient, unwrap } from '@lorenzo/api-client';

const client = createLorenzoClient({ baseUrl, getAccessToken });
const me = await unwrap(await client.GET('/me'));
```

## Regenerating the schema

After any change to `apps/api`'s routes or schemas:

```bash
mise run //apps/api:openapi-schema               # dumps apps/api/openapi.json (gitignored)
mise run //packages/api-client:generate-schema   # rewrites src/schema.d.ts
```

Commit the result. CI's `client-drift` job (`mise run //packages/api-client:check-schema`) fails while it's stale.

## Using it

It ships TypeScript source, like `@lorenzo/lorenzoscript`, so there's nothing to build. inventory-web's Vite build compiles it. loot-bot's `tsup` bundles it (`noExternal`), since loot-bot runs on Node from its own `dist/`.
