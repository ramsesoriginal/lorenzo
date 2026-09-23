import { beforeEach, describe, expect, it, vi } from "vitest";
import type { ChatInputCommandInteraction } from "../src/commands/types.js";
import type { Config } from "../src/config.js";
import { COVERAGE_NOTE } from "../src/format-changes.js";

const { getValidAccessToken } = vi.hoisted(() => ({ getValidAccessToken: vi.fn() }));
vi.mock("../src/token-provider.js", () => ({ getValidAccessToken }));

const db = vi.hoisted(() => ({
  getChangesSeenAt: vi.fn(),
  listCharacterEvents: vi.fn(),
  setChangesSeenAt: vi.fn(),
  pruneCharacterEvents: vi.fn(),
}));
vi.mock("../src/db.js", () => db);

const { getControlledCharacters, createLorenzoApiClient } = vi.hoisted(() => ({
  getControlledCharacters: vi.fn(),
  createLorenzoApiClient: vi.fn(),
}));
vi.mock("../src/lorenzo-client.js", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../src/lorenzo-client.js")>();
  return {
    ...actual,
    createLorenzoApiClient: createLorenzoApiClient.mockReturnValue({ getControlledCharacters }),
  };
});

const { changesCommand } = await import("../src/commands/changes.js");

const config = {
  lorenzoApiBaseUrl: "http://lorenzo-api.test",
  lorenzoTenantId: "tenant-1",
} as Config;
const warn = vi.fn();
const ctx = { config, logger: { warn } as never };

const SEEN = new Date("2026-09-19T10:00:00Z");

function fakeInteraction(history: boolean | null = null) {
  return {
    user: { id: "discord-1" },
    options: { getBoolean: vi.fn(() => history) },
    deferReply: vi.fn(async () => undefined),
    editReply: vi.fn(async () => undefined),
  } as unknown as ChatInputCommandInteraction & {
    deferReply: ReturnType<typeof vi.fn>;
    editReply: ReturnType<typeof vi.fn>;
  };
}

function event(id: string, summary: string) {
  return {
    id,
    eventId: id,
    characterEntityId: "char-1",
    kind: "gave",
    summary,
    createdAt: new Date(),
  };
}

function sentEmbed(interaction: { editReply: ReturnType<typeof vi.fn> }) {
  const payload = interaction.editReply.mock.calls[0]?.[0] as {
    embeds: { toJSON(): { title?: string; description?: string; footer?: { text: string } } }[];
  };
  return payload.embeds[0]?.toJSON() ?? {};
}

