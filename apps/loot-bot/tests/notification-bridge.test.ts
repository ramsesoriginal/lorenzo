import { beforeEach, describe, expect, it, vi } from "vitest";
import type { Config } from "../src/config.js";
import { DiscordApiError } from "../src/discord-rest.js";
import type { NotificationOut } from "../src/lorenzo-client.js";

const { getValidAccessToken } = vi.hoisted(() => ({ getValidAccessToken: vi.fn() }));
vi.mock("../src/token-provider.js", () => ({ getValidAccessToken }));

const db = vi.hoisted(() => ({
  listLinkedDiscordUserIds: vi.fn(),
  getOrCreateNotificationEnrollment: vi.fn(),
  claimNotificationDelivery: vi.fn(),
  markNotificationSent: vi.fn(),
  markNotificationUndelivered: vi.fn(),
  releaseNotificationClaim: vi.fn(),
  pruneNotificationDeliveries: vi.fn(),
}));
vi.mock("../src/db.js", () => db);

const { sendDirectMessage } = vi.hoisted(() => ({ sendDirectMessage: vi.fn() }));
vi.mock("../src/discord-rest.js", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../src/discord-rest.js")>();
  return { ...actual, sendDirectMessage };
});

const { listMyUnreadNotifications, createLorenzoApiClient } = vi.hoisted(() => ({
  listMyUnreadNotifications: vi.fn(),
  createLorenzoApiClient: vi.fn(),
}));
vi.mock("../src/lorenzo-client.js", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../src/lorenzo-client.js")>();
  return {
    ...actual,
    createLorenzoApiClient: createLorenzoApiClient.mockReturnValue({ listMyUnreadNotifications }),
  };
});

const {
  MAX_DMS_PER_USER_PER_RUN,
  MAX_NOTIFICATION_AGE_MS,
  deliverNotifications,
  selectDeliverable,
} = await import("../src/notification-bridge.js");

const TENANT = "tenant-1";
const NOW = new Date("2026-09-20T12:00:00Z");
const ENROLLED = new Date("2026-09-20T08:00:00Z");

const config = {
  lorenzoApiBaseUrl: "http://lorenzo-api.test",
  lorenzoTenantId: TENANT,
  discordBotToken: "bot-token",
} as Config;

function notification(id: string, over: Partial<NotificationOut> = {}): NotificationOut {
  return {
    id,
    batch_id: "batch-1",
    user_id: "lorenzo-user-1",
    scope: "campaign",
    type: "custom",
    tenant_id: TENANT,
    source_id: null,
    title: `Title ${id}`,
    body: `Body ${id}`,
    read_at: null,
    created_at: "2026-09-20T10:00:00Z",
    ...over,
  };
}

const select = (notifications: NotificationOut[], enrolledAt = ENROLLED) =>
  selectDeliverable(notifications, { tenantId: TENANT, enrolledAt, now: NOW }).map((n) => n.id);

