import { beforeEach, describe, expect, it, vi } from "vitest";
import type {
  AutocompleteInteraction,
  ChatInputCommandInteraction,
} from "../src/commands/types.js";
import type { Config } from "../src/config.js";
import { LorenzoApiError } from "../src/lorenzo-client.js";

const { getValidAccessToken } = vi.hoisted(() => ({ getValidAccessToken: vi.fn() }));
vi.mock("../src/token-provider.js", () => ({ getValidAccessToken }));

const { recordUndo } = vi.hoisted(() => ({ recordUndo: vi.fn() }));
vi.mock("../src/undo-actions.js", () => ({ recordUndo }));

const {
  isCampaignGm,
  getGmCampaignIds,
  getCampaignPlayers,
  getCharacterName,
  getItemInstancesOwnedBy,
  getItemInstance,
  splitItemInstance,
  setItemInstanceOwner,
  createLorenzoApiClient,
} = vi.hoisted(() => ({
  isCampaignGm: vi.fn(),
  getGmCampaignIds: vi.fn(),
  getCampaignPlayers: vi.fn(),
  getCharacterName: vi.fn(),
  getItemInstancesOwnedBy: vi.fn(),
  getItemInstance: vi.fn(),
  splitItemInstance: vi.fn(),
  setItemInstanceOwner: vi.fn(),
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
      setItemInstanceOwner,
    }),
  };
});

const { reassignCommand } = await import("../src/commands/reassign.js");

const config = {
  lorenzoApiBaseUrl: "http://lorenzo-api.test",
  lorenzoTenantId: "tenant-1",
} as Config;

