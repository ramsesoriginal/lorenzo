import { beforeEach, describe, expect, it, vi } from "vitest";
import type {
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
  getItemInstance,
  splitItemInstance,
  setItemInstanceOwner,
  createLorenzoApiClient,
} = vi.hoisted(() => ({
  isCampaignGm: vi.fn(),
  getItemInstancesByContainer: vi.fn(),
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
      getItemInstancesByContainer,
      getItemInstance,
      splitItemInstance,
      setItemInstanceOwner,
    }),
  };
});

const { dropCommand } = await import("../src/commands/drop.js");

const config = {
  lorenzoApiBaseUrl: "http://lorenzo-api.test",
  lorenzoTenantId: "tenant-1",
} as Config;

function fakeExecuteInteraction(userId = "gm-1") {
  return {
    user: { id: userId },
    channelId: "channel-1",
    options: { getString: vi.fn(() => "container-1") },
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

function fakeModalSubmit(customId: string, quantity: string, userId = "user-1") {
  return {
    user: { id: userId },
    customId,
    fields: { getTextInputValue: vi.fn(() => quantity) },
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
      containerEntityId: "container-1",
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
    });
    expect(interaction.update).toHaveBeenCalled();
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

  it("processes each claim, reports mixed outcomes, and cleans up", async () => {
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
    // First claim on item-1: unowned -> succeeds. Second claim on item-1
    // re-fetches fresh and sees it's now owned by char-1 -> already-taken.
    getItemInstance
      .mockResolvedValueOnce({
        data: { entity_id: "item-1", title: "Sword", quantity: null, owner_entity_id: null },
        etag: "etag-1",
      })
      .mockResolvedValueOnce({
        data: { entity_id: "item-1", title: "Sword", quantity: null, owner_entity_id: "char-1" },
        etag: "etag-1b",
      })
      .mockResolvedValueOnce({
        data: { entity_id: "item-2", title: "Torch", quantity: 5, owner_entity_id: null },
        etag: "etag-2",
      });
    setItemInstanceOwner.mockResolvedValue({ entity_id: "item-1", title: "Sword" });
    const interaction = fakeButton("drop:apply:drop-1");

    await dropCommand.onButton?.(interaction, { config, logger: {} as never });

    expect(setItemInstanceOwner).toHaveBeenCalledTimes(1);
    expect(setItemInstanceOwner).toHaveBeenCalledWith(
      "tenant-1",
      "item-1",
      "char-1",
      "gm-token",
      "etag-1",
    );
    expect(splitItemInstance).not.toHaveBeenCalled(); // claim 3 requested more than the 5 available
    expect(markLootDropApplied).toHaveBeenCalledWith("drop-1");
    expect(deleteLootClaimsForDrop).toHaveBeenCalledWith("drop-1");
    expect(interaction.editReply).toHaveBeenCalledWith(expect.objectContaining({ components: [] }));
  });
});
