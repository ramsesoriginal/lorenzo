import { beforeEach, describe, expect, it, vi } from "vitest";
import type {
  ChatInputCommandInteraction,
  StringSelectMenuInteraction,
} from "../src/commands/types.js";
import type { Config } from "../src/config.js";

const { getValidAccessToken } = vi.hoisted(() => ({ getValidAccessToken: vi.fn() }));
vi.mock("../src/token-provider.js", () => ({ getValidAccessToken }));

const { recordCharacterEvents } = vi.hoisted(() => ({ recordCharacterEvents: vi.fn() }));
vi.mock("../src/character-events.js", async (importOriginal) => ({
  ...(await importOriginal<typeof import("../src/character-events.js")>()),
  recordCharacterEvents,
}));

const { storePendingBulkGive, consumePendingBulkGive } = vi.hoisted(() => ({
  storePendingBulkGive: vi.fn(),
  consumePendingBulkGive: vi.fn(),
}));
vi.mock("../src/pending-bulk-give.js", () => ({ storePendingBulkGive, consumePendingBulkGive }));

const {
  getMyItemInstances,
  getMyPlayers,
  getCharacterName,
  bulkAssignItemInstances,
  createLorenzoApiClient,
} = vi.hoisted(() => ({
  getMyItemInstances: vi.fn(),
  getMyPlayers: vi.fn(),
  getCharacterName: vi.fn(),
  bulkAssignItemInstances: vi.fn(),
  createLorenzoApiClient: vi.fn(),
}));
vi.mock("../src/lorenzo-client.js", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../src/lorenzo-client.js")>();
  return {
    ...actual,
    createLorenzoApiClient: createLorenzoApiClient.mockReturnValue({
      getMyItemInstances,
      getMyPlayers,
      getCharacterName,
      bulkAssignItemInstances,
    }),
  };
});

const { giveBulkCommand } = await import("../src/commands/give-bulk.js");

const config = {
  lorenzoApiBaseUrl: "http://lorenzo-api.test",
  lorenzoTenantId: "tenant-1",
} as Config;

function fakeExecuteInteraction() {
  return {
    user: { id: "discord-user-1" },
    deferReply: vi.fn(async () => undefined),
    editReply: vi.fn(async () => undefined),
  } as unknown as ChatInputCommandInteraction & {
    deferReply: ReturnType<typeof vi.fn>;
    editReply: ReturnType<typeof vi.fn>;
  };
}

function fakeSelectMenu(customId: string, values: string[]) {
  return {
    user: { id: "discord-user-1" },
    customId,
    values,
    update: vi.fn(async () => undefined),
  } as unknown as StringSelectMenuInteraction & { update: ReturnType<typeof vi.fn> };
}

describe("giveBulkCommand.execute", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("prompts to /link when there's no valid access token", async () => {
    getValidAccessToken.mockResolvedValue(null);
    const interaction = fakeExecuteInteraction();

    await giveBulkCommand.execute(interaction, { config, logger: {} as never });

    expect(interaction.editReply).toHaveBeenCalledWith(
      expect.stringContaining("run `/link` first"),
    );
  });

  it("tells the caller they have nothing to give", async () => {
    getValidAccessToken.mockResolvedValue("token-123");
    getMyItemInstances.mockResolvedValue([]);
    const interaction = fakeExecuteInteraction();

    await giveBulkCommand.execute(interaction, { config, logger: {} as never });

    expect(interaction.editReply).toHaveBeenCalledWith(
      expect.stringContaining("don't have any items"),
    );
  });

  it("posts a multi-select of the caller's own items", async () => {
    getValidAccessToken.mockResolvedValue("token-123");
    getMyItemInstances.mockResolvedValue([
      { entityId: "item-1", title: "Torch", quantity: 5 },
      { entityId: "item-2", title: "Sword", quantity: null },
    ]);
    const interaction = fakeExecuteInteraction();

    await giveBulkCommand.execute(interaction, { config, logger: {} as never });

    const call = interaction.editReply.mock.calls[0]?.[0];
    const menuJson = call.components[0].components[0].toJSON();
    expect(menuJson.custom_id).toBe("give-bulk:pick-items");
    expect(menuJson.options).toHaveLength(2);
  });
});

