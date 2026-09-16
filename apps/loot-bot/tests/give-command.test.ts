import type { AutocompleteInteraction, ChatInputCommandInteraction } from "discord.js";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { Config } from "../src/config.js";
import { LorenzoApiError } from "../src/lorenzo-client.js";

const { getValidAccessToken } = vi.hoisted(() => ({ getValidAccessToken: vi.fn() }));
vi.mock("../src/token-provider.js", () => ({ getValidAccessToken }));

const {
  getMyPlayers,
  getMyItemInstances,
  getItemInstance,
  splitItemInstance,
  setItemInstanceOwner,
  getCampaignPlayers,
  getCharacterName,
  createLorenzoApiClient,
} = vi.hoisted(() => ({
  getMyPlayers: vi.fn(),
  getMyItemInstances: vi.fn(),
  getItemInstance: vi.fn(),
  splitItemInstance: vi.fn(),
  setItemInstanceOwner: vi.fn(),
  getCampaignPlayers: vi.fn(),
  getCharacterName: vi.fn(),
  createLorenzoApiClient: vi.fn(),
}));
vi.mock("../src/lorenzo-client.js", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../src/lorenzo-client.js")>();
  return {
    ...actual,
    createLorenzoApiClient: createLorenzoApiClient.mockReturnValue({
      getMyPlayers,
      getMyItemInstances,
      getItemInstance,
      splitItemInstance,
      setItemInstanceOwner,
      getCampaignPlayers,
      getCharacterName,
    }),
  };
});

const { giveCommand } = await import("../src/commands/give.js");

const config = {
  lorenzoApiBaseUrl: "http://lorenzo-api.test",
  lorenzoTenantId: "tenant-1",
} as Config;

function fakeInteraction(userId = "discord-user-1") {
  return {
    user: { id: userId },
    options: {
      getString: vi.fn(),
      getInteger: vi.fn(() => null),
    },
    deferReply: vi.fn(async () => undefined),
    editReply: vi.fn(async () => undefined),
  } as unknown as ChatInputCommandInteraction & {
    options: { getString: ReturnType<typeof vi.fn>; getInteger: ReturnType<typeof vi.fn> };
    deferReply: ReturnType<typeof vi.fn>;
    editReply: ReturnType<typeof vi.fn>;
  };
}

function fakeAutocomplete(
  focusedName: "item" | "to",
  focusedValue = "",
  itemValue: string | null = null,
) {
  return {
    user: { id: "discord-user-1" },
    options: {
      getFocused: vi.fn(() => ({ name: focusedName, value: focusedValue })),
      getString: vi.fn((name: string) => (name === "item" ? itemValue : null)),
    },
    respond: vi.fn(async () => undefined),
  } as unknown as AutocompleteInteraction & { respond: ReturnType<typeof vi.fn> };
}

