# 0142 - Acquiring a stat group on the generic stat `PUT`

Status: accepted

One of four small `apps/api` additions for [RFC 0025](../rfcs/0025-lorenzo-cli-mpmb-item-importer.md) (R9, R11; slice 3, the one the review's code check turned up). See [ADR 0139](0139-name-an-item-when-it-is-created.md).

## Context

An entity *acquires* a stat group ([ADR 0014](0014-stats.md)) through an `entity_stat_group` row. The row is what `GET .../entities/{id}` lists as the entity's `stat_groups`, and it is repository content: a copy carries it to the subscriber, and a sync compares it ([ADR 0119](0119-copying-a-repository-into-a-tenant.md), [ADR 0121](0121-repository-updates-and-re-sync.md)).

Only the tag routes write it ([ADR 0103](0103-stat-tags-enum-values-and-mandatory-groups.md): `PUT`, `PATCH` and `DELETE .../tags/{id}` pass `acquire_group=True`), so only a `bool` stat can bring its group along. The generic `PUT .../stats/{id}` passes `acquire_group=False`, which ADR 0037 named as a gap and left. So `physical`, `economic`, `destroyable` and `damaging` cannot be acquired by any route: an item imported with a weight would carry the value, but list no group, and a subscriber's copy would inherit the same.

RFC 0025 R9 assumed the importer could acquire groups itself. It can't, without this.

## Decision

`SetEntityStatRequest` gains an optional `acquire_group`, a boolean defaulting to `false`.

- When `true`, the stat's group is added to the entity (an `entity_stat_group` row) if it is missing, by the same path the tag routes use (`_write_own_value`), in the same transaction as the value.
- When `false` or omitted, the route behaves exactly as before. A stat write that would fail (a formula on the entity, a wrong type) fails without acquiring anything.
- It only ever adds. Nothing removes a group on this route, as nothing does on the tag `PUT`; removing a value never removes a group.
- It is a field of the body, not a query parameter, because the caller already sends a JSON object.

## Consequences

- Additive and optional on the wire; no migration. The default keeps every existing caller's behaviour, which ADR 0037 chose deliberately for hand edits. The generated TypeScript types make a field with a default required, so the callers of this route in inventory-web's end-to-end support code now send `acquire_group: false`; that change ships with this one.
- The importer sets `acquire_group: true` on the first stat it writes from each group, so the groups reach a copy.
- The choice is the caller's. A client that wants a value stored without listing its group still can.
