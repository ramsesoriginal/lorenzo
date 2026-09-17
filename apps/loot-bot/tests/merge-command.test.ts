import { beforeEach, describe, expect, it, vi } from "vitest";
import type {
  AutocompleteInteraction,
  ChatInputCommandInteraction,
} from "../src/commands/types.js";
import type { Config } from "../src/config.js";
import { LorenzoApiError } from "../src/lorenzo-client.js";

const { getValidAccessToken } = vi.hoisted(() => ({ getValidAccessToken: vi.fn() }));
vi.mock("../src/token-provider.js", () => ({ getValidAccessToken }));

const { getMyItemInstances, getItemInstance, mergeItemInstance, createLorenzoApiClient } =
  vi.hoisted(() => ({
    getMyItemInstances: vi.fn(),
    getItemInstance: vi.fn(),
    mergeItemInstance: vi.fn(),
    createLorenzoApiClient: vi.fn(),
  }));
vi.mock("../src/lorenzo-client.js", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../src/lorenzo-client.js")>();
  return {
    ...actual,
    createLorenzoApiClient: createLorenzoApiClient.mockReturnValue({
      getMyItemInstances,
      getItemInstance,
      mergeItemInstance,
    }),
  };
});

const { mergeCommand } = await import("../src/commands/merge.js");

const config = {
  lorenzoApiBaseUrl: "http://lorenzo-api.test",
  lorenzoTenantId: "tenant-1",
} as Config;

function fakeInteraction() {
  return {
    user: { id: "discord-user-1" },
    options: {
      getString: vi.fn((name: string) => (name === "item" ? "item-1" : "item-2")),
    },
    deferReply: vi.fn(async () => undefined),
    editReply: vi.fn(async () => undefined),
  } as unknown as ChatInputCommandInteraction & {
    options: { getString: ReturnType<typeof vi.fn> };
    deferReply: ReturnType<typeof vi.fn>;
    editReply: ReturnType<typeof vi.fn>;
  };
}

function fakeAutocomplete(
  focusedName: "item" | "into",
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

describe("mergeCommand.execute", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("prompts to /link when there's no valid access token", async () => {
    getValidAccessToken.mockResolvedValue(null);
    const interaction = fakeInteraction();

    await mergeCommand.execute(interaction, { config, logger: {} as never });

    expect(interaction.editReply).toHaveBeenCalledWith(
      expect.stringContaining("run `/link` first"),
    );
    expect(mergeItemInstance).not.toHaveBeenCalled();
  });

  it("rejects merging a stack into itself, before calling the API", async () => {
    getValidAccessToken.mockResolvedValue("token-123");
    const interaction = fakeInteraction();
    interaction.options.getString.mockImplementation(() => "item-1");

    await mergeCommand.execute(interaction, { config, logger: {} as never });

    expect(interaction.editReply).toHaveBeenCalledWith(
      expect.stringContaining("can't merge into itself"),
    );
    expect(mergeItemInstance).not.toHaveBeenCalled();
  });

  it("merges the source into the target and confirms with the survivor's title", async () => {
    getValidAccessToken.mockResolvedValue("token-123");
    getItemInstance.mockResolvedValue({ data: { entity_id: "item-1" }, etag: "etag-1" });
    mergeItemInstance.mockResolvedValue({ entity_id: "item-2", title: "Arrows" });
    const interaction = fakeInteraction();

    await mergeCommand.execute(interaction, { config, logger: {} as never });

    expect(mergeItemInstance).toHaveBeenCalledWith(
      "tenant-1",
      "item-1",
      "item-2",
      "token-123",
      "etag-1",
    );
    expect(interaction.editReply).toHaveBeenCalledWith("Merged into Arrows.");
  });

  it.each([
    [403, "reachable from any of your characters"],
    [404, "Couldn't find one of those stacks"],
    [412, "Someone else changed that stack"],
    [422, "Couldn't do that"],
  ])("gives a specific message for a %i error", async (status, expectedText) => {
    getValidAccessToken.mockResolvedValue("token-123");
    getItemInstance.mockResolvedValue({ data: { entity_id: "item-1" }, etag: "etag-1" });
    mergeItemInstance.mockRejectedValue(new LorenzoApiError("boom", status));
    const interaction = fakeInteraction();

    await mergeCommand.execute(interaction, { config, logger: {} as never });

    expect(interaction.editReply).toHaveBeenCalledWith(expect.stringContaining(expectedText));
  });
});

describe("mergeCommand.autocomplete", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("responds with no choices when there's no valid access token", async () => {
    getValidAccessToken.mockResolvedValue(null);
    const interaction = fakeAutocomplete("item");

    await mergeCommand.autocomplete?.(interaction, { config, logger: {} as never });

    expect(interaction.respond).toHaveBeenCalledWith([]);
  });

  it("suggests the caller's own items for 'item'", async () => {
    getValidAccessToken.mockResolvedValue("token-123");
    getMyItemInstances.mockResolvedValue([
      { entityId: "item-1", title: "Torch", quantity: 5 },
      { entityId: "item-2", title: "Sword", quantity: null },
    ]);

    const interaction = fakeAutocomplete("item", "tor");
    await mergeCommand.autocomplete?.(interaction, { config, logger: {} as never });

    expect(interaction.respond).toHaveBeenCalledWith([{ name: "Torch ×5", value: "item-1" }]);
  });

  it("narrows 'into' to other stacks sharing the chosen item's title", async () => {
    getValidAccessToken.mockResolvedValue("token-123");
    getMyItemInstances.mockResolvedValue([
      { entityId: "item-1", title: "Torch", quantity: 5 },
      { entityId: "item-2", title: "Torch", quantity: 3 },
      { entityId: "item-3", title: "Sword", quantity: null },
    ]);

    const interaction = fakeAutocomplete("into", "", "item-1");
    await mergeCommand.autocomplete?.(interaction, { config, logger: {} as never });

    expect(interaction.respond).toHaveBeenCalledWith([{ name: "Torch ×3", value: "item-2" }]);
  });

  it("falls back to every item for 'into' when no item is chosen yet", async () => {
    getValidAccessToken.mockResolvedValue("token-123");
    getMyItemInstances.mockResolvedValue([
      { entityId: "item-1", title: "Torch", quantity: 5 },
      { entityId: "item-2", title: "Sword", quantity: null },
    ]);

    const interaction = fakeAutocomplete("into");
    await mergeCommand.autocomplete?.(interaction, { config, logger: {} as never });

    expect(interaction.respond).toHaveBeenCalledWith([
      { name: "Torch ×5", value: "item-1" },
      { name: "Sword", value: "item-2" },
    ]);
  });
});
