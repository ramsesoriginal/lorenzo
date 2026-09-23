import { beforeEach, describe, expect, it, vi } from "vitest";
import type {
  AutocompleteInteraction,
  ChatInputCommandInteraction,
} from "../src/commands/types.js";
import type { Config } from "../src/config.js";
import { LorenzoApiError } from "../src/lorenzo-client.js";

const { getValidAccessToken } = vi.hoisted(() => ({ getValidAccessToken: vi.fn() }));
vi.mock("../src/token-provider.js", () => ({ getValidAccessToken }));

const { resolveCurrentCharacter } = vi.hoisted(() => ({ resolveCurrentCharacter: vi.fn() }));
vi.mock("../src/preferences.js", () => ({ resolveCurrentCharacter }));

const { getControlledCharacters, getEntity, createLorenzoApiClient } = vi.hoisted(() => ({
  getControlledCharacters: vi.fn(),
  getEntity: vi.fn(),
  createLorenzoApiClient: vi.fn(),
}));
vi.mock("../src/lorenzo-client.js", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../src/lorenzo-client.js")>();
  return {
    ...actual,
    createLorenzoApiClient: createLorenzoApiClient.mockReturnValue({
      getControlledCharacters,
      getEntity,
    }),
  };
});

const { sheetCommand } = await import("../src/commands/sheet.js");

const config = {
  lorenzoApiBaseUrl: "http://lorenzo-api.test",
  lorenzoTenantId: "tenant-1",
} as Config;
const ctx = { config, logger: {} as never };

const CHARACTER = {
  id: "char-1",
  name: "Frodo",
  created_at: "2026-01-01T00:00:00Z",
  updated_at: "2026-01-01T00:00:00Z",
  stats: [
    { name: "hp", value: 12 },
    { name: "class", value: "Rogue" },
  ],
  stat_groups: [],
  information: [
    {
      id: "info-1",
      title: "Backstory",
      type: "note",
      payloads: [{ kind: "description", content: "Raised in the Shire.", locale: "en-US" }],
    },
  ],
  prototypes: [],
  instances: [],
  parent: null,
  quantity: null,
  children: [],
};

function fakeInteraction(character: string | null = null) {
  return {
    user: { id: "user-1" },
    channelId: "channel-1",
    options: { getString: vi.fn(() => character) },
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
    options: { getFocused: vi.fn(() => ({ name: "character", value })) },
    respond: vi.fn(async () => undefined),
  } as unknown as AutocompleteInteraction & { respond: ReturnType<typeof vi.fn> };
}

function sentEmbed(interaction: { editReply: ReturnType<typeof vi.fn> }) {
  const payload = interaction.editReply.mock.calls[0]?.[0] as {
    embeds: { toJSON(): { title?: string; fields?: { name: string; value: string }[] } }[];
  };
  return payload.embeds[0]?.toJSON() ?? {};
}

