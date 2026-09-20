import {
  customType,
  index,
  integer,
  pgSchema,
  primaryKey,
  smallint,
  text,
  timestamp,
  uuid,
} from "drizzle-orm/pg-core";

/**
 * This bot's own schema inside the shared `lorenzo` database - a dedicated
 * role/schema, not a second database, per ADR 0050 ("Data isolation: own
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
 * One Discord user <-> one Authgear identity link (ADR 0050's "Account
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
  // can't silently attach to two Discord users (ADR 0050).
  authgearSubjectId: text("authgear_subject_id").notNull().unique(),

  refreshTokenEncrypted: bytea("refresh_token_encrypted").notNull(),
  accessTokenEncrypted: bytea("access_token_encrypted"),
  accessTokenExpiresAt: timestamp("access_token_expires_at", { withTimezone: true }),

  // Enables future key rotation (ADR 0050) at zero migration cost - the
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

/**
 * A Discord user's "current character" and "current default container" -
 * what every command that takes an implicit character/container target
 * (loot-drop take, `/award`, `/move`) falls back to when nothing explicit
 * is given. Bot-local state, not an `apps/api` concept - a player can have
 * many controlled characters (`GET /me`'s `players[].characters[]`) and
 * apps/api has no notion of "which one is active right now."
 *
 * Scoped per Discord channel (ADR 0068) - primary key
 * `(discordUserId, discordChannelId)` - a player active in more than one
 * channel (e.g. a "downtime" channel vs. the main table channel) can have a
 * different current character/container in each. `discordChannelId = ""`
 * is a reserved sentinel for the "global default" row: `/link`'s own
 * auto-set-on-single-character behavior writes there (an OAuth callback has
 * no Discord channel to scope to at all), and `getPreference` falls back to
 * it whenever no channel-specific row exists yet.
 *
 * No FK to `linked_account.discord_user_id`: this row can outlive an
 * unlink/relink (the preference itself - "I usually play Frodo" - isn't
 * tied to which Authgear identity happens to be linked at the moment),
 * and `character_entity_id`/`container_entity_id` are apps/api entity ids,
 * meaningless to validate against this bot's own schema anyway.
 */
export const playerPreference = lootBotSchema.table(
  "player_preference",
  {
    discordUserId: text("discord_user_id").notNull(),
    discordChannelId: text("discord_channel_id").notNull(),
    currentCharacterEntityId: text("current_character_entity_id"),
    currentContainerEntityId: text("current_container_entity_id"),
    updatedAt: timestamp("updated_at", { withTimezone: true }).notNull().defaultNow(),
  },
  (table) => [primaryKey({ columns: [table.discordUserId, table.discordChannelId] })],
);

export type PlayerPreference = typeof playerPreference.$inferSelect;
export type NewPlayerPreferenceRow = typeof playerPreference.$inferInsert;

/** The reserved `discordChannelId` for a "global default" preference row -
 * see {@link playerPreference}'s own docstring. */
export const GLOBAL_PREFERENCE_CHANNEL_ID = "";

/**
 * A GM's "drop" of a pre-made container's contents into a Discord channel
 * (ADR 0052) - one row per `/drop`, tracking the message it lives on
 * (needed to find and edit it later, as items get taken/claimed/applied)
 * and whether claims have been applied yet. `status` is a plain `text`
 * column with a TypeScript-level union (`LootDropStatus`), not a Postgres
 * enum or CHECK constraint - matches this schema's existing minimalism
 * (`linked_account` has none either), and the only two writers of this
 * column (`insertLootDrop`, `markLootDropApplied` in db.ts) already fully
 * control which value goes in.
 */
export const lootDrop = lootBotSchema.table("loot_drop", {
  id: uuid("id").primaryKey().defaultRandom(),
  containerEntityId: text("container_entity_id").notNull(),
  discordChannelId: text("discord_channel_id").notNull(),
  // Set once the message is actually posted - the row is inserted first
  // (its generated id gets baked into the message's own component
  // customIds), so this starts null.
  discordMessageId: text("discord_message_id"),
  createdByDiscordUserId: text("created_by_discord_user_id").notNull(),
  status: text("status").notNull().default("open"),
  createdAt: timestamp("created_at", { withTimezone: true }).notNull().defaultNow(),
});

export type LootDropStatus = "open" | "applied";
export type LootDrop = typeof lootDrop.$inferSelect;
export type NewLootDropRow = typeof lootDrop.$inferInsert;

