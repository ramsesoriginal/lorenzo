import { beforeEach, describe, expect, it, vi } from "vitest";
import type {
  AutocompleteInteraction,
  ChatInputCommandInteraction,
} from "../src/commands/types.js";
import type { Config } from "../src/config.js";
import { LorenzoApiError } from "../src/lorenzo-client.js";

const { getValidAccessToken } = vi.hoisted(() => ({ getValidAccessToken: vi.fn() }));
vi.mock("../src/token-provider.js", () => ({ getValidAccessToken }));

const { recordCharacterEvents } = vi.hoisted(() => ({ recordCharacterEvents: vi.fn() }));
vi.mock("../src/character-events.js", async (importOriginal) => ({
  ...(await importOriginal<typeof import("../src/character-events.js")>()),
  recordCharacterEvents,
}));

const {
  isCampaignGm,
  getGmCampaignIds,
  getCampaignPlayers,
  getCharacterName,
  getItemInstancesOwnedBy,
  getItemInstance,
  splitItemInstance,
  deleteItemInstance,
  createLorenzoApiClient,
} = vi.hoisted(() => ({
  isCampaignGm: vi.fn(),
  getGmCampaignIds: vi.fn(),
  getCampaignPlayers: vi.fn(),
  getCharacterName: vi.fn(),
  getItemInstancesOwnedBy: vi.fn(),
  getItemInstance: vi.fn(),
  splitItemInstance: vi.fn(),
  deleteItemInstance: vi.fn(),
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
      getItemInstance,
      splitItemInstance,
      deleteItemInstance,
    }),
  };
});

const { confiscateCommand } = await import("../src/commands/confiscate.js");

const config = {
  lorenzoApiBaseUrl: "http://lorenzo-api.test",
  lorenzoTenantId: "tenant-1",
} as Config;

