# 0117 - Same-tenant references, enforced by composite foreign keys

Status: accepted

## Context

Every tenant table carries a `tenant_id`, and RLS keeps each tenant's rows to itself ([ADR 0002](0002-multi-tenancy-shared-schema-rls.md), [ADR 0021](0021-restricted-app-role-for-rls-enforcement.md)). But a row that points at another row, such as `entity_prototype.prototype_id → entity.id` or `entity_stat.stat_definition_id → stat_definition.id`, uses a single-column foreign key. Nothing in the database says both ends share a tenant. The routers keep them together by looking the target up with an explicit `tenant_id` filter first (`get_entity_or_404` and its siblings).

That has been enough, because a request could only ever see its own tenant's rows. [RFC 0024](../rfcs/0024-repositories.md) changes that: a subscriber will be able to read a repository's rows, inside the requests that ask to ([ADR 0118](0118-repository-tenants-subscriptions-and-a-gated-read.md)). A foreign-key check ignores RLS, so from then on a single lookup that relied on RLS alone would be enough to store a reference from one tenant into another. RFC 0024 promises that can never happen; the amendment's A2 makes this ADR its prerequisite.

## Decision

**Every foreign key between two tenant tables includes `tenant_id`.** `FOREIGN KEY (prototype_id, tenant_id) REFERENCES entity (id, tenant_id)`, and the same for every other one. Both ends must then share a tenant, or the write fails, whatever the application code does.

- **The referenced tables** gain a `UNIQUE (id, tenant_id)` for a composite key to point at: `entity`, `stat_group`, `stat_definition`, `information`, `payload`, `being` and `character` (on `entity_id`), `campaign`, `player`, and `computed_stat` (on `entity_id, stat_definition_id`).
- **The referencing keys** are every foreign key whose two tables both carry `tenant_id` — about forty, listed in the migration. Keys to `tenant`, `app_user`, and `profile_picture` are untouched: those tables aren't tenant data.
- **`ON DELETE` behaviour is unchanged.** The one `SET NULL` among them, `character.owner_player_id → player`, becomes `ON DELETE SET NULL (owner_player_id)`, so that deleting a player never tries to null `tenant_id` as well. That column-list form needs PostgreSQL 15, which CI (17) and Neon both run.
- **The models say the same.** Each model declares its composite key in `__table_args__`. Relationships name their own id column in `foreign_keys=`, so the ORM joins exactly as before and no two relationships fight over `tenant_id` ([ADR 0018](0018-sqlalchemy-modeling-conventions.md)).
- **Existing rows are checked.** The migration adds each key and validates it. If some row already points across tenants, the migration fails and names the constraint, rather than carrying a bad row forward.

## Consequences

- A cross-tenant reference can't be stored, even by a buggy route or a policy that shows more than it should.
- The routers' explicit `tenant_id` filters stay. They are what turn a wrong id into a clean 404 instead of a constraint error.
- Each referenced table carries one more unique index. They're small, and each duplicates a primary key plus one column.
- Any new table that references tenant data follows the same rule. [RFC 0026](../rfcs/0026-world-model-axes-and-address.md) and [RFC 0028](../rfcs/0028-time-causality-and-calendars.md) already draft their tables that way.
