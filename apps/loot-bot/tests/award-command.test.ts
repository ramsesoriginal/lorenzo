import { beforeEach, describe, expect, it, vi } from "vitest";
import type {
  AutocompleteInteraction,
  ChatInputCommandInteraction,
} from "../src/commands/types.js";
import type { Config } from "../src/config.js";
import { LorenzoApiError } from "../src/lorenzo-client.js";

const { getValidAccessToken } = vi.hoisted(() => ({ getValidAccessToken: vi.fn() }));
vi.mock("../src/token-provider.js", () => ({ getValidAccessToken }));

const {
  isCampaignGm,
  getGmCampaignIds,
  listItems,
  getCampaignPlayers,
  createItemInstance,
  getCharacterName,
  createLorenzoApiClient,
} = vi.hoisted(() => ({
  isCampaignGm: vi.fn(),
  getGmCampaignIds: vi.fn(),
  listItems: vi.fn(),
  getCampaignPlayers: vi.fn(),
  createItemInstance: vi.fn(),
  getCharacterName: vi.fn(),
  createLorenzoApiClient: vi.fn(),
}));
vi.mock("../src/lorenzo-client.js", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../src/lorenzo-client.js")>();
  return {
    ...actual,
    createLorenzoApiClient: createLorenzoApiClient.mockReturnValue({
      isCampaignGm,
      getGmCampaignIds,
      listItems,
      getCampaignPlayers,
      createItemInstance,
      getCharacterName,
    }),
  };
});

const { awardCommand } = await import("../src/commands/award.js");

const config = {
  lorenzoApiBaseUrl: "http://lorenzo-api.test",
  lorenzoTenantId: "tenant-1",
} as Config;

function fakeInteraction(userId = "gm-1") {
  return {
    user: { id: userId },
    options: { getString: vi.fn() },
    deferReply: vi.fn(async () => undefined),
    editReply: vi.fn(async () => undefined),
  } as unknown as ChatInputCommandInteraction & {
    options: { getString: ReturnType<typeof vi.fn> };
    deferReply: ReturnType<typeof vi.fn>;
    editReply: ReturnType<typeof vi.fn>;
  };
}

function fakeAutocomplete(focusedName: "item" | "character", focusedValue = "") {
  return {
    user: { id: "gm-1" },
    options: { getFocused: vi.fn(() => ({ name: focusedName, value: focusedValue })) },
    respond: vi.fn(async () => undefined),
  } as unknown as AutocompleteInteraction & { respond: ReturnType<typeof vi.fn> };
}

