import { beforeEach, describe, expect, it, vi } from "vitest";
import type {
  AutocompleteInteraction,
  ChatInputCommandInteraction,
} from "../src/commands/types.js";
import type { Config } from "../src/config.js";

const { getValidAccessToken } = vi.hoisted(() => ({ getValidAccessToken: vi.fn() }));
vi.mock("../src/token-provider.js", () => ({ getValidAccessToken }));

const {
  isCampaignGm,
  getGmCampaignIds,
  getCampaignPlayers,
  getCharacterName,
  getItemInstancesOwnedBy,
  createLorenzoApiClient,
} = vi.hoisted(() => ({
  isCampaignGm: vi.fn(),
  getGmCampaignIds: vi.fn(),
  getCampaignPlayers: vi.fn(),
  getCharacterName: vi.fn(),
  getItemInstancesOwnedBy: vi.fn(),
  createLorenzoApiClient: vi.fn(),
}));
vi.mock("../src/lorenzo-client.js", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../src/lorenzo-client.js")>();
  return {
    ...actual,
    createLorenzoApiClient: createLorenzoApiClient.mockReturnValue({
      isCampaignGm,
      getGmCampaignIds,
      getCampaignPlayers,
      getCharacterName,
      getItemInstancesOwnedBy,
    }),
  };
});

const { inspectCommand } = await import("../src/commands/inspect.js");

const config = {
  lorenzoApiBaseUrl: "http://lorenzo-api.test",
  lorenzoTenantId: "tenant-1",
} as Config;

function fakeInteraction(userId = "gm-1") {
  return {
    user: { id: userId },
    options: { getString: vi.fn(() => "char-1") },
    deferReply: vi.fn(async () => undefined),
    editReply: vi.fn(async () => undefined),
  } as unknown as ChatInputCommandInteraction & {
    options: { getString: ReturnType<typeof vi.fn> };
    deferReply: ReturnType<typeof vi.fn>;
    editReply: ReturnType<typeof vi.fn>;
  };
}

function fakeAutocomplete(focusedValue = "") {
  return {
    user: { id: "gm-1" },
    options: {
      getFocused: vi.fn(() => ({ name: "character", value: focusedValue })),
      getString: vi.fn(() => null),
    },
    respond: vi.fn(async () => undefined),
  } as unknown as AutocompleteInteraction & { respond: ReturnType<typeof vi.fn> };
}

describe("inspectCommand.execute", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("prompts to /link when there's no valid access token", async () => {
    getValidAccessToken.mockResolvedValue(null);
    const interaction = fakeInteraction();

    await inspectCommand.execute(interaction, { config, logger: {} as never });

    expect(interaction.editReply).toHaveBeenCalledWith(
      expect.stringContaining("run `/link` first"),
    );
    expect(getItemInstancesOwnedBy).not.toHaveBeenCalled();
  });

  it("rejects a non-GM", async () => {
    getValidAccessToken.mockResolvedValue("token-123");
    isCampaignGm.mockResolvedValue(false);
    const interaction = fakeInteraction();

    await inspectCommand.execute(interaction, { config, logger: {} as never });

    expect(interaction.editReply).toHaveBeenCalledWith(expect.stringContaining("Only a GM"));
    expect(getItemInstancesOwnedBy).not.toHaveBeenCalled();
  });

  it("shows the chosen character's inventory as one embed", async () => {
    getValidAccessToken.mockResolvedValue("gm-token");
    isCampaignGm.mockResolvedValue(true);
    getCharacterName.mockResolvedValue("Frodo");
    getItemInstancesOwnedBy.mockResolvedValue({
      groups: [{ container: null, item_instances: [{ entity_id: "item-1", title: "Ring" }] }],
    });
    const interaction = fakeInteraction();

    await inspectCommand.execute(interaction, { config, logger: {} as never });

    expect(getItemInstancesOwnedBy).toHaveBeenCalledWith("tenant-1", "char-1", "gm-token");
    const call = interaction.editReply.mock.calls[0]?.[0];
    expect(call.embeds).toHaveLength(1);
    expect(call.embeds[0].data.title).toBe("Frodo");
  });

  it("still succeeds even if the friendly-name lookup fails", async () => {
    getValidAccessToken.mockResolvedValue("gm-token");
    isCampaignGm.mockResolvedValue(true);
    getCharacterName.mockRejectedValue(new Error("boom"));
    getItemInstancesOwnedBy.mockResolvedValue({ groups: [] });
    const interaction = fakeInteraction();

    await inspectCommand.execute(interaction, { config, logger: {} as never });

    const call = interaction.editReply.mock.calls[0]?.[0];
    expect(call.embeds[0].data.title).toBe("that character");
  });
});

describe("inspectCommand.autocomplete", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("responds with no choices when there's no valid access token", async () => {
    getValidAccessToken.mockResolvedValue(null);
    const interaction = fakeAutocomplete();

    await inspectCommand.autocomplete?.(interaction, { config, logger: {} as never });

    expect(interaction.respond).toHaveBeenCalledWith([]);
  });

  it("suggests every character in a campaign the caller GMs", async () => {
    getValidAccessToken.mockResolvedValue("gm-token");
    getGmCampaignIds.mockResolvedValue(["campaign-1"]);
    getCampaignPlayers.mockResolvedValue([{ entityId: "char-1", name: "Frodo" }]);

    const interaction = fakeAutocomplete("fro");
    await inspectCommand.autocomplete?.(interaction, { config, logger: {} as never });

    expect(interaction.respond).toHaveBeenCalledWith([{ name: "Frodo", value: "char-1" }]);
  });
});
