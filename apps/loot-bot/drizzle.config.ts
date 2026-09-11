import { defineConfig } from "drizzle-kit";
import { loadConfig } from "./src/config.js";

/**
 * drizzle-kit's own config - used by `drizzle-kit generate` (mise task
 * `db-generate`) to diff src/db-schema.ts against apps/loot-bot/migrations's
 * history and write new migration files, and by `drizzle-kit`'s own
 * push/introspect/studio commands if this project ever uses them.
 *
 * `dbCredentials` uses the *privileged* bootstrap role
 * (LOOT_BOT_MIGRATIONS_DATABASE_URL), matching migrate.ts's own connection
 * choice (ADR 0029) - `generate` itself never actually opens a connection
 * (it only diffs local files against apps/loot-bot/migrations/meta), but
 * DDL-issuing commands do, and DDL needs the privileged role regardless.
 *
 * loadConfig() rather than raw `process.env`, for consistency with the
 * rest of this app - safe here specifically because drizzle-kit's own CLI
 * loads `.env` itself (it bundles `dotenv/config`, confirmed by reading
 * its bin.cjs) before this file is evaluated, the same way
 * `tsx --env-file=.env` does for every other entrypoint here.
 *
 * `schemaFilter` is the actual isolation boundary ADR 0029 relies on:
 * scoped to `loot_bot` only, so drizzle-kit is structurally incapable of
 * ever seeing or diffing apps/api's own tables (all under `public`), even
 * by accident.
 */
export default defineConfig({
  dialect: "postgresql",
  schema: "./src/db-schema.ts",
  out: "./migrations",
  dbCredentials: {
    url: loadConfig().migrationsDatabaseUrl,
  },
  schemaFilter: ["loot_bot"],
});
