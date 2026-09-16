import type { ChatInputCommandInteraction } from "discord.js";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { Config } from "../src/config.js";
import { LorenzoApiError } from "../src/lorenzo-client.js";

const { getValidAccessToken } = vi.hoisted(() => ({ getValidAccessToken: vi.fn() }));
vi.mock("../src/token-provider.js", () => ({ getValidAccessToken }));

const { resolveCurrentCharacter } = vi.hoisted(() => ({ resolveCurrentCharacter: vi.fn() }));
vi.mock("../src/preferences.js", () => ({ resolveCurrentCharacter }));

const { createInformation, addInformationKnower, createLorenzoApiClient } = vi.hoisted(() => ({
  createInformation: vi.fn(),
  addInformationKnower: vi.fn(),
  createLorenzoApiClient: vi.fn(),
}));
vi.mock("../src/lorenzo-client.js", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../src/lorenzo-client.js")>();
  return {
    ...actual,
    createLorenzoApiClient: createLorenzoApiClient.mockReturnValue({
      createInformation,
      addInformationKnower,
    }),
  };
});

const { noteCommand } = await import("../src/commands/note.js");

const config = {
  lorenzoApiBaseUrl: "http://lorenzo-api.test",
  lorenzoTenantId: "tenant-1",
} as Config;

function fakeInteraction(fields: Record<string, string>) {
  return {
    user: { id: "user-1" },
    options: { getString: vi.fn((name: string) => fields[name] ?? null) },
    deferReply: vi.fn(async () => undefined),
    editReply: vi.fn(async () => undefined),
  } as unknown as ChatInputCommandInteraction & {
    options: { getString: ReturnType<typeof vi.fn> };
    deferReply: ReturnType<typeof vi.fn>;
    editReply: ReturnType<typeof vi.fn>;
  };
}

describe("noteCommand.execute", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("prompts to /link when there's no valid access token", async () => {
    getValidAccessToken.mockResolvedValue(null);
    const interaction = fakeInteraction({
      item: "item-1",
      visibility: "public",
      title: "T",
      content: "C",
    });

    await noteCommand.execute(interaction, { config, logger: {} as never });

    expect(interaction.editReply).toHaveBeenCalledWith(
      expect.stringContaining("run `/link` first"),
    );
    expect(createInformation).not.toHaveBeenCalled();
  });

  it("creates a public note with is_public true and no knower call", async () => {
    getValidAccessToken.mockResolvedValue("token-123");
    createInformation.mockResolvedValue({ id: "info-1" });
    const interaction = fakeInteraction({
      item: "item-1",
      visibility: "public",
      title: "Lore",
      content: "It glows.",
    });

    await noteCommand.execute(interaction, { config, logger: {} as never });

    expect(createInformation).toHaveBeenCalledWith(
      "tenant-1",
      "item-1",
      { title: "Lore", type: "note", isPublic: true, content: "It glows." },
      "token-123",
    );
    expect(addInformationKnower).not.toHaveBeenCalled();
    expect(interaction.editReply).toHaveBeenCalledWith("Added a public note to that item.");
  });

  it("creates a gm-private note with is_public false and no knower call", async () => {
    getValidAccessToken.mockResolvedValue("token-123");
    createInformation.mockResolvedValue({ id: "info-1" });
    const interaction = fakeInteraction({
      item: "item-1",
      visibility: "gm-private",
      title: "Secret",
      content: "Cursed.",
    });

    await noteCommand.execute(interaction, { config, logger: {} as never });

    expect(createInformation).toHaveBeenCalledWith(
      "tenant-1",
      "item-1",
      { title: "Secret", type: "note", isPublic: false, content: "Cursed." },
      "token-123",
    );
    expect(addInformationKnower).not.toHaveBeenCalled();
    expect(interaction.editReply).toHaveBeenCalledWith("Added a gm-private note to that item.");
  });

  it("rejects a private note up front when there's no current character", async () => {
    resolveCurrentCharacter.mockResolvedValue(undefined);
    const interaction = fakeInteraction({
      item: "item-1",
      visibility: "private",
      title: "Mine",
      content: "Just for me.",
    });

    await noteCommand.execute(interaction, { config, logger: {} as never });

    expect(interaction.editReply).toHaveBeenCalledWith(expect.stringContaining("/set-current"));
    expect(createInformation).not.toHaveBeenCalled();
  });

  it("creates a private note and grants the author's current character as a knower", async () => {
    getValidAccessToken.mockResolvedValue("token-123");
    resolveCurrentCharacter.mockResolvedValue("char-1");
    createInformation.mockResolvedValue({ id: "info-1" });
    addInformationKnower.mockResolvedValue({ id: "info-1" });
    const interaction = fakeInteraction({
      item: "item-1",
      visibility: "private",
      title: "Mine",
      content: "Just for me.",
    });

    await noteCommand.execute(interaction, { config, logger: {} as never });

    expect(createInformation).toHaveBeenCalledWith(
      "tenant-1",
      "item-1",
      { title: "Mine", type: "note", isPublic: false, content: "Just for me." },
      "token-123",
    );
    expect(addInformationKnower).toHaveBeenCalledWith("tenant-1", "info-1", "char-1", "token-123");
    expect(interaction.editReply).toHaveBeenCalledWith("Added a private note to that item.");
  });

  it("reports a distinct message when the note was created but the knower grant failed", async () => {
    getValidAccessToken.mockResolvedValue("token-123");
    resolveCurrentCharacter.mockResolvedValue("char-1");
    createInformation.mockResolvedValue({ id: "info-1" });
    addInformationKnower.mockRejectedValue(new LorenzoApiError("boom", 500));
    const interaction = fakeInteraction({
      item: "item-1",
      visibility: "private",
      title: "Mine",
      content: "Just for me.",
    });

    await noteCommand.execute(interaction, { config, logger: {} as never });

    expect(interaction.editReply).toHaveBeenCalledWith(
      expect.stringContaining("couldn't grant your character visibility"),
    );
  });

  it.each([
    [403, "reachable from any of your characters"],
    [404, "Couldn't find that item"],
    [422, "Couldn't do that"],
  ])("gives a specific message for a %i error creating the note", async (status, expectedText) => {
    getValidAccessToken.mockResolvedValue("token-123");
    createInformation.mockRejectedValue(new LorenzoApiError("boom", status));
    const interaction = fakeInteraction({
      item: "item-1",
      visibility: "public",
      title: "T",
      content: "C",
    });

    await noteCommand.execute(interaction, { config, logger: {} as never });

    expect(interaction.editReply).toHaveBeenCalledWith(expect.stringContaining(expectedText));
  });
});
