import { beforeEach, describe, expect, it, vi } from "vitest";
import type {
  AutocompleteInteraction,
  ChatInputCommandInteraction,
} from "../src/commands/types.js";
import type { Config } from "../src/config.js";
import { LorenzoApiError } from "../src/lorenzo-client.js";

const { getValidAccessToken } = vi.hoisted(() => ({ getValidAccessToken: vi.fn() }));
vi.mock("../src/token-provider.js", () => ({ getValidAccessToken }));

const { resolveCurrentCharacter } = vi.hoisted(() => ({ resolveCurrentCharacter: vi.fn() }));
vi.mock("../src/preferences.js", () => ({ resolveCurrentCharacter }));

const { createInformation, addInformationKnower, listGroups, createLorenzoApiClient } = vi.hoisted(
  () => ({
    createInformation: vi.fn(),
    addInformationKnower: vi.fn(),
    listGroups: vi.fn(),
    createLorenzoApiClient: vi.fn(),
  }),
);
vi.mock("../src/lorenzo-client.js", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../src/lorenzo-client.js")>();
  return {
    ...actual,
    createLorenzoApiClient: createLorenzoApiClient.mockReturnValue({
      createInformation,
      addInformationKnower,
      listGroups,
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

function fakeAutocomplete(focusedName: "item" | "group", focusedValue = "") {
  return {
    user: { id: "user-1" },
    options: {
      getFocused: vi.fn(() => ({ name: focusedName, value: focusedValue })),
    },
    respond: vi.fn(async () => undefined),
  } as unknown as AutocompleteInteraction & { respond: ReturnType<typeof vi.fn> };
}

describe("noteCommand.autocomplete", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("suggests the group's own read API (ADR 0045) for the group option", async () => {
    getValidAccessToken.mockResolvedValue("token-123");
    listGroups.mockResolvedValue([{ entityId: "group-1", name: "The Party" }]);
    const interaction = fakeAutocomplete("group");

    await noteCommand.autocomplete?.(interaction, { config, logger: {} as never });

    expect(listGroups).toHaveBeenCalledWith("tenant-1", "token-123");
    expect(interaction.respond).toHaveBeenCalledWith([{ name: "The Party", value: "group-1" }]);
  });
});

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
      expect.stringContaining("couldn't grant visibility"),
    );
  });

  it("rejects a group note up front when no group is given", async () => {
    getValidAccessToken.mockResolvedValue("token-123");
    const interaction = fakeInteraction({
      item: "item-1",
      visibility: "group",
      title: "For the party",
      content: "Only you lot know this.",
    });

    await noteCommand.execute(interaction, { config, logger: {} as never });

    expect(interaction.editReply).toHaveBeenCalledWith(expect.stringContaining("Pick a group"));
    expect(createInformation).not.toHaveBeenCalled();
  });

  it("creates a group note and grants the chosen group as a knower", async () => {
    getValidAccessToken.mockResolvedValue("token-123");
    createInformation.mockResolvedValue({ id: "info-1" });
    addInformationKnower.mockResolvedValue({ id: "info-1" });
    const interaction = fakeInteraction({
      item: "item-1",
      visibility: "group",
      title: "For the party",
      content: "Only you lot know this.",
      group: "group-1",
    });

    await noteCommand.execute(interaction, { config, logger: {} as never });

    expect(createInformation).toHaveBeenCalledWith(
      "tenant-1",
      "item-1",
      { title: "For the party", type: "note", isPublic: false, content: "Only you lot know this." },
      "token-123",
    );
    expect(addInformationKnower).toHaveBeenCalledWith("tenant-1", "info-1", "group-1", "token-123");
    expect(interaction.editReply).toHaveBeenCalledWith("Added a group note to that item.");
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
