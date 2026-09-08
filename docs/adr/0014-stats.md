# 0014 - Stats: definitions, groups, and per-entity values

Status: accepted

## Context

[RFC 0001](../rfcs/0001-core-domain-data-model.md) designed `stat_definition`/`stat_group`/`entity_stat` as the extensible-attribute mechanism (weight, HP, and anything else) without a migration per new stat. This ADR promotes that piece as sub-slice 3, after `entity` ([ADR 0012](0012-entity-table.md)) and the tenant bootstrap ([ADR 0013](0013-tenant-table-bootstrap.md)). Prototype inheritance and the effective-stat resolution algorithm that walks it (RFC 0001's "more specific wins, tie-break on `stat_group.priority`") are **not** part of this decision — `entity_prototype` doesn't exist yet, so there's nothing to resolve or walk. This sub-slice only covers direct stat values and group membership.

## Decision

Four tables, all tenant-scoped (`tenant_id` + `ENABLE`/`FORCE ROW LEVEL SECURITY`, the pattern established in ADR 0012):

- **`stat_group`**`(id, tenant_id, name, priority, created_at, updated_at)` — clusters related stats ("physical," "combat"). `priority` (integer, default `0`) is stored now for RFC 0001's future inheritance tie-break, even though nothing resolves it yet — the column has to exist before `entity_prototype` does, or it's yet another later migration. `UNIQUE(tenant_id, name)`: two stat groups named "combat" in the same tenant is a bug, not a feature.
- **`stat_definition`**`(id, tenant_id, stat_group_id REFERENCES stat_group, name, value_type, created_at, updated_at)` — one `stat_group` has many `stat_definition`s. `value_type` is a native PostgreSQL enum (`int`/`text`/`float`/`bool`) — a small, fixed, schema-relevant set, unlike the open-ended `stat_group`/`stat_definition` names themselves. `UNIQUE(tenant_id, name)`, same reasoning as `stat_group`.
- **`entity_stat_group`**`(entity_id REFERENCES entity, stat_group_id REFERENCES stat_group, tenant_id)` — the n:m "which stat groups has this entity/prototype acquired" relation. Composite primary key `(entity_id, stat_group_id)`; no separate surrogate id for a pure join table.
- **`entity_stat`**`(entity_id REFERENCES entity, stat_definition_id REFERENCES stat_definition, tenant_id, value_int, value_text, value_float, value_bool, created_at, updated_at)` — the actual values, one row per `(entity, stat_definition)`, composite primary key. Exactly one of the four `value_*` columns may be set (`CHECK (num_nonnulls(value_int, value_text, value_float, value_bool) = 1)`) — *which* one should be set, matching `stat_definition.value_type`, isn't enforced by the schema (that needs a cross-table check, i.e. a trigger); left to application code for now.

`tenant_id` is denormalized onto all four tables (not derived via join), matching every table so far — needed for a simple, direct RLS policy on each.

## Consequences

- Filtering/aggregating stats directly against `entity_stat` (rather than through a `v_item`-style view) means a self-join per stat of interest — the standard EAV cost, already accepted in RFC 0001.
- **Known, unsolved gap**: nothing enforces that an `entity_stat_group`/`entity_stat` row's own `tenant_id` actually matches its `entity`'s and `stat_group`'s/`stat_definition`'s `tenant_id`. A row linking mismatched tenants wouldn't leak data — RLS still filters each side independently, so the join would just silently fail to resolve — but it would be a real data-integrity bug. Not solved here.
- No resolution algorithm yet: "what's this entity's effective weight, inherited or not" isn't answerable until `entity_prototype` exists and something walks it. This sub-slice only proves an entity can acquire stat groups and hold direct values.
- Same RLS caveat as ADR 0012: policies are real and tested, but currently unenforced in practice until the app's DB role stops being a superuser.