describe("selectDeliverable", () => {
  it("keeps a recent, unread notification for this bot's tenant", () => {
    expect(select([notification("a")])).toEqual(["a"]);
  });

  it("keeps platform-wide notifications (no tenant) - they're addressed to the user, not a tenant", () => {
    expect(select([notification("a", { tenant_id: null, scope: "platform" })])).toEqual(["a"]);
  });

  it("drops another tenant's notifications - a bot serves exactly one", () => {
    expect(select([notification("a", { tenant_id: "some-other-tenant" })])).toEqual([]);
  });

  it("drops anything created at or before enrollment, so switching this on never DMs the existing inbox", () => {
    expect(
      select([
        notification("old", { created_at: "2026-09-20T07:59:59Z" }),
        notification("edge", { created_at: ENROLLED.toISOString() }),
        notification("new", { created_at: "2026-09-20T08:00:01Z" }),
      ]),
    ).toEqual(["new"]);
  });

  it("drops anything older than the age cap, however unread", () => {
    const tooOld = new Date(NOW.getTime() - MAX_NOTIFICATION_AGE_MS - 1000).toISOString();
    const justInside = new Date(NOW.getTime() - MAX_NOTIFICATION_AGE_MS + 1000).toISOString();

    expect(
      select(
        [
          notification("too-old", { created_at: tooOld }),
          notification("inside", { created_at: justInside }),
        ],
        new Date(0),
      ),
    ).toEqual(["inside"]);
  });

  it("drops anything already read", () => {
    expect(select([notification("a", { read_at: "2026-09-20T11:00:00Z" })])).toEqual([]);
  });

  it("sends oldest first, so they arrive in the order they happened", () => {
    expect(
      select([
        notification("b", { created_at: "2026-09-20T11:00:00Z" }),
        notification("a", { created_at: "2026-09-20T09:00:00Z" }),
        notification("c", { created_at: "2026-09-20T10:00:00Z" }),
      ]),
    ).toEqual(["a", "c", "b"]);
  });

  it("caps how many go out per run, leaving the newest for the next one", () => {
    const many = Array.from({ length: MAX_DMS_PER_USER_PER_RUN + 3 }, (_, i) =>
      notification(`n${i}`, { created_at: `2026-09-20T10:0${i}:00Z` }),
    );

    const ids = select(many);

    expect(ids).toHaveLength(MAX_DMS_PER_USER_PER_RUN);
    expect(ids[0]).toBe("n0");
  });
});

