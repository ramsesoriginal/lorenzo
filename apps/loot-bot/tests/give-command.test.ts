import { beforeEach, describe, expect, it, vi } from "vitest";
import type {
  AutocompleteInteraction,
  ButtonInteraction,
  ChatInputCommandInteraction,
} from "../src/commands/types.js";
import type { Config } from "../src/config.js";
import { GIVE_CANCEL_CUSTOM_ID, buildGiveConfirmCustomId } from "../src/format-give.js";
import { LorenzoApiError } from "../src/lorenzo-client.js";

const { getValidAccessToken } = vi.hoisted(() => ({ getValidAccessToken: vi.fn() }));
vi.mock("../src/token-provider.js", () => ({ getValidAccessToken }));

const { recordCharacterEvents } = vi.hoisted(() => ({ recordCharacterEvents: vi.fn() }));
vi.mock("../src/character-events.js", async (importOriginal) => ({
  ...(await importOriginal<typeof import("../src/character-events.js")>()),
  recordCharacterEvents,
}));

const { recordUndo } = vi.hoisted(() => ({ recordUndo: vi.fn() }));
vi.mock("../src/undo-actions.js", () => ({ recordUndo }));

const { rememberActingCharacter } = vi.hoisted(() => ({ rememberActingCharacter: vi.fn() }));
vi.mock("../src/commands/remember-character.js", () => ({ rememberActingCharacter }));

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

const ctx = { config, logger: {} as never };

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

function fakeButton(customId: string, userId = "discord-user-1") {
  return {
    user: { id: userId },
    customId,
    update: vi.fn(async () => undefined),
    editReply: vi.fn(async () => undefined),
  } as unknown as ButtonInteraction & {
    update: ReturnType<typeof vi.fn>;
    editReply: ReturnType<typeof vi.fn>;
  };
}

