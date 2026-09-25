import { beforeEach, describe, expect, it, vi } from "vitest";
import type {
  AutocompleteInteraction,
  ButtonInteraction,
  ChatInputCommandInteraction,
  ModalMessageModalSubmitInteraction,
  StringSelectMenuInteraction,
} from "../src/commands/types.js";
import type { Config } from "../src/config.js";
import { LorenzoApiError } from "../src/lorenzo-client.js";

const { getValidAccessToken } = vi.hoisted(() => ({ getValidAccessToken: vi.fn() }));
vi.mock("../src/token-provider.js", () => ({ getValidAccessToken }));

const { resolveCurrentCharacter } = vi.hoisted(() => ({ resolveCurrentCharacter: vi.fn() }));
vi.mock("../src/preferences.js", () => ({ resolveCurrentCharacter }));

const {
  insertLootDrop,
  setLootDropMessageId,
  getLootDrop,
  markLootDropApplied,
  getLootClaim,
  listLootClaims,
  upsertLootClaim,
  deleteLootClaim,
  deleteLootClaimsForDrop,
} = vi.hoisted(() => ({
  insertLootDrop: vi.fn(),
  setLootDropMessageId: vi.fn(),
  getLootDrop: vi.fn(),
  markLootDropApplied: vi.fn(),
  getLootClaim: vi.fn(),
  listLootClaims: vi.fn(),
  upsertLootClaim: vi.fn(),
  deleteLootClaim: vi.fn(),
  deleteLootClaimsForDrop: vi.fn(),
}));
vi.mock("../src/db.js", () => ({
  insertLootDrop,
  setLootDropMessageId,
  getLootDrop,
  markLootDropApplied,
  getLootClaim,
  listLootClaims,
  upsertLootClaim,
  deleteLootClaim,
  deleteLootClaimsForDrop,
}));

const {
  isCampaignGm,
  getItemInstancesByContainer,
  getUnownedItemInstances,
  getMyItemInstances,
  getItemInstance,
  getItemInstanceBySlug,
  splitItemInstance,
  setItemInstanceOwner,
  bulkAssignItemInstances,
  getCharacterName,
  createLorenzoApiClient,
} = vi.hoisted(() => ({
  isCampaignGm: vi.fn(),
  getItemInstancesByContainer: vi.fn(),
  getUnownedItemInstances: vi.fn(),
  getMyItemInstances: vi.fn(),
  getItemInstance: vi.fn(),
  getItemInstanceBySlug: vi.fn(),
  splitItemInstance: vi.fn(),
  setItemInstanceOwner: vi.fn(),
  bulkAssignItemInstances: vi.fn(),
  getCharacterName: vi.fn(),
  createLorenzoApiClient: vi.fn(),
}));
vi.mock("../src/lorenzo-client.js", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../src/lorenzo-client.js")>();
  return {
    ...actual,
    createLorenzoApiClient: createLorenzoApiClient.mockReturnValue({
      isCampaignGm,
      getItemInstancesByContainer,
      getUnownedItemInstances,
      getMyItemInstances,
      getItemInstance,
      getItemInstanceBySlug,
      splitItemInstance,
      setItemInstanceOwner,
      bulkAssignItemInstances,
      getCharacterName,
    }),
  };
});

const { dropCommand } = await import("../src/commands/drop.js");

const config = {
  lorenzoApiBaseUrl: "http://lorenzo-api.test",
  lorenzoTenantId: "tenant-1",
} as Config;

const CONTAINER_UUID = "11111111-1111-1111-1111-111111111111";

function fakeExecuteInteraction(userId = "gm-1", container = CONTAINER_UUID) {
  return {
    user: { id: userId },
    channelId: "channel-1",
    options: { getString: vi.fn(() => container) },
    deferReply: vi.fn(async () => undefined),
    editReply: vi.fn(async () => ({ id: "message-1" })),
  } as unknown as ChatInputCommandInteraction & {
    options: { getString: ReturnType<typeof vi.fn> };
    deferReply: ReturnType<typeof vi.fn>;
    editReply: ReturnType<typeof vi.fn>;
  };
}

