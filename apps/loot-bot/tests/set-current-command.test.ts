import { beforeEach, describe, expect, it, vi } from "vitest";
import type {
  AutocompleteInteraction,
  ChatInputCommandInteraction,
} from "../src/commands/types.js";
import type { Config } from "../src/config.js";

const { getValidAccessToken } = vi.hoisted(() => ({ getValidAccessToken: vi.fn() }));
vi.mock("../src/token-provider.js", () => ({ getValidAccessToken }));

const { getPreference, setPreference } = vi.hoisted(() => ({
  getPreference: vi.fn(),
  setPreference: vi.fn(),
}));
vi.mock("../src/db.js", () => ({ getPreference, setPreference }));

const {
  getMyPlayers,
  getItemInstancesOwnedBy,
  getItemInstance,
  getCharacterName,
  createLorenzoApiClient,
} = vi.hoisted(() => ({
  getMyPlayers: vi.fn(),
  getItemInstancesOwnedBy: vi.fn(),
  getItemInstance: vi.fn(),
  getCharacterName: vi.fn(),
  createLorenzoApiClient: vi.fn(),
}));
vi.mock("../src/lorenzo-client.js", () => ({
  createLorenzoApiClient: createLorenzoApiClient.mockReturnValue({
    getMyPlayers,
    getItemInstancesOwnedBy,
    getItemInstance,
    getCharacterName,
  }),
}));

const { setCurrentCommand } = await import("../src/commands/set-current.js");

const config = {
  lorenzoApiBaseUrl: "http://lorenzo-api.test",
  lorenzoTenantId: "tenant-1",
} as Config;

function fakeInteraction(userId = "discord-user-1") {
  return {
    user: { id: userId },
    options: { getString: vi.fn(() => null) },
    deferReply: vi.fn(async () => undefined),
    editReply: vi.fn(async () => undefined),
  } as unknown as ChatInputCommandInteraction & {
    options: { getString: ReturnType<typeof vi.fn> };
    deferReply: ReturnType<typeof vi.fn>;
    editReply: ReturnType<typeof vi.fn>;
  };
}

function fakeAutocomplete(
  focusedName: "character" | "container",
  focusedValue = "",
  characterValue: string | null = null,
) {
  return {
    user: { id: "discord-user-1" },
    options: {
      getFocused: vi.fn(() => ({ name: focusedName, value: focusedValue })),
      getString: vi.fn((name: string) => (name === "character" ? characterValue : null)),
    },
    respond: vi.fn(async () => undefined),
  } as unknown as AutocompleteInteraction & { respond: ReturnType<typeof vi.fn> };
}

describe("setCurrentCommand.execute", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("prompts to /link when there's no valid access token", async () => {
    getValidAccessToken.mockResolvedValue(null);
    const interaction = fakeInteraction();

    await setCurrentCommand.execute(interaction, { config, logger: {} as never });

    expect(interaction.editReply).toHaveBeenCalledWith(
      expect.stringContaining("run `/link` first"),
    );
    expect(setPreference).not.toHaveBeenCalled();
  });

  it("rejects a call with neither character nor container given", async () => {
    getValidAccessToken.mockResolvedValue("token-123");
    const interaction = fakeInteraction();

    await setCurrentCommand.execute(interaction, { config, logger: {} as never });

    expect(interaction.editReply).toHaveBeenCalledWith(
      expect.stringContaining("Give me a character and/or a container"),
    );
    expect(setPreference).not.toHaveBeenCalled();
  });

  it("sets just the character, leaving the container field untouched", async () => {
    getValidAccessToken.mockResolvedValue("token-123");
    getCharacterName.mockResolvedValue("Frodo");
    const interaction = fakeInteraction();
    interaction.options.getString.mockImplementation((name: string) =>
      name === "character" ? "char-1" : null,
    );

    await setCurrentCommand.execute(interaction, { config, logger: {} as never });

    expect(setPreference).toHaveBeenCalledWith("discord-user-1", { characterEntityId: "char-1" });
    expect(interaction.editReply).toHaveBeenCalledWith("Set your current character: Frodo.");
  });

  it("sets both character and container in one call", async () => {
    getValidAccessToken.mockResolvedValue("token-123");
    getCharacterName.mockResolvedValue("Frodo");
    getItemInstance.mockResolvedValue({ data: { title: "Backpack" }, etag: null });
    const interaction = fakeInteraction();
    interaction.options.getString.mockImplementation((name: string) =>
      name === "character" ? "char-1" : "container-1",
    );

    await setCurrentCommand.execute(interaction, { config, logger: {} as never });

    expect(setPreference).toHaveBeenCalledWith("discord-user-1", {
      characterEntityId: "char-1",
      containerEntityId: "container-1",
    });
    expect(interaction.editReply).toHaveBeenCalledWith(
      "Set your current character: Frodo, default container: Backpack.",
    );
  });

  it("still succeeds even if the friendly-name lookups fail", async () => {
    getValidAccessToken.mockResolvedValue("token-123");
    getCharacterName.mockRejectedValue(new Error("boom"));
    const interaction = fakeInteraction();
    interaction.options.getString.mockImplementation((name: string) =>
      name === "character" ? "char-1" : null,
    );

    await setCurrentCommand.execute(interaction, { config, logger: {} as never });

    expect(interaction.editReply).toHaveBeenCalledWith(
      "Set your current character: that character.",
    );
  });
});

