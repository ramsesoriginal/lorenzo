import { and, asc, eq, inArray, lt, sql } from "drizzle-orm";
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
  type NotificationDelivery,
  type PendingUndo,
  type PlayerPreference,
  containerPrototype,
  linkedAccount,
  lootClaim,
  lootDrop,
  notificationDelivery,
  notificationEnrollment,
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
  NotificationDelivery,
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
  schema: {
    linkedAccount,
    playerPreference,
    lootDrop,
    lootClaim,
    pendingUndo,
    containerPrototype,
    notificationEnrollment,
    notificationDelivery,
  },
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
 * (ADR 0068) when no channel-specific one exists yet. Pass
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
 * ADR 0068). Only the fields actually given are touched on conflict -
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
 * source (ADR 0068), oldest first so a long-running server sees its
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
 * second one, matching the table's own primary key. `claimType` (ADR 0068)
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

/** The caller's own most recent undoable action, if any (ADR 0068) -
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
 * user by design (ADR 0068: a history/stack was explicitly not built),
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

/** The stored id of the catalog item `/container-new` makes sacks from, for
 * one tenant (ADR 0094), or `undefined` if nobody with catalog access has
 * set it up yet. */
export async function getContainerPrototypeId(tenantId: string): Promise<string | undefined> {
  const rows = await db
    .select()
    .from(containerPrototype)
    .where(eq(containerPrototype.tenantId, tenantId))
    .limit(1);
  return rows[0]?.prototypeEntityId;
}

/** Stores (or replaces) the sack prototype for a tenant. An upsert rather
 * than an insert: two people racing the very first `/container-new` may both
 * find-or-create, and the last write winning is harmless - they resolve to
 * the same "Sack" by name, or to two equivalent ones. */
export async function setContainerPrototypeId(
  tenantId: string,
  prototypeEntityId: string,
): Promise<void> {
  await db
    .insert(containerPrototype)
    .values({ tenantId, prototypeEntityId })
    .onConflictDoUpdate({
      target: containerPrototype.tenantId,
      set: { prototypeEntityId, createdAt: new Date() },
    });
}

/** Idempotent, like every other `delete*` here - called when the stored
 * prototype turns out to no longer exist, so the next run re-resolves it. */
export async function clearContainerPrototypeId(tenantId: string): Promise<void> {
  await db.delete(containerPrototype).where(eq(containerPrototype.tenantId, tenantId));
}

/** Every linked Discord user id - what the notification bridge (ADR 0095)
 * walks, since only a linked user has a stored token to read their own
 * notifications with. */
export async function listLinkedDiscordUserIds(): Promise<readonly string[]> {
  const rows = await db.select({ id: linkedAccount.discordUserId }).from(linkedAccount);
  return rows.map((row) => row.id);
}

/**
 * When this user became eligible for notification DMs, stamping *now* on
 * their first ever call (ADR 0095): the bridge only DMs notifications
 * created after this, so enabling it never floods anyone with their existing
 * inbox. The stamp is written once and never moves.
 */
export async function getOrCreateNotificationEnrollment(discordUserId: string): Promise<Date> {
  await db.insert(notificationEnrollment).values({ discordUserId }).onConflictDoNothing();
  const rows = await db
    .select()
    .from(notificationEnrollment)
    .where(eq(notificationEnrollment.discordUserId, discordUserId))
    .limit(1);
  const row = rows[0];
  if (!row) throw new Error(`notification_enrollment row missing for ${discordUserId}`);
  return row.enrolledAt;
}

/** How long a `sending` claim is honoured before another run may take it
 * over - long enough for a real send to finish, short enough that a run
 * which died mid-send doesn't strand a notification for good. */
const STALE_CLAIM_MS = 10 * 60 * 1000;

/**
 * Atomically claims one notification for delivery to one user: `true` means
 * this caller (and only this caller) should send it. One
 * `INSERT ... ON CONFLICT DO UPDATE ... WHERE`, not check-then-write, so two
 * overlapping scheduler runs (or two Cloud Run instances) can never both
 * DM the same notification. An existing row is only takeable when it is a
 * *stale* `sending` claim; `sent`/`undelivered`/`noticed` are terminal here.
 */