describe("giveCommand.execute", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("prompts to /link when there's no valid access token", async () => {
    getValidAccessToken.mockResolvedValue(null);
    const interaction = fakeInteraction();

    await giveCommand.execute(interaction, { config, logger: {} as never });

    expect(interaction.editReply).toHaveBeenCalledWith(
      expect.stringContaining("run `/link` first"),
    );
    expect(getItemInstance).not.toHaveBeenCalled();
  });

  it("transfers the whole instance when no quantity is given", async () => {
    getValidAccessToken.mockResolvedValue("token-123");
    getItemInstance.mockResolvedValue({
      data: { entity_id: "item-1", quantity: 5, title: "Torch" },
      etag: "etag-1",
    });
    setItemInstanceOwner.mockResolvedValue({ entity_id: "item-1", title: "Torch" });
    getCharacterName.mockResolvedValue("Frodo");

    const interaction = fakeInteraction();
    interaction.options.getString.mockImplementation((name: string) =>
      name === "item" ? "item-1" : "char-2",
    );

    await giveCommand.execute(interaction, { config, logger: {} as never });

    expect(splitItemInstance).not.toHaveBeenCalled();
    expect(setItemInstanceOwner).toHaveBeenCalledWith(
      "tenant-1",
      "item-1",
      "char-2",
      "token-123",
      "etag-1",
    );
    expect(interaction.editReply).toHaveBeenCalledWith("Gave Torch to Frodo.");
  });

  it("splits off the requested quantity and transfers only the split, for a partial give", async () => {
    getValidAccessToken.mockResolvedValue("token-123");
    getItemInstance.mockResolvedValue({
      data: { entity_id: "item-1", quantity: 5, title: "Torch" },
      etag: "etag-1",
    });
    splitItemInstance.mockResolvedValue({
      data: { entity_id: "item-2", quantity: 2, title: "Torch" },
      etag: "etag-2",
    });
    setItemInstanceOwner.mockResolvedValue({ entity_id: "item-2", title: "Torch" });
    getCharacterName.mockResolvedValue("Sam");

    const interaction = fakeInteraction();
    interaction.options.getString.mockImplementation((name: string) =>
      name === "item" ? "item-1" : "char-2",
    );
    interaction.options.getInteger.mockReturnValue(2);

    await giveCommand.execute(interaction, { config, logger: {} as never });

    expect(splitItemInstance).toHaveBeenCalledWith("tenant-1", "item-1", 2, "token-123", "etag-1");
    expect(setItemInstanceOwner).toHaveBeenCalledWith(
      "tenant-1",
      "item-2",
      "char-2",
      "token-123",
      "etag-2",
    );
    expect(interaction.editReply).toHaveBeenCalledWith("Gave 2 of Torch to Sam.");
  });

  it("transfers the whole stack outright when quantity covers all of it", async () => {
    getValidAccessToken.mockResolvedValue("token-123");
    getItemInstance.mockResolvedValue({
      data: { entity_id: "item-1", quantity: 5, title: "Torch" },
      etag: "etag-1",
    });
    setItemInstanceOwner.mockResolvedValue({ entity_id: "item-1", title: "Torch" });
    getCharacterName.mockResolvedValue("Sam");

    const interaction = fakeInteraction();
    interaction.options.getString.mockImplementation((name: string) =>
      name === "item" ? "item-1" : "char-2",
    );
    interaction.options.getInteger.mockReturnValue(5);

    await giveCommand.execute(interaction, { config, logger: {} as never });

    expect(splitItemInstance).not.toHaveBeenCalled();
    expect(setItemInstanceOwner).toHaveBeenCalledWith(
      "tenant-1",
      "item-1",
      "char-2",
      "token-123",
      "etag-1",
    );
  });

  it("rejects a quantity for an item that isn't a stack, before calling the API", async () => {
    getValidAccessToken.mockResolvedValue("token-123");
    getItemInstance.mockResolvedValue({
      data: { entity_id: "item-1", quantity: null, title: "Sword" },
      etag: "etag-1",
    });

    const interaction = fakeInteraction();
    interaction.options.getString.mockImplementation((name: string) =>
      name === "item" ? "item-1" : "char-2",
    );
    interaction.options.getInteger.mockReturnValue(1);

    await giveCommand.execute(interaction, { config, logger: {} as never });

    expect(interaction.editReply).toHaveBeenCalledWith(expect.stringContaining("isn't a stack"));
    expect(splitItemInstance).not.toHaveBeenCalled();
    expect(setItemInstanceOwner).not.toHaveBeenCalled();
  });

  it.each([
    [403, "reachable from any of your characters"],
    [404, "Couldn't find that item"],
    [422, "Couldn't do that"],
  ])("gives a specific message for a %i error", async (status, expectedText) => {
    getValidAccessToken.mockResolvedValue("token-123");
    getItemInstance.mockRejectedValue(new LorenzoApiError("boom", status));

    const interaction = fakeInteraction();
    interaction.options.getString.mockImplementation((name: string) =>
      name === "item" ? "item-1" : "char-2",
    );

    await giveCommand.execute(interaction, { config, logger: {} as never });

    expect(interaction.editReply).toHaveBeenCalledWith(expect.stringContaining(expectedText));
  });

  it("still succeeds even if the friendly-name lookup fails", async () => {
    getValidAccessToken.mockResolvedValue("token-123");
    getItemInstance.mockResolvedValue({
      data: { entity_id: "item-1", quantity: null, title: "Sword" },
      etag: "etag-1",
    });
    setItemInstanceOwner.mockResolvedValue({ entity_id: "item-1", title: "Sword" });
    getCharacterName.mockRejectedValue(new LorenzoApiError("not found", 404));

    const interaction = fakeInteraction();
    interaction.options.getString.mockImplementation((name: string) =>
      name === "item" ? "item-1" : "char-2",
    );

    await giveCommand.execute(interaction, { config, logger: {} as never });

    expect(interaction.editReply).toHaveBeenCalledWith("Gave Sword to them.");
  });

  it("tells the caller to retry when the write 412s on a stale etag", async () => {
    getValidAccessToken.mockResolvedValue("token-123");
    getItemInstance.mockResolvedValue({
      data: { entity_id: "item-1", quantity: null, title: "Sword" },
      etag: "etag-1",
    });
    setItemInstanceOwner.mockRejectedValue(new LorenzoApiError("stale", 412));

    const interaction = fakeInteraction();
    interaction.options.getString.mockImplementation((name: string) =>
      name === "item" ? "item-1" : "char-2",
    );

    await giveCommand.execute(interaction, { config, logger: {} as never });

    expect(interaction.editReply).toHaveBeenCalledWith(
      expect.stringContaining("Someone else changed that item"),
    );
  });
});

