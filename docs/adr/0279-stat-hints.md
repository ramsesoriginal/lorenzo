# 0279 - Stat hints: a maximum, a minimum and a resolved value, as clues

Status: accepted, decided with the maintainer on 2026-10-12. Slice A4 of [RFC 0043](../rfcs/0043-the-being-sheet.md); builds on [ADR 0278](0278-stat-definition-display-fields-order-and-patch.md).

## Context

A sheet draws "3 of 9" beside stress and "+3" beside a strength of 16. Both are other stats of the same being: a maximum stat and a modifier stat. Nothing says which stat belongs beside which, and a pair as a single tile is a template matter ([RFC 0043](../rfcs/0043-the-being-sheet.md), not in scope). The sheet only needs to know where to look.

## Decision

- **Three optional links on a stat definition**, each to another definition of the same tenant: `max_hint_id`, `min_hint_id` and `resolved_hint_id`, returned by `StatDefinitionOut`, accepted on create and on `PATCH`.
- **They are clues, not limits.** The API does not check a value against a hint and never changes a value because of one. A client reads the hinted stat's value on the same entity (it is already in the entity's stats): "of {max}", a caption {resolved}, and a stepper's floor {min}. If the hinted stat has no value on that entity, there is nothing to show and nothing to clamp.
- **Validation.** A definition cannot hint itself (422). A minimum or maximum hint must be a numeric definition, `int` or `float` (422). A resolved hint may be of any type.
- **Same tenant, by key.** Each link is a composite foreign key `(hint_id, tenant_id)` to `stat_definition (id, tenant_id)` ([ADR 0117](0117-same-tenant-references-by-composite-foreign-keys.md)). Deleting the hinted definition clears the link and keeps the definition: `ON DELETE SET NULL (hint_id)`, Postgres 15 or later, as `repository_copy` already does, since a plain `SET NULL` would try to null `tenant_id`.

## Not in scope

Pairs drawn as one tile; enforcing a hint; hints to a stat of another entity; copy, update and seed ([ADR 0280](0280-display-fields-in-repository-copy-updates-and-seed.md)).

## Consequences

- A floor at zero needs a stat holding zero (on a base prototype, say) and a minimum hint to it. That is clumsy, and was accepted: the alternative, a plain number on the definition, was not what was asked for.
- One migration; additive OpenAPI.
