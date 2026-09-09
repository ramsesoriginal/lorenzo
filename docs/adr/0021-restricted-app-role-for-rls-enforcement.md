# 0021 - A restricted app role, so RLS actually enforces something

Status: accepted

## Context

[ADR 0002](0002-multi-tenancy-shared-schema-rls.md)/[0012](0012-entity-table.md) confirmed the app's own Postgres role is a superuser, which bypasses row-level security unconditionally - every RLS policy written so far (entity, containment, entity_prototype, stats, information/payload, item/item_instance) is correct but currently unenforced, since the only role that ever queries through it ignores RLS entirely. This was explicitly deferred to "`feat/auth-users` territory." It's not just local/CI hygiene: Neon's own docs state its default/owner role is a member of `neon_superuser`, which Neon grants `BYPASSRLS` - the same bypass, live in production, not just dev. Building Membership next (this branch's actual reason for existing) is the natural forcing function to fix this first: it's the first table an isolation bug against would be genuinely embarrassing, and this fix has zero dependency on Membership existing - it's fully testable today against tables that already do.

## Decision

A new, restricted, `LOGIN`-capable role, created by migration: `lorenzo_app` - `NOSUPERUSER NOBYPASSRLS NOCREATEDB NOCREATEROLE NOREPLICATION`. Granted `SELECT, INSERT, UPDATE, DELETE` on every existing table (views included - `security_invoker` views need their underlying tables grantable regardless, already confirmed for `v_item`/`v_item_instance` in [ADR 0019](0019-item-and-v-item.md)), plus `ALTER DEFAULT PRIVILEGES ... GRANT ...` so every future migration's new tables are covered automatically - no per-migration grant to remember, no exceptions to audit for.

This needs two distinct connection strings, not one: `Settings.database_url` (what the running app/tests connect as - now the restricted role) and a new `Settings.migrations_database_url` (what Alembic connects as - stays privileged, since creating tables/roles/policies needs it). The role-creation migration itself reads the *target* username/password to create from `database_url` (via `sqlalchemy.engine.make_url`), so no separate "app role password" secret needs inventing - whatever `DATABASE_URL` the deployer configures for the app becomes exactly the role the migration ensures exists.

Three environments need both values: local dev (`.env.example` - `docker-compose.yml`'s Postgres container itself is unchanged, it only ever bootstraps the one privileged role via `POSTGRES_USER`; `lorenzo_app` is created by the migration, not compose), CI (`ci.yml`'s `test` job and `deploy-api.yml`'s `verify` job, both currently set a single `DATABASE_URL`), and production (`deploy-api.yml`'s `deploy` job currently reuses one `secrets.DATABASE_URL` both to run migrations against Neon *and* as the deployed Cloud Run service's own env var - these need to split into `MIGRATIONS_DATABASE_URL` (the existing privileged Neon connection, renamed) and a `DATABASE_URL` secret rotated to a new restricted Neon role).

**Rotating the actual production secret is a deliberate, separate, human-confirmed step** - not something to fold silently into a commit. This ADR and its migration/config/CI changes make the fix real and testable everywhere except the live secret value itself.

The six existing ad-hoc RLS tests (`test_entity.py`, `test_containment.py`, `test_entity_prototype.py`, `test_information.py`, `test_stats.py`, `test_v_item.py`) each `CREATE ROLE rls_test_role`/`SET ROLE`/`RESET ROLE` through the app's own `engine` to get a non-superuser connection to test against - the only way to do that before this ADR, since the app's real connection was itself a superuser. Now that `lorenzo_app` is a real, persistent, correctly-scoped role, that whole dance is redundant: these tests get a new shared `admin_session_factory` fixture (a second engine, built from `migrations_database_url`, for fixture setup that deliberately needs to bypass RLS across tenants) and switch their actual isolation assertions to run through the app's own (now-restricted) `engine`/`async_session_factory` directly - more faithful, since it proves the real runtime connection is safe, not a synthetic stand-in.

## Consequences

- A genuinely new assertion becomes possible and is added: a query issued through the app's real connection with `app.tenant_id` unset or wrong now actually returns nothing cross-tenant - proving enforcement, not just that a policy exists.
- No new tables, no ER diagram - this is a role/privilege change, not a domain-model addition.
- Any future migration that adds a tenant-scoped table still needs its own `CREATE POLICY` (unchanged from ADR 0002) - `ALTER DEFAULT PRIVILEGES` only covers the *grant*, not the policy itself.
- Until the production secret is actually rotated (deliberately left as a follow-up, human-confirmed step), production remains exposed exactly as documented in ADR 0002/0012 - this ADR makes the fix ready, not yet flipped live.
