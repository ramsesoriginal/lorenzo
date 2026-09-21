import { beforeEach, describe, expect, it, vi } from "vitest";
import type {
  AutocompleteInteraction,
  ChatInputCommandInteraction,
  StringSelectMenuInteraction,
} from "../src/commands/types.js";
import type { Config } from "../src/config.js";
import { buildFillCustomId } from "../src/format-container.js";
import { LorenzoApiError } from "../src/lorenzo-client.js";

const { getValidAccessToken } = vi.hoisted(() => ({ getValidAccessToken: vi.fn() }));
vi.mock("../src/token-provider.js", () => ({ getValidAccessToken }));

const { resolveCurrentCharacter } = vi.hoisted(() => ({ resolveCurrentCharacter: vi.fn() }));
vi.mock("../src/preferences.js", () => ({ resolveCurrentCharacter }));

const { clearContainerPrototypeId } = vi.hoisted(() => ({ clearContainerPrototypeId: vi.fn() }));
vi.mock("../src/db.js", () => ({ clearContainerPrototypeId }));

const { resolveSackPrototype } = vi.hoisted(() => ({ resolveSackPrototype: vi.fn() }));
vi.mock("../src/commands/sack-prototype.js", () => ({ resolveSackPrototype }));

const {
  getControlledCharacters,
  createItemInstance,
  getItemInstancesOwnedBy,
  bulkMoveItemInstances,
  createLorenzoApiClient,
} = vi.hoisted(() => ({
  getControlledCharacters: vi.fn(),
  createItemInstance: vi.fn(),
  getItemInstancesOwnedBy: vi.fn(),
  bulkMoveItemInstances: vi.fn(),
  createLorenzoApiClient: vi.fn(),
}));
vi.mock("../src/lorenzo-client.js", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../src/lorenzo-client.js")>();
  return {
    ...actual,
    createLorenzoApiClient: createLorenzoApiClient.mockReturnValue({
      getControlledCharacters,
      createItemInstance,
      getItemInstancesOwnedBy,
      bulkMoveItemInstances,
    }),
  };
});

const { containerNewCommand } = await import("../src/commands/container-new.js");

const config = {
  lorenzoApiBaseUrl: "http://lorenzo-api.test",
  lorenzoTenantId: "tenant-1",
} as Config;
const ctx = { config, logger: {} as never };

function fakeInteraction(name: string | null = "Camp supplies", character: string | null = null) {
  return {
    user: { id: "user-1" },
    channelId: "channel-1",
    options: {
      getString: vi.fn((option: string) => (option === "name" ? name : character)),
    },
    deferReply: vi.fn(async () => undefined),
    editReply: vi.fn(async () => undefined),
  } as unknown as ChatInputCommandInteraction & {
    options: { getString: ReturnType<typeof vi.fn> };
    deferReply: ReturnType<typeof vi.fn>;
    editReply: ReturnType<typeof vi.fn>;
  };
}

