import { afterAll, afterEach, describe, expect, it } from "vitest";

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

  afterAll(async () => {
    await db.closeDb();
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

  it("completely overwrites an existing link on re-upsert (ADR 0029: /link always overwrites)", async () => {
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