function fakeSelectMenu(customId: string, value: string, userId = "user-1") {
  return {
    user: { id: userId },
    customId,
    values: [value],
    showModal: vi.fn(async () => undefined),
    update: vi.fn(async () => undefined),
    deferUpdate: vi.fn(async () => undefined),
  } as unknown as StringSelectMenuInteraction & {
    showModal: ReturnType<typeof vi.fn>;
    update: ReturnType<typeof vi.fn>;
    deferUpdate: ReturnType<typeof vi.fn>;
  };
}

function fakeModalSubmit(customId: string, quantity: string, userId = "user-1", claimType = "") {
  return {
    user: { id: userId },
    customId,
    fields: {
      getTextInputValue: vi.fn((fieldId: string) =>
        fieldId === "claim-type" ? claimType : quantity,
      ),
    },
    isFromMessage: vi.fn(() => true),
    reply: vi.fn(async () => undefined),
    update: vi.fn(async () => undefined),
    deferUpdate: vi.fn(async () => undefined),
    followUp: vi.fn(async () => undefined),
  } as unknown as ModalMessageModalSubmitInteraction & {
    reply: ReturnType<typeof vi.fn>;
    update: ReturnType<typeof vi.fn>;
    deferUpdate: ReturnType<typeof vi.fn>;
    followUp: ReturnType<typeof vi.fn>;
  };
}

function fakeButton(customId: string, userId = "gm-1") {
  return {
    user: { id: userId },
    customId,
    reply: vi.fn(async () => undefined),
    deferUpdate: vi.fn(async () => undefined),
    editReply: vi.fn(async () => undefined),
  } as unknown as ButtonInteraction & {
    reply: ReturnType<typeof vi.fn>;
    deferUpdate: ReturnType<typeof vi.fn>;
    editReply: ReturnType<typeof vi.fn>;
  };
}

describe("dropCommand.execute", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("prompts to /link when there's no valid access token", async () => {
    getValidAccessToken.mockResolvedValue(null);
    const interaction = fakeExecuteInteraction();

    await dropCommand.execute(interaction, { config, logger: {} as never });

    expect(interaction.editReply).toHaveBeenCalledWith(
      expect.stringContaining("run `/link` first"),
    );
  });

  it("rejects a non-GM", async () => {
    getValidAccessToken.mockResolvedValue("token-123");
    isCampaignGm.mockResolvedValue(false);
    const interaction = fakeExecuteInteraction();

    await dropCommand.execute(interaction, { config, logger: {} as never });

    expect(interaction.editReply).toHaveBeenCalledWith(expect.stringContaining("Only a GM"));
    expect(getItemInstancesByContainer).not.toHaveBeenCalled();
  });

  it("gives a friendly message for an unknown container", async () => {
    getValidAccessToken.mockResolvedValue("token-123");
    isCampaignGm.mockResolvedValue(true);
    getItemInstancesByContainer.mockRejectedValue(new LorenzoApiError("not found", 404));
    const interaction = fakeExecuteInteraction();

    await dropCommand.execute(interaction, { config, logger: {} as never });

    expect(interaction.editReply).toHaveBeenCalledWith(
      expect.stringContaining("Couldn't find that container"),
    );
  });

  it("resolves a non-uuid container option as a slug (ADR 0043) before listing contents", async () => {
    getValidAccessToken.mockResolvedValue("token-123");
    isCampaignGm.mockResolvedValue(true);
    getItemInstanceBySlug.mockResolvedValue({
      data: { entity_id: CONTAINER_UUID, title: "The Chest" },
      etag: "etag-container",
    });
    getItemInstancesByContainer.mockResolvedValue([]);
    insertLootDrop.mockResolvedValue({ id: "drop-1" });
    const interaction = fakeExecuteInteraction("gm-1", "the-chest");

    await dropCommand.execute(interaction, { config, logger: {} as never });

    expect(getItemInstanceBySlug).toHaveBeenCalledWith("tenant-1", "the-chest", "token-123");
    expect(getItemInstancesByContainer).toHaveBeenCalledWith(
      "tenant-1",
      CONTAINER_UUID,
      "token-123",
    );
    expect(insertLootDrop).toHaveBeenCalledWith(
      expect.objectContaining({ containerEntityId: CONTAINER_UUID }),
    );
  });

  it("gives a friendly message for an unknown slug", async () => {
    getValidAccessToken.mockResolvedValue("token-123");
    isCampaignGm.mockResolvedValue(true);
    getItemInstanceBySlug.mockRejectedValue(new LorenzoApiError("not found", 404));
    const interaction = fakeExecuteInteraction("gm-1", "no-such-slug");

    await dropCommand.execute(interaction, { config, logger: {} as never });

    expect(interaction.editReply).toHaveBeenCalledWith(
      expect.stringContaining("Couldn't find that container"),
    );
    expect(getItemInstancesByContainer).not.toHaveBeenCalled();
  });

  it("posts the drop message and records its id", async () => {
    getValidAccessToken.mockResolvedValue("token-123");
    isCampaignGm.mockResolvedValue(true);
    getItemInstancesByContainer.mockResolvedValue([
      { entity_id: "item-1", title: "Torch", quantity: 5, owner_entity_id: null },
    ]);
    insertLootDrop.mockResolvedValue({ id: "drop-1" });
    const interaction = fakeExecuteInteraction();

    await dropCommand.execute(interaction, { config, logger: {} as never });

    expect(insertLootDrop).toHaveBeenCalledWith({
      containerEntityId: CONTAINER_UUID,
      discordChannelId: "channel-1",
      createdByDiscordUserId: "gm-1",
    });
    expect(interaction.editReply).toHaveBeenCalledWith(
      expect.objectContaining({ embeds: expect.any(Array), components: expect.any(Array) }),
    );
    expect(setLootDropMessageId).toHaveBeenCalledWith("drop-1", "message-1");
  });
});