describe("deliverNotifications", () => {
  const logger = { warn: vi.fn(), error: vi.fn(), info: vi.fn() } as never;

  beforeEach(() => {
    vi.clearAllMocks();
    db.listLinkedDiscordUserIds.mockResolvedValue(["discord-1"]);
    getValidAccessToken.mockResolvedValue("token-1");
    db.getOrCreateNotificationEnrollment.mockResolvedValue(ENROLLED);
    db.claimNotificationDelivery.mockResolvedValue(true);
    db.pruneNotificationDeliveries.mockResolvedValue(undefined);
    sendDirectMessage.mockResolvedValue({ kind: "sent" });
  });

  it("DMs a new notification to its recipient, as an embed, using the bot token", async () => {
    listMyUnreadNotifications.mockResolvedValue([notification("n1")]);

    const report = await deliverNotifications(config, logger, NOW);

    expect(listMyUnreadNotifications).toHaveBeenCalledWith("token-1");
    expect(sendDirectMessage).toHaveBeenCalledTimes(1);
    const [token, userId, body] = sendDirectMessage.mock.calls[0] as [
      string,
      string,
      { embeds: { title: string }[] },
    ];
    expect(token).toBe("bot-token");
    expect(userId).toBe("discord-1");
    expect(body.embeds[0]?.title).toBe("Title n1");
    expect(db.markNotificationSent).toHaveBeenCalledWith("discord-1", "n1");
    expect(report).toEqual({ users: 1, skippedUsers: 0, delivered: 1, undelivered: 0, failed: 0 });
  });

  it("reads the notifications as the recipient - with their own token, never anyone else's", async () => {
    db.listLinkedDiscordUserIds.mockResolvedValue(["discord-1", "discord-2"]);
    getValidAccessToken.mockImplementation(async (id: string) => `token-for-${id}`);
    listMyUnreadNotifications.mockResolvedValue([]);

    await deliverNotifications(config, logger, NOW);

    expect(listMyUnreadNotifications.mock.calls.map((c) => c[0]).sort()).toEqual([
      "token-for-discord-1",
      "token-for-discord-2",
    ]);
  });

  it("never marks anything read in Lorenzo - the bridge only reads", async () => {
    // The client mock exposes only the read; a write would throw.
    listMyUnreadNotifications.mockResolvedValue([notification("n1")]);

    await expect(deliverNotifications(config, logger, NOW)).resolves.toMatchObject({
      delivered: 1,
    });
  });

  it("queues a notification for the banner when Discord says the user's DMs are closed", async () => {
    listMyUnreadNotifications.mockResolvedValue([notification("n1")]);
    sendDirectMessage.mockResolvedValue({ kind: "closed" });

    const report = await deliverNotifications(config, logger, NOW);

    expect(db.markNotificationUndelivered).toHaveBeenCalledWith("discord-1", "n1", {
      title: "Title n1",
      body: "Body n1",
    });
    expect(db.markNotificationSent).not.toHaveBeenCalled();
    expect(report).toMatchObject({ delivered: 0, undelivered: 1, failed: 0 });
  });

  it("skips one already claimed or delivered, so it's never sent twice", async () => {
    listMyUnreadNotifications.mockResolvedValue([notification("n1")]);
    db.claimNotificationDelivery.mockResolvedValue(false);

    const report = await deliverNotifications(config, logger, NOW);

    expect(sendDirectMessage).not.toHaveBeenCalled();
    expect(report).toMatchObject({ delivered: 0, undelivered: 0, failed: 0 });
  });

  it("claims before it sends", async () => {
    listMyUnreadNotifications.mockResolvedValue([notification("n1")]);

    await deliverNotifications(config, logger, NOW);

    expect(db.claimNotificationDelivery.mock.invocationCallOrder[0]).toBeLessThan(
      sendDirectMessage.mock.invocationCallOrder[0] as number,
    );
  });

  it("gives the claim back on a transient failure so the next run retries, and stops for that user", async () => {
    listMyUnreadNotifications.mockResolvedValue([notification("n1"), notification("n2")]);
    sendDirectMessage.mockRejectedValue(new DiscordApiError(429, undefined, "rate limited"));

    const report = await deliverNotifications(config, logger, NOW);

    expect(db.releaseNotificationClaim).toHaveBeenCalledWith("discord-1", "n1");
    expect(sendDirectMessage).toHaveBeenCalledTimes(1);
    expect(db.markNotificationSent).not.toHaveBeenCalled();
    expect(db.markNotificationUndelivered).not.toHaveBeenCalled();
    expect(report).toMatchObject({ delivered: 0, failed: 1 });
  });

  it("only enrolls and reads for a user with a usable token, and counts the rest as skipped", async () => {
    getValidAccessToken.mockResolvedValue(null);

    const report = await deliverNotifications(config, logger, NOW);

    expect(listMyUnreadNotifications).not.toHaveBeenCalled();
    expect(db.getOrCreateNotificationEnrollment).not.toHaveBeenCalled();
    expect(report).toMatchObject({ users: 1, skippedUsers: 1 });
  });

  it("does not let one user's failure stop everyone else's notifications", async () => {
    db.listLinkedDiscordUserIds.mockResolvedValue(["discord-bad", "discord-good"]);
    getValidAccessToken.mockImplementation(async (id: string) => {
      if (id === "discord-bad") throw new Error("token store exploded");
      return "token-good";
    });
    listMyUnreadNotifications.mockResolvedValue([notification("n1")]);

    const report = await deliverNotifications(config, logger, NOW);

    expect(report).toMatchObject({ users: 2, delivered: 1, failed: 1 });
  });

  it("delivers nothing for a just-enrolled user's existing inbox", async () => {
    // Enrollment happens *now*, so everything already in the inbox predates it.
    db.getOrCreateNotificationEnrollment.mockResolvedValue(NOW);
    listMyUnreadNotifications.mockResolvedValue([notification("n1"), notification("n2")]);

    const report = await deliverNotifications(config, logger, NOW);

    expect(sendDirectMessage).not.toHaveBeenCalled();
    expect(report).toMatchObject({ delivered: 0 });
  });

  it("prunes old finished ledger rows - far older than the age cap, so nothing can be re-sent", async () => {
    listMyUnreadNotifications.mockResolvedValue([]);

    await deliverNotifications(config, logger, NOW);

    const [cutoff] = db.pruneNotificationDeliveries.mock.calls[0] as [Date];
    expect(NOW.getTime() - cutoff.getTime()).toBeGreaterThan(MAX_NOTIFICATION_AGE_MS);
  });

  it("still reports the run if pruning fails", async () => {
    listMyUnreadNotifications.mockResolvedValue([]);
    db.pruneNotificationDeliveries.mockRejectedValue(new Error("db down"));

    await expect(deliverNotifications(config, logger, NOW)).resolves.toMatchObject({ users: 1 });
  });
});
