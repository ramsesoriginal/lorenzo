import { fileURLToPath } from "node:url";
import { drizzle } from "drizzle-orm/node-postgres";
import { migrate } from "drizzle-orm/node-postgres/migrator";
import { Pool } from "pg";
import { buildBootstrapSql, parseRoleCredentials } from "./bootstrap-sql.js";
import { loadConfig } from "./config.js";
import { logger } from "./logger.js";

/**
 * Resolved relative to this *file's* own location, not `process.cwd()` -
 * robust regardless of where `mise run db-migrate` (or a test importing
 * this module) happens to be invoked from.
 */
const migrationsFolder = fileURLToPath(new URL("../migrations", import.meta.url));

/**
 * Applies everything this app's database needs, in the only order that can
 * work, against the *privileged* bootstrap role
 * (LOOT_BOT_MIGRATIONS_DATABASE_URL) throughout - see ADR 0029's "Data
 * isolation" section:
 *
 *  1. The hand-written bootstrap SQL (bootstrap-sql.ts) - creates the
 *     `loot_bot` role/schema and grants it what it needs. Has to run
 *     first: neither the role nor the schema exist yet the very first
 *     time this runs, and every later Drizzle migration creates objects
 *     *inside* that schema.
 *  2. Drizzle's own migrator, applying everything under
 *     apps/loot-bot/migrations (drizzle-kit-generated) - e.g. creating
 *     `linked_account`. Still needs the privileged role even after step 1:
 *     the now-existing `loot_bot` role only has DML rights (SELECT/INSERT/
 *     UPDATE/DELETE), not DDL (CREATE TABLE) - exactly mirroring why
 *     apps/api's own Alembic always runs privileged too.
 *
 * Both steps are idempotent, so re-running this whole function is always
 * safe (matches apps/api's own `alembic upgrade head` being re-run in
 * tests/CI every time) - see bootstrap-sql.ts for why step 1 is safe to
 * repeat, and Drizzle's own migrator already tracks applied migrations in
 * a `__drizzle_migrations` table and no-ops anything already applied.
 */
export async function runMigrations(): Promise<void> {
  const config = loadConfig();
  const pool = new Pool({ connectionString: config.migrationsDatabaseUrl });
  try {
    const { role, password } = parseRoleCredentials(config.databaseUrl);
    logger.info({ role }, "bootstrapping loot_bot role and schema");
    await pool.query(buildBootstrapSql(role, password));

    logger.info({ migrationsFolder }, "applying drizzle migrations");
    const db = drizzle(pool);
    await migrate(db, { migrationsFolder });

    logger.info("migrations complete");
  } finally {
    await pool.end();
  }
}

// Only auto-run when this file is the actual process entrypoint (`tsx
// --env-file=.env src/migrate.ts`, wired as `mise run db-migrate`) - not
// merely imported, e.g. by tests/db.test.ts, which calls runMigrations()
// directly itself and needs its own `await` to see a real rejection,
// rather than one silently swallowed by the .catch() below.
const isMainModule =
  process.argv[1] !== undefined && fileURLToPath(import.meta.url) === process.argv[1];

if (isMainModule) {
  runMigrations().catch((error: unknown) => {
    logger.error({ err: error }, "migration failed");
    process.exitCode = 1;
  });
}