function fakeMenu(customId: string, values: string[]) {
  return {
    user: { id: "user-1" },
    customId,
    values,
    update: vi.fn(async () => undefined),
    deferUpdate: vi.fn(async () => undefined),
    editReply: vi.fn(async () => undefined),
  } as unknown as StringSelectMenuInteraction & {
    update: ReturnType<typeof vi.fn>;
    deferUpdate: ReturnType<typeof vi.fn>;
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

function owned(entity_id: string, title: string, quantity: number | null = null) {
  return { entity_id, title, quantity };
}

/** The happy path up to (not including) the loose-items listing. */
function setUpSack() {
  getValidAccessToken.mockResolvedValue("token-123");
  resolveCurrentCharacter.mockResolvedValue("char-1");
  resolveSackPrototype.mockResolvedValue({ kind: "ok", prototypeId: "proto-1" });
  createItemInstance.mockResolvedValue({ entity_id: "sack-1", title: "Camp supplies" });
}

function sentPayload(interaction: { editReply: ReturnType<typeof vi.fn> }) {
  return interaction.editReply.mock.calls[0]?.[0] as {
    content: string;
    components: {
      toJSON(): { components: { custom_id: string; options: { value: string }[] }[] };
    }[];
  };
}

describe("containerNewCommand.execute", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("is private, and prompts to /link when there's no valid access token", async () => {
    getValidAccessToken.mockResolvedValue(null);
    const interaction = fakeInteraction();

    await containerNewCommand.execute(interaction, ctx);

    expect(interaction.deferReply).toHaveBeenCalledWith({ ephemeral: true });
    expect(interaction.editReply).toHaveBeenCalledWith(
      expect.stringContaining("run `/link` first"),
    );
    expect(createItemInstance).not.toHaveBeenCalled();
  });

  it("makes the sack for the resolved character, named as asked, as the caller", async () => {
    setUpSack();
    getItemInstancesOwnedBy.mockResolvedValue({ groups: [] });
    const interaction = fakeInteraction("Camp supplies", "char-2");

    await containerNewCommand.execute(interaction, ctx);

    expect(resolveCurrentCharacter).toHaveBeenCalledWith("user-1", "channel-1", "char-2");
    expect(resolveSackPrototype).toHaveBeenCalledWith(expect.anything(), "tenant-1", "token-123");
    expect(createItemInstance).toHaveBeenCalledWith(
      "tenant-1",
      "proto-1",
      "char-1",
      undefined,
      "token-123",
      "Camp supplies",
    );
  });

  it("trims the name, and refuses one that's only whitespace", async () => {
    setUpSack();
    getItemInstancesOwnedBy.mockResolvedValue({ groups: [] });

    await containerNewCommand.execute(fakeInteraction("  Camp supplies  "), ctx);
    expect(createItemInstance.mock.calls[0]?.[5]).toBe("Camp supplies");

    createItemInstance.mockClear();
    const blank = fakeInteraction("   ");
    await containerNewCommand.execute(blank, ctx);
    expect(blank.editReply).toHaveBeenCalledWith("Give the sack a name.");
    expect(createItemInstance).not.toHaveBeenCalled();
  });

  it("offers only loose items - not ones already in a container, and not the new sack itself", async () => {
    setUpSack();
    getItemInstancesOwnedBy.mockResolvedValue({
      groups: [
        {
          container: null,
          item_instances: [owned("sack-1", "Camp supplies"), owned("torch-1", "Torch", 5)],
        },
        { container: { id: "bag-1", name: "Bag" }, item_instances: [owned("rope-1", "Rope")] },
        { container: null, item_instances: [owned("sword-1", "Sword")] },
      ],
    });
    const interaction = fakeInteraction();

    await containerNewCommand.execute(interaction, ctx);

    const payload = sentPayload(interaction);
    expect(payload.content).toContain("Made **Camp supplies**");
    const menu = payload.components[0]?.toJSON().components[0];
    expect(menu?.custom_id).toBe(buildFillCustomId("sack-1"));
    expect(menu?.options.map((o) => o.value)).toEqual(["torch-1", "sword-1"]);
  });

  it("says so, with no picker, when there's nothing loose to put in", async () => {
    setUpSack();
    getItemInstancesOwnedBy.mockResolvedValue({
      groups: [{ container: null, item_instances: [owned("sack-1", "Camp supplies")] }],
    });
    const interaction = fakeInteraction();

    await containerNewCommand.execute(interaction, ctx);

    expect(interaction.editReply).toHaveBeenCalledWith(
      expect.stringContaining("nothing loose to put in it"),
    );
  });

  it("says how many more there are when the picker can't show them all", async () => {
    setUpSack();
    getItemInstancesOwnedBy.mockResolvedValue({
      groups: [
        {
          container: null,
          item_instances: Array.from({ length: 30 }, (_, i) => owned(`item-${i}`, `Thing ${i}`)),
        },
      ],
    });
    const interaction = fakeInteraction();

    await containerNewCommand.execute(interaction, ctx);

    const payload = sentPayload(interaction);
    expect(payload.content).toContain("Only the first 25 are listed; 5 more aren't.");
    expect(payload.components[0]?.toJSON().components[0]?.options).toHaveLength(25);
  });

  it("tells a player who can't reach the catalog who to ask, and makes nothing", async () => {
    getValidAccessToken.mockResolvedValue("token-123");
    resolveCurrentCharacter.mockResolvedValue("char-1");
    resolveSackPrototype.mockResolvedValue({ kind: "needs-catalog-access" });
    const interaction = fakeInteraction();

    await containerNewCommand.execute(interaction, ctx);

    expect(interaction.editReply).toHaveBeenCalledWith(
      expect.stringContaining("Ask a GM or admin"),
    );
    expect(createItemInstance).not.toHaveBeenCalled();
  });

  it("forgets a stored prototype that's gone missing, so the next run re-resolves it", async () => {
    setUpSack();
    createItemInstance.mockRejectedValue(new LorenzoApiError("not an item", 422));
    const interaction = fakeInteraction();

    await containerNewCommand.execute(interaction, ctx);

    expect(clearContainerPrototypeId).toHaveBeenCalledWith("tenant-1");
    expect(interaction.editReply).toHaveBeenCalledWith(
      expect.stringContaining("run `/container-new` again"),
    );
  });

  it("doesn't forget the prototype for an unrelated failure", async () => {
    setUpSack();
    createItemInstance.mockRejectedValue(new LorenzoApiError("forbidden", 403));
    const interaction = fakeInteraction();

    await containerNewCommand.execute(interaction, ctx);

    expect(clearContainerPrototypeId).not.toHaveBeenCalled();
    expect(interaction.editReply).toHaveBeenCalledWith(
      expect.stringContaining("can't make a sack for that character"),
    );
  });

  it("rethrows an unexpected error for the generic handler", async () => {
    setUpSack();
    createItemInstance.mockRejectedValue(new Error("boom"));

    await expect(containerNewCommand.execute(fakeInteraction(), ctx)).rejects.toThrow("boom");
  });

  it("falls back to the only character the caller controls", async () => {
    setUpSack();
    resolveCurrentCharacter.mockResolvedValue(undefined);
    getControlledCharacters.mockResolvedValue([{ entityId: "char-only", name: "Frodo" }]);
    getItemInstancesOwnedBy.mockResolvedValue({ groups: [] });

    await containerNewCommand.execute(fakeInteraction(), ctx);

    expect(createItemInstance.mock.calls[0]?.[2]).toBe("char-only");
  });

  it("asks whose sack it is when there's no default and several characters", async () => {
    getValidAccessToken.mockResolvedValue("token-123");
    resolveCurrentCharacter.mockResolvedValue(undefined);
    getControlledCharacters.mockResolvedValue([
      { entityId: "char-1", name: "Frodo" },
      { entityId: "char-2", name: "Sam" },
    ]);
    const interaction = fakeInteraction();

    await containerNewCommand.execute(interaction, ctx);

    expect(interaction.editReply).toHaveBeenCalledWith(
      expect.stringContaining("more than one character"),
    );
    expect(resolveSackPrototype).not.toHaveBeenCalled();
  });

  it("says so when the caller controls no characters at all", async () => {
    getValidAccessToken.mockResolvedValue("token-123");
    resolveCurrentCharacter.mockResolvedValue(undefined);
    getControlledCharacters.mockResolvedValue([]);
    const interaction = fakeInteraction();

    await containerNewCommand.execute(interaction, ctx);

    expect(interaction.editReply).toHaveBeenCalledWith(
      expect.stringContaining("don't control any characters"),
    );
  });
});

describe("containerNewCommand.onSelectMenu (filling the sack)", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("refuses a menu id that isn't a fill", async () => {
    const menu = fakeMenu("container-new:banana:sack-1", ["a"]);

    await containerNewCommand.onSelectMenu?.(menu, ctx);

    expect(menu.update).toHaveBeenCalledWith(
      expect.objectContaining({ content: expect.stringContaining("isn't valid anymore") }),
    );
    expect(bulkMoveItemInstances).not.toHaveBeenCalled();
  });

  it("acknowledges first, then moves exactly the picked items into the sack, as the caller", async () => {
    getValidAccessToken.mockResolvedValue("token-123");
    bulkMoveItemInstances.mockResolvedValue([
      { entity_id: "a", status: "ok" },
      { entity_id: "b", status: "ok" },
    ]);
    const menu = fakeMenu(buildFillCustomId("sack-1"), ["a", "b"]);

    await containerNewCommand.onSelectMenu?.(menu, ctx);

    expect(bulkMoveItemInstances).toHaveBeenCalledWith(
      "tenant-1",
      "sack-1",
      ["a", "b"],
      "token-123",
    );
    expect(menu.deferUpdate.mock.invocationCallOrder[0]).toBeLessThan(
      bulkMoveItemInstances.mock.invocationCallOrder[0] as number,
    );
    expect(menu.editReply).toHaveBeenCalledWith({ content: "Put 2 items in.", components: [] });
  });

  it("uses the singular for one item", async () => {
    getValidAccessToken.mockResolvedValue("token-123");
    bulkMoveItemInstances.mockResolvedValue([{ entity_id: "a", status: "ok" }]);
    const menu = fakeMenu(buildFillCustomId("sack-1"), ["a"]);

    await containerNewCommand.onSelectMenu?.(menu, ctx);

    expect(menu.editReply).toHaveBeenCalledWith({ content: "Put 1 item in.", components: [] });
  });

  it("reports the ones that couldn't move, with why, without hiding the ones that did", async () => {
    getValidAccessToken.mockResolvedValue("token-123");
    bulkMoveItemInstances.mockResolvedValue([
      { entity_id: "a", status: "ok" },
      { entity_id: "b", status: "error", problem: { title: "Forbidden", detail: "Not yours" } },
      { entity_id: "c", status: "error", problem: { title: "Forbidden", detail: "Not yours" } },
    ]);
    const menu = fakeMenu(buildFillCustomId("sack-1"), ["a", "b", "c"]);

    await containerNewCommand.onSelectMenu?.(menu, ctx);

    expect(menu.editReply).toHaveBeenCalledWith({
      content: "Put 1 item in. 2 couldn't be moved: Not yours",
      components: [],
    });
  });

  it("says nothing went in when every move failed", async () => {
    getValidAccessToken.mockResolvedValue("token-123");
    bulkMoveItemInstances.mockResolvedValue([
      { entity_id: "a", status: "error", problem: { title: "Gone", detail: "Item is gone" } },
    ]);
    const menu = fakeMenu(buildFillCustomId("sack-1"), ["a"]);

    await containerNewCommand.onSelectMenu?.(menu, ctx);

    expect(menu.editReply).toHaveBeenCalledWith({
      content: "Nothing went in. 1 couldn't be moved: Item is gone",
      components: [],
    });
  });

  it("prompts to /link when the clicker has no valid access token", async () => {
    getValidAccessToken.mockResolvedValue(null);
    const menu = fakeMenu(buildFillCustomId("sack-1"), ["a"]);

    await containerNewCommand.onSelectMenu?.(menu, ctx);

    expect(menu.editReply).toHaveBeenCalledWith(
      expect.objectContaining({ content: expect.stringContaining("run `/link` first") }),
    );
    expect(bulkMoveItemInstances).not.toHaveBeenCalled();
  });

  it.each([
    [403, "can't move things into that sack"],
    [404, "Couldn't find that sack anymore"],
  ])("gives a specific message for a %i", async (status, expected) => {
    getValidAccessToken.mockResolvedValue("token-123");
    bulkMoveItemInstances.mockRejectedValue(new LorenzoApiError("nope", status));
    const menu = fakeMenu(buildFillCustomId("sack-1"), ["a"]);

    await containerNewCommand.onSelectMenu?.(menu, ctx);

    expect(menu.editReply).toHaveBeenCalledWith({
      content: expect.stringContaining(expected),
      components: [],
    });
  });
});

describe("containerNewCommand.autocomplete", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("responds with no choices when there's no valid access token", async () => {
    getValidAccessToken.mockResolvedValue(null);
    const interaction = fakeAutocomplete();

    await containerNewCommand.autocomplete?.(interaction, ctx);

    expect(interaction.respond).toHaveBeenCalledWith([]);
  });

  it("suggests the caller's own characters, filtered by what's typed", async () => {
    getValidAccessToken.mockResolvedValue("token-123");
    getControlledCharacters.mockResolvedValue([
      { entityId: "char-1", name: "Frodo" },
      { entityId: "char-2", name: "Sam" },
    ]);
    const interaction = fakeAutocomplete("fr");

    await containerNewCommand.autocomplete?.(interaction, ctx);

    expect(interaction.respond).toHaveBeenCalledWith([{ name: "Frodo", value: "char-1" }]);
  });
});
