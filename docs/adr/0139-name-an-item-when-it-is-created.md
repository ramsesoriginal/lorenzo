# 0139 - Naming an item when it is created: `ItemCreate.slug`

Status: accepted

One of four small `apps/api` additions for [RFC 0025](../rfcs/0025-lorenzo-cli-mpmb-item-importer.md) (R4, R11; slice 3). The others are [ADR 0140](0140-a-stack-when-an-item-instance-is-created.md), [ADR 0141](0141-fractional-weights-in-the-named-columns.md) and [ADR 0142](0142-acquiring-a-stat-group-on-the-generic-stat-put.md).

## Context

An entity's slug is its name in addresses and in `[[…]]` links, unique per tenant across every kind of entity ([ADR 0107](0107-entity-slugs-and-batch-resolve.md)). An item instance can be given one when it is created (`ItemInstanceCreate.slug`, [ADR 0043](0043-item-instance-slug.md)). A catalog item can't: `POST /items` takes a name and prototypes, and the slug is a second call, `PUT .../entities/{id}/slug`.

For most callers that is fine. For the importer of RFC 0025 it isn't, because the slug is the item's identity (R4): a run that is interrupted between the two calls leaves an item that exists but that no later run can recognise, and a repeated `POST` for the same source key makes a second, unnamed item instead of failing.

## Decision

`ItemCreate` gains an optional `slug`, with the same grammar as every slug write (`Slug`, ADR 0107).

- When given, `POST /items` checks that no entity in the tenant already has it and answers `409` if one does, with the same problem as `PUT .../entities/{id}/slug` (`EntitySlugConflictError`). Otherwise the `entity_slug` row is written in the same transaction as the entity and the item.
- When omitted, nothing changes.
- The `409` is the point: a second `POST` for a key that was already imported is refused cleanly, so "already imported" is an answer and not a duplicate.
- `ItemOut` does not gain a `slug` field. `GET .../entities/{id}` and `GET .../entities/resolve` already return it, and widening `ItemOut` is a separate question.
- The activity log entry for `item.created` is unchanged.

## Consequences

- Additive and optional: no migration, no change for a caller that doesn't send it. The OpenAPI diff is an added optional property.
- The slug is checked before it is written, as for item instances. Two requests for the same new slug at the same moment can both pass the check, and then `UNIQUE (tenant_id, slug)` refuses the second; that surfaces as it does for item instances today. A single importer run creates sequentially.
- The importer no longer needs the "create, then `PUT` the slug" fallback of R4, or the adoption rule that goes with it, against an API that has this field.
