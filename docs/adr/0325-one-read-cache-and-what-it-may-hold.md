# 0325 - One read cache, and what it may hold

Status: accepted, decided with the maintainer on 2026-10-22. Builds on ADR 0313 and 0315 (Calendars) and ADR 0317 (Sessions).

## Context

Four read caches exist. `staleCache.ts` in `beings` and `inventory-web` is one file twice (in memory, keyed `peek`, `refresh(key, maxAge)` and `prefetch`, newest fetch wins); the copy in `beings` has no caller. Account-hub's `cache.ts` is a global stale-while-revalidate store kept in memory and mirrored to `sessionStorage` (fresh for 15 seconds, discarded after 30 minutes, emptied by any write and at sign-in and sign-out). Calendars' `read-cache.ts` is scoped by viewer, tenant and role, with byte limits. Sessions has none and sends many reads with `cache: 'no-store'`.

Calendars keeps a response only when `events/access` says `can_retain_private`, which is true for full-visibility administrators alone. A GM or a player gets no retained response and no prefetch, so they see the slowest version of the app. Its `start()` calls `/app-links`, `/me`, `/tenants` and `events/access` one after another.

[ADR 0313](0313-event-participation-browsing-and-calendar-addresses.md) allows bounded viewer-, tenant- and visibility-scoped caches, in-flight de-duplication and bounded prefetch; it keeps private Information in the session and out of durable storage, says a cache is not authorization, and says prefetch never creates a period or moves the selected date. [ADR 0317](0317-sessions-scenes-and-collaborative-planning.md) allows no durable private cache and no offline grant.

## Decision

- **One package, `packages/read-cache`**, with a keyed stale-while-revalidate core: in-flight de-duplication, newest-wins, a time to keep, a byte and entry limit, prefix invalidation, `clear()`, and a bounded prefetch queue with one binder for hover, focus and touch. The key always contains a scope (viewer, library, role and the opt-out flags that change what the viewer sees) and resolved UUIDs, never a slug. Calendars and Sessions use it. The copy in `beings` is deleted and the one in `inventory-web` moves onto it; account-hub keeps its own cache for now.
- **What may be held, and where:**

  | Held | Where | For how long |
  | --- | --- | --- |
  | Entries, Information and notes, periods and summaries, rosters, Sessions, Scenes, Event order, calendar definitions and year previews | memory only, in the viewer's scope | short, as stale-while-revalidate |
  | `/me`, `/tenants` and `/app-links` | `sessionStorage`, as account-hub already holds them | minutes; emptied at sign-out |
  | The theme and the last library | `localStorage`, as now | until changed |
  | Anything else | nowhere durable | none |

  Private bodies never reach `sessionStorage` or `localStorage`. The retention restriction to administrators is lifted because the scope, not the role, now decides who may see a held response.
- **A cache is not authorization.** Entering a protected view still awaits `events/access` (one small read) before cached private data is drawn; a denied read, a role change or a different library clears what that scope held; sign-out and a restore from the back-forward cache clear everything. The API decides every write.
- **Writes** invalidate the affected prefix before the request and again after it, and a read that began before the invalidation cannot repopulate the cache.
- **Prefetch** stays bounded (two requests at once, eight queued, sixteen distinct intentions per view), is a `GET` only, respects the same scope, creates no period and changes no selection.
- **Start-up** runs `/app-links`, `/me` and `/tenants` in parallel, answers from the held `sessionStorage` copy at once while revalidating, then reads `events/access`.
- **HTTP revalidation** is checked before the package is written: where the API already sends an `ETag` and a private cache policy, Sessions drops `cache: 'no-store'` so a `304` carries the unchanged body; where it does not, the package's own freshness rules apply and the API is left alone.

## Not in scope

An offline mode, a service worker or any durable copy of private text; migrating account-hub's cache; caching writes or comparison `POST`s.

## Consequences

- GMs and players get the same held responses and prefetch as administrators, within their own scope.
- Second and later navigations in a tab skip the three start-up reads.
- A single set of tests covers invalidation, scope isolation and clearing.
- `sessionStorage` holds membership data for the length of a tab; it is already the practice in account-hub and no private body is added to it.
