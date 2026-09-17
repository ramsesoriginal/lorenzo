import { beforeEach, describe, expect, it, vi } from "vitest";
import type { ChatInputCommandInteraction } from "../src/commands/types.js";
import type { Config } from "../src/config.js";

const { getValidAccessToken } = vi.hoisted(() => ({ getValidAccessToken: vi.fn() }));
vi.mock("../src/token-provider.js", () => ({ getValidAccessToken }));

const { listOpenLootDrops, listLootClaims } = vi.hoisted(() => ({
  listOpenLootDrops: vi.fn(),
  listLootClaims: vi.fn(),
}));
vi.mock("../src/db.js", () => ({ listOpenLootDrops, listLootClaims }));

const { getItemInstancesByContainer, getItemInstance, createLorenzoApiClient } = vi.hoisted(() => ({
  getItemInstancesByContainer: vi.fn(),
  getItemInstance: vi.fn(),
  createLorenzoApiClient: vi.fn(),
}));
vi.mock("../src/lorenzo-client.js", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../src/lorenzo-client.js")>();
  return {
    ...actual,
    createLorenzoApiClient: createLorenzoApiClient.mockReturnValue({
      getItemInstancesByContainer,
      getItemInstance,
    }),
  };
});

const { pendingClaimsCommand } = await import("../src/commands/pending-claims.js");

const config = {
  lorenzoApiBaseUrl: "http://lorenzo-api.test",
  lorenzoTenantId: "tenant-1",
  discordGuildId: "guild-1",
} as Config;

function fakeInteraction(userId = "user-1") {
  return {
    user: { id: userId },
    deferReply: vi.fn(async () => undefined),
    editReply: vi.fn(async () => undefined),
  } as unknown as ChatInputCommandInteraction & {
    deferReply: ReturnType<typeof vi.fn>;
    editReply: ReturnType<typeof vi.fn>;
  };
}

describe("pendingClaimsCommand.execute", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("prompts to /link when there's no valid access token", async () => {
    getValidAccessToken.mockResolvedValue(null);
    const interaction = fakeInteraction();

    await pendingClaimsCommand.execute(interaction, { config, logger: {} as never });

    expect(interaction.editReply).toHaveBeenCalledWith(
      expect.stringContaining("run `/link` first"),
    );
    expect(listOpenLootDrops).not.toHaveBeenCalled();
  });

  it("is not GM-gated - any linked caller can run it", async () => {
    getValidAccessToken.mockResolvedValue("token-123");
    listOpenLootDrops.mockResolvedValue([]);
    const interaction = fakeInteraction();

    await pendingClaimsCommand.execute(interaction, { config, logger: {} as never });

    const call = interaction.editReply.mock.calls[0]?.[0];
    expect(call.embeds[0].data.description).toContain("No pending drops");
  });

  it("summarizes each open drop's outstanding claims with resolved titles", async () => {
    getValidAccessToken.mockResolvedValue("token-123");
    listOpenLootDrops.mockResolvedValue([
      {
        id: "drop-1",
        containerEntityId: "container-1",
        discordChannelId: "channel-1",
        discordMessageId: "message-1",
        status: "open",
      },
    ]);
    getItemInstance.mockResolvedValue({ data: { title: "Treasure Chest" } });
    getItemInstancesByContainer.mockResolvedValue([{ entity_id: "item-1", title: "Torch" }]);
    listLootClaims.mockResolvedValue([
      {
        lootDropId: "drop-1",
        itemEntityId: "item-1",
        discordUserId: "user-2",
        characterEntityId: "char-2",
        quantity: 3,
        claimType: "need",
        createdAt: new Date(),
      },
    ]);
    const interaction = fakeInteraction();

    await pendingClaimsCommand.execute(interaction, { config, logger: {} as never });

    const call = interaction.editReply.mock.calls[0]?.[0];
    const field = call.embeds[0].data.fields[0];
    expect(field.name).toBe("Treasure Chest");
    expect(field.value).toContain("<@user-2> wants 3 of **Torch** (need)");
  });

  it("falls back gracefully when the container/item lookups fail", async () => {
    getValidAccessToken.mockResolvedValue("token-123");
    listOpenLootDrops.mockResolvedValue([
      {
        id: "drop-1",
        containerEntityId: "container-1",
        discordChannelId: "channel-1",
        discordMessageId: null,
        status: "open",
      },
    ]);
    getItemInstance.mockRejectedValue(new Error("not visible"));
    getItemInstancesByContainer.mockRejectedValue(new Error("not visible"));
    listLootClaims.mockResolvedValue([
      {
        lootDropId: "drop-1",
        itemEntityId: "item-1",
        discordUserId: "user-2",
        characterEntityId: "char-2",
        quantity: null,
        claimType: "greed",
        createdAt: new Date(),
      },
    ]);
    const interaction = fakeInteraction();

    await pendingClaimsCommand.execute(interaction, { config, logger: {} as never });

    const call = interaction.editReply.mock.calls[0]?.[0];
    const field = call.embeds[0].data.fields[0];
    expect(field.name).toBe("(container)");
    expect(field.value).toContain("(item no longer available)");
  });
});