describe("sheetCommand.execute", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("is private - a sheet is for the player, not the channel", async () => {
    getValidAccessToken.mockResolvedValue("token-123");
    resolveCurrentCharacter.mockResolvedValue("char-1");
    getEntity.mockResolvedValue(CHARACTER);
    const interaction = fakeInteraction();

    await sheetCommand.execute(interaction, ctx);

    expect(interaction.deferReply).toHaveBeenCalledWith({ ephemeral: true });
  });

  it("prompts to /link when there's no valid access token", async () => {
    getValidAccessToken.mockResolvedValue(null);
    const interaction = fakeInteraction();

    await sheetCommand.execute(interaction, ctx);

    expect(interaction.editReply).toHaveBeenCalledWith(
      expect.stringContaining("run `/link` first"),
    );
    expect(getEntity).not.toHaveBeenCalled();
  });

  it("shows the resolved stats and the notes the API returned, as the caller", async () => {
    getValidAccessToken.mockResolvedValue("token-123");
    resolveCurrentCharacter.mockResolvedValue("char-1");
    getEntity.mockResolvedValue(CHARACTER);
    const interaction = fakeInteraction();

    await sheetCommand.execute(interaction, ctx);

    expect(getEntity).toHaveBeenCalledWith("tenant-1", "char-1", "token-123");
    const embed = sentEmbed(interaction);
    expect(embed.title).toBe("Frodo");
    expect(embed.fields).toContainEqual({ name: "Stats", value: "hp: 12\nclass: Rogue" });
    expect(embed.fields).toContainEqual({ name: "Backstory", value: "Raised in the Shire." });
  });

  it("shows only what the API cleared - a filtered-out secret simply isn't there", async () => {
    getValidAccessToken.mockResolvedValue("token-123");
    resolveCurrentCharacter.mockResolvedValue("char-1");
    getEntity.mockResolvedValue({ ...CHARACTER, information: [] });
    const interaction = fakeInteraction();

    await sheetCommand.execute(interaction, ctx);

    const embed = sentEmbed(interaction);
    expect(embed.fields?.map((f) => f.name)).toEqual(["Stats"]);
  });

  it("uses an explicit character over the stored default", async () => {
    getValidAccessToken.mockResolvedValue("token-123");
    resolveCurrentCharacter.mockImplementation(
      async (_u, _c, explicit) => explicit ?? "char-default",
    );
    getEntity.mockResolvedValue(CHARACTER);
    const interaction = fakeInteraction("char-2");

    await sheetCommand.execute(interaction, ctx);

    expect(resolveCurrentCharacter).toHaveBeenCalledWith("user-1", "channel-1", "char-2");
    expect(getEntity).toHaveBeenCalledWith("tenant-1", "char-2", "token-123");
  });

  it("falls back to the only character the caller controls, without asking", async () => {
    getValidAccessToken.mockResolvedValue("token-123");
    resolveCurrentCharacter.mockResolvedValue(undefined);
    getControlledCharacters.mockResolvedValue([{ entityId: "char-only", name: "Frodo" }]);
    getEntity.mockResolvedValue(CHARACTER);
    const interaction = fakeInteraction();

    await sheetCommand.execute(interaction, ctx);

    expect(getEntity).toHaveBeenCalledWith("tenant-1", "char-only", "token-123");
  });

  it("asks which one when there's no default and several characters", async () => {
    getValidAccessToken.mockResolvedValue("token-123");
    resolveCurrentCharacter.mockResolvedValue(undefined);
    getControlledCharacters.mockResolvedValue([
      { entityId: "char-1", name: "Frodo" },
      { entityId: "char-2", name: "Sam" },
    ]);
    const interaction = fakeInteraction();

    await sheetCommand.execute(interaction, ctx);

    expect(interaction.editReply).toHaveBeenCalledWith(
      expect.stringContaining("more than one character"),
    );
    expect(getEntity).not.toHaveBeenCalled();
  });

  it("says so when the caller controls no characters at all", async () => {
    getValidAccessToken.mockResolvedValue("token-123");
    resolveCurrentCharacter.mockResolvedValue(undefined);
    getControlledCharacters.mockResolvedValue([]);
    const interaction = fakeInteraction();

    await sheetCommand.execute(interaction, ctx);

    expect(interaction.editReply).toHaveBeenCalledWith(
      expect.stringContaining("don't control any characters"),
    );
  });

  it("doesn't ask the API who the caller controls when a character is already known", async () => {
    getValidAccessToken.mockResolvedValue("token-123");
    resolveCurrentCharacter.mockResolvedValue("char-1");
    getEntity.mockResolvedValue(CHARACTER);

    await sheetCommand.execute(fakeInteraction(), ctx);

    expect(getControlledCharacters).not.toHaveBeenCalled();
  });

  it.each([403, 404])("gives a friendly message for a %i", async (status) => {
    getValidAccessToken.mockResolvedValue("token-123");
    resolveCurrentCharacter.mockResolvedValue("char-1");
    getEntity.mockRejectedValue(new LorenzoApiError("nope", status));
    const interaction = fakeInteraction();

    await sheetCommand.execute(interaction, ctx);

    expect(interaction.editReply).toHaveBeenCalledWith(
      expect.stringContaining("Couldn't open that character's sheet"),
    );
  });

  it("rethrows an unexpected error for the generic handler", async () => {
    getValidAccessToken.mockResolvedValue("token-123");
    resolveCurrentCharacter.mockResolvedValue("char-1");
    getEntity.mockRejectedValue(new LorenzoApiError("boom", 500));

    await expect(sheetCommand.execute(fakeInteraction(), ctx)).rejects.toThrow("boom");
  });
});

describe("sheetCommand.autocomplete", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("responds with no choices when there's no valid access token", async () => {
    getValidAccessToken.mockResolvedValue(null);
    const interaction = fakeAutocomplete();

    await sheetCommand.autocomplete?.(interaction, ctx);

    expect(interaction.respond).toHaveBeenCalledWith([]);
  });

  it("suggests the caller's own characters, filtered by what's typed", async () => {
    getValidAccessToken.mockResolvedValue("token-123");
    getControlledCharacters.mockResolvedValue([
      { entityId: "char-1", name: "Frodo" },
      { entityId: "char-2", name: "Sam" },
    ]);
    const interaction = fakeAutocomplete("sa");

    await sheetCommand.autocomplete?.(interaction, ctx);

    expect(interaction.respond).toHaveBeenCalledWith([{ name: "Sam", value: "char-2" }]);
  });
});
