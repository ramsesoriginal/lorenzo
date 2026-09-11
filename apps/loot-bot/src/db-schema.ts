import { customType, pgSchema, smallint, text, timestamp } from "drizzle-orm/pg-core";

/**
 * This bot's own schema inside the shared `lorenzo` database - a dedicated
 * role/schema, not a second database, per ADR 0029 ("Data isolation: own
 * role + schema, same Postgres instance"). `drizzle.config.ts`'s own
 * `schemaFilter: ["loot_bot"]` keeps drizzle-kit structurally incapable of
 * ever seeing or diffing apps/api's own tables (which live in `public`).
 */
export const lootBotSchema = pgSchema("loot_bot");

/**
 * Postgres `bytea` - drizzle-orm's pg-core has built-in helpers for every
 * other column type this table needs (text/smallint/timestamptz), but not
 * for `bytea` (only MySQL/SQLite get binary-column helpers upstream as of
 * drizzle-orm 0.36). `customType` is drizzle's own documented escape hatch
 * for exactly this gap. `data`/`driverData` are both `Buffer`: node-postgres
 * already decodes a `bytea` column to a `Buffer` on read and accepts one
 * directly as a query parameter on write, so no `toDriver`/`fromDriver`
 * mapping function is needed here - the driver's own default handling is
 * the identity mapping we want.
 */
const bytea = customType<{ data: Buffer; driverData: Buffer }>({
  dataType() {
    return "bytea";
  },
});

/**
 * One Discord user <-> one Authgear identity link (ADR 0029's "Account
 * linking" section). Encryption of the token columns themselves is a
 * separate workstream (src/token-provider.ts) - this table only owns the
 * storage shape (`bytea` for ciphertext) and the query functions in db.ts.
 */
export const linkedAccount = lootBotSchema.table("linked_account", {
  // A Discord snowflake, stored as its decimal-string wire representation -
  // never as `number`/`bigint` column, since snowflakes routinely exceed
  // 2^53 and would silently lose precision as a JS/Postgres `number`.
  discordUserId: text("discord_user_id").primaryKey(),

  // Mirrors apps/api's own `app_user.authgear_subject_id` UNIQUE constraint
  // (see apps/api/src/lorenzo_api/models/user.py) - one Lorenzo identity
  // can't silently attach to two Discord users (ADR 0029).
  authgearSubjectId: text("authgear_subject_id").notNull().unique(),

  refreshTokenEncrypted: bytea("refresh_token_encrypted").notNull(),
  accessTokenEncrypted: bytea("access_token_encrypted"),
  accessTokenExpiresAt: timestamp("access_token_expires_at", { withTimezone: true }),

  // Enables future key rotation (ADR 0029) at zero migration cost - the
  // column has existed, and been populated, since day one.
  keyVersion: smallint("key_version").notNull().default(1),

  lastRefreshedAt: timestamp("last_refreshed_at", { withTimezone: true }),

  createdAt: timestamp("created_at", { withTimezone: true }).notNull().defaultNow(),
  updatedAt: timestamp("updated_at", { withTimezone: true }).notNull().defaultNow(),
});

/**
 * Inferred, not hand-duplicated - stays in sync with the table definition
 * above by construction. `LinkedAccount` is what a `SELECT` returns;
 * `NewLinkedAccountRow` is what an `INSERT` accepts (columns with a
 * default, like `keyVersion`/`createdAt`/`updatedAt`, are optional there).
 */
export type LinkedAccount = typeof linkedAccount.$inferSelect;
export type NewLinkedAccountRow = typeof linkedAccount.$inferInsert;
