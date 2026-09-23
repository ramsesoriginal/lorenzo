import { beforeEach, describe, expect, it, vi } from "vitest";
import type { ChatInputCommandInteraction } from "../src/commands/types.js";
import type { Config } from "../src/config.js";
import type { EntityChangeOut } from "../src/lorenzo-client.js";

const { getValidAccessToken } = vi.hoisted(() => ({ getValidAccessToken: vi.fn() }));
vi.mock("../src/token-provider.js", () => ({ getValidAccessToken }));

const db = vi.hoisted(() => ({
  getChangesSeenAt: vi.fn(),
  setChangesSeenAt: vi.fn(),
}));
vi.mock("../src/db.js", () => db);

const { listMyChanges, getCharacterName, createLorenzoApiClient } = vi.hoisted(() => ({
  listMyChanges: vi.fn(),
  getCharacterName: vi.fn(),
  createLorenzoApiClient: vi.fn(),
}));
vi.mock("../src/lorenzo-client.js", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../src/lorenzo-client.js")>();
  return {
    ...actual,
    createLorenzoApiClient: createLorenzoApiClient.mockReturnValue({
      listMyChanges,
      getCharacterName,
    }),
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

function row(overrides: Partial<EntityChangeOut> = {}): EntityChangeOut {
  return {
    id: "row-1",
    tenant_id: "tenant-1",
    character_entity_id: "char-1",
    entity_id: "item-1",
    entity_name: "Torch",
    kind: "received",
    detail: null,
    actor_user_id: null,
    occurred_at: new Date().toISOString(),
    ...overrides,
  } as EntityChangeOut;
}

function sentEmbed(interaction: { editReply: ReturnType<typeof vi.fn> }) {
  const payload = interaction.editReply.mock.calls[0]?.[0] as {
    embeds: { toJSON(): { title?: string; description?: string } }[];
  };
  return payload.embeds[0]?.toJSON() ?? {};
}

describe("changesCommand.execute", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    getValidAccessToken.mockResolvedValue("token-123");
    getCharacterName.mockResolvedValue("Frodo");
    db.getChangesSeenAt.mockResolvedValue(SEEN);
    db.setChangesSeenAt.mockResolvedValue(undefined);
    listMyChanges.mockResolvedValue([]);
  });

  it("is private, and prompts to /link when there's no valid access token", async () => {
    getValidAccessToken.mockResolvedValue(null);
    const interaction = fakeInteraction();

    await changesCommand.execute(interaction, ctx);

    expect(interaction.deferReply).toHaveBeenCalledWith({ ephemeral: true });
    expect(interaction.editReply).toHaveBeenCalledWith(
      expect.stringContaining("run `/link` first"),
    );
    expect(listMyChanges).not.toHaveBeenCalled();
  });

  it("reads the feed for the caller's own tenant, since they last looked", async () => {
    await changesCommand.execute(fakeInteraction(), ctx);

    expect(db.getChangesSeenAt).toHaveBeenCalledWith("discord-1");
    expect(listMyChanges).toHaveBeenCalledWith("tenant-1", "token-123", SEEN);
  });

  it("shows what changed, naming the character each row concerns", async () => {
    listMyChanges.mockResolvedValue([row({ kind: "received", entity_name: "Torch" })]);
    const interaction = fakeInteraction();

    await changesCommand.execute(interaction, ctx);

    expect(sentEmbed(interaction).description).toContain("Frodo received Torch.");
  });

  it("resolves one name per distinct character, not per row", async () => {
    listMyChanges.mockResolvedValue([
      row({ id: "r1", character_entity_id: "char-1" }),
      row({ id: "r2", character_entity_id: "char-1" }),
      row({ id: "r3", character_entity_id: "char-2" }),
    ]);

    await changesCommand.execute(fakeInteraction(), ctx);

    expect(getCharacterName).toHaveBeenCalledTimes(2);
  });

  it("falls back to 'another character' when a name lookup fails", async () => {
    getCharacterName.mockRejectedValue(new Error("nope"));
    listMyChanges.mockResolvedValue([row()]);
    const interaction = fakeInteraction();

    await changesCommand.execute(interaction, ctx);

    expect(sentEmbed(interaction).description).toContain("another character received Torch.");
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
    expect(listMyChanges).toHaveBeenCalledWith("tenant-1", "token-123", undefined);
    expect(db.setChangesSeenAt).not.toHaveBeenCalled();
    expect(sentEmbed(interaction).title).toBe("Recent changes");
  });

  it("on a first look (no marker), shows the recent past rather than nothing", async () => {
    db.getChangesSeenAt.mockResolvedValue(undefined);

    await changesCommand.execute(fakeInteraction(), ctx);

    expect(listMyChanges).toHaveBeenCalledWith("tenant-1", "token-123", undefined);
  });

  it("says how many it left out when there are more than fit", async () => {
    listMyChanges.mockResolvedValue(
      Array.from({ length: 26 }, (_, i) => row({ id: `r${i}`, entity_name: `Item ${i}` })),
    );
    const interaction = fakeInteraction();

    await changesCommand.execute(interaction, ctx);

    expect(sentEmbed(interaction).description).toContain("1 older change not shown");
  });

  it("still answers, and only logs, if the bookkeeping afterwards fails", async () => {
    db.setChangesSeenAt.mockRejectedValue(new Error("db down"));
    const interaction = fakeInteraction();

    await expect(changesCommand.execute(interaction, ctx)).resolves.toBeUndefined();

    expect(interaction.editReply).toHaveBeenCalledTimes(1);
    expect(warn).toHaveBeenCalledTimes(1);
  });
});
