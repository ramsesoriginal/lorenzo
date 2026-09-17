import { beforeEach, describe, expect, it, vi } from "vitest";
import type {
  AutocompleteInteraction,
  ChatInputCommandInteraction,
} from "../src/commands/types.js";
import type { Config } from "../src/config.js";
import { LorenzoApiError } from "../src/lorenzo-client.js";

const { getValidAccessToken } = vi.hoisted(() => ({ getValidAccessToken: vi.fn() }));
vi.mock("../src/token-provider.js", () => ({ getValidAccessToken }));

const { getMyItemInstances, bulkMoveItemInstancesFromContainer, createLorenzoApiClient } =
  vi.hoisted(() => ({
    getMyItemInstances: vi.fn(),
    bulkMoveItemInstancesFromContainer: vi.fn(),
    createLorenzoApiClient: vi.fn(),
  }));
vi.mock("../src/lorenzo-client.js", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../src/lorenzo-client.js")>();
  return {
    ...actual,
    createLorenzoApiClient: createLorenzoApiClient.mockReturnValue({
      getMyItemInstances,
      bulkMoveItemInstancesFromContainer,
    }),
  };
});

const { moveBulkCommand } = await import("../src/commands/move-bulk.js");

const config = {
  lorenzoApiBaseUrl: "http://lorenzo-api.test",
  lorenzoTenantId: "tenant-1",
} as Config;

function fakeInteraction() {
  return {
    user: { id: "discord-user-1" },
    options: {
      getString: vi.fn((name: string) => (name === "from" ? "container-1" : "container-2")),
    },
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
    user: { id: "discord-user-1" },
    options: { getFocused: vi.fn(() => ({ name: "from", value })) },
    respond: vi.fn(async () => undefined),
  } as unknown as AutocompleteInteraction & { respond: ReturnType<typeof vi.fn> };
}

describe("moveBulkCommand.execute", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("prompts to /link when there's no valid access token", async () => {
    getValidAccessToken.mockResolvedValue(null);
    const interaction = fakeInteraction();

    await moveBulkCommand.execute(interaction, { config, logger: {} as never });

    expect(interaction.editReply).toHaveBeenCalledWith(
      expect.stringContaining("run `/link` first"),
    );
    expect(bulkMoveItemInstancesFromContainer).not.toHaveBeenCalled();
  });

  it("rejects moving a container into itself, before calling the API", async () => {
    getValidAccessToken.mockResolvedValue("token-123");
    const interaction = fakeInteraction();
    interaction.options.getString.mockImplementation(() => "container-1");

    await moveBulkCommand.execute(interaction, { config, logger: {} as never });

    expect(interaction.editReply).toHaveBeenCalledWith(expect.stringContaining("no-op"));
    expect(bulkMoveItemInstancesFromContainer).not.toHaveBeenCalled();
  });

  it("moves everything and reports how many succeeded/failed", async () => {
    getValidAccessToken.mockResolvedValue("token-123");
    bulkMoveItemInstancesFromContainer.mockResolvedValue([
      { entity_id: "item-1", status: "ok" },
      { entity_id: "item-2", status: "error" },
    ]);
    const interaction = fakeInteraction();

    await moveBulkCommand.execute(interaction, { config, logger: {} as never });

    expect(bulkMoveItemInstancesFromContainer).toHaveBeenCalledWith(
      "tenant-1",
      "container-1",
      "container-2",
      "token-123",
    );
    expect(interaction.editReply).toHaveBeenCalledWith(
      "Moved 1 item.\n1 couldn't be moved — they may not be reachable from you.",
    );
  });

  it("tells the caller the container was already empty", async () => {
    getValidAccessToken.mockResolvedValue("token-123");
    bulkMoveItemInstancesFromContainer.mockResolvedValue([]);
    const interaction = fakeInteraction();

    await moveBulkCommand.execute(interaction, { config, logger: {} as never });

    expect(interaction.editReply).toHaveBeenCalledWith(expect.stringContaining("already empty"));
  });

  it.each([
    [404, "Couldn't find one of those containers"],
    [422, "Couldn't do that"],
  ])("gives a specific message for a %i error", async (status, expectedText) => {
    getValidAccessToken.mockResolvedValue("token-123");
    bulkMoveItemInstancesFromContainer.mockRejectedValue(new LorenzoApiError("boom", status));
    const interaction = fakeInteraction();

    await moveBulkCommand.execute(interaction, { config, logger: {} as never });

    expect(interaction.editReply).toHaveBeenCalledWith(expect.stringContaining(expectedText));
  });
});

describe("moveBulkCommand.autocomplete", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("responds with no choices when there's no valid access token", async () => {
    getValidAccessToken.mockResolvedValue(null);
    const interaction = fakeAutocomplete();

    await moveBulkCommand.autocomplete?.(interaction, { config, logger: {} as never });

    expect(interaction.respond).toHaveBeenCalledWith([]);
  });

  it("suggests only items flagged as containers", async () => {
    getValidAccessToken.mockResolvedValue("token-123");
    getMyItemInstances.mockResolvedValue([
      { entityId: "item-1", title: "Backpack", quantity: null, isContainer: true },
      { entityId: "item-2", title: "Sword", quantity: null, isContainer: false },
    ]);

    const interaction = fakeAutocomplete("back");
    await moveBulkCommand.autocomplete?.(interaction, { config, logger: {} as never });

    expect(interaction.respond).toHaveBeenCalledWith([{ name: "Backpack", value: "item-1" }]);
  });
});