describe("setCurrentCommand.autocomplete", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("responds with no choices when there's no valid access token", async () => {
    getValidAccessToken.mockResolvedValue(null);
    const interaction = fakeAutocomplete("character");

    await setCurrentCommand.autocomplete?.(interaction, { config, logger: {} as never });

    expect(interaction.respond).toHaveBeenCalledWith([]);
  });

  it("suggests every character the caller controls", async () => {
    getValidAccessToken.mockResolvedValue("token-123");
    getMyPlayers.mockResolvedValue([
      { campaignId: "campaign-1", characters: [{ entityId: "char-1", name: "Frodo" }] },
      { campaignId: "campaign-2", characters: [{ entityId: "char-2", name: "Bilbo" }] },
    ]);

    const interaction = fakeAutocomplete("character", "fro");
    await setCurrentCommand.autocomplete?.(interaction, { config, logger: {} as never });

    expect(interaction.respond).toHaveBeenCalledWith([{ name: "Frodo", value: "char-1" }]);
  });

  it("suggests items owned by the character chosen in this same interaction", async () => {
    getValidAccessToken.mockResolvedValue("token-123");
    getItemInstancesOwnedBy.mockResolvedValue({
      groups: [
        {
          container: null,
          item_instances: [{ entity_id: "item-1", title: "Backpack", quantity: null }],
        },
      ],
    });

    const interaction = fakeAutocomplete("container", "", "char-1");
    await setCurrentCommand.autocomplete?.(interaction, { config, logger: {} as never });

    expect(getItemInstancesOwnedBy).toHaveBeenCalledWith("tenant-1", "char-1", "token-123");
    expect(interaction.respond).toHaveBeenCalledWith([{ name: "Backpack", value: "item-1" }]);
  });

  it("falls back to the stored preference's character when none is chosen yet", async () => {
    getValidAccessToken.mockResolvedValue("token-123");
    getPreference.mockResolvedValue({ currentCharacterEntityId: "char-stored" });
    getItemInstancesOwnedBy.mockResolvedValue({ groups: [] });

    const interaction = fakeAutocomplete("container");
    await setCurrentCommand.autocomplete?.(interaction, { config, logger: {} as never });

    expect(getItemInstancesOwnedBy).toHaveBeenCalledWith("tenant-1", "char-stored", "token-123");
  });

  it("responds with no choices when there's no character context at all", async () => {
    getValidAccessToken.mockResolvedValue("token-123");
    getPreference.mockResolvedValue(undefined);

    const interaction = fakeAutocomplete("container");
    await setCurrentCommand.autocomplete?.(interaction, { config, logger: {} as never });

    expect(interaction.respond).toHaveBeenCalledWith([]);
    expect(getItemInstancesOwnedBy).not.toHaveBeenCalled();
  });
});