describe("giveCommand.autocomplete", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("responds with no choices when there's no valid access token", async () => {
    getValidAccessToken.mockResolvedValue(null);
    const interaction = fakeAutocomplete("item");

    await giveCommand.autocomplete?.(interaction, { config, logger: {} as never });

    expect(interaction.respond).toHaveBeenCalledWith([]);
  });

  it("suggests the caller's own items, across every controlled character", async () => {
    getValidAccessToken.mockResolvedValue("token-123");
    getMyItemInstances.mockResolvedValue([
      { entityId: "item-1", title: "Torch", quantity: 5 },
      { entityId: "item-2", title: "Sword", quantity: null },
    ]);

    const interaction = fakeAutocomplete("item", "tor");
    await giveCommand.autocomplete?.(interaction, { config, logger: {} as never });

    expect(interaction.respond).toHaveBeenCalledWith([{ name: "Torch ×5", value: "item-1" }]);
  });

  it("suggests characters from the chosen item's own campaign for 'to'", async () => {
    getValidAccessToken.mockResolvedValue("token-123");
    getMyPlayers.mockResolvedValue([
      { campaignId: "campaign-1", characters: [{ entityId: "char-1", name: "Frodo" }] },
      { campaignId: "campaign-2", characters: [{ entityId: "char-3", name: "Bilbo" }] },
    ]);
    getItemInstance.mockResolvedValue({
      data: { entity_id: "item-1", owner_entity_id: "char-1" },
      etag: null,
    });
    getCampaignPlayers.mockResolvedValue([
      { entityId: "char-1", name: "Frodo" },
      { entityId: "char-2", name: "Sam" },
    ]);

    const interaction = fakeAutocomplete("to", "", "item-1");
    await giveCommand.autocomplete?.(interaction, { config, logger: {} as never });

    expect(getCampaignPlayers).toHaveBeenCalledWith("tenant-1", "campaign-1", "token-123");
    expect(interaction.respond).toHaveBeenCalledWith([
      { name: "Frodo", value: "char-1" },
      { name: "Sam", value: "char-2" },
    ]);
  });
});
