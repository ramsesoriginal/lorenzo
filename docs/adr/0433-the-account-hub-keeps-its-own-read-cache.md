# 0433 - The account hub keeps its own read cache

Status: accepted, decided with the maintainer on 2026-11-07. Builds on [ADR 0325](0325-one-read-cache-and-what-it-may-hold.md), which put one read cache in `packages/read-cache` and left the account hub's own cache out of scope.

## Context

Calendars, Maps, Sessions and Social read through `@lorenzo/read-cache`: a cache in front of `fetch`, scoped to the viewer, bounded, with a prefetch queue and a link-intent binder. The account hub does not. It has an older pair, `lib/cache.ts` (a keyed stale-while-revalidate store wrapped around each call as `cached(key, fn)`) and `lib/prefetch.ts` (the hover warmers per page). The question was whether the web redesign ([ADR 0428](0428-the-account-hub-moves-into-the-web-shell.md)) should move the hub onto the package.

The two differ in a way that decides it. The other apps are single-page: a navigation stays in one document, so memory is enough. The hub is a set of separate pages, and **every click is a full page load**, which empties memory. The hub's cache therefore mirrors what it holds into `sessionStorage`, so the next page can paint from it at once, and its hover warmers fill that storage before the click.

`@lorenzo/read-cache` keeps scoped reads (a library's campaigns, rosters, characters) in memory only and writes just `/me`, `/tenants` and `/app-links` to storage, because private bodies must not reach storage (ADR 0325). On the hub that would mean every library read is asked for again after every click, and the warmers would fill memory that the next page load throws away. The hub would be slower than it is.

## Decision

- **The hub keeps `lib/cache.ts` and `lib/prefetch.ts`.** They are not moved onto `@lorenzo/read-cache`.
- **This is a deliberate exception to ADR 0325, not an oversight.** The reason is the hub's shape (a full page load on every click), which the package's memory-only rule does not suit.
- **What the hub's cache does stays as it is**, including its three rules: a write that succeeds empties it, sign-in and sign-out empty it, and a reload asks again for everything. It is per tab, gone when the tab closes.
- **Its improvements land in the hub**, not in the package: the UI-D slices re-read `/me` each time a library is drawn, because a write empties the cache.

## Possible future addition

If one cache for every app becomes worth its cost, `@lorenzo/read-cache` could gain an **opt-in mode that keeps scoped reads in `sessionStorage`** for apps that are not single-page, and the hub would move onto it. That would bring the package's viewer scope, size and count limits, per-path invalidation and bounded prefetch queue to the hub at about the speed it has now. It would need its own ADR, because it amends ADR 0325's rule that private bodies never reach storage: the storage is per tab, scoped to the viewer, bounded and emptied at sign-out, but private text would sit in it for the life of the tab. The package would stay memory-only by default, so the other apps would not change. Repository and Discover reads in the hub would move last, once the work on those pages has landed.

## Consequences

- The hub is as fast as before, and no private-data rule is relaxed or newly argued.
- Two read caches remain, with different rules, and the hub's holds library bodies in `sessionStorage`, which ADR 0325 does not allow elsewhere.
- Changes to the package's cache (bounds, scoping, invalidation) do not reach the hub until the addition above is decided.
