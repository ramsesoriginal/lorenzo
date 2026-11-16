# 0448 - A game system as a row, and the prefix rule

Status: accepted, built (2026-11-12). Slice Y1 of [RFC 0052](../rfcs/0052-game-systems-in-one-library.md). Builds on
[ADR 0014](0014-stats.md), [ADR 0037](0037-effective-stat-resolution.md) (a definition's group and its priority),
[ADR 0390](0390-renaming-a-stat-and-an-enum-value.md) and [ADR 0443](0443-the-api-answers-what-it-used-to-ignore-crash-on-or-return-out-of-order.md)
(a duplicate name is a 409). Resolution does not change.

## Context

One library can hold the stats of several game systems only by convention: a prefix on every stat of a system, one group per
system. The convention has no home, so the sheet, a campaign and a repository cannot name a system, and a second `hp` collides.

## Decision

- **A system is a row.** `system(id, tenant_id, slug, name, root_entry_id)`: the slug is a short lowercase word (`[a-z][a-z0-9]{0,31}`,
  no underscore) unique in the library, the prefix of the names of its stats; the name is for people and may change; the root entry is
  the system root of [ADR 0181](0181-the-seeds-four-layers-and-a-system-root.md), optional, and is cleared if the entry goes. A library has no systems until
  someone makes one. Nothing is seeded.
- **Routes**, at the vocabulary's tier: `POST`, `GET` (a page, by slug), `GET /{id}`, `PATCH /{id}` and `DELETE /{id}` under
  `/tenants/{t}/systems`. Any member who may author the vocabulary makes and edits a system; a participant reads; an administrator
  deletes. A slug another system has is a 409, a root entry that is not one of the library's entries a 422. The slug cannot change
  while a stat group belongs to the system (409 `system-slug-in-use`), since the names of its stats start with it; a system a group
  belongs to is not deleted (409 `system-in-use`).
- **A stat group carries a system, and its definitions follow.** `stat_group.system_id` is null for a neutral group, and is in
  `POST /stat-groups`, `PATCH /stat-groups/{id}` (the one field that can be cleared) and the group's response. A definition keeps
  its group (ADR 0443), so its system is its group's and is as permanent.
- **The prefix rule.** A definition of a group with a system is named the slug, an underscore, and something: `ds_stamina`. The
  check runs on create, on rename, and when a group takes a system (or moves to another), which is refused (422
  `stat-name-prefix`, naming the first stats that do not carry the prefix) until every definition in it does. Names stay unique in
  the library, so reads by name keep working; a neutral definition takes any name. A group takes a system only when its definitions
  already carry the prefix, so existing groups stay neutral.
- **A stat row says where it comes from.** The entity read, the bulk read (`GET .../entities/effective-stats`) and the stat
  explanation add `stat_definition_id` (the entity read; the others have it), `group_id` and `system` (the slug, null for a neutral
  group) to each stat. A client need not join to the definitions by name.
- **Nothing else changes.** Every existing request and response keeps its path, body and status.

## Design

`system` is a tenant table with `tenant_id`, a same-tenant key to its root entry (the key's `SET NULL` clears only `root_entry_id`,
ADR 0117) and `FORCE ROW LEVEL SECURITY`, and is repository content (`repository_read`). It is in the copyable-table registry as not
copied yet: a repository carries systems from Y6, and until then a copy writes its groups neutral. `stat_group.system_id` is a
same-tenant key to it that does not clear the group. The slug of a stat row's group's system comes with the group in the queries that
already load it (a join in the entity read, one in the bulk read's definitions, one in the explanation), so no read costs a statement
it did not.

## Validation and delivery

A test for each: the routes (make, read, list, rename, reslug, delete, a root entry), the slug (a short lowercase word, never an
uppercase letter, an underscore, a digit first, empty or long; a duplicate; a root entry that is not one), the prefix rule on create
and on rename for a system's group and a neutral one, a group taking a system with and without the prefix and moving and clearing,
a slug that stays while a group uses it and a system that is not deleted then, a stat row's three fields on the entity read, the
bulk read and the explanation, a definition that cannot change group, and RLS. The OpenAPI change is the new routes and the new
fields on three responses; the CLI models and `packages/api-client` are regenerated.

## Consequences

- Two systems cannot collide on a stat name by construction, and the slug is permanent while a group uses it.
- A stat row grows three fields; a client that keyed on the name keeps working.
- Y2 to Y6 build on the row: roles, a system filter, templates, a campaign's system and the repository's.
