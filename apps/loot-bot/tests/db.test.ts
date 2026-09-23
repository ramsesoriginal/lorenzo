import { afterAll, afterEach, describe, expect, it, vi } from "vitest";

/**
 * Real-Postgres tests, no mocking the database - conceptually mirrors
 * apps/api/tests/conftest.py's own session-scoped `_migrate_database`
 * fixture: migrations run once, then every test exercises the real thing.
 *
 * Gated so this file skips cleanly (not a hard failure) wherever Postgres
 * isn't available - e.g. LOOT_BOT_DATABASE_URL/LOOT_BOT_MIGRATIONS_DATABASE_URL
 * aren't set, or nothing is actually listening. `describe.skipIf`/`it.skipIf`
 * are real, current Vitest APIs (confirmed via @vitest/runner's own type
 * declarations for the installed version, not assumed).
 *
 * This whole gate - including running migrations - has to happen through a
 * *dynamic* import, awaited before `describe.skipIf` runs, rather than a
 * static top-level `import ... from "../src/db.js"`: db.ts builds its
 * connection pool from `loadConfig()` at module-evaluation time, and
 * loadConfig() validates this app's *entire* env (Discord/Authgear
 * settings included, not just the two LOOT_BOT_* database vars) as one
 * schema. A static import would throw during Vitest's own module-collection
 * step the moment any of that is missing, turning what should be a clean
 * skip into a hard failure of the whole file - exactly what this gate
 * exists to avoid. Deferring both the migration run and the import into one
 * try/catch, evaluated once up front, collapses "env incomplete", "DB
 * unreachable", and "migration failed" into the same clean-skip outcome.
 */
let db: typeof import("../src/db.js");

async function tryPrepareDatabase(): Promise<boolean> {
  if (!process.env.LOOT_BOT_DATABASE_URL || !process.env.LOOT_BOT_MIGRATIONS_DATABASE_URL) {
    console.warn(
      "[tests/db.test.ts] skipping: LOOT_BOT_DATABASE_URL/LOOT_BOT_MIGRATIONS_DATABASE_URL not set.",
    );
    return false;
  }
  try {
    const { runMigrations } = await import("../src/migrate.js");
    await runMigrations();
    db = await import("../src/db.js");
    return true;
  } catch (error) {
    console.warn("[tests/db.test.ts] skipping: could not migrate/reach Postgres.", error);
    return false;
  }
}

const canRunDbTests = await tryPrepareDatabase();

// Closed exactly once, after every describe block below has finished - all
// three share this file's one module-level pool (db.ts's own singleton),
// so closing it per-block would tear it down after the first block and
// throw "Called end on pool more than once" on every block after that.
afterAll(async () => {
  if (canRunDbTests) await db.closeDb();
});

