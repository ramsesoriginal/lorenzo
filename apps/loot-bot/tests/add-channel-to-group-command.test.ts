import { beforeEach, describe, expect, it, vi } from "vitest";
import type {
  AutocompleteInteraction,
  ChatInputCommandInteraction,
} from "../src/commands/types.js";
import type { Config } from "../src/config.js";
import { LorenzoApiError } from "../src/lorenzo-client.js";

const { getValidAccessToken } = vi.hoisted(() => ({ getValidAccessToken: vi.fn() }));
vi.mock("../src/token-provider.js", () => ({ getValidAccessToken }));

const { getRecentChannelAuthorIds } = vi.hoisted(() => ({
  getRecentChannelAuthorIds: vi.fn(),
}));
vi.mock("../src/discord-rest.js", () => ({ getRecentChannelAuthorIds }));

const { resolveOrCreateGroup } = vi.hoisted(() => ({ resolveOrCreateGroup: vi.fn() }));
vi.mock("../src/commands/group-lookup.js", () => ({ resolveOrCreateGroup }));

const {
  isCampaignGm,
  getControlledCharacters,
  bulkAddGroupMembers,
  listGroups,
  createLorenzoApiClient,
} = vi.hoisted(() => ({
  isCampaignGm: vi.fn(),
  getControlledCharacters: vi.fn(),
  bulkAddGroupMembers: vi.fn(),
  listGroups: vi.fn(),
  createLorenzoApiClient: vi.fn(),
}));
vi.mock("../src/lorenzo-client.js", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../src/lorenzo-client.js")>();
  return {
    ...actual,
    createLorenzoApiClient: createLorenzoApiClient.mockReturnValue({
      isCampaignGm,
      getControlledCharacters,
      bulkAddGroupMembers,
      listGroups,
    }),
  };
});

const { addChannelToGroupCommand } = await import("../src/commands/add-channel-to-group.js");

const config = {
  lorenzoApiBaseUrl: "http://lorenzo-api.test",
  lorenzoTenantId: "tenant-1",
  discordBotToken: "bot-token-abc",
} as Config;

function fakeInteraction(channelId = "channel-1") {
  return {
    user: { id: "gm-1" },
    channelId,
    options: { getString: vi.fn(() => "The Fellowship") },
    deferReply: vi.fn(async () => undefined),
    editReply: vi.fn(async () => undefined),
  } as unknown as ChatInputCommandInteraction & {
    options: { getString: ReturnType<typeof vi.fn> };
    deferReply: ReturnType<typeof vi.fn>;
    editReply: ReturnType<typeof vi.fn>;
  };
}

function fakeAutocomplete(value = "") {
  return {
    user: { id: "gm-1" },
    options: { getFocused: vi.fn(() => ({ name: "group", value })) },
    respond: vi.fn(async () => undefined),
  } as unknown as AutocompleteInteraction & { respond: ReturnType<typeof vi.fn> };
}