describe("dropCommand.onSelectMenu", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("opens the take modal without touching the database", async () => {
    const interaction = fakeSelectMenu("drop:take:drop-1", "item-1");

    await dropCommand.onSelectMenu?.(interaction, { config, logger: {} as never });

    expect(interaction.showModal).toHaveBeenCalled();
    expect(getLootClaim).not.toHaveBeenCalled();
  });

  it("opens the claim modal when the caller has no existing claim on this item", async () => {
    getLootClaim.mockResolvedValue(undefined);
    const interaction = fakeSelectMenu("drop:claim:drop-1", "item-1");

    await dropCommand.onSelectMenu?.(interaction, { config, logger: {} as never });

    expect(interaction.showModal).toHaveBeenCalled();
    expect(deleteLootClaim).not.toHaveBeenCalled();
  });

  it("unclaims directly, without a modal, when the caller already has a claim", async () => {
    getLootClaim.mockResolvedValue({ discordUserId: "user-1" });
    getLootDrop.mockResolvedValue({
      id: "drop-1",
      containerEntityId: "container-1",
      createdByDiscordUserId: "gm-1",
    });
    getValidAccessToken.mockResolvedValue("gm-token");
    getItemInstancesByContainer.mockResolvedValue([]);
    listLootClaims.mockResolvedValue([]);
    const interaction = fakeSelectMenu("drop:claim:drop-1", "item-1");

    await dropCommand.onSelectMenu?.(interaction, { config, logger: {} as never });

    expect(deleteLootClaim).toHaveBeenCalledWith("drop-1", "item-1", "user-1");
    expect(interaction.showModal).not.toHaveBeenCalled();
    expect(interaction.update).toHaveBeenCalled();
  });
});