describe.skipIf(!canRunDbTests)("linked_account (real Postgres)", () => {
  // Distinct per-file IDs so a run of this suite can never collide with
  // anything a developer's own manual testing left behind.
  const DISCORD_ID_A = "db-test-discord-user-a";
  const DISCORD_ID_B = "db-test-discord-user-b";
  const SUBJECT_A = "authgear|db-test-subject-a";
  const SUBJECT_B = "authgear|db-test-subject-b";

  afterEach(async () => {
    // Best-effort cleanup after every test, not just at the end - keeps
    // the unique-authgear_subject_id tests from interfering with each
    // other, and keeps re-runs against a persistent dev database clean.
    await db.deleteLinkedAccount(DISCORD_ID_A);
    await db.deleteLinkedAccount(DISCORD_ID_B);
  });

  it("returns undefined for a discord user that was never linked", async () => {
    await expect(db.getLinkedAccount("never-linked-user")).resolves.toBeUndefined();
  });

  it("upserts a new link and reads it back", async () => {
    await db.upsertLinkedAccount({
      discordUserId: DISCORD_ID_A,
      authgearSubjectId: SUBJECT_A,
      refreshTokenEncrypted: Buffer.from("refresh-bytes-1"),
      keyVersion: 1,
    });

    const row = await db.getLinkedAccount(DISCORD_ID_A);
    expect(row).toBeDefined();
    expect(row?.discordUserId).toBe(DISCORD_ID_A);
    expect(row?.authgearSubjectId).toBe(SUBJECT_A);
    expect(row?.refreshTokenEncrypted).toEqual(Buffer.from("refresh-bytes-1"));
    expect(row?.keyVersion).toBe(1);
    expect(row?.accessTokenEncrypted).toBeNull();
    expect(row?.accessTokenExpiresAt).toBeNull();
    expect(row?.createdAt).toBeInstanceOf(Date);
    expect(row?.updatedAt).toBeInstanceOf(Date);
  });

  it("defaults keyVersion to 1 when the caller omits it", async () => {
    await db.upsertLinkedAccount({
      discordUserId: DISCORD_ID_A,
      authgearSubjectId: SUBJECT_A,
      refreshTokenEncrypted: Buffer.from("refresh-bytes"),
    });

    const row = await db.getLinkedAccount(DISCORD_ID_A);
    expect(row?.keyVersion).toBe(1);
  });

  it("completely overwrites an existing link on re-upsert (ADR 0050: /link always overwrites)", async () => {
    await db.upsertLinkedAccount({
      discordUserId: DISCORD_ID_A,
      authgearSubjectId: SUBJECT_A,
      refreshTokenEncrypted: Buffer.from("first-token"),
      keyVersion: 1,
    });

    await db.upsertLinkedAccount({
      discordUserId: DISCORD_ID_A,
      authgearSubjectId: SUBJECT_A,
      refreshTokenEncrypted: Buffer.from("second-token"),
      keyVersion: 1,
    });

    const row = await db.getLinkedAccount(DISCORD_ID_A);
    expect(row?.refreshTokenEncrypted).toEqual(Buffer.from("second-token"));
  });

  it("rejects linking a second discord user to an already-linked authgear subject", async () => {
    await db.upsertLinkedAccount({
      discordUserId: DISCORD_ID_A,
      authgearSubjectId: SUBJECT_A,
      refreshTokenEncrypted: Buffer.from("token-a"),
      keyVersion: 1,
    });

    const attempt = db.upsertLinkedAccount({
      discordUserId: DISCORD_ID_B,
      authgearSubjectId: SUBJECT_A, // same subject, different discord user
      refreshTokenEncrypted: Buffer.from("token-b"),
      keyVersion: 1,
    });

    await expect(attempt).rejects.toBeInstanceOf(db.AuthgearSubjectAlreadyLinkedError);
    // The second discord user must not have been linked to anything.
    await expect(db.getLinkedAccount(DISCORD_ID_B)).resolves.toBeUndefined();
  });

  it("still allows the same discord user to be re-upserted with the same subject", async () => {
    await db.upsertLinkedAccount({
      discordUserId: DISCORD_ID_A,
      authgearSubjectId: SUBJECT_A,
      refreshTokenEncrypted: Buffer.from("token-1"),
      keyVersion: 1,
    });

    await expect(
      db.upsertLinkedAccount({
        discordUserId: DISCORD_ID_A,
        authgearSubjectId: SUBJECT_A,
        refreshTokenEncrypted: Buffer.from("token-2"),
        keyVersion: 1,
      }),
    ).resolves.toBeUndefined();
  });

  it("updates the access token without touching the refresh token when the caller omits it", async () => {
    await db.upsertLinkedAccount({
      discordUserId: DISCORD_ID_A,
      authgearSubjectId: SUBJECT_A,
      refreshTokenEncrypted: Buffer.from("original-refresh"),
      keyVersion: 1,
    });

    const expiresAt = new Date(Date.now() + 3_600_000);
    await db.updateAccessToken(DISCORD_ID_A, {
      accessTokenEncrypted: Buffer.from("new-access"),
      accessTokenExpiresAt: expiresAt,
      keyVersion: 1,
    });

    const row = await db.getLinkedAccount(DISCORD_ID_A);
    expect(row?.accessTokenEncrypted).toEqual(Buffer.from("new-access"));
    expect(row?.accessTokenExpiresAt?.getTime()).toBe(expiresAt.getTime());
    expect(row?.refreshTokenEncrypted).toEqual(Buffer.from("original-refresh"));
  });

  it("overwrites the refresh token only when the caller does pass a new one", async () => {
    await db.upsertLinkedAccount({
      discordUserId: DISCORD_ID_A,
      authgearSubjectId: SUBJECT_A,
      refreshTokenEncrypted: Buffer.from("original-refresh"),
      keyVersion: 1,
    });

    await db.updateAccessToken(DISCORD_ID_A, {
      accessTokenEncrypted: Buffer.from("new-access"),
      accessTokenExpiresAt: new Date(),
      refreshTokenEncrypted: Buffer.from("rotated-refresh"),
      keyVersion: 2,
    });

    const row = await db.getLinkedAccount(DISCORD_ID_A);
    expect(row?.refreshTokenEncrypted).toEqual(Buffer.from("rotated-refresh"));
    expect(row?.keyVersion).toBe(2);
  });

  it("rejects updating the access token for a discord user that was never linked", async () => {
    await expect(
      db.updateAccessToken("never-linked-user", {
        accessTokenEncrypted: Buffer.from("x"),
        accessTokenExpiresAt: new Date(),
        keyVersion: 1,
      }),
    ).rejects.toBeInstanceOf(db.LinkedAccountNotFoundError);
  });

  it("deletes a linked account (dead-link cleanup on invalid_grant)", async () => {
    await db.upsertLinkedAccount({
      discordUserId: DISCORD_ID_A,
      authgearSubjectId: SUBJECT_A,
      refreshTokenEncrypted: Buffer.from("token"),
      keyVersion: 1,
    });

    await db.deleteLinkedAccount(DISCORD_ID_A);

    await expect(db.getLinkedAccount(DISCORD_ID_A)).resolves.toBeUndefined();
  });

  it("is idempotent when deleting an account that was never linked", async () => {
    await expect(db.deleteLinkedAccount("never-linked-user")).resolves.toBeUndefined();
  });

  it("frees an authgear subject for reuse once its old link is deleted", async () => {
    await db.upsertLinkedAccount({
      discordUserId: DISCORD_ID_A,
      authgearSubjectId: SUBJECT_B,
      refreshTokenEncrypted: Buffer.from("token-a"),
      keyVersion: 1,
    });
    await db.deleteLinkedAccount(DISCORD_ID_A);

    // Now a *different* discord user can claim that same subject.
    await expect(
      db.upsertLinkedAccount({
        discordUserId: DISCORD_ID_B,
        authgearSubjectId: SUBJECT_B,
        refreshTokenEncrypted: Buffer.from("token-b"),
        keyVersion: 1,
      }),
    ).resolves.toBeUndefined();
  });
});