describe("giveBulkCommand.onSelectMenu", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("stores the chosen items and shows a target-character select", async () => {
    getValidAccessToken.mockResolvedValue("token-123");
    storePendingBulkGive.mockReturnValue("token-abc");
    getMyPlayers.mockResolvedValue([
      { campaignId: "campaign-1", characters: [{ entityId: "char-1", name: "Frodo" }] },
    ]);
    const interaction = fakeSelectMenu("give-bulk:pick-items", ["item-1", "item-2"]);

    await giveBulkCommand.onSelectMenu?.(interaction, { config, logger: {} as never });

    expect(storePendingBulkGive).toHaveBeenCalledWith({
      discordUserId: "discord-user-1",
      itemEntityIds: ["item-1", "item-2"],
    });
    const call = interaction.update.mock.calls[0]?.[0];
    expect(call.components[0].components[0].toJSON().custom_id).toBe(
      "give-bulk:pick-target:token-abc",
    );
  });

  it("tells the caller they control no characters to give to", async () => {
    getValidAccessToken.mockResolvedValue("token-123");
    storePendingBulkGive.mockReturnValue("token-abc");
    getMyPlayers.mockResolvedValue([]);
    const interaction = fakeSelectMenu("give-bulk:pick-items", ["item-1"]);

    await giveBulkCommand.onSelectMenu?.(interaction, { config, logger: {} as never });

    expect(interaction.update).toHaveBeenCalledWith(
      expect.objectContaining({ content: expect.stringContaining("don't control any characters") }),
    );
  });

  it("applies the bulk-assign once a target is chosen and summarizes the outcome", async () => {
    getValidAccessToken.mockResolvedValue("token-123");
    consumePendingBulkGive.mockReturnValue({
      discordUserId: "discord-user-1",
      itemEntityIds: ["item-1", "item-2"],
    });
    bulkAssignItemInstances.mockResolvedValue([
      { entity_id: "item-1", status: "ok" },
      { entity_id: "item-2", status: "error" },
    ]);
    getCharacterName.mockResolvedValue("Sam");
    const interaction = fakeSelectMenu("give-bulk:pick-target:token-abc", ["char-2"]);

    await giveBulkCommand.onSelectMenu?.(interaction, { config, logger: {} as never });

    expect(bulkAssignItemInstances).toHaveBeenCalledWith(
      "tenant-1",
      [
        { entity_id: "item-1", owner_character_id: "char-2" },
        { entity_id: "item-2", owner_character_id: "char-2" },
      ],
      "token-123",
    );
    expect(interaction.update).toHaveBeenCalledWith({
      content:
        "Gave 1 item to Sam.\n1 couldn't be given — they may no longer be reachable from you.",
      components: [],
    });
  });

  it("rejects an expired or foreign token", async () => {
    getValidAccessToken.mockResolvedValue("token-123");
    consumePendingBulkGive.mockReturnValue(undefined);
    const interaction = fakeSelectMenu("give-bulk:pick-target:token-abc", ["char-2"]);

    await giveBulkCommand.onSelectMenu?.(interaction, { config, logger: {} as never });

    expect(interaction.update).toHaveBeenCalledWith(
      expect.objectContaining({ content: expect.stringContaining("expired") }),
    );
    expect(bulkAssignItemInstances).not.toHaveBeenCalled();
  });
});

describe("giveBulkCommand - recording for /changes (ADR 0097)", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  function arrange(results: unknown[]) {
    getValidAccessToken.mockResolvedValue("token-123");
    consumePendingBulkGive.mockReturnValue({
      discordUserId: "discord-user-1",
      itemEntityIds: ["item-1", "item-2", "item-3"],
    });
    bulkAssignItemInstances.mockResolvedValue(results);
    getCharacterName.mockResolvedValue("Sam");
    return fakeSelectMenu("give-bulk:pick-target:token-abc", ["char-2"]);
  }

  it("records what arrived for the receiver - only the items that actually moved", async () => {
    const menu = arrange([
      { entity_id: "item-1", status: "ok", item_instance: { title: "Sword", quantity: null } },
      { entity_id: "item-2", status: "ok", item_instance: { title: "Torch", quantity: 5 } },
      { entity_id: "item-3", status: "error" },
    ]);

    await giveBulkCommand.onSelectMenu?.(menu, { config, logger: {} as never });

    expect(recordCharacterEvents).toHaveBeenCalledWith(
      [
        expect.objectContaining({
          kind: "given-in-bulk",
          summary: "Sam was given 2 items: Sword, Torch ×5.",
          characterEntityIds: ["char-2"],
        }),
      ],
      expect.anything(),
    );
  });

  it("records nothing when nothing moved", async () => {
    const menu = arrange([{ entity_id: "item-1", status: "error" }]);

    await giveBulkCommand.onSelectMenu?.(menu, { config, logger: {} as never });

    expect(recordCharacterEvents).not.toHaveBeenCalled();
  });
});