function fakeInteraction(userId = "gm-1") {
  return {
    user: { id: userId },
    options: {
      getString: vi.fn((name: string) => (name === "item" ? "item-1" : "char-2")),
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

function fakeAutocomplete(focusedName: "item" | "to", focusedValue = "") {
  return {
    user: { id: "gm-1" },
    options: {
      getFocused: vi.fn(() => ({ name: focusedName, value: focusedValue })),
      getString: vi.fn(() => null),
    },
    respond: vi.fn(async () => undefined),
  } as unknown as AutocompleteInteraction & { respond: ReturnType<typeof vi.fn> };
}

describe("reassignCommand.execute", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("prompts to /link when there's no valid access token", async () => {
    getValidAccessToken.mockResolvedValue(null);
    const interaction = fakeInteraction();

    await reassignCommand.execute(interaction, { config, logger: {} as never });

    expect(interaction.editReply).toHaveBeenCalledWith(
      expect.stringContaining("run `/link` first"),
    );
    expect(getItemInstance).not.toHaveBeenCalled();
  });

  it("rejects a non-GM", async () => {
    getValidAccessToken.mockResolvedValue("token-123");
    isCampaignGm.mockResolvedValue(false);
    const interaction = fakeInteraction();

    await reassignCommand.execute(interaction, { config, logger: {} as never });

    expect(interaction.editReply).toHaveBeenCalledWith(expect.stringContaining("Only a GM"));
    expect(getItemInstance).not.toHaveBeenCalled();
  });

  it("transfers the whole instance when no quantity is given", async () => {
    getValidAccessToken.mockResolvedValue("gm-token");
    isCampaignGm.mockResolvedValue(true);
    getItemInstance.mockResolvedValue({
      data: { entity_id: "item-1", quantity: 5, title: "Torch", owner_entity_id: "char-1" },
      etag: "etag-1",
    });
    setItemInstanceOwner.mockResolvedValue({ entity_id: "item-1", title: "Torch" });
    getCharacterName.mockResolvedValue("Sam");
    const interaction = fakeInteraction();

    await reassignCommand.execute(interaction, { config, logger: {} as never });

    expect(setItemInstanceOwner).toHaveBeenCalledWith(
      "tenant-1",
      "item-1",
      "char-2",
      "gm-token",
      "etag-1",
    );
    expect(interaction.editReply).toHaveBeenCalledWith("Reassigned Torch to Sam.");
    expect(recordUndo).toHaveBeenCalledWith("gm-1", {
      kind: "restore-owner",
      entityId: "item-1",
      previousOwnerCharacterId: "char-1",
    });
  });

  it("splits with the owner in one call for a partial reassign", async () => {
    getValidAccessToken.mockResolvedValue("gm-token");
    isCampaignGm.mockResolvedValue(true);
    getItemInstance.mockResolvedValue({
      data: { entity_id: "item-1", quantity: 5, title: "Torch" },
      etag: "etag-1",
    });
    splitItemInstance.mockResolvedValue({
      data: { entity_id: "item-2", quantity: 2, title: "Torch", owner_entity_id: "char-2" },
      etag: "etag-2",
    });
    getCharacterName.mockResolvedValue("Sam");
    const interaction = fakeInteraction();
    interaction.options.getInteger.mockReturnValue(2);

    await reassignCommand.execute(interaction, { config, logger: {} as never });

    expect(splitItemInstance).toHaveBeenCalledWith(
      "tenant-1",
      "item-1",
      2,
      "gm-token",
      "etag-1",
      "char-2",
    );
    expect(setItemInstanceOwner).not.toHaveBeenCalled();
    expect(interaction.editReply).toHaveBeenCalledWith("Reassigned 2 of Torch to Sam.");
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

    await reassignCommand.execute(interaction, { config, logger: {} as never });

    expect(interaction.editReply).toHaveBeenCalledWith(expect.stringContaining("isn't a stack"));
    expect(setItemInstanceOwner).not.toHaveBeenCalled();
  });

  it.each([
    [403, "reachable from any campaign you GM"],
    [404, "Couldn't find that item"],
    [412, "Someone else changed that item"],
    [422, "Couldn't do that"],
  ])("gives a specific message for a %i error", async (status, expectedText) => {
    getValidAccessToken.mockResolvedValue("gm-token");
    isCampaignGm.mockResolvedValue(true);
    getItemInstance.mockResolvedValue({
      data: { entity_id: "item-1", quantity: null, title: "Sword" },
      etag: "etag-1",
    });
    setItemInstanceOwner.mockRejectedValue(new LorenzoApiError("boom", status));
    const interaction = fakeInteraction();

    await reassignCommand.execute(interaction, { config, logger: {} as never });

    expect(interaction.editReply).toHaveBeenCalledWith(expect.stringContaining(expectedText));
  });
});

describe("reassignCommand.autocomplete", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("responds with no choices when there's no valid access token", async () => {
    getValidAccessToken.mockResolvedValue(null);
    const interaction = fakeAutocomplete("item");

    await reassignCommand.autocomplete?.(interaction, { config, logger: {} as never });

    expect(interaction.respond).toHaveBeenCalledWith([]);
  });

  it("suggests every item owned by any character in a campaign the caller GMs", async () => {
    getValidAccessToken.mockResolvedValue("gm-token");
    getGmCampaignIds.mockResolvedValue(["campaign-1"]);
    getCampaignPlayers.mockResolvedValue([{ entityId: "char-1", name: "Frodo" }]);
    getItemInstancesOwnedBy.mockResolvedValue({
      groups: [
        { container: null, item_instances: [{ entity_id: "item-1", title: "Torch", quantity: 5 }] },
      ],
    });

    const interaction = fakeAutocomplete("item", "tor");
    await reassignCommand.autocomplete?.(interaction, { config, logger: {} as never });

    expect(interaction.respond).toHaveBeenCalledWith([{ name: "Torch ×5", value: "item-1" }]);
  });

  it("suggests every character in a campaign the caller GMs for 'to'", async () => {
    getValidAccessToken.mockResolvedValue("gm-token");
    getGmCampaignIds.mockResolvedValue(["campaign-1"]);
    getCampaignPlayers.mockResolvedValue([{ entityId: "char-1", name: "Frodo" }]);

    const interaction = fakeAutocomplete("to", "fro");
    await reassignCommand.autocomplete?.(interaction, { config, logger: {} as never });

    expect(interaction.respond).toHaveBeenCalledWith([{ name: "Frodo", value: "char-1" }]);
  });
});
