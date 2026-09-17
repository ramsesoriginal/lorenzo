import { and, eq } from "drizzle-orm";
import { drizzle } from "drizzle-orm/node-postgres";
import { DatabaseError, Pool } from "pg";
import { loadConfig } from "./config.js";
import {
  type ClaimType,
  GLOBAL_PREFERENCE_CHANNEL_ID,
  type LinkedAccount,
  type LootClaim,
  type LootDrop,
  type NewLinkedAccountRow,
  type PendingUndo,
  type PlayerPreference,
  linkedAccount,
  lootClaim,
  lootDrop,
  pendingUndo,
  playerPreference,
} from "./db-schema.js";

export type {
  LinkedAccount,
  NewLinkedAccountRow,
  PlayerPreference,
  LootDrop,
  LootClaim,
  ClaimType,
  PendingUndo,
};
export { GLOBAL_PREFERENCE_CHANNEL_ID };

/**
 * This app's own restricted role's connection (LOOT_BOT_DATABASE_URL) - not
 * the privileged one migrate.ts uses. See ADR 0050.
 *
 * Deliberately not exported: every other module reaches this table only
 * through the functions below, never through the pool or the Drizzle
 * query builder directly.
 */
const pool = new Pool({ connectionString: loadConfig().databaseUrl });
const db = drizzle(pool, {
  schema: { linkedAccount, playerPreference, lootDrop, lootClaim, pendingUndo },
});

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
 * message per ADR 0050, not let a raw Postgres error surface.
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
  // drizzle-orm wraps every driver error in its own DrizzleQueryError, with
  // the real pg DatabaseError only reachable via `.cause` - unwrap it before
  // checking, rather than assuming `error` itself is the raw driver error.
  const cause =
    error instanceof Error && error.cause instanceof DatabaseError ? error.cause : error;
  return (
    cause instanceof DatabaseError &&
    cause.code === "23505" &&
    (cause.constraint?.includes(constraintNameIncludes) ?? false)
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
 * Inserts a brand-new link, or - per ADR 0050 ("`/link` ... always
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
 * per ADR 0050, Authgear's refresh response doesn't always include a new
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
 * (ADR 0050: "`invalid_grant` deletes the row and surfaces 'run `/link`
 * again'"). Idempotent by design (a plain `DELETE ... WHERE`, not asserting
 * a row existed) - safe to call again if a caller retries after a partial
 * failure.
 */
export async function deleteLinkedAccount(discordUserId: string): Promise<void> {
  await db.delete(linkedAccount).where(eq(linkedAccount.discordUserId, discordUserId));
}

/**
 * Looks up a Discord user's "current character"/"current default
 * container" preference for one channel, if any has ever been set for it -
 * falling back to the `GLOBAL_PREFERENCE_CHANNEL_ID` "global default" row
 * (ADR 0064) when no channel-specific one exists yet. Pass
 * `GLOBAL_PREFERENCE_CHANNEL_ID` itself to look up only the global default
 * (skips the redundant second query).
 */
export async function getPreference(
  discordUserId: string,
  discordChannelId: string,
): Promise<PlayerPreference | undefined> {
  const rows = await db
    .select()
    .from(playerPreference)
    .where(
      and(
        eq(playerPreference.discordUserId, discordUserId),
        eq(playerPreference.discordChannelId, discordChannelId),
      ),
    )
    .limit(1);
  if (rows[0] || discordChannelId === GLOBAL_PREFERENCE_CHANNEL_ID) return rows[0];

  const globalRows = await db
    .select()
    .from(playerPreference)
    .where(
      and(
        eq(playerPreference.discordUserId, discordUserId),
        eq(playerPreference.discordChannelId, GLOBAL_PREFERENCE_CHANNEL_ID),
      ),
    )
    .limit(1);
  return globalRows[0];
}

/**
 * Upserts a Discord user's current-character/current-container preference
 * for one channel (or the `GLOBAL_PREFERENCE_CHANNEL_ID` global default -
 * ADR 0064). Only the fields actually given are touched on conflict -
 * `/set-current` lets a caller set either or both in one call, and setting
 * just one (e.g. switching characters) deliberately leaves the other as it
 * was rather than implicitly clearing it (explicit-only, matching this
 * codebase's general preference - see ADR 0051's "container left
 * untouched" precedent).
 */
export async function setPreference(
  discordUserId: string,
  discordChannelId: string,
  fields: { characterEntityId?: string; containerEntityId?: string },
): Promise<void> {
  await db
    .insert(playerPreference)
    .values({
      discordUserId,
      discordChannelId,
      currentCharacterEntityId: fields.characterEntityId ?? null,
      currentContainerEntityId: fields.containerEntityId ?? null,
    })
    .onConflictDoUpdate({
      target: [playerPreference.discordUserId, playerPreference.discordChannelId],
      set: {
        updatedAt: new Date(),
        ...(fields.characterEntityId !== undefined
          ? { currentCharacterEntityId: fields.characterEntityId }
          : {}),
        ...(fields.containerEntityId !== undefined
          ? { currentContainerEntityId: fields.containerEntityId }
          : {}),
      },
    });
}

/** Idempotent by design, matching {@link deleteLinkedAccount}'s own
 * shape - a plain `DELETE ... WHERE`, safe to call on a row that was
 * never set. */
export async function deletePreference(
  discordUserId: string,
  discordChannelId: string,
): Promise<void> {
  await db
    .delete(playerPreference)
    .where(
      and(
        eq(playerPreference.discordUserId, discordUserId),
        eq(playerPreference.discordChannelId, discordChannelId),
      ),
    );
}

/**
 * Starts a new loot drop (ADR 0052) - inserted *before* the Discord
 * message is posted, since the message's own select-menu/button
 * `customId`s need the generated `id` baked in. Returns the full row so
 * the caller has that id without a second round trip.
 */
export async function insertLootDrop(fields: {
  containerEntityId: string;
  discordChannelId: string;
  createdByDiscordUserId: string;
}): Promise<LootDrop> {
  const rows = await db.insert(lootDrop).values(fields).returning();
  const row = rows[0];
  if (!row) throw new Error("insertLootDrop: INSERT ... RETURNING produced no row");
  return row;
}

/** Records which message a drop ended up on, once it's actually been
 * posted - see {@link insertLootDrop}'s own note on why this is a
 * separate step rather than part of the initial insert. */
export async function setLootDropMessageId(
  dropId: string,
  discordMessageId: string,
): Promise<void> {
  await db.update(lootDrop).set({ discordMessageId }).where(eq(lootDrop.id, dropId));
}

export async function getLootDrop(dropId: string): Promise<LootDrop | undefined> {
  const rows = await db.select().from(lootDrop).where(eq(lootDrop.id, dropId)).limit(1);
  return rows[0];
}

/** Every drop still `"open"` (not yet applied) - `/pending-claims`'s own
 * source (ADR 0064), oldest first so a long-running server sees its
 * oldest-outstanding drops first. */
export async function listOpenLootDrops(): Promise<readonly LootDrop[]> {
  return db.select().from(lootDrop).where(eq(lootDrop.status, "open")).orderBy(lootDrop.createdAt);
}

/** Matches every other table in this schema having a full delete path -
 * used by this file's own tests to clean up after themselves (mirroring
 * {@link deleteLinkedAccount}/{@link deletePreference}'s identical role),
 * and exercises `loot_claim.loot_drop_id`'s `ON DELETE CASCADE`. */
export async function deleteLootDrop(dropId: string): Promise<void> {
  await db.delete(lootDrop).where(eq(lootDrop.id, dropId));
}

/** Marks a drop as resolved, once every outstanding claim has been
 * processed - `/drop`'s own handler is responsible for deleting the
 * drop's claim rows separately ({@link deleteLootClaimsForDrop}), not
 * this function, so a caller can still read them one last time (e.g. to
 * build the final summary) before they're gone. */
export async function markLootDropApplied(dropId: string): Promise<void> {
  await db.update(lootDrop).set({ status: "applied" }).where(eq(lootDrop.id, dropId));
}

/** The caller's own existing claim on this item within this drop, if
 * any - the claim-menu's own "toggle" decision (ADR 0052: picking an
 * already-claimed item unclaims it, picking anything else opens the
 * quantity modal) reads this first. */
export async function getLootClaim(
  dropId: string,
  itemEntityId: string,
  discordUserId: string,
): Promise<LootClaim | undefined> {
  const rows = await db
    .select()
    .from(lootClaim)
    .where(
      and(
        eq(lootClaim.lootDropId, dropId),
        eq(lootClaim.itemEntityId, itemEntityId),
        eq(lootClaim.discordUserId, discordUserId),
      ),
    )
    .limit(1);
  return rows[0];
}

/** Every outstanding claim on a drop, oldest first - the order
 * apply-claims (ADR 0052) processes them in, and what the drop
 * message's own claims-annotation is built from. */
export async function listLootClaims(dropId: string): Promise<readonly LootClaim[]> {
  return db
    .select()
    .from(lootClaim)
    .where(eq(lootClaim.lootDropId, dropId))
    .orderBy(lootClaim.createdAt);
}

/** Upserts one player's claim on one item - claiming again (a new
 * quantity, or re-confirming the same one) replaces the existing row for
 * that `(dropId, itemEntityId, discordUserId)` rather than stacking a
 * second one, matching the table's own primary key. `claimType` (ADR 0064)
 * is re-set on every upsert too - re-claiming can change need-vs-greed,
 * not just quantity. */
export async function upsertLootClaim(fields: {
  lootDropId: string;
  itemEntityId: string;
  discordUserId: string;
  characterEntityId: string;
  quantity: number | null;
  claimType: ClaimType;
}): Promise<void> {
  await db
    .insert(lootClaim)
    .values(fields)
    .onConflictDoUpdate({
      target: [lootClaim.lootDropId, lootClaim.itemEntityId, lootClaim.discordUserId],
      set: {
        characterEntityId: fields.characterEntityId,
        quantity: fields.quantity,
        claimType: fields.claimType,
      },
    });
}

/** Idempotent, matching every other `delete*` function in this module -
 * safe to call on a claim that doesn't exist (e.g. a double-click on
 * "unclaim"). */
export async function deleteLootClaim(
  dropId: string,
  itemEntityId: string,
  discordUserId: string,
): Promise<void> {
  await db
    .delete(lootClaim)
    .where(
      and(
        eq(lootClaim.lootDropId, dropId),
        eq(lootClaim.itemEntityId, itemEntityId),
        eq(lootClaim.discordUserId, discordUserId),
      ),
    );
}

/** Cleanup once a drop's claims have all been processed - see
 * {@link markLootDropApplied}'s own note on why this is separate. */
export async function deleteLootClaimsForDrop(dropId: string): Promise<void> {
  await db.delete(lootClaim).where(eq(lootClaim.lootDropId, dropId));
}

/** The caller's own most recent undoable action, if any (ADR 0064) -
 * `/undo`'s own read; the caller decides what "too old" means (a TTL),
 * this just returns whatever's there. */
export async function getPendingUndo(discordUserId: string): Promise<PendingUndo | undefined> {
  const rows = await db
    .select()
    .from(pendingUndo)
    .where(eq(pendingUndo.discordUserId, discordUserId))
    .limit(1);
  return rows[0];
}

/** Records (or overwrites) the caller's one undoable action - one row per
 * user by design (ADR 0064: a history/stack was explicitly not built),
 * so a second undoable write silently replaces whatever was there before. */
export async function setPendingUndo(
  discordUserId: string,
  fields: { actionType: string; payload: string },
): Promise<void> {
  await db
    .insert(pendingUndo)
    .values({ discordUserId, ...fields })
    .onConflictDoUpdate({
      target: pendingUndo.discordUserId,
      set: { ...fields, createdAt: new Date() },
    });
}

/** Idempotent, matching every other `delete*` function in this module -
 * `/undo` calls this once it's done, whether or not the undo actually
 * succeeded (a failed inverse call shouldn't leave a stale row someone
 * might retry against outdated state). */
export async function deletePendingUndo(discordUserId: string): Promise<void> {
  await db.delete(pendingUndo).where(eq(pendingUndo.discordUserId, discordUserId));
}
