import { beforeEach, describe, expect, it, vi } from "vitest";
import type {
  AutocompleteInteraction,
  ChatInputCommandInteraction,
} from "../src/commands/types.js";
import type { Config } from "../src/config.js";
import { LorenzoApiError } from "../src/lorenzo-client.js";

const { getValidAccessToken } = vi.hoisted(() => ({ getValidAccessToken: vi.fn() }));
vi.mock("../src/token-provider.js", () => ({ getValidAccessToken }));

const { getMyItemInstances, getEntity, createLorenzoApiClient } = vi.hoisted(() => ({
  getMyItemInstances: vi.fn(),
  getEntity: vi.fn(),
  createLorenzoApiClient: vi.fn(),
}));
vi.mock("../src/lorenzo-client.js", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../src/lorenzo-client.js")>();
  return {
    ...actual,
    createLorenzoApiClient: createLorenzoApiClient.mockReturnValue({
      getMyItemInstances,
      getEntity,
    }),
  };
});

const { itemCommand } = await import("../src/commands/item.js");

const config = {
  lorenzoApiBaseUrl: "http://lorenzo-api.test",
  lorenzoTenantId: "tenant-1",
} as Config;

function fakeInteraction(userId = "user-1") {
  return {
    user: { id: userId },
    options: { getString: vi.fn(() => "item-1") },
    deferReply: vi.fn(async () => undefined),
    editReply: vi.fn(async () => undefined),
  } as unknown as ChatInputCommandInteraction & {
    options: { getString: ReturnType<typeof vi.fn> };
    deferReply: ReturnType<typeof vi.fn>;
    editReply: ReturnType<typeof vi.fn>;
  };
}

function fakeAutocomplete(value = "") {
  return {
    user: { id: "user-1" },
    options: { getFocused: vi.fn(() => ({ name: "item", value })) },
    respond: vi.fn(async () => undefined),
  } as unknown as AutocompleteInteraction & { respond: ReturnType<typeof vi.fn> };
}

describe("itemCommand.execute", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("prompts to /link when there's no valid access token", async () => {
    getValidAccessToken.mockResolvedValue(null);
    const interaction = fakeInteraction();

    await itemCommand.execute(interaction, { config, logger: {} as never });

    expect(interaction.editReply).toHaveBeenCalledWith(
      expect.stringContaining("run `/link` first"),
    );
    expect(getEntity).not.toHaveBeenCalled();
  });

  it("replies with an embed built from the fetched entity", async () => {
    getValidAccessToken.mockResolvedValue("token-123");
    getEntity.mockResolvedValue({
      id: "item-1",
      name: "Ashfang",
      created_at: "2026-01-01T00:00:00Z",
      updated_at: "2026-01-01T00:00:00Z",
      stats: [],
      stat_groups: [],
      information: [],
      prototypes: [],
      instances: [],
      parent: null,
      quantity: null,
      children: [],
    });
    const interaction = fakeInteraction();

    await itemCommand.execute(interaction, { config, logger: {} as never });

    expect(getEntity).toHaveBeenCalledWith("tenant-1", "item-1", "token-123");
    expect(interaction.editReply).toHaveBeenCalledWith(
      expect.objectContaining({ embeds: expect.any(Array) }),
    );
  });

  it("gives a friendly message for an unknown item", async () => {
    getValidAccessToken.mockResolvedValue("token-123");
    getEntity.mockRejectedValue(new LorenzoApiError("not found", 404));
    const interaction = fakeInteraction();

    await itemCommand.execute(interaction, { config, logger: {} as never });

    expect(interaction.editReply).toHaveBeenCalledWith(
      expect.stringContaining("Couldn't find that item"),
    );
  });

  it("rethrows a non-404 error for the generic handler", async () => {
    getValidAccessToken.mockResolvedValue("token-123");
    getEntity.mockRejectedValue(new LorenzoApiError("forbidden", 403));
    const interaction = fakeInteraction();

    await expect(itemCommand.execute(interaction, { config, logger: {} as never })).rejects.toThrow(
      "forbidden",
    );
  });
});

describe("itemCommand.autocomplete", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("responds with no choices when there's no valid access token", async () => {
    getValidAccessToken.mockResolvedValue(null);
    const interaction = fakeAutocomplete();

    await itemCommand.autocomplete?.(interaction, { config, logger: {} as never });

    expect(interaction.respond).toHaveBeenCalledWith([]);
  });

  it("suggests the caller's own items", async () => {
    getValidAccessToken.mockResolvedValue("token-123");
    getMyItemInstances.mockResolvedValue([
      { entityId: "item-1", title: "Torch", quantity: 5 },
      { entityId: "item-2", title: "Sword", quantity: null },
    ]);

    const interaction = fakeAutocomplete("sw");
    await itemCommand.autocomplete?.(interaction, { config, logger: {} as never });

    expect(interaction.respond).toHaveBeenCalledWith([{ name: "Sword", value: "item-2" }]);
  });
});