describe("dropCommand.onModalSubmit — take", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("rejects a non-numeric quantity", async () => {
    const interaction = fakeModalSubmit("drop:take-modal:drop-1:item-1", "banana");

    await dropCommand.onModalSubmit?.(interaction, { config, logger: {} as never });

    expect(interaction.reply).toHaveBeenCalledWith(
      expect.objectContaining({ content: expect.stringContaining("valid quantity") }),
    );
  });

  it("asks to /set-current when the caller has no current character", async () => {
    getValidAccessToken.mockResolvedValue("token-123");
    resolveCurrentCharacter.mockResolvedValue(undefined);
    const interaction = fakeModalSubmit("drop:take-modal:drop-1:item-1", "");

    await dropCommand.onModalSubmit?.(interaction, { config, logger: {} as never });

    expect(interaction.reply).toHaveBeenCalledWith(
      expect.objectContaining({ content: expect.stringContaining("/set-current") }),
    );
  });

  it("takes the whole item, refreshes the message, and confirms ephemerally", async () => {
    getValidAccessToken.mockResolvedValue("token-123");
    resolveCurrentCharacter.mockResolvedValue("char-1");
    getItemInstance.mockResolvedValue({
      data: { entity_id: "item-1", title: "Torch", quantity: null, owner_entity_id: null },
      etag: "etag-1",
    });
    setItemInstanceOwner.mockResolvedValue({ entity_id: "item-1", title: "Torch" });
    getCharacterName.mockResolvedValue("Frodo");
    getLootDrop.mockResolvedValue({
      id: "drop-1",
      containerEntityId: "container-1",
      createdByDiscordUserId: "gm-1",
    });
    getItemInstancesByContainer.mockResolvedValue([]);
    listLootClaims.mockResolvedValue([]);
    const interaction = fakeModalSubmit("drop:take-modal:drop-1:item-1", "");

    await dropCommand.onModalSubmit?.(interaction, { config, logger: {} as never });

    expect(setItemInstanceOwner).toHaveBeenCalledWith(
      "tenant-1",
      "item-1",
      "char-1",
      "token-123",
      "etag-1",
    );
    expect(interaction.update).toHaveBeenCalled();
    expect(interaction.followUp).toHaveBeenCalledWith(
      expect.objectContaining({ content: "Took Torch for Frodo.", ephemeral: true }),
    );
    // Names the recipient from the *resolved* character, not a fresh guess -
    // it's a remembered default (ADR 0088), so a wrong one must be visible.
    expect(getCharacterName).toHaveBeenCalledWith("tenant-1", "char-1", "token-123");
  });

  it("still confirms the take, just without a name, if the character lookup fails", async () => {
    getValidAccessToken.mockResolvedValue("token-123");
    resolveCurrentCharacter.mockResolvedValue("char-1");
    getItemInstance.mockResolvedValue({
      data: { entity_id: "item-1", title: "Torch", quantity: null, owner_entity_id: null },
      etag: "etag-1",
    });
    setItemInstanceOwner.mockResolvedValue({ entity_id: "item-1", title: "Torch" });
    getCharacterName.mockRejectedValue(new LorenzoApiError("not found", 404));
    getLootDrop.mockResolvedValue({
      id: "drop-1",
      containerEntityId: "container-1",
      createdByDiscordUserId: "gm-1",
    });
    getItemInstancesByContainer.mockResolvedValue([]);
    listLootClaims.mockResolvedValue([]);
    const interaction = fakeModalSubmit("drop:take-modal:drop-1:item-1", "");

    await dropCommand.onModalSubmit?.(interaction, { config, logger: {} as never });

    expect(interaction.followUp).toHaveBeenCalledWith(
      expect.objectContaining({ content: "Took Torch.", ephemeral: true }),
    );
  });

  it("rejects a quantity for a non-stacked item without a partial take", async () => {
    getValidAccessToken.mockResolvedValue("token-123");
    resolveCurrentCharacter.mockResolvedValue("char-1");
    getItemInstance.mockResolvedValue({
      data: { entity_id: "item-1", title: "Sword", quantity: null, owner_entity_id: null },
      etag: "etag-1",
    });
    const interaction = fakeModalSubmit("drop:take-modal:drop-1:item-1", "2");

    await dropCommand.onModalSubmit?.(interaction, { config, logger: {} as never });

    expect(interaction.reply).toHaveBeenCalledWith(
      expect.objectContaining({ content: expect.stringContaining("isn't a stack") }),
    );
    expect(setItemInstanceOwner).not.toHaveBeenCalled();
  });

  it("tells the caller someone already took it, on a 404", async () => {
    getValidAccessToken.mockResolvedValue("token-123");
    resolveCurrentCharacter.mockResolvedValue("char-1");
    getItemInstance.mockRejectedValue(new LorenzoApiError("gone", 404));
    const interaction = fakeModalSubmit("drop:take-modal:drop-1:item-1", "");

    await dropCommand.onModalSubmit?.(interaction, { config, logger: {} as never });

    expect(interaction.reply).toHaveBeenCalledWith(
      expect.objectContaining({ content: expect.stringContaining("already took") }),
    );
  });

  it("tells the caller to retry on a 412", async () => {
    getValidAccessToken.mockResolvedValue("token-123");
    resolveCurrentCharacter.mockResolvedValue("char-1");
    getItemInstance.mockResolvedValue({
      data: { entity_id: "item-1", title: "Torch", quantity: null, owner_entity_id: null },
      etag: "etag-1",
    });
    setItemInstanceOwner.mockRejectedValue(new LorenzoApiError("stale", 412));
    const interaction = fakeModalSubmit("drop:take-modal:drop-1:item-1", "");

    await dropCommand.onModalSubmit?.(interaction, { config, logger: {} as never });

    expect(interaction.reply).toHaveBeenCalledWith(
      expect.objectContaining({ content: expect.stringContaining("Someone else changed") }),
    );
  });
});