/**
 * One player's outstanding claim on one item within one drop - bot-local
 * bookkeeping only, never itself an `apps/api` call (ADR 0052: claiming
 * doesn't reserve anything). `characterEntityId` is resolved once, from
 * the claimant's `/set-current` preference, at claim time - not re-
 * resolved when claims are later applied, so a claim always targets the
 * character the claimant meant at the moment they made it.
 *
 * Primary key `(lootDropId, itemEntityId, discordUserId)`: one active
 * claim per user per item: claiming again with a different quantity
 * updates this same row (an upsert) rather than stacking a second one;
 * unclaiming deletes it.
 *
 * `claimType` (ADR 0068) is a need/greed tier, plain `text` with a
 * TypeScript-level union (`ClaimType`) - same not-a-Postgres-enum idiom
 * `loot_drop.status` already uses. Defaults `"greed"` so any row inserted
 * before this column existed reads the same as an explicit greed claim,
 * not a silently-more-privileged need claim.
 */
export const lootClaim = lootBotSchema.table(
  "loot_claim",
  {
    lootDropId: uuid("loot_drop_id")
      .notNull()
      .references(() => lootDrop.id, { onDelete: "cascade" }),
    itemEntityId: text("item_entity_id").notNull(),
    discordUserId: text("discord_user_id").notNull(),
    characterEntityId: text("character_entity_id").notNull(),
    // null means "whatever's left when this claim gets applied" - not
    // "the current amount right now" (claims don't reserve anything).
    quantity: integer("quantity"),
    claimType: text("claim_type").notNull().default("greed"),
    createdAt: timestamp("created_at", { withTimezone: true }).notNull().defaultNow(),
  },
  (table) => [primaryKey({ columns: [table.lootDropId, table.itemEntityId, table.discordUserId] })],
);

export type ClaimType = "need" | "greed";
export type LootClaim = typeof lootClaim.$inferSelect;
export type NewLootClaimRow = typeof lootClaim.$inferInsert;

/**
 * The caller's own most recent undoable action (ADR 0068) - one row per
 * Discord user, overwritten by each new undoable write, not a history/stack.
 * `payload` is a plain JSON-encoded `text` column (matching this schema's
 * existing minimalism - no `jsonb` used anywhere else here either); its
 * shape depends on `actionType` and is interpreted only by `/undo`'s own
 * dispatch. `/confiscate` never writes here - a destroyed instance's id is
 * gone, so there is no real inverse to record.
 */
export const pendingUndo = lootBotSchema.table("pending_undo", {
  discordUserId: text("discord_user_id").primaryKey(),
  actionType: text("action_type").notNull(),
  payload: text("payload").notNull(),
  createdAt: timestamp("created_at", { withTimezone: true }).notNull().defaultNow(),
});

export type PendingUndo = typeof pendingUndo.$inferSelect;
export type NewPendingUndoRow = typeof pendingUndo.$inferInsert;

/**
 * What the bot itself saw happen to a character's belongings (ADR 0096) -
 * the source `/changes` reads. Bot-recorded only: anything done through
 * `apps/inventory-web`, `apps/account-hub`, or the API directly never
 * appears here, which `/changes` says plainly (RFC 0022 is the API-side
 * feed that would make it complete).
 *
 * One row per *affected character*, keyed by the character's entity id
 * rather than a Discord user: the bot has no reverse lookup from a character
 * to whoever plays it, but a player can list the characters they control, so
 * "events for my characters" is answerable and "events for that Discord
 * user" wouldn't be. A transfer between two characters writes two rows that
 * share an `eventId`, so a player who controls both sides sees it once.
 *
 * `summary` is rendered *when recorded*, from names the acting user was
 * allowed to read then - the viewer may not be allowed to look up the other
 * character's name later. It names characters rather than saying "you", so
 * it reads correctly for a player with several characters. It never names a
 * GM who acted: what happened to your stuff is shown, not who decided it.
 */
export const characterEvent = lootBotSchema.table(
  "character_event",
  {
    id: uuid("id").primaryKey().defaultRandom(),
    eventId: uuid("event_id").notNull(),
    characterEntityId: text("character_entity_id").notNull(),
    kind: text("kind").notNull(),
    summary: text("summary").notNull(),
    createdAt: timestamp("created_at", { withTimezone: true }).notNull().defaultNow(),
  },
  (table) => [
    index("character_event_character_created_idx").on(table.characterEntityId, table.createdAt),
  ],
);

export type CharacterEvent = typeof characterEvent.$inferSelect;

/** When a Discord user last ran `/changes` - what "since you last looked"
 * means (ADR 0096). One row per user, overwritten each time. */
export const changesSeen = lootBotSchema.table("changes_seen", {
  discordUserId: text("discord_user_id").primaryKey(),
  seenAt: timestamp("seen_at", { withTimezone: true }).notNull().defaultNow(),
});