describe.skipIf(!canRunDbTests)("player_preference (real Postgres)", () => {
  const DISCORD_ID = "db-test-preference-user";
  const CHANNEL_ID = "db-test-channel";

  afterEach(async () => {
    await db.deletePreference(DISCORD_ID, CHANNEL_ID);
    await db.deletePreference(DISCORD_ID, db.GLOBAL_PREFERENCE_CHANNEL_ID);
  });

  it("returns undefined for a discord user with no preference set", async () => {
    await expect(db.getPreference(DISCORD_ID, CHANNEL_ID)).resolves.toBeUndefined();
  });

  it("sets a character on first use, leaving container unset", async () => {
    await db.setPreference(DISCORD_ID, CHANNEL_ID, { characterEntityId: "char-1" });

    const row = await db.getPreference(DISCORD_ID, CHANNEL_ID);
    expect(row?.currentCharacterEntityId).toBe("char-1");
    expect(row?.currentContainerEntityId).toBeNull();
  });

  it("sets both character and container in one call", async () => {
    await db.setPreference(DISCORD_ID, CHANNEL_ID, {
      characterEntityId: "char-1",
      containerEntityId: "container-1",
    });

    const row = await db.getPreference(DISCORD_ID, CHANNEL_ID);
    expect(row?.currentCharacterEntityId).toBe("char-1");
    expect(row?.currentContainerEntityId).toBe("container-1");
  });

  it("updating just the container leaves the existing character untouched", async () => {
    await db.setPreference(DISCORD_ID, CHANNEL_ID, {
      characterEntityId: "char-1",
      containerEntityId: "container-1",
    });

    await db.setPreference(DISCORD_ID, CHANNEL_ID, { containerEntityId: "container-2" });

    const row = await db.getPreference(DISCORD_ID, CHANNEL_ID);
    expect(row?.currentCharacterEntityId).toBe("char-1");
    expect(row?.currentContainerEntityId).toBe("container-2");
  });

  it("updating just the character leaves the existing container untouched", async () => {
    await db.setPreference(DISCORD_ID, CHANNEL_ID, {
      characterEntityId: "char-1",
      containerEntityId: "container-1",
    });

    await db.setPreference(DISCORD_ID, CHANNEL_ID, { characterEntityId: "char-2" });

    const row = await db.getPreference(DISCORD_ID, CHANNEL_ID);
    expect(row?.currentCharacterEntityId).toBe("char-2");
    expect(row?.currentContainerEntityId).toBe("container-1");
  });

  it("is idempotent when deleting a preference that was never set", async () => {
    await expect(db.deletePreference("never-set-user", CHANNEL_ID)).resolves.toBeUndefined();
  });

  it("falls back to the global-default row when no channel-specific one exists", async () => {
    await db.setPreference(DISCORD_ID, db.GLOBAL_PREFERENCE_CHANNEL_ID, {
      characterEntityId: "char-global",
    });

    const row = await db.getPreference(DISCORD_ID, CHANNEL_ID);
    expect(row?.currentCharacterEntityId).toBe("char-global");

    await db.deletePreference(DISCORD_ID, db.GLOBAL_PREFERENCE_CHANNEL_ID);
  });

  it("prefers a channel-specific row over the global default once one exists", async () => {
    await db.setPreference(DISCORD_ID, db.GLOBAL_PREFERENCE_CHANNEL_ID, {
      characterEntityId: "char-global",
    });
    await db.setPreference(DISCORD_ID, CHANNEL_ID, { characterEntityId: "char-channel" });

    const row = await db.getPreference(DISCORD_ID, CHANNEL_ID);
    expect(row?.currentCharacterEntityId).toBe("char-channel");

    await db.deletePreference(DISCORD_ID, db.GLOBAL_PREFERENCE_CHANNEL_ID);
  });

  // ADR 0088: the fallback to the global default is per field, not per
  // row - `/set-current container:...` alone creates a channel row with no
  // character, which used to hide the user's server-wide (last-used) one.
  it("falls back to the global character when the channel row only sets a container", async () => {
    await db.setPreference(DISCORD_ID, db.GLOBAL_PREFERENCE_CHANNEL_ID, {
      characterEntityId: "char-global",
    });
    await db.setPreference(DISCORD_ID, CHANNEL_ID, { containerEntityId: "container-channel" });

    const row = await db.getPreference(DISCORD_ID, CHANNEL_ID);
    expect(row?.currentCharacterEntityId).toBe("char-global");
    expect(row?.currentContainerEntityId).toBe("container-channel");
  });

  it("falls back to the global container when the channel row only sets a character", async () => {
    await db.setPreference(DISCORD_ID, db.GLOBAL_PREFERENCE_CHANNEL_ID, {
      characterEntityId: "char-global",
      containerEntityId: "container-global",
    });
    await db.setPreference(DISCORD_ID, CHANNEL_ID, { characterEntityId: "char-channel" });

    const row = await db.getPreference(DISCORD_ID, CHANNEL_ID);
    expect(row?.currentCharacterEntityId).toBe("char-channel");
    expect(row?.currentContainerEntityId).toBe("container-global");
  });

  it("leaves a field unset when neither the channel nor the global row sets it", async () => {
    await db.setPreference(DISCORD_ID, db.GLOBAL_PREFERENCE_CHANNEL_ID, {
      characterEntityId: "char-global",
    });
    await db.setPreference(DISCORD_ID, CHANNEL_ID, { characterEntityId: "char-channel" });

    const row = await db.getPreference(DISCORD_ID, CHANNEL_ID);
    expect(row?.currentContainerEntityId).toBeNull();
  });

  it("returns the channel's own row identity when merging, not the global one", async () => {
    await db.setPreference(DISCORD_ID, db.GLOBAL_PREFERENCE_CHANNEL_ID, {
      characterEntityId: "char-global",
    });
    await db.setPreference(DISCORD_ID, CHANNEL_ID, { containerEntityId: "container-channel" });

    const row = await db.getPreference(DISCORD_ID, CHANNEL_ID);
    expect(row?.discordChannelId).toBe(CHANNEL_ID);
  });

  it("looking up the global default itself is unaffected by any channel row", async () => {
    await db.setPreference(DISCORD_ID, db.GLOBAL_PREFERENCE_CHANNEL_ID, {
      characterEntityId: "char-global",
    });
    await db.setPreference(DISCORD_ID, CHANNEL_ID, { characterEntityId: "char-channel" });

    const row = await db.getPreference(DISCORD_ID, db.GLOBAL_PREFERENCE_CHANNEL_ID);
    expect(row?.currentCharacterEntityId).toBe("char-global");
    expect(row?.discordChannelId).toBe(db.GLOBAL_PREFERENCE_CHANNEL_ID);
  });
});