describe("dropCommand.onModalSubmit — claim", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("rejects a non-numeric quantity without touching the database", async () => {
    const interaction = fakeModalSubmit("drop:claim-modal:drop-1:item-1", "not-a-number");

    await dropCommand.onModalSubmit?.(interaction, { config, logger: {} as never });

    expect(interaction.reply).toHaveBeenCalledWith(
      expect.objectContaining({ content: expect.stringContaining("valid quantity") }),
    );
    expect(upsertLootClaim).not.toHaveBeenCalled();
  });

  it("upserts the claim with the resolved character and refreshes the message", async () => {
    resolveCurrentCharacter.mockResolvedValue("char-1");
    getLootDrop.mockResolvedValue({
      id: "drop-1",
      containerEntityId: "container-1",
      createdByDiscordUserId: "gm-1",
    });
    getValidAccessToken.mockResolvedValue("gm-token");
    getItemInstancesByContainer.mockResolvedValue([]);
    listLootClaims.mockResolvedValue([]);
    const interaction = fakeModalSubmit("drop:claim-modal:drop-1:item-1", "3");

    await dropCommand.onModalSubmit?.(interaction, { config, logger: {} as never });

    expect(upsertLootClaim).toHaveBeenCalledWith({
      lootDropId: "drop-1",
      itemEntityId: "item-1",
      discordUserId: "user-1",
      characterEntityId: "char-1",
      quantity: 3,
      claimType: "greed",
    });
    expect(interaction.update).toHaveBeenCalled();
  });

  it("records a need claim when the claim-type field says so", async () => {
    resolveCurrentCharacter.mockResolvedValue("char-1");
    getLootDrop.mockResolvedValue({
      id: "drop-1",
      containerEntityId: "container-1",
      createdByDiscordUserId: "gm-1",
    });
    getValidAccessToken.mockResolvedValue("gm-token");
    getItemInstancesByContainer.mockResolvedValue([]);
    listLootClaims.mockResolvedValue([]);
    const interaction = fakeModalSubmit("drop:claim-modal:drop-1:item-1", "", "user-1", "Need");

    await dropCommand.onModalSubmit?.(interaction, { config, logger: {} as never });

    expect(upsertLootClaim).toHaveBeenCalledWith(expect.objectContaining({ claimType: "need" }));
  });

  it("blank quantity claims null (whatever's left)", async () => {
    resolveCurrentCharacter.mockResolvedValue("char-1");
    getLootDrop.mockResolvedValue({
      id: "drop-1",
      containerEntityId: "container-1",
      createdByDiscordUserId: "gm-1",
    });
    getValidAccessToken.mockResolvedValue("gm-token");
    getItemInstancesByContainer.mockResolvedValue([]);
    listLootClaims.mockResolvedValue([]);
    const interaction = fakeModalSubmit("drop:claim-modal:drop-1:item-1", "  ");

    await dropCommand.onModalSubmit?.(interaction, { config, logger: {} as never });

    expect(upsertLootClaim).toHaveBeenCalledWith(expect.objectContaining({ quantity: null }));
  });
});