describe("awardCommand.execute", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("prompts to /link when there's no valid access token", async () => {
    getValidAccessToken.mockResolvedValue(null);
    const interaction = fakeInteraction();

    await awardCommand.execute(interaction, { config, logger: {} as never });

    expect(interaction.editReply).toHaveBeenCalledWith(
      expect.stringContaining("run `/link` first"),
    );
    expect(createItemInstance).not.toHaveBeenCalled();
  });

  it("rejects a non-GM", async () => {
    getValidAccessToken.mockResolvedValue("token-123");
    isCampaignGm.mockResolvedValue(false);
    const interaction = fakeInteraction();

    await awardCommand.execute(interaction, { config, logger: {} as never });

    expect(interaction.editReply).toHaveBeenCalledWith(expect.stringContaining("Only a GM"));
    expect(createItemInstance).not.toHaveBeenCalled();
  });

  it("awards the item and confirms with the character's name", async () => {
    getValidAccessToken.mockResolvedValue("token-123");
    isCampaignGm.mockResolvedValue(true);
    createItemInstance.mockResolvedValue({
      entity_id: "item-1",
      title: "Sword",
      owner_entity_id: "char-1",
    });
    getCharacterName.mockResolvedValue("Frodo");
    const interaction = fakeInteraction();
    interaction.options.getString.mockImplementation((name: string) =>
      name === "item" ? "prototype-1" : "char-1",
    );

    await awardCommand.execute(interaction, { config, logger: {} as never });

    expect(createItemInstance).toHaveBeenCalledWith(
      "tenant-1",
      "prototype-1",
      "char-1",
      undefined,
      "token-123",
    );
    expect(interaction.editReply).toHaveBeenCalledWith("Awarded Sword to Frodo.");
  });

  it("still succeeds even if the friendly-name lookup fails", async () => {
    getValidAccessToken.mockResolvedValue("token-123");
    isCampaignGm.mockResolvedValue(true);
    createItemInstance.mockResolvedValue({
      entity_id: "item-1",
      title: "Sword",
      owner_entity_id: "char-1",
    });
    getCharacterName.mockRejectedValue(new LorenzoApiError("not found", 404));
    const interaction = fakeInteraction();
    interaction.options.getString.mockImplementation((name: string) =>
      name === "item" ? "prototype-1" : "char-1",
    );

    await awardCommand.execute(interaction, { config, logger: {} as never });

    expect(interaction.editReply).toHaveBeenCalledWith("Awarded Sword to them.");
  });

  it.each([
    [403, "not a GM of any campaign"],
    [404, "Couldn't find that item"],
    [422, "Couldn't do that"],
  ])("gives a specific message for a %i error", async (status, expectedText) => {
    getValidAccessToken.mockResolvedValue("token-123");
    isCampaignGm.mockResolvedValue(true);
    createItemInstance.mockRejectedValue(new LorenzoApiError("boom", status));
    const interaction = fakeInteraction();
    interaction.options.getString.mockImplementation((name: string) =>
      name === "item" ? "prototype-1" : "char-1",
    );

    await awardCommand.execute(interaction, { config, logger: {} as never });

    expect(interaction.editReply).toHaveBeenCalledWith(expect.stringContaining(expectedText));
  });
});

describe("awardCommand.autocomplete", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("responds with no choices when there's no valid access token", async () => {
    getValidAccessToken.mockResolvedValue(null);
    const interaction = fakeAutocomplete("item");

    await awardCommand.autocomplete?.(interaction, { config, logger: {} as never });

    expect(interaction.respond).toHaveBeenCalledWith([]);
  });

  it("suggests items from the catalog", async () => {
    getValidAccessToken.mockResolvedValue("token-123");
    listItems.mockResolvedValue([
      { entity_id: "item-1", title: "Sword" },
      { entity_id: "item-2", title: "Shield" },
    ]);

    const interaction = fakeAutocomplete("item", "sw");
    await awardCommand.autocomplete?.(interaction, { config, logger: {} as never });

    expect(interaction.respond).toHaveBeenCalledWith([{ name: "Sword", value: "item-1" }]);
  });

  it("suggests characters from every campaign the caller GMs, deduplicated", async () => {
    getValidAccessToken.mockResolvedValue("token-123");
    getGmCampaignIds.mockResolvedValue(["campaign-1", "campaign-2"]);
    getCampaignPlayers.mockImplementation(async (_tenantId: string, campaignId: string) =>
      campaignId === "campaign-1"
        ? [{ entityId: "char-1", name: "Frodo" }]
        : [
            { entityId: "char-1", name: "Frodo" },
            { entityId: "char-2", name: "Sam" },
          ],
    );

    const interaction = fakeAutocomplete("character", "");
    await awardCommand.autocomplete?.(interaction, { config, logger: {} as never });

    expect(interaction.respond).toHaveBeenCalledWith([
      { name: "Frodo", value: "char-1" },
      { name: "Sam", value: "char-2" },
    ]);
  });

  it("skips a campaign whose roster lookup fails rather than failing the whole request", async () => {
    getValidAccessToken.mockResolvedValue("token-123");
    getGmCampaignIds.mockResolvedValue(["campaign-1", "other-tenant-campaign"]);
    getCampaignPlayers.mockImplementation(async (_tenantId: string, campaignId: string) => {
      if (campaignId === "other-tenant-campaign") throw new LorenzoApiError("not found", 404);
      return [{ entityId: "char-1", name: "Frodo" }];
    });

    const interaction = fakeAutocomplete("character", "");
    await awardCommand.autocomplete?.(interaction, { config, logger: {} as never });

    expect(interaction.respond).toHaveBeenCalledWith([{ name: "Frodo", value: "char-1" }]);
  });
});
