# 0449 - Roles: the API reads a stat by what it is for, not by its name

Status: accepted, built (2026-11-12). Slice Y2 of [RFC 0052](../rfcs/0052-game-systems-in-one-library.md). Builds on
[ADR 0448](0448-a-game-system-as-a-row.md) (a game system and its prefix),
[ADR 0390](0390-renaming-a-stat-and-an-enum-value.md) (what blocked renaming a stat the API reads by name) and
[ADR 0014](0014-stats.md) (the stat vocabulary).

## Context

The API reads some stats by name: the `weight` of an item, the `hp` and `armor` of a being, the `binding` of an instance, the
`carry_capacity` of a character, the groups `physical`, `economic`, `destroyable`, `damaging` and `tags` that make up an item's
named lists. A stat called that is read; one called anything else is not. With several game systems in one library (ADR 0448)
the name cannot be the contract: a system's own `ds_weight` is not the library's weight, and a library that calls it `mass`
cannot have it read.

## Decision

- **A role is a closed word a stat or a group may hold.** `stat_definition.role` is one of `weight`, `height`, `price`,
  `rarity`, `hp`, `armor`, `size`, `carry_capacity`, `containment_capacity`, `max_item_size`, `binding`, `is_container`;
  `stat_group.role` is one of `physical`, `economic`, `destroyable`, `damaging`, `tags`. Null for every other stat and group.
- **One holder per library.** A partial unique index on `(tenant_id, role) WHERE role IS NOT NULL` for each table: a second holder
  is a 409 (`stat-role-taken`).
- **A holder fits its role.** A definition takes a role only when its type is one the API reads it as (a number for `weight`, an
  enum with the value `none` for `binding`, a bool for `is_container`; `rarity` is read as a number, text or enum), else 422
  (`invalid-stat-role`). Only a new assignment is checked, so what exists keeps working.
- **A role-holder is neutral.** It belongs to no game system: a group with a system takes no role, a group that holds a role or
  has a stat that does takes no system, and a stat in a group with a system takes none (422). The role is the library's, the
  system's `ds_weight` is an ordinary stat.
- **`role` is in the requests and responses** of `POST`/`PATCH /stat-groups` and `POST`/`PATCH /stat-definitions`, and in the
  responses that return them. A `PATCH` with `role: null` clears it.
- **A name that is a role takes it, as before.** A new stat or group created without `role` that is called after a free role (and,
  for a stat, fits it and is in a group without a system) takes the role, so every existing client keeps the behaviour it had;
  `role: null` says none. A role-holder may be **renamed** now: the block of ADR 0390 on the reserved names is gone, since the
  name is no longer the contract. The value `none` of a `binding` stays reserved (renaming it is a 409), by role.
- **Reads follow the role.** The item and item-instance reads (`v_item`, `v_item_instance`, the named fields `weight`, `hp`...,
  `physical_stats` and the other lists, `is_container`), capacity and containment, the binding rules and the link preview pick
  their stats by role, not name.

## Design

The migration adds both columns and gives every existing stat and group whose name is in a list that role, whatever its type, so
each read answers as it did. It adds a check for the closed list and the partial unique index (names are already unique in a
library, so the backfill cannot collide), and replaces `v_item` and `v_item_instance` (a view cannot lose a column and keep its
dependents) with the same query reading `sd.role` where it read `sd.name`. The readers go through `roles.py`
(`DEFINITION_ROLES`, `GROUP_ROLES`, `role_fits`, `RESERVED_ENUM_VALUES`) and the entity view mixin
(`resolved_value_by_role`, groups and tags by group role).

A repository carries the role ([ADR 0118](0118-repository-tenants-subscriptions-and-a-gated-read.md)): a copy writes a group's or a definition's role when the library
has none holding it, and a role the library's own stat already holds is a collision of kind `stat_role` (the two stats merge when
they are the same type, else the incoming stat is skipped and holds none). The release document is format 41 with a `role` on
groups and definitions; a format 40 document is read with the roles its names imply, as the migration gave them.

## Validation and delivery

A test for each: assigning and clearing a role on a stat and a group, an unknown role, a role held once, a type that does not
fit, a binding without `none`, the neutral rule both ways, the default for a name that is a role (and `null`), the item read
following a role under another name, a renamed role-holder, a role cleared, a system's `ds_weight` not read, the reserved `none`
by role, the format 40 reader, and the copy. The existing tests that build stats by hand with a role's name get the role from a
hook in `conftest.py`. The OpenAPI change is the new field and the new collision kind (recorded in
`openapi-breaking-accepted.txt`); the CLI models and `packages/api-client` are regenerated.

## Consequences

- A library may name its weight anything, and a game system's own stats are never mistaken for the library's.
- Nothing changes for a library that never uses roles: its stats and groups have the roles their names imply.
- Y3 to Y6 build on roles: the system filter, templates, a campaign's system and the repository's systems.