describe("dropCommand.onButton — apply claims", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("rejects a non-GM", async () => {
    getValidAccessToken.mockResolvedValue("token-123");
    isCampaignGm.mockResolvedValue(false);
    const interaction = fakeButton("drop:apply:drop-1");

    await dropCommand.onButton?.(interaction, { config, logger: {} as never });

    expect(interaction.reply).toHaveBeenCalledWith(
      expect.objectContaining({ content: expect.stringContaining("Only a GM") }),
    );
    expect(listLootClaims).not.toHaveBeenCalled();
  });

  it("resolves eligibility client-side, then applies everything eligible in one bulk-assign call", async () => {
    getValidAccessToken.mockResolvedValue("gm-token");
    isCampaignGm.mockResolvedValue(true);
    listLootClaims.mockResolvedValue([
      {
        lootDropId: "drop-1",
        itemEntityId: "item-1",
        discordUserId: "user-1",
        characterEntityId: "char-1",
        quantity: null,
        createdAt: new Date("2026-01-01T00:00:00Z"),
      },
      {
        lootDropId: "drop-1",
        itemEntityId: "item-1",
        discordUserId: "user-2",
        characterEntityId: "char-2",
        quantity: null,
        createdAt: new Date("2026-01-01T00:01:00Z"),
      },
      {
        lootDropId: "drop-1",
        itemEntityId: "item-2",
        discordUserId: "user-3",
        characterEntityId: "char-3",
        quantity: 10,
        createdAt: new Date("2026-01-01T00:02:00Z"),
      },
    ]);
    // One snapshot per unique item (not per claim) - item-1 is unowned, so
    // the *first* (oldest) of its two claims is eligible; the second is
    // rejected client-side (already assigned this run), never reaching
    // bulk-assign at all. Claim 3 asks for more of item-2 than its
    // snapshot has (10 > 5) - also rejected client-side, never sent.
    getItemInstance.mockImplementation(async (_tenantId: string, entityId: string) => {
      if (entityId === "item-1") {
        return {
          data: { entity_id: "item-1", title: "Sword", quantity: null, owner_entity_id: null },
          etag: "etag-1",
        };
      }
      return {
        data: { entity_id: "item-2", title: "Torch", quantity: 5, owner_entity_id: null },
        etag: "etag-2",
      };
    });
    bulkAssignItemInstances.mockResolvedValue([
      { entity_id: "item-1", status: "ok", item_instance: { entity_id: "item-1", title: "Sword" } },
    ]);
    const interaction = fakeButton("drop:apply:drop-1");

    await dropCommand.onButton?.(interaction, { config, logger: {} as never });

    expect(getItemInstance).toHaveBeenCalledTimes(2); // once per unique item, not per claim
    expect(setItemInstanceOwner).not.toHaveBeenCalled();
    expect(splitItemInstance).not.toHaveBeenCalled();
    expect(bulkAssignItemInstances).toHaveBeenCalledWith(
      "tenant-1",
      [
        {
          entity_id: "item-1",
          owner_character_id: "char-1",
          move_to_owner: false,
          if_match: "etag-1",
        },
      ],
      "gm-token",
    );
    expect(markLootDropApplied).toHaveBeenCalledWith("drop-1");
    expect(deleteLootClaimsForDrop).toHaveBeenCalledWith("drop-1");
    expect(interaction.editReply).toHaveBeenCalledWith(expect.objectContaining({ components: [] }));
  });

  it("splits a stack across two claims in the same batch, whole-transferring what's left to the last one", async () => {
    getValidAccessToken.mockResolvedValue("gm-token");
    isCampaignGm.mockResolvedValue(true);
    listLootClaims.mockResolvedValue([
      {
        lootDropId: "drop-1",
        itemEntityId: "item-1",
        discordUserId: "user-1",
        characterEntityId: "char-1",
        quantity: 2,
        createdAt: new Date("2026-01-01T00:00:00Z"),
      },
      {
        lootDropId: "drop-1",
        itemEntityId: "item-1",
        discordUserId: "user-2",
        characterEntityId: "char-2",
        quantity: null, // "whatever's left"
        createdAt: new Date("2026-01-01T00:01:00Z"),
      },
    ]);
    getItemInstance.mockResolvedValue({
      data: { entity_id: "item-1", title: "Arrows", quantity: 5, owner_entity_id: null },
      etag: "etag-1",
    });
    bulkAssignItemInstances.mockResolvedValue([
      {
        entity_id: "item-1",
        status: "ok",
        item_instance: { entity_id: "item-2", title: "Arrows" },
      },
      {
        entity_id: "item-1",
        status: "ok",
        item_instance: { entity_id: "item-1", title: "Arrows" },
      },
    ]);
    const interaction = fakeButton("drop:apply:drop-1");

    await dropCommand.onButton?.(interaction, { config, logger: {} as never });

    expect(bulkAssignItemInstances).toHaveBeenCalledWith(
      "tenant-1",
      [
        {
          entity_id: "item-1",
          owner_character_id: "char-1",
          move_to_owner: false,
          quantity: 2,
          if_match: "etag-1",
        },
        {
          entity_id: "item-1",
          owner_character_id: "char-2",
          move_to_owner: false,
          if_match: "etag-1",
        },
      ],
      "gm-token",
    );
  });

  it("rejects a claim for more than a stack's snapshotted quantity before ever calling bulk-assign", async () => {
    getValidAccessToken.mockResolvedValue("gm-token");
    isCampaignGm.mockResolvedValue(true);
    listLootClaims.mockResolvedValue([
      {
        lootDropId: "drop-1",
        itemEntityId: "item-2",
        discordUserId: "user-3",
        characterEntityId: "char-3",
        quantity: 10,
        createdAt: new Date("2026-01-01T00:02:00Z"),
      },
    ]);
    getItemInstance.mockResolvedValue({
      data: { entity_id: "item-2", title: "Torch", quantity: 5, owner_entity_id: null },
      etag: "etag-2",
    });
    const interaction = fakeButton("drop:apply:drop-1");

    await dropCommand.onButton?.(interaction, { config, logger: {} as never });

    expect(bulkAssignItemInstances).not.toHaveBeenCalled();
  });

  it("gives a need claim first crack at a non-stack item, even though it was claimed second", async () => {
    getValidAccessToken.mockResolvedValue("gm-token");
    isCampaignGm.mockResolvedValue(true);
    listLootClaims.mockResolvedValue([
      {
        lootDropId: "drop-1",
        itemEntityId: "item-1",
        discordUserId: "user-greed",
        characterEntityId: "char-greed",
        quantity: null,
        claimType: "greed",
        createdAt: new Date("2026-01-01T00:00:00Z"),
      },
      {
        lootDropId: "drop-1",
        itemEntityId: "item-1",
        discordUserId: "user-need",
        characterEntityId: "char-need",
        quantity: null,
        claimType: "need",
        createdAt: new Date("2026-01-01T00:01:00Z"),
      },
    ]);
    getItemInstance.mockResolvedValue({
      data: { entity_id: "item-1", title: "Sword", quantity: null, owner_entity_id: null },
      etag: "etag-1",
    });
    bulkAssignItemInstances.mockResolvedValue([
      { entity_id: "item-1", status: "ok", item_instance: { entity_id: "item-1", title: "Sword" } },
    ]);
    const interaction = fakeButton("drop:apply:drop-1");

    await dropCommand.onButton?.(interaction, { config, logger: {} as never });

    // Only one bulk-assign entry: the need claim wins the non-stack item
    // even though the greed claim was made first (ADR 0068).
    expect(bulkAssignItemInstances).toHaveBeenCalledWith(
      "tenant-1",
      [
        {
          entity_id: "item-1",
          owner_character_id: "char-need",
          move_to_owner: false,
          if_match: "etag-1",
        },
      ],
      "gm-token",
    );
  });
});