describe("changesCommand.execute", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    getValidAccessToken.mockResolvedValue("token-123");
    getControlledCharacters.mockResolvedValue([
      { entityId: "char-1", name: "Frodo" },
      { entityId: "char-2", name: "Sam" },
    ]);
    db.getChangesSeenAt.mockResolvedValue(SEEN);
    db.listCharacterEvents.mockResolvedValue({ events: [], total: 0 });
    db.setChangesSeenAt.mockResolvedValue(undefined);
    db.pruneCharacterEvents.mockResolvedValue(undefined);
  });

  it("is private, and prompts to /link when there's no valid access token", async () => {
    getValidAccessToken.mockResolvedValue(null);
    const interaction = fakeInteraction();

    await changesCommand.execute(interaction, ctx);

    expect(interaction.deferReply).toHaveBeenCalledWith({ ephemeral: true });
    expect(interaction.editReply).toHaveBeenCalledWith(
      expect.stringContaining("run `/link` first"),
    );
    expect(db.listCharacterEvents).not.toHaveBeenCalled();
  });

  it("says so when the caller controls no characters", async () => {
    getControlledCharacters.mockResolvedValue([]);
    const interaction = fakeInteraction();

    await changesCommand.execute(interaction, ctx);

    expect(interaction.editReply).toHaveBeenCalledWith(
      expect.stringContaining("don't control any characters"),
    );
    expect(db.listCharacterEvents).not.toHaveBeenCalled();
  });

  it("reads the events of *all the caller's own characters*, since they last looked", async () => {
    await changesCommand.execute(fakeInteraction(), ctx);

    expect(getControlledCharacters).toHaveBeenCalledWith("tenant-1", "token-123");
    expect(db.getChangesSeenAt).toHaveBeenCalledWith("discord-1");
    expect(db.listCharacterEvents).toHaveBeenCalledWith(["char-1", "char-2"], {
      since: SEEN,
      limit: 25,
    });
  });

  it("shows what changed, and always says it only covers changes made through the bot", async () => {
    db.listCharacterEvents.mockResolvedValue({
      events: [event("e1", "Frodo gave Torch to Sam.")],
      total: 1,
    });
    const interaction = fakeInteraction();

    await changesCommand.execute(interaction, ctx);

    const embed = sentEmbed(interaction);
    expect(embed.description).toContain("Frodo gave Torch to Sam.");
    expect(embed.footer?.text).toBe(COVERAGE_NOTE);
  });

  it("moves the 'last looked' marker to when it started reading, after answering", async () => {
    const interaction = fakeInteraction();
    const before = Date.now();

    await changesCommand.execute(interaction, ctx);

    const [, seenAt] = db.setChangesSeenAt.mock.calls[0] as [string, Date];
    expect(db.setChangesSeenAt).toHaveBeenCalledWith("discord-1", expect.any(Date));
    expect(seenAt.getTime()).toBeGreaterThanOrEqual(before);
    expect(interaction.editReply.mock.invocationCallOrder[0]).toBeLessThan(
      db.setChangesSeenAt.mock.invocationCallOrder[0] as number,
    );
  });

  it("with history:true, ignores the marker and doesn't move it", async () => {
    const interaction = fakeInteraction(true);

    await changesCommand.execute(interaction, ctx);

    expect(db.getChangesSeenAt).not.toHaveBeenCalled();
    expect(db.listCharacterEvents).toHaveBeenCalledWith(["char-1", "char-2"], {
      since: undefined,
      limit: 25,
    });
    expect(db.setChangesSeenAt).not.toHaveBeenCalled();
    expect(sentEmbed(interaction).title).toBe("Recent changes");
  });

  it("on a first look (no marker), shows the recent past rather than nothing", async () => {
    db.getChangesSeenAt.mockResolvedValue(undefined);

    await changesCommand.execute(fakeInteraction(), ctx);

    expect(db.listCharacterEvents).toHaveBeenCalledWith(["char-1", "char-2"], {
      since: undefined,
      limit: 25,
    });
  });

  it("says how many it left out when there are more than fit", async () => {
    db.listCharacterEvents.mockResolvedValue({
      events: [event("e1", "a")],
      total: 30,
    });
    const interaction = fakeInteraction();

    await changesCommand.execute(interaction, ctx);

    expect(sentEmbed(interaction).description).toContain("29 older changes not shown");
  });

  it("prunes old events, after answering", async () => {
    const interaction = fakeInteraction();

    await changesCommand.execute(interaction, ctx);

    const [cutoff] = db.pruneCharacterEvents.mock.calls[0] as [Date];
    const ninetyDays = 90 * 24 * 60 * 60 * 1000;
    expect(Date.now() - cutoff.getTime()).toBeGreaterThanOrEqual(ninetyDays - 5000);
    expect(interaction.editReply.mock.invocationCallOrder[0]).toBeLessThan(
      db.pruneCharacterEvents.mock.invocationCallOrder[0] as number,
    );
  });

  it("still answers, and only logs, if the bookkeeping afterwards fails", async () => {
    db.setChangesSeenAt.mockRejectedValue(new Error("db down"));
    const interaction = fakeInteraction();

    await expect(changesCommand.execute(interaction, ctx)).resolves.toBeUndefined();

    expect(interaction.editReply).toHaveBeenCalledTimes(1);
    expect(warn).toHaveBeenCalledTimes(1);
  });
});