/** The confirm button `/give` would have shown for this intent. */
function confirmButton(quantity: number | null = null) {
  return fakeButton(
    buildGiveConfirmCustomId({
      itemEntityId: "item-1",
      targetCharacterId: "char-2",
      quantity,
    }),
  );
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

describe("giveCommand.execute (the confirmation prompt)", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  function promptFor(quantity: number | null = null) {
    const interaction = fakeInteraction();
    interaction.options.getString.mockImplementation((name: string) =>
      name === "item" ? "item-1" : "char-2",
    );
    interaction.options.getInteger.mockReturnValue(quantity);
    return interaction;
  }

  it("prompts to /link when there's no valid access token", async () => {
    getValidAccessToken.mockResolvedValue(null);
    const interaction = fakeInteraction();

    await giveCommand.execute(interaction, ctx);

    expect(interaction.editReply).toHaveBeenCalledWith(
      expect.stringContaining("run `/link` first"),
    );
    expect(getItemInstance).not.toHaveBeenCalled();
  });

  it("asks before giving a whole stack, and writes nothing", async () => {
    getValidAccessToken.mockResolvedValue("token-123");
    getItemInstance.mockResolvedValue({
      data: { entity_id: "item-1", quantity: 5, title: "Torch", owner_entity_id: "char-1" },
      etag: "etag-1",
    });
    getCharacterName.mockResolvedValue("Sam");
    const interaction = promptFor();

    await giveCommand.execute(interaction, ctx);

    expect(interaction.editReply).toHaveBeenCalledWith({
      content: "Give **Torch ×5** to **Sam**?",
      components: expect.any(Array),
    });
    expect(splitItemInstance).not.toHaveBeenCalled();
    expect(setItemInstanceOwner).not.toHaveBeenCalled();
    expect(recordUndo).not.toHaveBeenCalled();
  });

  it("words a partial give with what's left in the stack", async () => {
    getValidAccessToken.mockResolvedValue("token-123");
    getItemInstance.mockResolvedValue({
      data: { entity_id: "item-1", quantity: 5, title: "Torch", owner_entity_id: "char-1" },
      etag: "etag-1",
    });
    getCharacterName.mockResolvedValue("Sam");
    const interaction = promptFor(2);

    await giveCommand.execute(interaction, ctx);

    expect(interaction.editReply).toHaveBeenCalledWith(
      expect.objectContaining({ content: "Give **2 of Torch** (you have 5) to **Sam**?" }),
    );
  });

  it("puts the whole intent in the confirm button, so the click needs no bot-side state", async () => {
    getValidAccessToken.mockResolvedValue("token-123");
    getItemInstance.mockResolvedValue({
      data: { entity_id: "item-1", quantity: 5, title: "Torch" },
      etag: "etag-1",
    });
    getCharacterName.mockResolvedValue("Sam");
    const interaction = promptFor(2);

    await giveCommand.execute(interaction, ctx);

    const [{ components }] = interaction.editReply.mock.calls[0] as [
      { components: { toJSON(): { components: { custom_id: string; label: string }[] } }[] },
    ];
    const buttons = components[0]?.toJSON().components ?? [];
    expect(buttons.map((b) => [b.label, b.custom_id])).toEqual([
      ["Give", "give:ok:item-1:char-2:2"],
      ["Cancel", GIVE_CANCEL_CUSTOM_ID],
    ]);
  });

  it("rejects a quantity for an item that isn't a stack, before offering a click", async () => {
    getValidAccessToken.mockResolvedValue("token-123");
    getItemInstance.mockResolvedValue({
      data: { entity_id: "item-1", quantity: null, title: "Sword" },
      etag: "etag-1",
    });
    const interaction = promptFor(1);

    await giveCommand.execute(interaction, ctx);

    expect(interaction.editReply).toHaveBeenCalledWith(expect.stringContaining("isn't a stack"));
    expect(getCharacterName).not.toHaveBeenCalled();
  });

  it.each([
    [403, "reachable from any of your characters"],
    [404, "Couldn't find that item"],
    [422, "Couldn't do that"],
  ])(
    "gives a specific message when reading the item fails with %i",
    async (status, expectedText) => {
      getValidAccessToken.mockResolvedValue("token-123");
      getItemInstance.mockRejectedValue(new LorenzoApiError("boom", status));
      const interaction = promptFor();

      await giveCommand.execute(interaction, ctx);

      expect(interaction.editReply).toHaveBeenCalledWith(expect.stringContaining(expectedText));
    },
  );

  it("fails early, without a prompt, when the target character doesn't exist", async () => {
    getValidAccessToken.mockResolvedValue("token-123");
    getItemInstance.mockResolvedValue({
      data: { entity_id: "item-1", quantity: null, title: "Sword" },
      etag: "etag-1",
    });
    getCharacterName.mockRejectedValue(new LorenzoApiError("not found", 404));
    const interaction = promptFor();

    await giveCommand.execute(interaction, ctx);

    expect(interaction.editReply).toHaveBeenCalledWith(
      expect.stringContaining("Couldn't find that item or that character"),
    );
  });
});

