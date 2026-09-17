import { beforeEach, describe, expect, it, vi } from "vitest";
import type { ChatInputCommandInteraction } from "../src/commands/types.js";
import type { Config } from "../src/config.js";

const { getValidAccessToken } = vi.hoisted(() => ({ getValidAccessToken: vi.fn() }));
vi.mock("../src/token-provider.js", () => ({ getValidAccessToken }));

const { getControlledCharacters, getCharacterGroups, createLorenzoApiClient } = vi.hoisted(() => ({
  getControlledCharacters: vi.fn(),
  getCharacterGroups: vi.fn(),
  createLorenzoApiClient: vi.fn(),
}));
vi.mock("../src/lorenzo-client.js", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../src/lorenzo-client.js")>();
  return {
    ...actual,
    createLorenzoApiClient: createLorenzoApiClient.mockReturnValue({
      getControlledCharacters,
      getCharacterGroups,
    }),
  };
});

const { myGroupsCommand } = await import("../src/commands/my-groups.js");

const config = {
  lorenzoApiBaseUrl: "http://lorenzo-api.test",
  lorenzoTenantId: "tenant-1",
} as Config;

function fakeInteraction() {
  return {
    user: { id: "discord-user-1" },
    deferReply: vi.fn(async () => undefined),
    editReply: vi.fn(async () => undefined),
  } as unknown as ChatInputCommandInteraction & {
    deferReply: ReturnType<typeof vi.fn>;
    editReply: ReturnType<typeof vi.fn>;
  };
}

describe("myGroupsCommand.execute", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("prompts to /link when there's no valid access token", async () => {
    getValidAccessToken.mockResolvedValue(null);
    const interaction = fakeInteraction();

    await myGroupsCommand.execute(interaction, { config, logger: {} as never });

    expect(interaction.editReply).toHaveBeenCalledWith(
      expect.stringContaining("run `/link` first"),
    );
    expect(getCharacterGroups).not.toHaveBeenCalled();
  });

  it("tells the player they control no characters yet", async () => {
    getValidAccessToken.mockResolvedValue("token-123");
    getControlledCharacters.mockResolvedValue([]);
    const interaction = fakeInteraction();

    await myGroupsCommand.execute(interaction, { config, logger: {} as never });

    expect(interaction.editReply).toHaveBeenCalledWith(
      expect.stringContaining("don't control any characters"),
    );
  });

  it("lists each character's groups, in character order", async () => {
    getValidAccessToken.mockResolvedValue("token-123");
    getControlledCharacters.mockResolvedValue([
      { entityId: "char-1", name: "Frodo" },
      { entityId: "char-2", name: "Sam" },
    ]);
    getCharacterGroups.mockImplementation(async (_tenantId: string, characterId: string) =>
      characterId === "char-1" ? [{ entityId: "group-1", name: "The Fellowship" }] : [],
    );

    const interaction = fakeInteraction();
    await myGroupsCommand.execute(interaction, { config, logger: {} as never });

    const call = interaction.editReply.mock.calls[0]?.[0];
    expect(call.embeds[0].data.fields).toEqual([
      { name: "Frodo", value: "The Fellowship" },
      { name: "Sam", value: "No groups." },
    ]);
  });
});