describe("dropCommand.onButton — clear claims", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("rejects a non-GM, without touching any claim", async () => {
    getValidAccessToken.mockResolvedValue("token-123");
    isCampaignGm.mockResolvedValue(false);
    const interaction = fakeButton("drop:clear:drop-1");

    await dropCommand.onButton?.(interaction, { config, logger: {} as never });

    expect(interaction.reply).toHaveBeenCalledWith(
      expect.objectContaining({ content: expect.stringContaining("Only a GM") }),
    );
    expect(deleteLootClaimsForDrop).not.toHaveBeenCalled();
  });

  it("discards every claim and leaves the drop open, unlike apply", async () => {
    getValidAccessToken.mockResolvedValue("gm-token");
    isCampaignGm.mockResolvedValue(true);
    getLootDrop.mockResolvedValue({
      id: "drop-1",
      containerEntityId: "container-1",
      createdByDiscordUserId: "gm-1",
    });
    getItemInstancesByContainer.mockResolvedValue([]);
    listLootClaims.mockResolvedValue([]);
    const interaction = fakeButton("drop:clear:drop-1");

    await dropCommand.onButton?.(interaction, { config, logger: {} as never });

    expect(deleteLootClaimsForDrop).toHaveBeenCalledWith("drop-1");
    expect(markLootDropApplied).not.toHaveBeenCalled();
    expect(interaction.editReply).toHaveBeenCalledWith(
      expect.objectContaining({ embeds: expect.anything(), components: expect.anything() }),
    );
  });
});