describe("giveCommand.onButton (the confirmed transfer)", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("cancels without touching the API", async () => {
    const button = fakeButton(GIVE_CANCEL_CUSTOM_ID);

    await giveCommand.onButton?.(button, ctx);

    expect(button.update).toHaveBeenCalledWith({
      content: "Cancelled — nothing was given.",
      components: [],
    });
    expect(getValidAccessToken).not.toHaveBeenCalled();
    expect(getItemInstance).not.toHaveBeenCalled();
  });

  it("refuses a malformed confirm id instead of guessing", async () => {
    const button = fakeButton("give:ok:item-1:char-2:banana");

    await giveCommand.onButton?.(button, ctx);

    expect(button.update).toHaveBeenCalledWith(
      expect.objectContaining({ content: expect.stringContaining("isn't valid anymore") }),
    );
    expect(getItemInstance).not.toHaveBeenCalled();
    expect(setItemInstanceOwner).not.toHaveBeenCalled();
  });

  it("strips the buttons as its very first response, before any API call", async () => {
    getValidAccessToken.mockResolvedValue("token-123");
    getItemInstance.mockResolvedValue({
      data: { entity_id: "item-1", quantity: null, title: "Sword", owner_entity_id: "char-1" },
      etag: "etag-1",
    });
    setItemInstanceOwner.mockResolvedValue({ entity_id: "item-1", title: "Sword" });
    getCharacterName.mockResolvedValue("Sam");
    const button = confirmButton();

    await giveCommand.onButton?.(button, ctx);

    expect(button.update).toHaveBeenCalledWith({ content: "Giving…", components: [] });
    expect(button.update.mock.invocationCallOrder[0]).toBeLessThan(
      getItemInstance.mock.invocationCallOrder[0] as number,
    );
  });

  it("prompts to /link when the clicker has no valid access token", async () => {
    getValidAccessToken.mockResolvedValue(null);
    const button = confirmButton();

    await giveCommand.onButton?.(button, ctx);

    expect(button.editReply).toHaveBeenCalledWith(expect.stringContaining("run `/link` first"));
    expect(setItemInstanceOwner).not.toHaveBeenCalled();
  });

  it("transfers the whole instance when no quantity was chosen", async () => {
    getValidAccessToken.mockResolvedValue("token-123");
    getItemInstance.mockResolvedValue({
      data: { entity_id: "item-1", quantity: 5, title: "Torch", owner_entity_id: "char-1" },
      etag: "etag-1",
    });
    setItemInstanceOwner.mockResolvedValue({ entity_id: "item-1", title: "Torch" });
    getCharacterName.mockResolvedValue("Frodo");
    const button = confirmButton();

    await giveCommand.onButton?.(button, ctx);

    expect(splitItemInstance).not.toHaveBeenCalled();
    expect(setItemInstanceOwner).toHaveBeenCalledWith(
      "tenant-1",
      "item-1",
      "char-2",
      "token-123",
      "etag-1",
    );
    expect(button.editReply).toHaveBeenCalledWith("Gave Torch to Frodo.");
    expect(recordUndo).toHaveBeenCalledWith("discord-user-1", {
      kind: "restore-owner",
      entityId: "item-1",
      previousOwnerCharacterId: "char-1",
    });
  });

  it("splits with the owner in one call for a partial give (ADR 0044 split-with-owner)", async () => {
    getValidAccessToken.mockResolvedValue("token-123");
    getItemInstance.mockResolvedValue({
      data: { entity_id: "item-1", quantity: 5, title: "Torch", owner_entity_id: "char-1" },
      etag: "etag-1",
    });
    splitItemInstance.mockResolvedValue({
      data: { entity_id: "item-2", quantity: 2, title: "Torch", owner_entity_id: "char-2" },
      etag: "etag-2",
    });
    getCharacterName.mockResolvedValue("Sam");
    const button = confirmButton(2);

    await giveCommand.onButton?.(button, ctx);

    expect(splitItemInstance).toHaveBeenCalledWith(
      "tenant-1",
      "item-1",
      2,
      "token-123",
      "etag-1",
      "char-2",
    );
    expect(setItemInstanceOwner).not.toHaveBeenCalled();
    expect(button.editReply).toHaveBeenCalledWith("Gave 2 of Torch to Sam.");
    // Undo of a split-give gives the *split-off* instance back, not the
    // original source - the source's own remaining quantity is untouched.
    expect(recordUndo).toHaveBeenCalledWith("discord-user-1", {
      kind: "restore-owner",
      entityId: "item-2",
      previousOwnerCharacterId: "char-1",
    });
  });

  it("transfers the whole stack outright when quantity covers all of it", async () => {
    getValidAccessToken.mockResolvedValue("token-123");
    getItemInstance.mockResolvedValue({
      data: { entity_id: "item-1", quantity: 5, title: "Torch" },
      etag: "etag-1",
    });
    setItemInstanceOwner.mockResolvedValue({ entity_id: "item-1", title: "Torch" });
    getCharacterName.mockResolvedValue("Sam");
    const button = confirmButton(5);

    await giveCommand.onButton?.(button, ctx);

    expect(splitItemInstance).not.toHaveBeenCalled();
    expect(setItemInstanceOwner).toHaveBeenCalledWith(
      "tenant-1",
      "item-1",
      "char-2",
      "token-123",
      "etag-1",
    );
  });

  it("decides against the stack as it is now, not as the prompt showed it", async () => {
    // The prompt offered "2 of 5"; by the click only 1 is left, so asking
    // for 2 covers the whole (remaining) stack and transfers it outright.
    getValidAccessToken.mockResolvedValue("token-123");
    getItemInstance.mockResolvedValue({
      data: { entity_id: "item-1", quantity: 1, title: "Torch", owner_entity_id: "char-1" },
      etag: "etag-9",
    });
    setItemInstanceOwner.mockResolvedValue({ entity_id: "item-1", title: "Torch" });
    getCharacterName.mockResolvedValue("Sam");
    const button = confirmButton(2);

    await giveCommand.onButton?.(button, ctx);

    expect(splitItemInstance).not.toHaveBeenCalled();
    expect(setItemInstanceOwner).toHaveBeenCalledWith(
      "tenant-1",
      "item-1",
      "char-2",
      "token-123",
      "etag-9",
    );
  });

  it("remembers the giving character as the caller's last-used one", async () => {
    getValidAccessToken.mockResolvedValue("token-123");
    getItemInstance.mockResolvedValue({
      data: { entity_id: "item-1", quantity: null, title: "Sword", owner_entity_id: "char-1" },
      etag: "etag-1",
    });
    setItemInstanceOwner.mockResolvedValue({ entity_id: "item-1", title: "Sword" });
    getCharacterName.mockResolvedValue("Sam");
    const button = confirmButton();

    await giveCommand.onButton?.(button, ctx);

    expect(rememberActingCharacter).toHaveBeenCalledWith(
      expect.anything(),
      "tenant-1",
      "token-123",
      "discord-user-1",
      "char-1",
      ctx.logger,
    );
  });

  it("does not remember anything when the give itself failed", async () => {
    getValidAccessToken.mockResolvedValue("token-123");
    getItemInstance.mockResolvedValue({
      data: { entity_id: "item-1", quantity: null, title: "Sword", owner_entity_id: "char-1" },
      etag: "etag-1",
    });
    setItemInstanceOwner.mockRejectedValue(new LorenzoApiError("stale", 412));
    const button = confirmButton();

    await giveCommand.onButton?.(button, ctx);

    expect(rememberActingCharacter).not.toHaveBeenCalled();
    expect(recordUndo).not.toHaveBeenCalled();
  });

  it("re-checks that a quantity still makes sense, if the item stopped being a stack", async () => {
    getValidAccessToken.mockResolvedValue("token-123");
    getItemInstance.mockResolvedValue({
      data: { entity_id: "item-1", quantity: null, title: "Sword" },
      etag: "etag-1",
    });
    const button = confirmButton(2);

    await giveCommand.onButton?.(button, ctx);

    expect(button.editReply).toHaveBeenCalledWith(expect.stringContaining("isn't a stack"));
    expect(setItemInstanceOwner).not.toHaveBeenCalled();
  });

  it.each([
    [403, "reachable from any of your characters"],
    [404, "Couldn't find that item"],
    [422, "Couldn't do that"],
  ])("gives a specific message for a %i error", async (status, expectedText) => {
    getValidAccessToken.mockResolvedValue("token-123");
    getItemInstance.mockRejectedValue(new LorenzoApiError("boom", status));
    const button = confirmButton();

    await giveCommand.onButton?.(button, ctx);

    expect(button.editReply).toHaveBeenCalledWith(expect.stringContaining(expectedText));
  });

  it("still succeeds even if the friendly-name lookup fails", async () => {
    getValidAccessToken.mockResolvedValue("token-123");
    getItemInstance.mockResolvedValue({
      data: { entity_id: "item-1", quantity: null, title: "Sword" },
      etag: "etag-1",
    });
    setItemInstanceOwner.mockResolvedValue({ entity_id: "item-1", title: "Sword" });
    getCharacterName.mockRejectedValue(new LorenzoApiError("not found", 404));
    const button = confirmButton();

    await giveCommand.onButton?.(button, ctx);

    expect(button.editReply).toHaveBeenCalledWith("Gave Sword to them.");
  });

  it("tells the caller to retry when the write 412s on a stale etag", async () => {
    getValidAccessToken.mockResolvedValue("token-123");
    getItemInstance.mockResolvedValue({
      data: { entity_id: "item-1", quantity: null, title: "Sword" },
      etag: "etag-1",
    });
    setItemInstanceOwner.mockRejectedValue(new LorenzoApiError("stale", 412));
    const button = confirmButton();

    await giveCommand.onButton?.(button, ctx);

    expect(button.editReply).toHaveBeenCalledWith(
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

    await giveCommand.autocomplete?.(interaction, ctx);

    expect(interaction.respond).toHaveBeenCalledWith([]);
  });

  it("suggests the caller's own items, across every controlled character", async () => {
    getValidAccessToken.mockResolvedValue("token-123");
    getMyItemInstances.mockResolvedValue([
      { entityId: "item-1", title: "Torch", quantity: 5 },
      { entityId: "item-2", title: "Sword", quantity: null },
    ]);

    const interaction = fakeAutocomplete("item", "tor");
    await giveCommand.autocomplete?.(interaction, ctx);

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
    await giveCommand.autocomplete?.(interaction, ctx);

    expect(getCampaignPlayers).toHaveBeenCalledWith("tenant-1", "campaign-1", "token-123");
    expect(interaction.respond).toHaveBeenCalledWith([
      { name: "Frodo", value: "char-1" },
      { name: "Sam", value: "char-2" },
    ]);
  });
});

