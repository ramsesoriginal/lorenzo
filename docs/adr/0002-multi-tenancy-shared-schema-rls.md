# 0002 - Multi-tenancy: shared schema + PostgreSQL row-level security

Status: accepted, refined by [ADR 0010](0010-user-tenant-membership-model.md)

## Context

Lorenzo is multi-tenant from day one: many independent GMs/campaigns/authors will share the same running API and database. Getting tenant isolation wrong is a data breach, not a bug. Options considered: database-per-tenant, schema-per-tenant, shared schema with application-level filtering only, shared schema with RLS.

Database- and schema-per-tenant don't fit here: tenants are numerous and small (a single GM's campaign), and cross-tenant features (shared "repositories" a game can draw from — see the domain overview) need to query across tenant boundaries deliberately, which is far harder across separate databases/schemas.

## Decision

Shared schema. Every tenant-scoped table will get a `tenant_id` column and a PostgreSQL row-level security policy that filters on `current_setting('app.tenant_id')`. The backend API's middleware will resolve the tenant from the request's currently-active tenant selection (validated against the user's memberships — see [ADR 0010](0010-user-tenant-membership-model.md), since a user can belong to more than one tenant) and run the equivalent of `SET LOCAL app.tenant_id` at the start of every request's transaction.

Application-level filtering (a scoped query helper) will still be required — RLS is meant as the safety net that makes a missed filter merely redundant instead of catastrophic, not a replacement for filtering deliberately.

## Consequences

- Every migration that adds a tenant-scoped table must add its RLS policy in the same migration — this needs to be enforced by review, and ideally by a test that proves cross-tenant reads fail even when application-level filtering is deliberately bypassed, once there's a backend to test.
- Cross-tenant "repository" sharing will need an explicit, audited exception path (e.g. a security-definer function, or a policy that also allows rows flagged as shared) — not designed yet.
- Background jobs and any raw/admin DB access will also need to set the tenant context, or scope explicitly — RLS doesn't help code that queries as a superuser/bypass-RLS role without setting the session variable.

Nothing here is implemented yet — it's recorded so the decision doesn't need re-litigating once the backend API is actually scoped.