describe.skipIf(!canRunDbTests)("loot_drop / loot_claim (real Postgres)", () => {
  const DISCORD_ID_A = "db-test-claimant-a";
  const DISCORD_ID_B = "db-test-claimant-b";

  let dropId: string;

  afterEach(async () => {
    // Deleting the drop cascades to its claims too (loot_claim's own
    // ON DELETE CASCADE) - one call cleans up everything a test created.
    if (dropId) await db.deleteLootDrop(dropId);
  });

  async function makeDrop(): Promise<string> {
    const row = await db.insertLootDrop({
      containerEntityId: "container-1",
      discordChannelId: "channel-1",
      createdByDiscordUserId: "gm-1",
    });
    dropId = row.id;
    return row.id;
  }

  it("starts open, with no message id yet", async () => {
    const id = await makeDrop();

    const row = await db.getLootDrop(id);
    expect(row?.status).toBe("open");
    expect(row?.discordMessageId).toBeNull();
    expect(row?.containerEntityId).toBe("container-1");
  });

  it("records the message id once the drop's message is posted", async () => {
    const id = await makeDrop();

    await db.setLootDropMessageId(id, "message-1");

    const row = await db.getLootDrop(id);
    expect(row?.discordMessageId).toBe("message-1");
  });

  it("marks a drop applied", async () => {
    const id = await makeDrop();

    await db.markLootDropApplied(id);

    const row = await db.getLootDrop(id);
    expect(row?.status).toBe("applied");
  });

  it("returns undefined for a drop that doesn't exist", async () => {
    await expect(db.getLootDrop("00000000-0000-0000-0000-000000000000")).resolves.toBeUndefined();
  });

  it("has no claim for a user who hasn't claimed anything", async () => {
    const id = await makeDrop();

    await expect(db.getLootClaim(id, "item-1", DISCORD_ID_A)).resolves.toBeUndefined();
  });

  it("upserts a claim and reads it back", async () => {
    const id = await makeDrop();

    await db.upsertLootClaim({
      lootDropId: id,
      itemEntityId: "item-1",
      discordUserId: DISCORD_ID_A,
      characterEntityId: "char-1",
      quantity: 3,
      claimType: "greed",
    });

    const row = await db.getLootClaim(id, "item-1", DISCORD_ID_A);
    expect(row?.characterEntityId).toBe("char-1");
    expect(row?.quantity).toBe(3);
  });

  it("re-claiming the same item replaces the existing claim, not a second row", async () => {
    const id = await makeDrop();

    await db.upsertLootClaim({
      lootDropId: id,
      itemEntityId: "item-1",
      discordUserId: DISCORD_ID_A,
      characterEntityId: "char-1",
      quantity: 3,
      claimType: "greed",
    });
    await db.upsertLootClaim({
      lootDropId: id,
      itemEntityId: "item-1",
      discordUserId: DISCORD_ID_A,
      characterEntityId: "char-1",
      quantity: 5,
      claimType: "greed",
    });

    const claims = await db.listLootClaims(id);
    expect(claims).toHaveLength(1);
    expect(claims[0]?.quantity).toBe(5);
  });

  it("lists claims oldest first, across different claimants", async () => {
    const id = await makeDrop();

    await db.upsertLootClaim({
      lootDropId: id,
      itemEntityId: "item-1",
      discordUserId: DISCORD_ID_A,
      characterEntityId: "char-1",
      quantity: null,
      claimType: "greed",
    });
    await db.upsertLootClaim({
      lootDropId: id,
      itemEntityId: "item-1",
      discordUserId: DISCORD_ID_B,
      characterEntityId: "char-2",
      quantity: null,
      claimType: "greed",
    });

    const claims = await db.listLootClaims(id);
    expect(claims.map((c) => c.discordUserId)).toEqual([DISCORD_ID_A, DISCORD_ID_B]);
  });

  it("deletes one claim (unclaim) without touching another claimant's", async () => {
    const id = await makeDrop();
    await db.upsertLootClaim({
      lootDropId: id,
      itemEntityId: "item-1",
      discordUserId: DISCORD_ID_A,
      characterEntityId: "char-1",
      quantity: null,
      claimType: "greed",
    });
    await db.upsertLootClaim({
      lootDropId: id,
      itemEntityId: "item-1",
      discordUserId: DISCORD_ID_B,
      characterEntityId: "char-2",
      quantity: null,
      claimType: "greed",
    });

    await db.deleteLootClaim(id, "item-1", DISCORD_ID_A);

    await expect(db.getLootClaim(id, "item-1", DISCORD_ID_A)).resolves.toBeUndefined();
    await expect(db.getLootClaim(id, "item-1", DISCORD_ID_B)).resolves.toBeDefined();
  });

  it("is idempotent when unclaiming something that was never claimed", async () => {
    const id = await makeDrop();

    await expect(db.deleteLootClaim(id, "item-1", DISCORD_ID_A)).resolves.toBeUndefined();
  });

  it("deletes every claim for a drop at once", async () => {
    const id = await makeDrop();
    await db.upsertLootClaim({
      lootDropId: id,
      itemEntityId: "item-1",
      discordUserId: DISCORD_ID_A,
      characterEntityId: "char-1",
      quantity: null,
      claimType: "greed",
    });
    await db.upsertLootClaim({
      lootDropId: id,
      itemEntityId: "item-2",
      discordUserId: DISCORD_ID_A,
      characterEntityId: "char-1",
      quantity: null,
      claimType: "greed",
    });

    await db.deleteLootClaimsForDrop(id);

    await expect(db.listLootClaims(id)).resolves.toEqual([]);
  });

  it("cascades: deleting a drop deletes its claims too", async () => {
    const id = await makeDrop();
    await db.upsertLootClaim({
      lootDropId: id,
      itemEntityId: "item-1",
      discordUserId: DISCORD_ID_A,
      characterEntityId: "char-1",
      quantity: null,
      claimType: "greed",
    });

    await db.deleteLootDrop(id);
    dropId = ""; // already gone - afterEach's own cleanup would no-op harmlessly either way

    await expect(db.getLootDrop(id)).resolves.toBeUndefined();
    await expect(db.listLootClaims(id)).resolves.toEqual([]);
  });

  it("is idempotent when deleting a drop that doesn't exist", async () => {
    await expect(
      db.deleteLootDrop("00000000-0000-0000-0000-000000000000"),
    ).resolves.toBeUndefined();
  });
});