export async function claimNotificationDelivery(
  discordUserId: string,
  notificationId: string,
): Promise<boolean> {
  const staleBefore = new Date(Date.now() - STALE_CLAIM_MS);
  const rows = await db
    .insert(notificationDelivery)
    .values({ discordUserId, notificationId, state: "sending" })
    .onConflictDoUpdate({
      target: [notificationDelivery.discordUserId, notificationDelivery.notificationId],
      set: { claimedAt: new Date(), updatedAt: new Date() },
      setWhere: sql`${notificationDelivery.state} = 'sending' AND ${notificationDelivery.claimedAt} < ${staleBefore.toISOString()}::timestamptz`,
    })
    .returning({ id: notificationDelivery.notificationId });
  return rows.length > 0;
}

/** The DM went out. */
export async function markNotificationSent(
  discordUserId: string,
  notificationId: string,
): Promise<void> {
  await db
    .update(notificationDelivery)
    .set({ state: "sent", updatedAt: new Date() })
    .where(deliveryKey(discordUserId, notificationId));
}

/** Discord refused the DM (closed DMs). Keeps the text - and only here - so
 * the "couldn't DM you" banner can show it on the user's next command. */
export async function markNotificationUndelivered(
  discordUserId: string,
  notificationId: string,
  fields: { title: string; body: string },
): Promise<void> {
  await db
    .update(notificationDelivery)
    .set({ state: "undelivered", ...fields, updatedAt: new Date() })
    .where(deliveryKey(discordUserId, notificationId));
}

/** Gives up a claim after a *transient* send failure, so the next scheduler
 * run retries. Only ever removes a `sending` row - never a finished one. */
export async function releaseNotificationClaim(
  discordUserId: string,
  notificationId: string,
): Promise<void> {
  await db
    .delete(notificationDelivery)
    .where(
      and(deliveryKey(discordUserId, notificationId), eq(notificationDelivery.state, "sending")),
    );
}

/** The notifications Discord wouldn't let the bot DM this user, oldest
 * first - what the "couldn't DM you" banner shows. Capped, so a long
 * outage can't make the banner (or this query) unbounded. */
export async function listUndeliveredNotifications(
  discordUserId: string,
  limit = 50,
): Promise<readonly NotificationDelivery[]> {
  return db
    .select()
    .from(notificationDelivery)
    .where(
      and(
        eq(notificationDelivery.discordUserId, discordUserId),
        eq(notificationDelivery.state, "undelivered"),
      ),
    )
    .orderBy(asc(notificationDelivery.updatedAt), asc(notificationDelivery.notificationId))
    .limit(limit);
}

/** The banner showed these; they won't show again, and their text is dropped. */
export async function markNotificationsNoticed(
  discordUserId: string,
  notificationIds: readonly string[],
): Promise<void> {
  if (notificationIds.length === 0) return;
  await db
    .update(notificationDelivery)
    .set({ state: "noticed", title: null, body: null, updatedAt: new Date() })
    .where(
      and(
        eq(notificationDelivery.discordUserId, discordUserId),
        eq(notificationDelivery.state, "undelivered"),
        inArray(notificationDelivery.notificationId, [...notificationIds]),
      ),
    );
}

/** Drops finished ledger rows older than `olderThan`. Must stay comfortably
 * longer than the bridge's own age cap on what it will deliver, or a
 * still-unread old notification could be delivered a second time. */
export async function pruneNotificationDeliveries(olderThan: Date): Promise<void> {
  await db
    .delete(notificationDelivery)
    .where(
      and(
        inArray(notificationDelivery.state, ["sent", "noticed"]),
        lt(notificationDelivery.updatedAt, olderThan),
      ),
    );
}

function deliveryKey(discordUserId: string, notificationId: string) {
  return and(
    eq(notificationDelivery.discordUserId, discordUserId),
    eq(notificationDelivery.notificationId, notificationId),
  );
}
