import { beforeEach, describe, expect, it, vi } from "vitest";
import type {
  AutocompleteInteraction,
  ChatInputCommandInteraction,
} from "../src/commands/types.js";
import type { Config } from "../src/config.js";
import { LorenzoApiError } from "../src/lorenzo-client.js";

const { getValidAccessToken } = vi.hoisted(() => ({ getValidAccessToken: vi.fn() }));
vi.mock("../src/token-provider.js", () => ({ getValidAccessToken }));

const { resolveOrCreateGroup } = vi.hoisted(() => ({ resolveOrCreateGroup: vi.fn() }));
vi.mock("../src/commands/group-lookup.js", () => ({ resolveOrCreateGroup }));

const { findGmControlledCharacters } = vi.hoisted(() => ({
  findGmControlledCharacters: vi.fn(),
}));
vi.mock("../src/commands/gm-roster.js", () => ({ findGmControlledCharacters }));

const {
  getControlledCharacters,
  getCharacterName,
  addGroupMember,
  listGroups,
  createLorenzoApiClient,
} = vi.hoisted(() => ({
  getControlledCharacters: vi.fn(),
  getCharacterName: vi.fn(),
  addGroupMember: vi.fn(),
  listGroups: vi.fn(),
  createLorenzoApiClient: vi.fn(),
}));
vi.mock("../src/lorenzo-client.js", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../src/lorenzo-client.js")>();
  return {
    ...actual,
    createLorenzoApiClient: createLorenzoApiClient.mockReturnValue({
      getControlledCharacters,
      getCharacterName,
      addGroupMember,
      listGroups,
    }),
  };
});

const { addToGroupCommand } = await import("../src/commands/add-to-group.js");

const config = {
  lorenzoApiBaseUrl: "http://lorenzo-api.test",
  lorenzoTenantId: "tenant-1",
} as Config;

function fakeInteraction() {
  return {
    user: { id: "discord-user-1" },
    options: {
      getString: vi.fn((name: string) => (name === "character" ? "char-1" : "The Fellowship")),
    },
    deferReply: vi.fn(async () => undefined),
    editReply: vi.fn(async () => undefined),
  } as unknown as ChatInputCommandInteraction & {
    options: { getString: ReturnType<typeof vi.fn> };
    deferReply: ReturnType<typeof vi.fn>;
    editReply: ReturnType<typeof vi.fn>;
  };
}

function fakeAutocomplete(focusedName: "character" | "group", value = "") {
  return {
    user: { id: "discord-user-1" },
    options: { getFocused: vi.fn(() => ({ name: focusedName, value })) },
    respond: vi.fn(async () => undefined),
  } as unknown as AutocompleteInteraction & { respond: ReturnType<typeof vi.fn> };
}

describe("addToGroupCommand.execute", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("prompts to /link when there's no valid access token", async () => {
    getValidAccessToken.mockResolvedValue(null);
    const interaction = fakeInteraction();

    await addToGroupCommand.execute(interaction, { config, logger: {} as never });

    expect(interaction.editReply).toHaveBeenCalledWith(
      expect.stringContaining("run `/link` first"),
    );
    expect(resolveOrCreateGroup).not.toHaveBeenCalled();
  });

  it("creates the group with the character as its first member when it doesn't exist yet", async () => {
    getValidAccessToken.mockResolvedValue("token-123");
    resolveOrCreateGroup.mockResolvedValue({
      group: { entityId: "group-1", name: "The Fellowship" },
      created: true,
    });
    getCharacterName.mockResolvedValue("Frodo");
    const interaction = fakeInteraction();

    await addToGroupCommand.execute(interaction, { config, logger: {} as never });

    expect(resolveOrCreateGroup).toHaveBeenCalledWith(
      expect.anything(),
      "tenant-1",
      "The Fellowship",
      "token-123",
      ["char-1"],
    );
    expect(addGroupMember).not.toHaveBeenCalled();
    expect(interaction.editReply).toHaveBeenCalledWith(
      'Created "The Fellowship" with Frodo as its first member.',
    );
  });

  it("adds the character to an existing group", async () => {
    getValidAccessToken.mockResolvedValue("token-123");
    resolveOrCreateGroup.mockResolvedValue({
      group: { entityId: "group-1", name: "The Fellowship" },
      created: false,
    });
    getCharacterName.mockResolvedValue("Frodo");
    const interaction = fakeInteraction();

    await addToGroupCommand.execute(interaction, { config, logger: {} as never });

    expect(addGroupMember).toHaveBeenCalledWith("tenant-1", "group-1", "char-1", "token-123");
    expect(interaction.editReply).toHaveBeenCalledWith('Added Frodo to "The Fellowship".');
  });

  it.each([
    [403, "you don't manage it"],
    [404, "Couldn't find that group"],
    [422, "Couldn't do that"],
  ])("gives a specific message for a %i error", async (status, expectedText) => {
    getValidAccessToken.mockResolvedValue("token-123");
    resolveOrCreateGroup.mockRejectedValue(new LorenzoApiError("boom", status));
    const interaction = fakeInteraction();

    await addToGroupCommand.execute(interaction, { config, logger: {} as never });

    expect(interaction.editReply).toHaveBeenCalledWith(expect.stringContaining(expectedText));
  });
});

describe("addToGroupCommand.autocomplete", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("unions the caller's own characters with the ones they GM", async () => {
    getValidAccessToken.mockResolvedValue("token-123");
    getControlledCharacters.mockResolvedValue([{ entityId: "char-1", name: "Frodo" }]);
    findGmControlledCharacters.mockResolvedValue([
      { entityId: "char-1", name: "Frodo" },
      { entityId: "char-2", name: "Sam" },
    ]);

    const interaction = fakeAutocomplete("character");
    await addToGroupCommand.autocomplete?.(interaction, { config, logger: {} as never });

    expect(interaction.respond).toHaveBeenCalledWith([
      { name: "Frodo", value: "char-1" },
      { name: "Sam", value: "char-2" },
    ]);
  });

  it("suggests existing group names", async () => {
    getValidAccessToken.mockResolvedValue("token-123");
    listGroups.mockResolvedValue([{ entityId: "group-1", name: "The Fellowship" }]);

    const interaction = fakeAutocomplete("group", "fellow");
    await addToGroupCommand.autocomplete?.(interaction, { config, logger: {} as never });

    expect(interaction.respond).toHaveBeenCalledWith([
      { name: "The Fellowship", value: "The Fellowship" },
    ]);
  });
});