describe.skipIf(!canRunDbTests)("container_prototype (real Postgres)", () => {
  const TENANT = "db-test-tenant-sack";
  const OTHER_TENANT = "db-test-tenant-sack-other";

  afterEach(async () => {
    await db.clearContainerPrototypeId(TENANT);
    await db.clearContainerPrototypeId(OTHER_TENANT);
  });

  it("returns undefined for a tenant nobody has set a sack up for", async () => {
    await expect(db.getContainerPrototypeId(TENANT)).resolves.toBeUndefined();
  });

  it("stores and returns the prototype id", async () => {
    await db.setContainerPrototypeId(TENANT, "prototype-1");

    await expect(db.getContainerPrototypeId(TENANT)).resolves.toBe("prototype-1");
  });

  it("replaces an existing id rather than failing - two racing first runs are harmless", async () => {
    await db.setContainerPrototypeId(TENANT, "prototype-1");
    await db.setContainerPrototypeId(TENANT, "prototype-2");

    await expect(db.getContainerPrototypeId(TENANT)).resolves.toBe("prototype-2");
  });

  it("keeps each tenant's prototype separate", async () => {
    await db.setContainerPrototypeId(TENANT, "prototype-1");
    await db.setContainerPrototypeId(OTHER_TENANT, "prototype-other");

    await expect(db.getContainerPrototypeId(TENANT)).resolves.toBe("prototype-1");
    await expect(db.getContainerPrototypeId(OTHER_TENANT)).resolves.toBe("prototype-other");
  });

  it("clears it, and clearing an unset one is a no-op", async () => {
    await db.setContainerPrototypeId(TENANT, "prototype-1");
    await db.clearContainerPrototypeId(TENANT);

    await expect(db.getContainerPrototypeId(TENANT)).resolves.toBeUndefined();
    await expect(db.clearContainerPrototypeId(TENANT)).resolves.toBeUndefined();
  });
});