describe("giveCommand.onButton - recording for /changes (ADR 0097)", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  function arrange(quantity: number | null = 5) {
    getValidAccessToken.mockResolvedValue("token-123");
    getItemInstance.mockResolvedValue({
      data: { entity_id: "item-1", quantity, title: "Torch", owner_entity_id: "char-1" },
      etag: "etag-1",
    });
    setItemInstanceOwner.mockResolvedValue({ entity_id: "item-1", title: "Torch", quantity });
    return confirmButton();
  }

  it("records the give against both characters, naming them", async () => {
    getCharacterName.mockImplementation(async (_t: string, id: string) =>
      id === "char-1" ? "Frodo" : "Sam",
    );

    await giveCommand.onButton?.(arrange(), ctx);

    expect(recordCharacterEvents).toHaveBeenCalledWith(
      [
        expect.objectContaining({
          kind: "gave",
          summary: "Frodo gave Torch ×5 to Sam.",
          characterEntityIds: ["char-1", "char-2"],
        }),
      ],
      expect.anything(),
    );
  });

  it("still records it, by id, when the name lookups fail - and the reply is unaffected", async () => {
    getCharacterName.mockRejectedValue(new LorenzoApiError("nope", 404));
    const button = arrange();

    await giveCommand.onButton?.(button, ctx);

    expect(button.editReply).toHaveBeenCalledWith("Gave Torch to them.");
    expect(recordCharacterEvents).toHaveBeenCalledWith(
      [expect.objectContaining({ characterEntityIds: ["char-1", "char-2"] })],
      expect.anything(),
    );
  });

  it("records nothing when the give itself failed", async () => {
    getCharacterName.mockResolvedValue("Sam");
    const button = arrange();
    setItemInstanceOwner.mockRejectedValue(new LorenzoApiError("stale", 412));

    await giveCommand.onButton?.(button, ctx);

    expect(recordCharacterEvents).not.toHaveBeenCalled();
  });
});
