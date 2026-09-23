import { beforeEach, describe, expect, it, vi } from "vitest";
import type { ChatInputCommandInteraction } from "../src/commands/types.js";

const db = vi.hoisted(() => ({
  listUndeliveredNotifications: vi.fn(),
  markNotificationsNoticed: vi.fn(),
}));
vi.mock("../src/db.js", () => db);

const { showUndeliveredNotice } = await import("../src/undelivered-notice.js");

const logger = { warn: vi.fn() } as never;

function fakeInteraction(over: { deferred?: boolean; replied?: boolean } = {}) {
  return {
    user: { id: "discord-1" },
    deferred: over.deferred ?? true,
    replied: over.replied ?? false,
    followUp: vi.fn(async () => ({ id: "m-1" })),
  } as unknown as ChatInputCommandInteraction & { followUp: ReturnType<typeof vi.fn> };
}

function row(n: number) {
  return { notificationId: `n-${n}`, title: `Notice ${n}`, body: `Body ${n}` };
}

describe("showUndeliveredNotice", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    db.listUndeliveredNotifications.mockResolvedValue([]);
  });

  it("says nothing when nothing is undelivered", async () => {
    const interaction = fakeInteraction();

    await showUndeliveredNotice(interaction, logger);

    expect(db.listUndeliveredNotifications).toHaveBeenCalledWith("discord-1");
    expect(interaction.followUp).not.toHaveBeenCalled();
    expect(db.markNotificationsNoticed).not.toHaveBeenCalled();
  });

  it("shows the queued notifications as a private follow-up marked 'couldn't DM you'", async () => {
    db.listUndeliveredNotifications.mockResolvedValue([row(1), row(2)]);
    const interaction = fakeInteraction();

    await showUndeliveredNotice(interaction, logger);

    expect(interaction.followUp).toHaveBeenCalledTimes(1);
    const [payload] = interaction.followUp.mock.calls[0] as [
      { content: string; ephemeral: boolean },
    ];
    expect(payload.ephemeral).toBe(true);
    expect(payload.content).toContain("Couldn't DM you");
    expect(payload.content).toContain("Notice 1");
    expect(payload.content).toContain("Notice 2");
  });

  it("marks them noticed once shown - and only after the follow-up went out", async () => {
    db.listUndeliveredNotifications.mockResolvedValue([row(1)]);
    const interaction = fakeInteraction();

    await showUndeliveredNotice(interaction, logger);

    expect(db.markNotificationsNoticed).toHaveBeenCalledWith("discord-1", ["n-1"]);
    expect(interaction.followUp.mock.invocationCallOrder[0]).toBeLessThan(
      db.markNotificationsNoticed.mock.invocationCallOrder[0] as number,
    );
  });

  it("marks only the ones it actually listed, leaving the rest queued for the next command", async () => {
    db.listUndeliveredNotifications.mockResolvedValue(
      Array.from({ length: 8 }, (_, i) => row(i + 1)),
    );

    await showUndeliveredNotice(fakeInteraction(), logger);

    expect(db.markNotificationsNoticed).toHaveBeenCalledWith("discord-1", [
      "n-1",
      "n-2",
      "n-3",
      "n-4",
      "n-5",
    ]);
  });

  it("doesn't mark anything noticed if the follow-up failed - the user hasn't seen it", async () => {
    db.listUndeliveredNotifications.mockResolvedValue([row(1)]);
    const interaction = fakeInteraction();
    interaction.followUp.mockRejectedValue(new Error("discord down"));

    await showUndeliveredNotice(interaction, logger);

    expect(db.markNotificationsNoticed).not.toHaveBeenCalled();
  });

  it("can't follow up on an interaction nothing has answered yet, so it does nothing", async () => {
    db.listUndeliveredNotifications.mockResolvedValue([row(1)]);
    const interaction = fakeInteraction({ deferred: false, replied: false });

    await showUndeliveredNotice(interaction, logger);

    expect(db.listUndeliveredNotifications).not.toHaveBeenCalled();
    expect(interaction.followUp).not.toHaveBeenCalled();
  });

  it("also works after a command that replied directly", async () => {
    db.listUndeliveredNotifications.mockResolvedValue([row(1)]);
    const interaction = fakeInteraction({ deferred: false, replied: true });

    await showUndeliveredNotice(interaction, logger);

    expect(interaction.followUp).toHaveBeenCalledTimes(1);
  });

  it("never throws - a notice problem must not turn a working command into an error", async () => {
    db.listUndeliveredNotifications.mockRejectedValue(new Error("db down"));

    await expect(showUndeliveredNotice(fakeInteraction(), logger)).resolves.toBeUndefined();
  });
});
