import { beforeEach, describe, expect, it, vi } from "vitest";
import type {
  AutocompleteInteraction,
  ButtonInteraction,
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

const {
  getMyItemInstances,
  getItemInstance,
  setItemInstanceContainer,
  isCampaignGm,
  createLorenzoApiClient,
} = vi.hoisted(() => ({
  getMyItemInstances: vi.fn(),
  getItemInstance: vi.fn(),
  setItemInstanceContainer: vi.fn(),
  isCampaignGm: vi.fn(),
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
      isCampaignGm,
    }),
  };
});

const { moveCommand } = await import("../src/commands/move.js");
const { buildMoveAnywayCustomId } = await import("../src/format-move.js");

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

function fakeButton(customId: string) {
  return {
    user: { id: "user-1" },
    customId,
    update: vi.fn(async () => undefined),
    editReply: vi.fn(async () => undefined),
  } as unknown as ButtonInteraction & {
    update: ReturnType<typeof vi.fn>;
    editReply: ReturnType<typeof vi.fn>;
  };
}

const FORCE = buildMoveAnywayCustomId({ itemEntityId: "item-1", containerEntityId: "container-1" });

const tooMuch = new LorenzoApiError(
  "Backpack can carry 20, and this would make it 26.",
  409,
  "capacity-exceeded",
);

function movable() {
  getValidAccessToken.mockResolvedValue("token-123");
  getItemInstance.mockResolvedValue({
    data: {
      entity_id: "item-1",
      container_entity_id: "old-container-1",
      owner_entity_id: "char-1",
    },
    etag: "etag-1",
  });
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
      data: {
        entity_id: "item-1",
        container_entity_id: "old-container-1",
        owner_entity_id: "char-1",
      },
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
      { override: false },
    );
    expect(interaction.editReply).toHaveBeenCalledWith("Moved Torch.");
    expect(recordUndo).toHaveBeenCalledWith("user-1", {
      kind: "restore-container",
      entityId: "item-1",
      previousContainerEntityId: "old-container-1",
    });
    expect(rememberActingCharacter).toHaveBeenCalledWith(
      expect.anything(),
      "tenant-1",
      "token-123",
      "user-1",
      "char-1",
      expect.anything(),
    );
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

describe("moveCommand, when it doesn't fit", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("shows a player the API's reason, and no button", async () => {
    movable();
    setItemInstanceContainer.mockRejectedValue(tooMuch);
    isCampaignGm.mockResolvedValue(false);
    const interaction = fakeInteraction();
    interaction.options.getString.mockImplementation((name: string) =>
      name === "item" ? "item-1" : "container-1",
    );

    await moveCommand.execute(interaction, { config, logger: {} as never });

    expect(interaction.editReply).toHaveBeenCalledWith({
      content: "Backpack can carry 20, and this would make it 26.",
      components: [],
    });
    expect(recordUndo).not.toHaveBeenCalled();
  });

  it("offers a GM a Move anyway button carrying the move", async () => {
    movable();
    setItemInstanceContainer.mockRejectedValue(tooMuch);
    isCampaignGm.mockResolvedValue(true);
    const interaction = fakeInteraction();
    interaction.options.getString.mockImplementation((name: string) =>
      name === "item" ? "item-1" : "container-1",
    );

    await moveCommand.execute(interaction, { config, logger: {} as never });

    const reply = interaction.editReply.mock.calls[0]?.[0];
    expect(reply.content).toBe("Backpack can carry 20, and this would make it 26.");
    const [button] = reply.components[0].toJSON().components;
    expect(button).toMatchObject({ custom_id: FORCE, label: "Move anyway" });
  });

  it("moves anyway on the button, with override, and keeps the Undo", async () => {
    movable();
    setItemInstanceContainer.mockResolvedValue({ entity_id: "item-1", title: "Anvil" });
    const button = fakeButton(FORCE);

    await moveCommand.onButton?.(button, { config, logger: {} as never });

    expect(button.update).toHaveBeenCalledWith({ content: "Moving…", components: [] });
    expect(setItemInstanceContainer).toHaveBeenCalledWith(
      "tenant-1",
      "item-1",
      "container-1",
      "token-123",
      "etag-1",
      { override: true },
    );
    expect(button.editReply).toHaveBeenCalledWith("Moved Anvil anyway.");
    expect(recordUndo).toHaveBeenCalledWith("user-1", {
      kind: "restore-container",
      entityId: "item-1",
      previousContainerEntityId: "old-container-1",
    });
  });

  it("says so when the API won't let them move anyway", async () => {
    movable();
    setItemInstanceContainer.mockRejectedValue(
      new LorenzoApiError(
        "Only a GM of this item's campaign can move it anyway.",
        403,
        "capacity-override-forbidden",
      ),
    );
    const button = fakeButton(FORCE);

    await moveCommand.onButton?.(button, { config, logger: {} as never });

    expect(button.editReply).toHaveBeenCalledWith(
      "Only a GM of this item's campaign can move it anyway.",
    );
  });

  it("refuses a button it can't read, without moving anything", async () => {
    const button = fakeButton("move:force:item-1");

    await moveCommand.onButton?.(button, { config, logger: {} as never });

    expect(button.update).toHaveBeenCalledWith({
      content: expect.stringContaining("run `/move` again"),
      components: [],
    });
    expect(setItemInstanceContainer).not.toHaveBeenCalled();
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
