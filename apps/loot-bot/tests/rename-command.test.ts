import { beforeEach, describe, expect, it, vi } from "vitest";
import type {
  AutocompleteInteraction,
  ChatInputCommandInteraction,
} from "../src/commands/types.js";
import type { Config } from "../src/config.js";
import { LorenzoApiError } from "../src/lorenzo-client.js";

const { getValidAccessToken } = vi.hoisted(() => ({ getValidAccessToken: vi.fn() }));
vi.mock("../src/token-provider.js", () => ({ getValidAccessToken }));

const { rememberActingCharacter } = vi.hoisted(() => ({ rememberActingCharacter: vi.fn() }));
vi.mock("../src/commands/remember-character.js", () => ({ rememberActingCharacter }));

const { recordUndo } = vi.hoisted(() => ({ recordUndo: vi.fn() }));
vi.mock("../src/undo-actions.js", () => ({ recordUndo }));

const { getMyItemInstances, getItemInstance, renameItemInstance, createLorenzoApiClient } =
  vi.hoisted(() => ({
    getMyItemInstances: vi.fn(),
    getItemInstance: vi.fn(),
    renameItemInstance: vi.fn(),
    createLorenzoApiClient: vi.fn(),
  }));
vi.mock("../src/lorenzo-client.js", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../src/lorenzo-client.js")>();
  return {
    ...actual,
    createLorenzoApiClient: createLorenzoApiClient.mockReturnValue({
      getMyItemInstances,
      getItemInstance,
      renameItemInstance,
    }),
  };
});

const { renameCommand } = await import("../src/commands/rename.js");

const config = {
  lorenzoApiBaseUrl: "http://lorenzo-api.test",
  lorenzoTenantId: "tenant-1",
} as Config;

function fakeInteraction() {
  return {
    user: { id: "discord-user-1" },
    options: {
      getString: vi.fn((name: string) => (name === "item" ? "item-1" : "Grandfather's Sword")),
    },
    deferReply: vi.fn(async () => undefined),
    editReply: vi.fn(async () => undefined),
  } as unknown as ChatInputCommandInteraction & {
    options: { getString: ReturnType<typeof vi.fn> };
    deferReply: ReturnType<typeof vi.fn>;
    editReply: ReturnType<typeof vi.fn>;
  };
}

function fakeAutocomplete(focusedValue = "") {
  return {
    user: { id: "discord-user-1" },
    options: { getFocused: vi.fn(() => ({ name: "item", value: focusedValue })) },
    respond: vi.fn(async () => undefined),
  } as unknown as AutocompleteInteraction & { respond: ReturnType<typeof vi.fn> };
}

describe("renameCommand.execute", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("prompts to /link when there's no valid access token", async () => {
    getValidAccessToken.mockResolvedValue(null);
    const interaction = fakeInteraction();

    await renameCommand.execute(interaction, { config, logger: {} as never });

    expect(interaction.editReply).toHaveBeenCalledWith(
      expect.stringContaining("run `/link` first"),
    );
    expect(renameItemInstance).not.toHaveBeenCalled();
  });

  it("renames the item and confirms with its new title", async () => {
    getValidAccessToken.mockResolvedValue("token-123");
    getItemInstance.mockResolvedValue({
      data: { entity_id: "item-1", title: "Sword", owner_entity_id: "char-1" },
      etag: "etag-1",
    });
    renameItemInstance.mockResolvedValue({ entity_id: "item-1", title: "Grandfather's Sword" });
    const interaction = fakeInteraction();

    await renameCommand.execute(interaction, { config, logger: {} as never });

    expect(renameItemInstance).toHaveBeenCalledWith(
      "tenant-1",
      "item-1",
      "Grandfather's Sword",
      "token-123",
      "etag-1",
    );
    expect(interaction.editReply).toHaveBeenCalledWith("Renamed to Grandfather's Sword.");
    expect(recordUndo).toHaveBeenCalledWith("discord-user-1", {
      kind: "restore-name",
      entityId: "item-1",
      previousTitle: "Sword",
    });
    expect(rememberActingCharacter).toHaveBeenCalledWith(
      expect.anything(),
      "tenant-1",
      "token-123",
      "discord-user-1",
      "char-1",
      expect.anything(),
    );
  });

  it.each([
    [403, "reachable from any of your characters"],
    [404, "Couldn't find that item"],
    [412, "Someone else changed that item"],
    [422, "Couldn't do that"],
  ])("gives a specific message for a %i error", async (status, expectedText) => {
    getValidAccessToken.mockResolvedValue("token-123");
    getItemInstance.mockResolvedValue({ data: { entity_id: "item-1" }, etag: "etag-1" });
    renameItemInstance.mockRejectedValue(new LorenzoApiError("boom", status));
    const interaction = fakeInteraction();

    await renameCommand.execute(interaction, { config, logger: {} as never });

    expect(interaction.editReply).toHaveBeenCalledWith(expect.stringContaining(expectedText));
  });
});

describe("renameCommand.autocomplete", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("responds with no choices when there's no valid access token", async () => {
    getValidAccessToken.mockResolvedValue(null);
    const interaction = fakeAutocomplete();

    await renameCommand.autocomplete?.(interaction, { config, logger: {} as never });

    expect(interaction.respond).toHaveBeenCalledWith([]);
  });

  it("suggests the caller's own items", async () => {
    getValidAccessToken.mockResolvedValue("token-123");
    getMyItemInstances.mockResolvedValue([{ entityId: "item-1", title: "Sword", quantity: null }]);

    const interaction = fakeAutocomplete("sw");
    await renameCommand.autocomplete?.(interaction, { config, logger: {} as never });

    expect(interaction.respond).toHaveBeenCalledWith([{ name: "Sword", value: "item-1" }]);
  });
});