describe.skipIf(!canRunDbTests)("notification bridge ledger (real Postgres)", () => {
  const USER = "db-test-notify-user";
  const OTHER_USER = "db-test-notify-other-user";
  const LINKED = "db-test-notify-linked-user";

  async function wipe() {
    // Finish and prune everything these tests could have left, wherever it got to.
    for (const id of ["n-1", "n-2", "n-3", "n-4"]) {
      for (const user of [USER, OTHER_USER]) {
        await db.releaseNotificationClaim(user, id);
      }
    }
    await db.pruneNotificationDeliveries(new Date(Date.now() + 60_000));
    await db.markNotificationsNoticed(USER, ["n-1", "n-2", "n-3", "n-4"]);
    await db.markNotificationsNoticed(OTHER_USER, ["n-1", "n-2", "n-3", "n-4"]);
    await db.pruneNotificationDeliveries(new Date(Date.now() + 60_000));
    await db.deleteLinkedAccount(LINKED);
  }

  afterEach(async () => {
    vi.restoreAllMocks();
    await wipe();
  });

  describe("listLinkedDiscordUserIds", () => {
    it("lists linked users", async () => {
      await db.upsertLinkedAccount({
        discordUserId: LINKED,
        authgearSubjectId: "authgear|db-test-notify-subject",
        refreshTokenEncrypted: Buffer.from("r"),
      });

      await expect(db.listLinkedDiscordUserIds()).resolves.toContain(LINKED);
    });
  });

  describe("getOrCreateNotificationEnrollment", () => {
    it("stamps 'now' on first sight, and never moves it afterwards", async () => {
      const before = Date.now();
      const first = await db.getOrCreateNotificationEnrollment(USER);
      const second = await db.getOrCreateNotificationEnrollment(USER);

      expect(first.getTime()).toBeGreaterThanOrEqual(before - 5000);
      expect(second.getTime()).toBe(first.getTime());
    });
  });

  describe("claimNotificationDelivery", () => {
    it("lets exactly one of several racing claims win", async () => {
      const results = await Promise.all(
        Array.from({ length: 8 }, () => db.claimNotificationDelivery(USER, "n-1")),
      );

      expect(results.filter(Boolean)).toHaveLength(1);
    });

    it("keeps claims separate per user and per notification", async () => {
      expect(await db.claimNotificationDelivery(USER, "n-1")).toBe(true);
      expect(await db.claimNotificationDelivery(OTHER_USER, "n-1")).toBe(true);
      expect(await db.claimNotificationDelivery(USER, "n-2")).toBe(true);
    });

    it("won't re-claim one that's in flight...", async () => {
      await db.claimNotificationDelivery(USER, "n-1");

      expect(await db.claimNotificationDelivery(USER, "n-1")).toBe(false);
    });

    it("...but will take over one whose run evidently died mid-send", async () => {
      await db.claimNotificationDelivery(USER, "n-1");
      vi.spyOn(Date, "now").mockReturnValue(Date.now() + 11 * 60 * 1000);

      expect(await db.claimNotificationDelivery(USER, "n-1")).toBe(true);
    });

    it.each([
      ["sent", async () => db.markNotificationSent(USER, "n-1")],
      [
        "undelivered",
        async () => db.markNotificationUndelivered(USER, "n-1", { title: "t", body: "b" }),
      ],
    ])("never re-claims a %s one, however old - it's finished", async (_state, finish) => {
      await db.claimNotificationDelivery(USER, "n-1");
      await finish();
      vi.spyOn(Date, "now").mockReturnValue(Date.now() + 60 * 60 * 1000);

      expect(await db.claimNotificationDelivery(USER, "n-1")).toBe(false);
    });
  });

  describe("releaseNotificationClaim", () => {
    it("frees a claim so the next run can take it", async () => {
      await db.claimNotificationDelivery(USER, "n-1");
      await db.releaseNotificationClaim(USER, "n-1");

      expect(await db.claimNotificationDelivery(USER, "n-1")).toBe(true);
    });

    it("never removes a finished row - a sent notification must stay sent", async () => {
      await db.claimNotificationDelivery(USER, "n-1");
      await db.markNotificationSent(USER, "n-1");
      await db.releaseNotificationClaim(USER, "n-1");

      expect(await db.claimNotificationDelivery(USER, "n-1")).toBe(false);
    });
  });

  describe("undelivered notifications and the banner", () => {
    async function queue(id: string, title: string) {
      await db.claimNotificationDelivery(USER, id);
      await db.markNotificationUndelivered(USER, id, { title, body: `${title} body` });
    }

    it("lists what Discord wouldn't deliver, with its text, oldest first", async () => {
      await queue("n-1", "First");
      await queue("n-2", "Second");

      const rows = await db.listUndeliveredNotifications(USER);

      expect(rows.map((r) => [r.notificationId, r.title, r.body])).toEqual([
        ["n-1", "First", "First body"],
        ["n-2", "Second", "Second body"],
      ]);
    });

    it("lists only this user's, and not ones that were delivered fine", async () => {
      await queue("n-1", "Mine");
      await db.claimNotificationDelivery(USER, "n-2");
      await db.markNotificationSent(USER, "n-2");
      await db.claimNotificationDelivery(OTHER_USER, "n-3");
      await db.markNotificationUndelivered(OTHER_USER, "n-3", { title: "Theirs", body: "x" });

      const rows = await db.listUndeliveredNotifications(USER);

      expect(rows.map((r) => r.notificationId)).toEqual(["n-1"]);
    });

    it("honours a limit", async () => {
      await queue("n-1", "A");
      await queue("n-2", "B");
      await queue("n-3", "C");

      expect(await db.listUndeliveredNotifications(USER, 2)).toHaveLength(2);
    });

    it("marks shown ones noticed, drops their stored text, and leaves the rest queued", async () => {
      await queue("n-1", "Shown");
      await queue("n-2", "Still waiting");

      await db.markNotificationsNoticed(USER, ["n-1"]);

      const rows = await db.listUndeliveredNotifications(USER);
      expect(rows.map((r) => r.notificationId)).toEqual(["n-2"]);
      // ...and a noticed one is finished: it can't be claimed and sent again.
      expect(await db.claimNotificationDelivery(USER, "n-1")).toBe(false);
    });

    it("does nothing for an empty list, and can't resurrect or alter a sent one", async () => {
      await db.claimNotificationDelivery(USER, "n-1");
      await db.markNotificationSent(USER, "n-1");

      await db.markNotificationsNoticed(USER, []);
      await db.markNotificationsNoticed(USER, ["n-1"]);

      expect(await db.listUndeliveredNotifications(USER)).toEqual([]);
    });
  });

  describe("pruneNotificationDeliveries", () => {
    it("drops finished rows older than the cutoff, but never a queued one", async () => {
      await db.claimNotificationDelivery(USER, "n-1");
      await db.markNotificationSent(USER, "n-1");
      await db.claimNotificationDelivery(USER, "n-2");
      await db.markNotificationUndelivered(USER, "n-2", { title: "t", body: "b" });

      await db.pruneNotificationDeliveries(new Date(Date.now() + 60_000));

      // n-1 was pruned, so it's claimable again; n-2 is still queued.
      expect(await db.claimNotificationDelivery(USER, "n-1")).toBe(true);
      expect((await db.listUndeliveredNotifications(USER)).map((r) => r.notificationId)).toEqual([
        "n-2",
      ]);
    });

    it("keeps rows newer than the cutoff", async () => {
      await db.claimNotificationDelivery(USER, "n-1");
      await db.markNotificationSent(USER, "n-1");

      await db.pruneNotificationDeliveries(new Date(Date.now() - 60 * 60 * 1000));

      expect(await db.claimNotificationDelivery(USER, "n-1")).toBe(false);
    });
  });
});
