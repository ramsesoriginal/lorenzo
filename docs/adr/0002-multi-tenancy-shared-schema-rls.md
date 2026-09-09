# 0002 - Multi-tenancy: shared schema + PostgreSQL row-level security

Status: accepted, refined by [ADR 0010](0010-user-tenant-membership-model.md) and [ADR 0021](0021-restricted-app-role-for-rls-enforcement.md)

## Context

Lorenzo is multi-tenant from day one: many independent GMs/campaigns/authors will share the same running API and database. Getting tenant isolation wrong is a data breach, not a bug. Options considered: database-per-tenant, schema-per-tenant, shared schema with application-level filtering only, shared schema with RLS.

Database- and schema-per-tenant don't fit here: tenants are numerous and small (a single GM's campaign), and cross-tenant features (shared "repositories" a game can draw from — see the domain overview) need to query across tenant boundaries deliberately, which is far harder across separate databases/schemas.

## Decision

Shared schema. Every tenant-scoped table will get a `tenant_id` column and a PostgreSQL row-level security policy that filters on `current_setting('app.tenant_id')`. The backend API's middleware will resolve the tenant from the request's currently-active tenant selection (validated against the user's memberships — see [ADR 0010](0010-user-tenant-membership-model.md), since a user can belong to more than one tenant) and run the equivalent of `SET LOCAL app.tenant_id` at the start of every request's transaction.

Application-level filtering (a scoped query helper) will still be required — RLS is meant as the safety net that makes a missed filter merely redundant instead of catastrophic, not a replacement for filtering deliberately.

## Consequences

- Every migration that adds a tenant-scoped table must add its RLS policy in the same migration — enforced by review. Per-table RLS-isolation tests exist too now (e.g. `test_rls_isolates_tenants_for_a_non_superuser_role` in `test_entity.py`, and the same pattern in `test_containment.py`/`test_entity_prototype.py`/`test_information.py`/`test_stats.py`/`test_v_item.py` — see [ADR 0021](0021-restricted-app-role-for-rls-enforcement.md)), proving cross-tenant reads fail even when application-level filtering is bypassed, through the app's real restricted connection.
- Cross-tenant "repository" sharing will need an explicit, audited exception path (e.g. a security-definer function, or a policy that also allows rows flagged as shared) — not designed yet.
- Background jobs and any raw/admin DB access will also need to set the tenant context, or scope explicitly — RLS doesn't help code that queries as a superuser/bypass-RLS role without setting the session variable.
- **Confirmed real, not hypothetical** (found building [ADR 0012](0012-entity-table.md)'s `entity` table): the `lorenzo` Postgres role used everywhere so far — migrations and the app's own runtime connection alike, locally and in CI — was an actual database superuser, created that way by the official Postgres image's `POSTGRES_USER` bootstrap. Superuser status bypasses RLS unconditionally; empirically confirmed that neither `ENABLE` nor `FORCE ROW LEVEL SECURITY` restricts it. **Fixed by [ADR 0021](0021-restricted-app-role-for-rls-enforcement.md)**: the app now connects as a genuinely restricted, non-superuser, non-`BYPASSRLS` role (`lorenzo_app`) instead, rotated into production too, not just CI/local dev — every RLS policy written so far now actually enforces.

This decision itself long predates any of it existing, recorded so the shared-schema-plus-RLS choice wouldn't need re-litigating once the backend API was actually scoped. That's since happened: every tenant-scoped table added has its `tenant_id` column and RLS policy, and the restricted-role gap above is closed.
