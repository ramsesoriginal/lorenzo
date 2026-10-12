# 0278 - Stat definition display fields, an order for stats and groups, and `PATCH`

Status: accepted, decided with the maintainer on 2026-10-12. Slice A3 of [RFC 0043](../rfcs/0043-the-being-sheet.md).

## Context

A stat definition is a name, a type, a group and, for an enum, its values ([ADR 0014](0014-stats.md), [0103](0103-stat-tags-enum-values-and-mandatory-groups.md)). The being sheet needs to say more about how a stat is shown: a unit, a sign, whether a number or tag can be changed in play, whether it is pinned to the sticky bar, and the order stats and groups come in. Today there is no order at all (clients sort by name; `stat_group.priority` is the rank that breaks ties between inherited values, [ADR 0037](0037-effective-stat-resolution.md), not a display order), and neither definitions nor groups can be edited: the routes are create, read, list and delete.

## Decision

- **Columns.** On `stat_definition`: `unit` (text, null), `adjustable_in_play` (bool, false), `pin` (bool, false), `signed` (bool, false), `position` (integer, not null). On `stat_group`: `position` (integer, not null). `priority` keeps its meaning.
- **Order.** Existing rows are numbered by name in the migration (definitions within their group, groups within their tenant), so nothing moves. A new row that does not give a position is appended after its siblings by a trigger, as `information.order` is ([ADR 0101](0101-editable-information-and-description-payloads.md)). Two rows may share a position; ties are broken by name.
- **`PATCH /stat-definitions/{id}`** edits `unit`, `adjustable_in_play`, `pin`, `signed` and `position`; `PATCH /stat-groups/{id}` edits `name`, `priority`, `mandatory` and `position`. A definition's type and group are not editable here (a retype is breaking for libraries that copied it, as the release digest says). Both are the tenant-admin tier of the other stat vocabulary writes. Neither is recorded in the activity log: they change how things are drawn, not what exists or who can see or do what ([ADR 0084](0084-activity-log-coverage-and-member-removal-notice.md)). A group's name is unique in its tenant (409 when taken).
- **Create takes the same fields**, all optional.
- **Bulk reorder.** `PUT /stat-groups/{id}/order` with the ids of the group's definitions in the new order, and `PUT /stat-groups/order` with the tenant's group ids. Each must list every row it orders exactly once (422 otherwise), renumbers from 0 and answers with the rows in their new order.
- **Reads are sorted** by (group position, group name, definition position, definition name): `GET /stat-definitions`, `GET /stat-groups`, an entity's `stats`, and the stat lists of items and characters. `EntityStatValueOut` stays keyed by name.
- **Whether `adjustable_in_play` and `pin` apply to a bool stat (a tag)** is the client's: a tag is adjustable in play when its definition says so.

## Not in scope

Hints ([ADR 0279](0279-stat-hints.md)); copy, update, digest and seed ([ADR 0280](0280-display-fields-in-repository-copy-updates-and-seed.md)); the authoring screens in Bench and account-hub.

## Consequences

- The vocabulary is editable for the first time; a library can fix a unit or an order without deleting a definition.
- Until A5 lands, a repository's order and units do not reach a copy. A5 follows directly.
- One migration; the OpenAPI changes are additive. The apps' sort-by-name is replaced by the server's order.