describe("addChannelToGroupCommand.execute", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("prompts to /link when there's no valid access token", async () => {
    getValidAccessToken.mockResolvedValue(null);
    const interaction = fakeInteraction();

    await addChannelToGroupCommand.execute(interaction, { config, logger: {} as never });

    expect(interaction.editReply).toHaveBeenCalledWith(
      expect.stringContaining("run `/link` first"),
    );
    expect(getRecentChannelAuthorIds).not.toHaveBeenCalled();
  });

  it("rejects a non-GM", async () => {
    getValidAccessToken.mockResolvedValue("gm-token");
    isCampaignGm.mockResolvedValue(false);
    const interaction = fakeInteraction();

    await addChannelToGroupCommand.execute(interaction, { config, logger: {} as never });

    expect(interaction.editReply).toHaveBeenCalledWith(expect.stringContaining("Only a GM"));
    expect(getRecentChannelAuthorIds).not.toHaveBeenCalled();
  });

  it("gives a friendly message when reading channel history fails", async () => {
    getValidAccessToken.mockResolvedValue("gm-token");
    isCampaignGm.mockResolvedValue(true);
    getRecentChannelAuthorIds.mockRejectedValue(new Error("403"));
    const interaction = fakeInteraction();

    await addChannelToGroupCommand.execute(interaction, { config, logger: {} as never });

    expect(interaction.editReply).toHaveBeenCalledWith(
      expect.stringContaining("Read Message History"),
    );
  });

  it("resolves each poster's own characters using their own stored token, not the GM's", async () => {
    getValidAccessToken.mockImplementation(async (discordUserId: string) => {
      if (discordUserId === "gm-1") return "gm-token";
      if (discordUserId === "user-a") return "user-a-token";
      return null; // user-b never linked
    });
    isCampaignGm.mockResolvedValue(true);
    getRecentChannelAuthorIds.mockResolvedValue(["user-a", "user-b"]);
    getControlledCharacters.mockImplementation(async (_tenantId: string, token: string) =>
      token === "user-a-token" ? [{ entityId: "char-a", name: "Frodo" }] : [],
    );
    resolveOrCreateGroup.mockResolvedValue({
      group: { entityId: "group-1", name: "The Fellowship" },
      created: false,
    });
    bulkAddGroupMembers.mockResolvedValue([{ character_entity_id: "char-a", status: "ok" }]);
    const interaction = fakeInteraction();

    await addChannelToGroupCommand.execute(interaction, { config, logger: {} as never });

    expect(getControlledCharacters).toHaveBeenCalledWith("tenant-1", "user-a-token");
    expect(getControlledCharacters).not.toHaveBeenCalledWith("tenant-1", "gm-token");
    expect(resolveOrCreateGroup).toHaveBeenCalledWith(
      expect.anything(),
      "tenant-1",
      "The Fellowship",
      "gm-token",
      ["char-a"],
    );
    expect(bulkAddGroupMembers).toHaveBeenCalledWith("tenant-1", "group-1", ["char-a"], "gm-token");
    expect(interaction.editReply).toHaveBeenCalledWith('Added 1 character to "The Fellowship".');
  });

  it("creates the group directly with every resolved character when it doesn't exist yet", async () => {
    getValidAccessToken.mockImplementation(async (discordUserId: string) =>
      discordUserId === "gm-1" ? "gm-token" : "user-token",
    );
    isCampaignGm.mockResolvedValue(true);
    getRecentChannelAuthorIds.mockResolvedValue(["user-a"]);
    getControlledCharacters.mockResolvedValue([{ entityId: "char-a", name: "Frodo" }]);
    resolveOrCreateGroup.mockResolvedValue({
      group: { entityId: "group-1", name: "The Fellowship" },
      created: true,
    });
    const interaction = fakeInteraction();

    await addChannelToGroupCommand.execute(interaction, { config, logger: {} as never });

    expect(bulkAddGroupMembers).not.toHaveBeenCalled();
    expect(interaction.editReply).toHaveBeenCalledWith(
      'Created "The Fellowship" with 1 character.',
    );
  });

  it("tells the caller when nobody recently active has any linked characters", async () => {
    getValidAccessToken.mockImplementation(async (discordUserId: string) =>
      discordUserId === "gm-1" ? "gm-token" : null,
    );
    isCampaignGm.mockResolvedValue(true);
    getRecentChannelAuthorIds.mockResolvedValue(["user-a", "user-b"]);
    const interaction = fakeInteraction();

    await addChannelToGroupCommand.execute(interaction, { config, logger: {} as never });

    expect(resolveOrCreateGroup).not.toHaveBeenCalled();
    expect(interaction.editReply).toHaveBeenCalledWith(
      expect.stringContaining("No linked characters found"),
    );
  });

  it("surfaces an API error from the group write", async () => {
    getValidAccessToken.mockImplementation(async (discordUserId: string) =>
      discordUserId === "gm-1" ? "gm-token" : "user-token",
    );
    isCampaignGm.mockResolvedValue(true);
    getRecentChannelAuthorIds.mockResolvedValue(["user-a"]);
    getControlledCharacters.mockResolvedValue([{ entityId: "char-a", name: "Frodo" }]);
    resolveOrCreateGroup.mockRejectedValue(new LorenzoApiError("boom", 422));
    const interaction = fakeInteraction();

    await addChannelToGroupCommand.execute(interaction, { config, logger: {} as never });

    expect(interaction.editReply).toHaveBeenCalledWith(expect.stringContaining("Couldn't do that"));
  });
});

describe("addChannelToGroupCommand.autocomplete", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("suggests existing group names", async () => {
    getValidAccessToken.mockResolvedValue("gm-token");
    listGroups.mockResolvedValue([{ entityId: "group-1", name: "The Fellowship" }]);

    const interaction = fakeAutocomplete("fellow");
    await addChannelToGroupCommand.autocomplete?.(interaction, { config, logger: {} as never });

    expect(interaction.respond).toHaveBeenCalledWith([
      { name: "The Fellowship", value: "The Fellowship" },
    ]);
  });
});