describe("dropCommand.autocomplete", () => {
  function fakeAutocomplete(value = "") {
    return {
      user: { id: "gm-1" },
      options: { getFocused: vi.fn(() => ({ name: "container", value })) },
      respond: vi.fn(async () => undefined),
    } as unknown as AutocompleteInteraction & { respond: ReturnType<typeof vi.fn> };
  }

  function owned(entityId: string, title: string, over: Record<string, unknown> = {}) {
    return { entityId, title, quantity: null, isContainer: true, slug: null, ...over };
  }

  beforeEach(() => {
    vi.clearAllMocks();
    getUnownedItemInstances.mockResolvedValue([]);
    getMyItemInstances.mockResolvedValue([]);
  });

  it("responds with no choices when there's no valid access token", async () => {
    getValidAccessToken.mockResolvedValue(null);
    const interaction = fakeAutocomplete();

    await dropCommand.autocomplete?.(interaction, { config, logger: {} as never });

    expect(interaction.respond).toHaveBeenCalledWith([]);
    expect(getUnownedItemInstances).not.toHaveBeenCalled();
  });

  it("suggests a GM's ownerless loot container, which their own inventory never lists", async () => {
    getValidAccessToken.mockResolvedValue("gm-token");
    getUnownedItemInstances.mockResolvedValue([owned("chest-1", "Goblin hoard")]);
    const interaction = fakeAutocomplete();

    await dropCommand.autocomplete?.(interaction, { config, logger: {} as never });

    expect(getUnownedItemInstances).toHaveBeenCalledWith("tenant-1", "gm-token");
    expect(interaction.respond).toHaveBeenCalledWith([{ name: "Goblin hoard", value: "chest-1" }]);
  });

  it("also suggests containers the caller owns, and only container-capable ones", async () => {
    getValidAccessToken.mockResolvedValue("gm-token");
    getUnownedItemInstances.mockResolvedValue([
      owned("chest-1", "Goblin hoard"),
      owned("sword-1", "Sword", { isContainer: false }),
      owned("rope-1", "Rope", { isContainer: null }),
    ]);
    getMyItemInstances.mockResolvedValue([
      owned("bag-1", "Bag of holding"),
      owned("torch-1", "Torch", { isContainer: false }),
    ]);
    const interaction = fakeAutocomplete();

    await dropCommand.autocomplete?.(interaction, { config, logger: {} as never });

    expect(interaction.respond).toHaveBeenCalledWith([
      { name: "Goblin hoard", value: "chest-1" },
      { name: "Bag of holding", value: "bag-1" },
    ]);
  });

  it("lists a container once even if both sources return it", async () => {
    getValidAccessToken.mockResolvedValue("gm-token");
    getUnownedItemInstances.mockResolvedValue([owned("chest-1", "Goblin hoard")]);
    getMyItemInstances.mockResolvedValue([owned("chest-1", "Goblin hoard")]);
    const interaction = fakeAutocomplete();

    await dropCommand.autocomplete?.(interaction, { config, logger: {} as never });

    expect(interaction.respond).toHaveBeenCalledWith([{ name: "Goblin hoard", value: "chest-1" }]);
  });

  it("shows the slug in the choice name, and matches what's typed against it", async () => {
    getValidAccessToken.mockResolvedValue("gm-token");
    getUnownedItemInstances.mockResolvedValue([
      owned("chest-1", "Goblin hoard", { slug: "goblin-hoard" }),
      owned("chest-2", "Dragon cache", { slug: "wyrm-vault" }),
    ]);
    const interaction = fakeAutocomplete("wyrm");

    await dropCommand.autocomplete?.(interaction, { config, logger: {} as never });

    expect(interaction.respond).toHaveBeenCalledWith([
      { name: "Dragon cache [wyrm-vault]", value: "chest-2" },
    ]);
  });
});
