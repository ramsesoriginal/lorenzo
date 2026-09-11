import { eq } from "drizzle-orm";
import { drizzle } from "drizzle-orm/node-postgres";
import { DatabaseError, Pool } from "pg";
import { loadConfig } from "./config.js";
import { type LinkedAccount, type NewLinkedAccountRow, linkedAccount } from "./db-schema.js";

export type { LinkedAccount, NewLinkedAccountRow };

/**
 * This app's own restricted role's connection (LOOT_BOT_DATABASE_URL) - not
 * the privileged one migrate.ts uses. See ADR 0029.
 *
 * Deliberately not exported: every other module reaches this table only
 * through the functions below, never through the pool or the Drizzle
 * query builder directly.
 */
const pool = new Pool({ connectionString: loadConfig().databaseUrl });
const db = drizzle(pool, { schema: { linkedAccount } });

/** Closes the underlying connection pool - for graceful shutdown and for
 * tests, so a real-Postgres test run doesn't leave the process hanging on
 * an open connection.
 */
export async function closeDb(): Promise<void> {
  await pool.end();
}

/**
 * Thrown by {@link upsertLinkedAccount} when the incoming
 * `authgear_subject_id` already belongs to a *different* Discord user.
 * `linked_account.authgear_subject_id` is UNIQUE (mirrors `app_user`'s own
 * constraint - see apps/api/src/lorenzo_api/models/user.py) specifically so
 * this can be detected rather than silently letting one Lorenzo identity
 * attach to two Discord accounts. The caller (the account-linking
 * workstream) is expected to catch this and turn it into a Discord-facing
 * message per ADR 0029, not let a raw Postgres error surface.
 */
export class AuthgearSubjectAlreadyLinkedError extends Error {
  constructor(public readonly authgearSubjectId: string) {
    super(
      `This Lorenzo account is already linked to a different Discord user (authgear_subject_id=${authgearSubjectId})`,
    );
    this.name = "AuthgearSubjectAlreadyLinkedError";
  }
}

/**
 * Thrown by {@link updateAccessToken} when no row exists for the given
 * Discord user - that function is only ever meaningful against an account
 * that already went through {@link upsertLinkedAccount}, so zero rows
 * affected means the caller has a bug (or is racing an unlink), not
 * something to silently no-op.
 */
export class LinkedAccountNotFoundError extends Error {
  constructor(public readonly discordUserId: string) {
    super(`No linked_account row for discord_user_id=${discordUserId}`);
    this.name = "LinkedAccountNotFoundError";
  }
}

function isUniqueViolation(error: unknown, constraintNameIncludes: string): boolean {
  return (
    error instanceof DatabaseError &&
    error.code === "23505" &&
    (error.constraint?.includes(constraintNameIncludes) ?? false)
  );
}

/** Looks up a Discord user's linked Lorenzo account, if any. */
export async function getLinkedAccount(discordUserId: string): Promise<LinkedAccount | undefined> {
  const rows = await db
    .select()
    .from(linkedAccount)
    .where(eq(linkedAccount.discordUserId, discordUserId))
    .limit(1);
  return rows[0];
}

/**
 * Inserts a brand-new link, or - per ADR 0029 ("`/link` ... always
 * overwrites any existing link on completion") - completely overwrites an
 * existing one for the same Discord user. One atomic
 * `INSERT ... ON CONFLICT (discord_user_id) DO UPDATE`, not a
 * check-then-write, mirroring apps/api's own `get_current_user` upsert
 * (see `pg_insert(...).on_conflict_do_update(...)` in
 * apps/api/src/lorenzo_api/dependencies.py) - two concurrent completions of
 * the same `/link` flow would otherwise race each other.
 *
 * `created_at` is intentionally left out of the `set` clause: it should
 * only ever be populated once, by the initial `INSERT`, never touched again
 * by a later conflict-update.
 *
 * @throws AuthgearSubjectAlreadyLinkedError if `row.authgearSubjectId`
 * already belongs to a different `discord_user_id`.
 */
export async function upsertLinkedAccount(row: NewLinkedAccountRow): Promise<void> {
  try {
    await db
      .insert(linkedAccount)
      .values(row)
      .onConflictDoUpdate({
        target: linkedAccount.discordUserId,
        set: {
          authgearSubjectId: row.authgearSubjectId,
          refreshTokenEncrypted: row.refreshTokenEncrypted,
          accessTokenEncrypted: row.accessTokenEncrypted ?? null,
          accessTokenExpiresAt: row.accessTokenExpiresAt ?? null,
          keyVersion: row.keyVersion ?? 1,
          lastRefreshedAt: row.lastRefreshedAt ?? null,
          updatedAt: new Date(),
        },
      });
  } catch (error) {
    if (isUniqueViolation(error, "authgear_subject_id")) {
      throw new AuthgearSubjectAlreadyLinkedError(row.authgearSubjectId);
    }
    throw error;
  }
}

/**
 * Persists the result of a token refresh. A single atomic `UPDATE`, not
 * read-then-write. `fields.refreshTokenEncrypted` is optional *on purpose*:
 * per ADR 0029, Authgear's refresh response doesn't always include a new
 * refresh token, and the stored one must only be overwritten when a new one
 * actually arrives - so the token-provider workstream simply omits this key
 * rather than needing some separate "leave refresh token untouched" sentinel.
 *
 * @throws LinkedAccountNotFoundError if `discordUserId` has no linked_account row.
 */
export async function updateAccessToken(
  discordUserId: string,
  fields: {
    accessTokenEncrypted: Buffer;
    accessTokenExpiresAt: Date;
    refreshTokenEncrypted?: Buffer;
    keyVersion: number;
  },
): Promise<void> {
  const result = await db
    .update(linkedAccount)
    .set({
      accessTokenEncrypted: fields.accessTokenEncrypted,
      accessTokenExpiresAt: fields.accessTokenExpiresAt,
      keyVersion: fields.keyVersion,
      lastRefreshedAt: new Date(),
      updatedAt: new Date(),
      ...(fields.refreshTokenEncrypted !== undefined
        ? { refreshTokenEncrypted: fields.refreshTokenEncrypted }
        : {}),
    })
    .where(eq(linkedAccount.discordUserId, discordUserId));

  if (result.rowCount === 0) {
    throw new LinkedAccountNotFoundError(discordUserId);
  }
}

/**
 * Deletes a dead link - called when a refresh comes back `invalid_grant`
 * (ADR 0029: "`invalid_grant` deletes the row and surfaces 'run `/link`
 * again'"). Idempotent by design (a plain `DELETE ... WHERE`, not asserting
 * a row existed) - safe to call again if a caller retries after a partial
 * failure.
 */
export async function deleteLinkedAccount(discordUserId: string): Promise<void> {
  await db.delete(linkedAccount).where(eq(linkedAccount.discordUserId, discordUserId));
}
