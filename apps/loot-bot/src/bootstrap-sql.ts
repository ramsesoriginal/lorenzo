/**
 * Builds the idempotent, hand-written SQL that bootstraps this app's own
 * restricted Postgres role and schema - the direct TS port of
 * apps/api/migrations/versions/8aced4b80842_create_restricted_lorenzo_app_role.py,
 * extended for the two things that migration didn't need (see ADR 0029,
 * "Data isolation: own role + schema, same Postgres instance"):
 *
 *  - `apps/api` granted onto the `public` schema, which already existed.
 *    This app owns its own schema (`loot_bot`) and has to create it first.
 *  - `apps/api` (SQLAlchemy/asyncpg) schema-qualifies every query itself.
 *    Drizzle/node-postgres has no equivalent per-query mechanism, so the
 *    role's own `search_path` is set here instead - a one-time, per-role
 *    server-side default, not something every query has to repeat.
 *
 * This is plain TypeScript, not a plain `.sql` file or a hand-inserted
 * drizzle-kit migration entry - see migrate.ts's own module comment for why.
 *
 * Kept dependency-free (no `pg`/`drizzle-orm` imports) and side-effect-free
 * (pure string building) on purpose: migrate.ts is the only thing that
 * executes this against a real connection, so this module is trivially
 * unit-testable without a database - see tests/bootstrap-sql.test.ts.
 */

/** Fixed by ADR 0029 - not environment-derived like the role/password are. */
export const LOOT_BOT_SCHEMA = "loot_bot";

/** Safely embeds `value` as a double-quoted Postgres identifier. */
function pgIdentifier(value: string): string {
  return `"${value.replace(/"/g, '""')}"`;
}

/** Safely embeds `value` as a single-quoted Postgres string literal. */
function pgStringLiteral(value: string): string {
  return `'${value.replace(/'/g, "''")}'`;
}

export class InvalidDatabaseUrlError extends Error {}

/**
 * The role this migration ensures exists is whatever `databaseUrl` (this
 * app's own, restricted connection string - LOOT_BOT_DATABASE_URL) names,
 * not a separate, hand-invented secret. Whoever deploys this app decides
 * the role/password by setting that env var; this just makes the role
 * real. Mirrors the Python migration's own `_app_url`/`_APP_ROLE` module
 * -level assertions, as a callable function instead (this needs to run
 * against a value read at migrate.ts's own runtime, not at module-import
 * time - loadConfig() isn't available yet this early during bootstrapping
 * in every possible caller, and keeping this function pure/testable is
 * more valuable than matching that detail of the Python original).
 */
export function parseRoleCredentials(databaseUrl: string): { role: string; password: string } {
  let url: URL;
  try {
    url = new URL(databaseUrl);
  } catch {
    throw new InvalidDatabaseUrlError("LOOT_BOT_DATABASE_URL is not a valid URL");
  }
  const role = decodeURIComponent(url.username);
  const password = decodeURIComponent(url.password);
  if (!role) {
    throw new InvalidDatabaseUrlError("LOOT_BOT_DATABASE_URL must carry a username");
  }
  if (!password) {
    throw new InvalidDatabaseUrlError("LOOT_BOT_DATABASE_URL must carry a password");
  }
  return { role, password };
}

/**
 * Returns the full bootstrap SQL, safe to send as one multi-statement
 * `pool.query()` call. Idempotent throughout, so re-running migrate.ts is
 * always safe (matches apps/api's own `alembic upgrade head` being re-run
 * in tests/CI every time):
 *
 *  - `CREATE ROLE` has no native `IF NOT EXISTS`, so it's wrapped in an
 *    explicit existence check, exactly like the Python migration - built
 *    via `format()`'s `%I`/`%L` (safe identifier/literal quoting) inside a
 *    `DO $$ ... $$` block, not hand-rolled string concatenation.
 *  - `CREATE SCHEMA IF NOT EXISTS` has native support.
 *  - Every `GRANT` and the final `ALTER ROLE ... SET` are naturally
 *    idempotent - re-applying the same grant/setting is a no-op, not an
 *    error.
 *
 * Deliberately grants nothing on `public`: unlike apps/api's own migration
 * (which only ever had `public` to work with), this role's whole reason to
 * exist is to never need anything outside its own schema (ADR 0029).
 */
export function buildBootstrapSql(role: string, password: string): string {
  const roleIdent = pgIdentifier(role);
  const roleLiteral = pgStringLiteral(role);
  const passwordLiteral = pgStringLiteral(password);
  const schemaIdent = pgIdentifier(LOOT_BOT_SCHEMA);

  return `
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = ${roleLiteral}) THEN
        EXECUTE format(
            'CREATE ROLE %I LOGIN PASSWORD %L '
            'NOSUPERUSER NOBYPASSRLS NOCREATEDB NOCREATEROLE NOREPLICATION',
            ${roleLiteral}, ${passwordLiteral}
        );
    END IF;
END $$;

CREATE SCHEMA IF NOT EXISTS ${schemaIdent} AUTHORIZATION ${roleIdent};

GRANT USAGE, CREATE ON SCHEMA ${schemaIdent} TO ${roleIdent};

GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA ${schemaIdent} TO ${roleIdent};

-- No "FOR ROLE ..." - defaults to the current role, which is exactly the
-- privileged role this whole script (and every future migration) runs as,
-- and therefore exactly the role that will own tables created after this.
ALTER DEFAULT PRIVILEGES IN SCHEMA ${schemaIdent}
    GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO ${roleIdent};

-- Drizzle/node-postgres-specific (the Python migration's own app never
-- needed this): so this app's runtime connection, as the now-restricted
-- role, doesn't have to schema-qualify every query it issues.
ALTER ROLE ${roleIdent} SET search_path = ${schemaIdent};
`;
}
