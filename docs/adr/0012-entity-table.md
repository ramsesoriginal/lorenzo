# 0012 - The entity table

Status: accepted

## Context

[RFC 0001](../rfcs/0001-core-domain-data-model.md) designed a full entity/component architecture. This ADR promotes only its smallest, foundational piece — the bare `entity` table — as the first real sub-slice of the "simple inventory management" vertical slice. Concrete types (`item`, `being`, `place`), prototypes/inheritance, stats, information/knowledge, and containment are deliberately not part of this decision; each gets its own sub-slice once entity itself is built and tested.

## Decision

`entity`:

- `id` — UUID primary key, server-generated (`gen_random_uuid()`, native in PostgreSQL 17 — confirmed no extension needed).
- `tenant_id` — UUID, not null, indexed. **No foreign key yet**: `tenant` doesn't exist as a real table — it's being built in parallel on the `feat/auth-users` branch. The column and its RLS policy (below) are both real now; the `REFERENCES tenant(id)` constraint is a follow-up migration once both branches integrate.
- `name` — text, not null. This is an internal/reference name, not the in-fiction, audience-gated display text RFC 0001's `information` will provide later — needed now because prototypes are referenced by name throughout RFC 0001 ("Shovel," "Physical Object"), and every entity can potentially be a prototype.
- `created_at`, `updated_at` — timestamptz, server-defaulted.

No "kind" or type-discriminator column: class-table-inheritance concrete types will reference back to `entity`, not the other way around, so `entity` doesn't need to know what subtypes exist.

RLS: `ENABLE ROW LEVEL SECURITY` and `FORCE ROW LEVEL SECURITY`, policy filtering on `tenant_id = current_setting('app.tenant_id')::uuid`, per [ADR 0002](0002-multi-tenancy-shared-schema-rls.md).

## Consequences

- A bare `entity` row is not yet meaningful on its own — it has no concrete type, so nothing can actually be created as "just an entity" in practice. That's expected; the next sub-slice (a concrete type, e.g. `item`) is what makes one useful.
- **A real gap found while building this, not a hypothetical**: RLS as configured currently protects nothing, anywhere. The `lorenzo` Postgres role — used for migrations and the app's own runtime connection alike, locally and in CI — is created as an actual database superuser by the official Postgres image's `POSTGRES_USER` bootstrap mechanism. Superuser status bypasses row-level security unconditionally in PostgreSQL; confirmed empirically that neither `ENABLE ROW LEVEL SECURITY` nor `FORCE ROW LEVEL SECURITY` restricts it. The policy on `entity` is written correctly and is tested (against a dedicated, deliberately non-superuser test role — not the app's own connection, since that connection doesn't currently exercise RLS at all), but it provides no actual protection until the app connects as a genuinely restricted role instead. Tracked as a required follow-up before this table (or any future tenant-scoped table) holds real multi-tenant data — natural overlap with the `feat/auth-users` branch, since role/credential setup is adjacent to that work.
- Every future tenant-scoped table should follow the same `tenant_id` + `FORCE ROW LEVEL SECURITY` pattern established here.