function fakeInteraction(userId = "gm-1") {
  return {
    user: { id: userId },
    options: {
      getString: vi.fn((name: string) => (name === "character" ? "char-1" : "item-1")),
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
  focusedName: "character" | "item",
  focusedValue = "",
  characterValue: string | null = null,
) {
  return {
    user: { id: "gm-1" },
    options: {
      getFocused: vi.fn(() => ({ name: focusedName, value: focusedValue })),
      getString: vi.fn((name: string) => (name === "character" ? characterValue : null)),
    },
    respond: vi.fn(async () => undefined),
  } as unknown as AutocompleteInteraction & { respond: ReturnType<typeof vi.fn> };
}

describe("confiscateCommand.execute", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("prompts to /link when there's no valid access token", async () => {
    getValidAccessToken.mockResolvedValue(null);
    const interaction = fakeInteraction();

    await confiscateCommand.execute(interaction, { config, logger: {} as never });

    expect(interaction.editReply).toHaveBeenCalledWith(
      expect.stringContaining("run `/link` first"),
    );
    expect(getItemInstance).not.toHaveBeenCalled();
  });

  it("rejects a non-GM", async () => {
    getValidAccessToken.mockResolvedValue("token-123");
    isCampaignGm.mockResolvedValue(false);
    const interaction = fakeInteraction();

    await confiscateCommand.execute(interaction, { config, logger: {} as never });

    expect(interaction.editReply).toHaveBeenCalledWith(expect.stringContaining("Only a GM"));
    expect(getItemInstance).not.toHaveBeenCalled();
  });

  it("destroys the whole instance when no quantity is given", async () => {
    getValidAccessToken.mockResolvedValue("gm-token");
    isCampaignGm.mockResolvedValue(true);
    getItemInstance.mockResolvedValue({
      data: { entity_id: "item-1", quantity: null, title: "Sword" },
      etag: "etag-1",
    });
    getCharacterName.mockResolvedValue("Frodo");
    const interaction = fakeInteraction();

    await confiscateCommand.execute(interaction, { config, logger: {} as never });

    expect(deleteItemInstance).toHaveBeenCalledWith("tenant-1", "item-1", "gm-token", "etag-1");
    expect(splitItemInstance).not.toHaveBeenCalled();
    expect(interaction.editReply).toHaveBeenCalledWith("Confiscated Sword from Frodo.");
  });

  it("splits off and destroys just the requested amount from a stack", async () => {
    getValidAccessToken.mockResolvedValue("gm-token");
    isCampaignGm.mockResolvedValue(true);
    getItemInstance.mockResolvedValue({
      data: { entity_id: "item-1", quantity: 5, title: "Arrows" },
      etag: "etag-1",
    });
    splitItemInstance.mockResolvedValue({
      data: { entity_id: "item-2", quantity: 2, title: "Arrows" },
      etag: "etag-2",
    });
    getCharacterName.mockResolvedValue("Frodo");
    const interaction = fakeInteraction();
    interaction.options.getInteger.mockReturnValue(2);

    await confiscateCommand.execute(interaction, { config, logger: {} as never });

    expect(splitItemInstance).toHaveBeenCalledWith("tenant-1", "item-1", 2, "gm-token", "etag-1");
    expect(deleteItemInstance).toHaveBeenCalledWith("tenant-1", "item-2", "gm-token");
    expect(interaction.editReply).toHaveBeenCalledWith("Confiscated 2 of Arrows from Frodo.");
  });

  it("rejects a quantity for an item that isn't a stack, before calling the API", async () => {
    getValidAccessToken.mockResolvedValue("gm-token");
    isCampaignGm.mockResolvedValue(true);
    getItemInstance.mockResolvedValue({
      data: { entity_id: "item-1", quantity: null, title: "Sword" },
      etag: "etag-1",
    });
    const interaction = fakeInteraction();
    interaction.options.getInteger.mockReturnValue(1);

    await confiscateCommand.execute(interaction, { config, logger: {} as never });

    expect(interaction.editReply).toHaveBeenCalledWith(expect.stringContaining("isn't a stack"));
    expect(deleteItemInstance).not.toHaveBeenCalled();
  });

  it.each([
    [403, "reachable from any campaign you GM"],
    [404, "Couldn't find that item"],
    [422, "Couldn't do that"],
  ])("gives a specific message for a %i error", async (status, expectedText) => {
    getValidAccessToken.mockResolvedValue("gm-token");
    isCampaignGm.mockResolvedValue(true);
    getItemInstance.mockRejectedValue(new LorenzoApiError("boom", status));
    const interaction = fakeInteraction();

    await confiscateCommand.execute(interaction, { config, logger: {} as never });

    expect(interaction.editReply).toHaveBeenCalledWith(expect.stringContaining(expectedText));
  });
});

describe("confiscateCommand.autocomplete", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("responds with no choices when there's no valid access token", async () => {
    getValidAccessToken.mockResolvedValue(null);
    const interaction = fakeAutocomplete("character");

    await confiscateCommand.autocomplete?.(interaction, { config, logger: {} as never });

    expect(interaction.respond).toHaveBeenCalledWith([]);
  });

  it("suggests every character in a campaign the caller GMs", async () => {
    getValidAccessToken.mockResolvedValue("gm-token");
    getGmCampaignIds.mockResolvedValue(["campaign-1"]);
    getCampaignPlayers.mockResolvedValue([{ entityId: "char-1", name: "Frodo" }]);

    const interaction = fakeAutocomplete("character", "fro");
    await confiscateCommand.autocomplete?.(interaction, { config, logger: {} as never });

    expect(interaction.respond).toHaveBeenCalledWith([{ name: "Frodo", value: "char-1" }]);
  });

  it("suggests items owned by the character chosen in this same interaction", async () => {
    getValidAccessToken.mockResolvedValue("gm-token");
    getItemInstancesOwnedBy.mockResolvedValue({
      groups: [
        {
          container: null,
          item_instances: [{ entity_id: "item-1", title: "Sword", quantity: null }],
        },
      ],
    });

    const interaction = fakeAutocomplete("item", "", "char-1");
    await confiscateCommand.autocomplete?.(interaction, { config, logger: {} as never });

    expect(getItemInstancesOwnedBy).toHaveBeenCalledWith("tenant-1", "char-1", "gm-token");
    expect(interaction.respond).toHaveBeenCalledWith([{ name: "Sword", value: "item-1" }]);
  });

  it("responds with no choices for 'item' when no character has been chosen yet", async () => {
    getValidAccessToken.mockResolvedValue("gm-token");

    const interaction = fakeAutocomplete("item");
    await confiscateCommand.autocomplete?.(interaction, { config, logger: {} as never });

    expect(interaction.respond).toHaveBeenCalledWith([]);
    expect(getItemInstancesOwnedBy).not.toHaveBeenCalled();
  });
});

describe("confiscateCommand.execute - recording for /changes (ADR 0096)", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("records what was taken, for the player it was taken from, without naming the GM", async () => {
    getValidAccessToken.mockResolvedValue("gm-token");
    isCampaignGm.mockResolvedValue(true);
    getItemInstance.mockResolvedValue({
      data: { entity_id: "item-1", quantity: null, title: "Sword" },
      etag: "etag-1",
    });
    getCharacterName.mockResolvedValue("Frodo");

    await confiscateCommand.execute(fakeInteraction(), { config, logger: {} as never });

    expect(recordCharacterEvents).toHaveBeenCalledWith(
      [
        expect.objectContaining({
          kind: "confiscated",
          summary: "Sword was taken from Frodo.",
          characterEntityIds: [expect.any(String)],
        }),
      ],
      expect.anything(),
    );
  });

  it("records nothing when the confiscation failed", async () => {
    getValidAccessToken.mockResolvedValue("gm-token");
    isCampaignGm.mockResolvedValue(true);
    getItemInstance.mockRejectedValue(new LorenzoApiError("gone", 404));

    await confiscateCommand.execute(fakeInteraction(), { config, logger: {} as never });

    expect(recordCharacterEvents).not.toHaveBeenCalled();
  });
});
