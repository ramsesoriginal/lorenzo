# 0101 - Editable information: singleton types, ordering, and description edits

Status: accepted

## Context

Accepts [RFC 0015](../rfcs/0015-information-metadata-shape.md) sub-slices 1 and 3, plus the description-only part of sub-slice 4.

At present, nothing created through the information API can be changed or removed. `routers/information.py` has a read route and knower grant/revoke, and nothing else ([ADR 0038](0038-information-payload-knowledge-crud-api.md)). `information` also carries a blanket `UNIQUE(entity_id, type)`, so an entity can hold one note and never a second.

RFC 0027 (LorenzoScript, proposed in [PR #203](https://github.com/ramsesoriginal/lorenzo/pull/203)) needs one more thing from this slice. Its inventory-web description editor ([issue #209](https://github.com/ramsesoriginal/lorenzo/issues/209)) has to replace the text of an existing description payload. RFC 0027 set four requirements for that endpoint:

- `If-Match`/`ETag` concurrency ([ADR 0042](0042-concurrency-token-on-reads.md)).
- The same self-or-managed authorization as description create (ADR 0038).
- `content` treated as opaque text.
- One shared write path for every description create and update, which its stage 7 ([issue #210](https://github.com/ramsesoriginal/lorenzo/issues/210)) will extend.

RFC 0015 sub-slice 2 (`entity_slug`) is **not** part of this ADR. RFC 0027 took it over as its own stage 5 ([issue #208](https://github.com/ramsesoriginal/lorenzo/issues/208)), and `item_instance.slug` is left untouched here.

## Decision

### Schema (one migration)

- **`information_type(name, is_singleton, category)`**: a global catalog, not tenant data. It has no `tenant_id` and no RLS; the app role gets `SELECT` only. `category` is `technical` or `gm_authored`. It is seeded with two rows, `description` and `main_picture`, both singleton and `technical`. Free-form types (`note`, `handout`, anything a GM invents) get no row.
- **The blanket `UNIQUE(entity_id, type)` is replaced by a partial unique index** `information_singleton_type ON information (entity_id, type) WHERE type IN ('description', 'main_picture')`. Every other type can repeat. The index predicate cannot read `information_type`, so the list and `is_singleton` are two separately maintained facts. A test compares them, so they can't drift silently.
- **`order` (integer, not null) on `information` and `payload`**, unique per parent: `UNIQUE(entity_id, "order")` and `UNIQUE(information_id, "order")`. Existing rows are backfilled 0, 1, 2, ... by `created_at, id` within each parent.
- **`information.created_by`** (`app_user.id`, `ON DELETE SET NULL`). [ADR 0029](0029-attribution-created-by-updated-by.md) deferred attribution on `information` until its write path was designed. The edit rule below needs it now. Existing rows keep `NULL`.

### Singleton checks are type-aware

`create_information` returns `409 InformationAlreadyExistsError` only when the type is singleton (looked up in `information_type`) and the entity already has a row of that type. A `PATCH` that changes `type` to a singleton type the entity already has fails the same way. These checks, and every `order` assignment, first take a row lock on the parent entity (`SELECT ... FOR UPDATE`). Two concurrent writers on one entity therefore run one after the other and cannot both pass the check.

### `order` on create

`InformationCreate` gains an optional `order`. If it is omitted, the server appends: `max(order) + 1` among the entity's rows, or `0` for the first row, under the same lock. An explicit `order` that is already taken returns `409 InformationOrderConflictError`. The single payload that `create_information` writes gets `order = 0`. A reorder endpoint (sub-slice 7) is not built. Swapping two rows means moving one to a free position first.

### Who may edit or delete an existing row

A caller needs **both** of the following:

1. **Standing over the entity**: the existing self-or-managed check, `authorize_entity_write` (ADR 0038). Failing this returns `403`.
2. **Sight of the row itself**: `information_visibility.can_see(row)`, or being the row's `created_by`. Failing this returns `404`, the same response as a missing row, so the row's existence isn't revealed.

Without (2), self-or-managed alone would let a player who owns a sword `PATCH` the GM's secret about that sword to `is_public = true`, or delete it. They could also grant their own character as a knower and read it. The `created_by` clause keeps a player able to edit a restricted note they wrote themselves, which (2) would otherwise block, because a new restricted row has no knowers yet. **The same gate is added to the existing knower `PUT`/`DELETE`**, which had the self-grant hole described above.

Creation is unchanged: anyone with standing can still author a row of any visibility (ADR 0038's deliberate narrowing, not reopened here).

### Routes

- **`PATCH /tenants/{tenant_id}/information/{information_id}`**: `InformationUpdate{title?, type?, is_public?, order?}`, with merge-patch semantics (`exclude_unset`) like every other `PATCH` in this API. `If-Match` is checked against `information.updated_at`. The response is `InformationOut` plus an `ETag` header.
- **`DELETE /tenants/{tenant_id}/information/{information_id}`**: `If-Match` as above, returns `204`. Payloads and knowledge rows cascade.
- **`PATCH /tenants/{tenant_id}/payloads/{payload_id}`**: `PayloadDescriptionUpdate{content?, locale?}`. It edits description payloads only. Any other kind returns `409 PayloadKindNotEditableError`, since number/picture/document authoring is still sub-slice 4's open question. `If-Match` is checked against `payload.updated_at`, and the route bumps that timestamp explicitly, because a change to `payload_description` alone doesn't touch the parent row. The response is `PayloadDescriptionOut` plus the payload's `ETag`. The authorization and visibility gate is the one above, applied to the payload's `information`.
- **`GET /tenants/{tenant_id}/information/{information_id}`** now also sets `ETag`.

The payloads router used to require a tenant `Membership` at the router level (`get_tenant_context`). That now applies to its `GET .../content` route only, not the whole router. The new `PATCH` uses `get_tenant_or_404` plus self-or-managed, like `routers/information.py`.

### One write path for description text

`description_payloads.write_description(session, *, payload, content, locale)` is the only code that creates or changes a `payload_description` row. `create_information` and the payload `PATCH` both call it. `content` is stored as given: no parsing, no validation, no length limit beyond what already exists. LorenzoScript is a client-side convention. RFC 0027 stage 7 adds its reference extractor inside this function.

### Response shapes (additive)

- `InformationOut` gains `is_public`, `order`, and `updated_at`.
- Every `PayloadOut` variant gains `id`, `order`, and `updated_at`. A client needs a payload's `id` to address it and its `updated_at` to build `If-Match`, and neither was exposed before.
- Payloads within an `InformationOut`, and information rows within `EntityDetailOut`, are listed by `order`.

### Activity log ([ADR 0084](0084-activity-log-coverage-and-member-removal-notice.md))

- `information.deleted` changes what exists, so it is logged.
- A `PATCH` that changes `is_public` changes who can see the row, so it logs `information.visibility_changed`. The detail carries the new tier only.
- Title, type, order, and payload text edits are descriptive-content edits and are not logged. That matches how renames and stat values are already handled.

## Not in scope

- RFC 0015 sub-slice 2 (`entity_slug`): RFC 0027 stage 5 owns it.
- The rest of sub-slice 4: adding payloads to an existing row, non-description payload kinds, binary upload format, `payload_entity`.
- Sub-slices 5 to 7: the per-entity information listing, player-knowers and knower listing, and the reorder endpoint.
- Tiering authorship by visibility (who may *create* a GM-only row). This stays as ADR 0038 left it.
- Reporting information changes in the player change feed ([ADR 0099](0099-player-facing-change-feed.md) left these out).

## Consequences

- An entity can now hold several notes, handouts, or anything else not in the singleton list. This applies to every existing row the moment the migration lands.
- The singleton list lives in two places: the index predicate and `information_type`. Adding a technical singleton type means changing both in one migration. The consistency test exists to catch a change that touches only one.
- Knower `PUT`/`DELETE` now also require sight of the row (or authorship). A caller with standing over an entity but no sight of a row about it now gets `404` where it used to succeed. This is the intended fix, and it is narrower than before.
- inventory-web's description editor (RFC 0027 stage 6) can now read a payload's `id`/`updated_at` from `GET /entities/{id}` or `GET /information/{id}` and `PATCH` it with `If-Match`.
- `order` values are unique but not dense: deleting a row leaves a gap, and nothing renumbers.
