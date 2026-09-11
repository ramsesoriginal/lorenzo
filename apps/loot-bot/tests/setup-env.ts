/**
 * Loads apps/loot-bot/.env into process.env for local test runs - mirrors
 * what `tsx --env-file=.env` already does for every other entrypoint in
 * this app (dev/migrate/register-commands). `vitest run` has no
 * equivalent built-in flag of its own. Node's own `process.loadEnvFile()`
 * (stable since Node 20.12) is used directly rather than adding a
 * `dotenv` dependency, matching this app's existing "Node 22's native
 * --env-file, no dotenv dependency needed" choice (ADR 0029).
 *
 * Only tests/db.test.ts actually needs real environment variables
 * (LOOT_BOT_DATABASE_URL / LOOT_BOT_MIGRATIONS_DATABASE_URL, to reach a
 * real Postgres) - every other test file passes its own explicit config
 * object and never reads real process.env, so loading this globally
 * doesn't change their behavior.
 *
 * Silently does nothing if `.env` doesn't exist - the expected case in
 * CI, which is expected to provide real environment variables directly
 * instead (see ADR 0029's own note that ci.yml needs
 * LOOT_BOT_DATABASE_URL/LOOT_BOT_MIGRATIONS_DATABASE_URL added), and the
 * expected case for anyone running the suite without ever having set up
 * a local Postgres.
 */
try {
  process.loadEnvFile();
} catch (error) {
  if ((error as NodeJS.ErrnoException).code !== "ENOENT") throw error;
}
