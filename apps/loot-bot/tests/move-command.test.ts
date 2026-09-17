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

const { getMyItemInstances, getItemInstance, setItemInstanceContainer, createLorenzoApiClient } =
  vi.hoisted(() => ({
    getMyItemInstances: vi.fn(),
    getItemInstance: vi.fn(),
    setItemInstanceContainer: vi.fn(),
    createLorenzoApiClient: vi.fn(),
  }));
vi.mock("../src/lorenzo-client.js", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../src/lorenzo-client.js")>();
  return {
    ...actual,
    createLorenzoApiClient: createLorenzoApiClient.mockReturnValue({
      getMyItemInstances,
      getItemInstance,
      setItemInstanceContainer,
    }),
  };
});

const { moveCommand } = await import("../src/commands/move.js");

const config = {
  lorenzoApiBaseUrl: "http://lorenzo-api.test",
  lorenzoTenantId: "tenant-1",
} as Config;

function fakeInteraction() {
  return {
    user: { id: "user-1" },
    options: { getString: vi.fn() },
    deferReply: vi.fn(async () => undefined),
    editReply: vi.fn(async () => undefined),
  } as unknown as ChatInputCommandInteraction & {
    options: { getString: ReturnType<typeof vi.fn> };
    deferReply: ReturnType<typeof vi.fn>;
    editReply: ReturnType<typeof vi.fn>;
  };
}

function fakeAutocomplete(value = "", focusedName: "item" | "container" = "item") {
  return {
    user: { id: "user-1" },
    options: { getFocused: vi.fn(() => ({ name: focusedName, value })) },
    respond: vi.fn(async () => undefined),
  } as unknown as AutocompleteInteraction & { respond: ReturnType<typeof vi.fn> };
}

describe("moveCommand.execute", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("prompts to /link when there's no valid access token", async () => {
    getValidAccessToken.mockResolvedValue(null);
    const interaction = fakeInteraction();

    await moveCommand.execute(interaction, { config, logger: {} as never });

    expect(interaction.editReply).toHaveBeenCalledWith(
      expect.stringContaining("run `/link` first"),
    );
    expect(setItemInstanceContainer).not.toHaveBeenCalled();
  });

  it("moves the item with a fresh etag and confirms", async () => {
    getValidAccessToken.mockResolvedValue("token-123");
    getItemInstance.mockResolvedValue({
      data: { entity_id: "item-1", container_entity_id: "old-container-1" },
      etag: "etag-1",
    });
    setItemInstanceContainer.mockResolvedValue({ entity_id: "item-1", title: "Torch" });
    const interaction = fakeInteraction();
    interaction.options.getString.mockImplementation((name: string) =>
      name === "item" ? "item-1" : "container-1",
    );

    await moveCommand.execute(interaction, { config, logger: {} as never });

    expect(setItemInstanceContainer).toHaveBeenCalledWith(
      "tenant-1",
      "item-1",
      "container-1",
      "token-123",
      "etag-1",
    );
    expect(interaction.editReply).toHaveBeenCalledWith("Moved Torch.");
    expect(recordUndo).toHaveBeenCalledWith("user-1", {
      kind: "restore-container",
      entityId: "item-1",
      previousContainerEntityId: "old-container-1",
    });
  });

  it.each([
    [403, "reachable from any of your characters"],
    [404, "Couldn't find that item"],
    [412, "Someone else changed"],
    [422, "Couldn't do that"],
  ])("gives a specific message for a %i error", async (status, expectedText) => {
    getValidAccessToken.mockResolvedValue("token-123");
    getItemInstance.mockRejectedValue(new LorenzoApiError("boom", status));
    const interaction = fakeInteraction();
    interaction.options.getString.mockImplementation((name: string) =>
      name === "item" ? "item-1" : "container-1",
    );

    await moveCommand.execute(interaction, { config, logger: {} as never });

    expect(interaction.editReply).toHaveBeenCalledWith(expect.stringContaining(expectedText));
  });
});

describe("moveCommand.autocomplete", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("suggests every owned item for 'item', container-capable or not", async () => {
    getValidAccessToken.mockResolvedValue("token-123");
    getMyItemInstances.mockResolvedValue([
      { entityId: "item-1", title: "Torch", quantity: 5, isContainer: null },
    ]);

    const interaction = fakeAutocomplete("tor", "item");
    await moveCommand.autocomplete?.(interaction, { config, logger: {} as never });

    expect(interaction.respond).toHaveBeenCalledWith([{ name: "Torch ×5", value: "item-1" }]);
  });

  it("narrows 'container' to items flagged as containers", async () => {
    getValidAccessToken.mockResolvedValue("token-123");
    getMyItemInstances.mockResolvedValue([
      { entityId: "item-1", title: "Backpack", quantity: null, isContainer: true },
      { entityId: "item-2", title: "Sword", quantity: null, isContainer: false },
      { entityId: "item-3", title: "Chest", quantity: null, isContainer: null },
    ]);

    const interaction = fakeAutocomplete("", "container");
    await moveCommand.autocomplete?.(interaction, { config, logger: {} as never });

    expect(interaction.respond).toHaveBeenCalledWith([{ name: "Backpack", value: "item-1" }]);
  });
});
