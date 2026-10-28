# @lorenzo/read-cache

A cache of what an app reads from the API, kept in front of `fetch`, and a bounded prefetch queue ([ADR 0325](../../docs/adr/0325-one-read-cache-and-what-it-may-hold.md)). Calendars, Sessions and Maps use it. It is bounded session memory, never an offline grant and never authorization: the API still decides every read and write, and a held answer is only ever served to the viewer it was read for.

## Using it

```ts
import { createFetchCache } from '@lorenzo/read-cache';
import { createLorenzoClient } from '@lorenzo/api-client';

const reads = createFetchCache({
  policy(url) {
    if (url.pathname === '/me' || url.pathname === '/tenants' || url.pathname === '/app-links') {
      return { freshMs: 15_000, staleMs: 600_000, persist: true }; // who the person is
    }
    if (!url.pathname.startsWith('/tenants/')) return null;
    return { freshMs: 10_000 }; // what a library holds
  },
  storage: sessionStorage,
});

const client = createLorenzoClient({ baseUrl, getAccessToken, fetch: reads.fetch });

reads.configure(JSON.stringify([viewerId, tenantId, role, flags])); // once the viewer is known
```

Every typed call through that client is then cached, and every write invalidates (before the request and after it).

## What it holds, and where

- **Scoped reads** (a library's entries, notes, periods, rosters...): in memory only, under the scope given to `configure`. A different scope (another viewer, library, role or opt-out) never sees them, and a new scope forgets the old one's. Nothing is held until a scope is set, and `suspend()` stops serving while a page changes. They are served for `freshMs` and no longer, and at most 64 entries, 2 MiB and 256 KiB per body by default.
- **Identity reads** (`/me`, `/tenants`, `/app-links`): who the person is and where they may go. With `persist` they are also kept in the storage given (the tab's `sessionStorage`), outside any scope, so a navigation that reloads the page still has them; with `staleMs` they are answered at once and read again in the background, and `onRefreshed` tells the page when the answer changed. Nothing else is ever written to storage.
- `clear()` forgets everything, storage included: call it at sign-in and sign-out. `dropScoped()` forgets the scoped reads and the scope but keeps the identity reads: call it when a page goes away (`pagehide`). A 401, 403 or 404 clears it too. A read that began before an invalidation cannot fill the cache.
- `invalidate('/tenants/<id>/calendars')` forgets only reads under a path.

## Prefetch

`createPrefetchQueue()` runs reads ahead of a click, at most two at once, eight waiting and sixteen distinct intentions per view (`reset()` for a new view). `bindLinkIntent` calls you when the pointer rests on a link, the keyboard arrives at one or it is touched. A prefetch is a read through the cache: it creates nothing and changes no selection.

## Tests

`mise run //packages/read-cache:test`: scope isolation, freshness, de-duplication, invalidation (including a read in flight), limits, the 404 reset, and what reaches storage.
