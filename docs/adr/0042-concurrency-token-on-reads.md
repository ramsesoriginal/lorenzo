# 0042 - Concurrency token on reads

Status: accepted

## Context

A client team building a "loot drop" flow on top of this API (a GM opens an already-prepared container, players race to take individual items or part of a stack, a GM later reassigns claimed items) reported that `If-Match` is effectively unusable today: [ADR 0032](0032-item-and-item-instance-crud-api.md) already wired `check_if_match`/`etag_for` (`etag.py`) into every item/item-instance write that accepts it (`PATCH`, `DELETE`, the owner/container `PUT`/`DELETE` actions, [ADR 0041](0041-containment-quantity-and-stacking.md)'s `split`), but nothing on the *read* side ever hands a client a token to send back - neither `ItemOut`/`ItemInstanceOut` nor any response header exposes one. Concretely: two clients racing to "take" the same item both currently succeed, last-write-wins, with no way for either to have detected the race in the first place, since neither ever had anything valid to put in `If-Match`.

## Decision

### Token shape: both a response header and a body field, same source

`etag.etag_for(entity.updated_at)` already exists and is what every write already checks `If-Match` against - reused as-is, not replaced. Every read/write response for an item or item instance now also sets it as the `ETag` response header, and `ItemOut`/`ItemInstanceOut` both gain `updated_at: datetime` (the plain field the ETag is derived from, already loaded - `entity.updated_at` is already touched by both schemas' `created_by`/`updated_by` fields, so this adds no new eager-load requirement). Exposing both, rather than picking one: a client already reading HTTP headers can round-trip the `ETag` header with no body parsing; a client working at the JSON-body level (or logging/debugging) can read `updated_at` directly without needing to also thread response headers through its own data layer. Both derive from the identical `entity.updated_at` value, so they can never disagree.

Applied to both `items` and `item-instances`, not item-instances alone as originally asked: `routers/items.py` accepts `If-Match` on the identical `PATCH`/`DELETE` shape and has the identical gap - fixing only one router would leave the other newly, visibly inconsistent.

### `If-Match` stays optional everywhere

Not made mandatory on any endpoint. `etag.py`'s own documented philosophy (a caller that skips `If-Match` gets last-write-wins, unchanged from before it existed) stands - nothing about closing the "can't obtain a token" gap requires also forcing every existing client to start sending one, and doing so would be a breaking change to already-shipped behavior with no requester for it.

### No `ETag` on paginated list responses

A `Page[ItemOut]`/`Page[ItemInstanceOut]` has no single resource state to key one entity's `updated_at` off - each row already carries its own `updated_at` field for a client that wants to cache/compare per-row.

## Not in scope

Making `If-Match` mandatory on any endpoint (see above - a real option, deliberately not taken here without a concrete requester). A `version: int` counter column as an alternative token shape - `updated_at` already serves the identical purpose at zero schema cost, and this ADR doesn't see a reason to add a second, redundant source of truth for it.

## Consequences

- `schemas/items.py`: `ItemOut`/`ItemInstanceOut` gain `updated_at: datetime`; `from_v_item`/`from_v_item_instance` populate it from `view.entity.updated_at`, alongside the `created_by`/`updated_by` fields already read from the same object.
- `routers/items.py`/`routers/item_instances.py`: every route that returns one of these two schemas now also sets `response.headers["ETag"]` before returning - `GET .../{id}`, and every write's own response (already holding a `Response` parameter, or gaining one where it didn't).
- A client can now do the thing the whole point of `If-Match` was for: `GET`, read either the `ETag` header or `updated_at`, then `PUT`/`PATCH`/`DELETE`/`split` with `If-Match` set to it - a genuinely enforced compare-and-swap against a concurrent write, surfaced as `412 PreconditionFailedError` (`etag.check_if_match`, unchanged) on conflict instead of silent last-write-wins.
