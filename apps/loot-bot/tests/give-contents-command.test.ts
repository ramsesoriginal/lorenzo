import { beforeEach, describe, expect, it, vi } from "vitest";
import type {
  AutocompleteInteraction,
  ButtonInteraction,
  ChatInputCommandInteraction,
} from "../src/commands/types.js";
import type { Config } from "../src/config.js";
import { GIVE_CONTENTS_CANCEL_CUSTOM_ID } from "../src/format-give-contents.js";
import { LorenzoApiError } from "../src/lorenzo-client.js";

const { getValidAccessToken } = vi.hoisted(() => ({ getValidAccessToken: vi.fn() }));
vi.mock("../src/token-provider.js", () => ({ getValidAccessToken }));

const { recordUndo } = vi.hoisted(() => ({ recordUndo: vi.fn() }));
vi.mock("../src/undo-actions.js", () => ({ recordUndo }));

const {
  getMyItemInstances,
  getItemInstance,
  getCharacterName,
  getGroupName,
  giveContents,
  createLorenzoApiClient,
} = vi.hoisted(() => ({
  getMyItemInstances: vi.fn(),
  getItemInstance: vi.fn(),
  getCharacterName: vi.fn(),
  getGroupName: vi.fn(),
  giveContents: vi.fn(),
  createLorenzoApiClient: vi.fn(),
}));
vi.mock("../src/lorenzo-client.js", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../src/lorenzo-client.js")>();
  return {
    ...actual,
    createLorenzoApiClient: createLorenzoApiClient.mockReturnValue({
      getMyItemInstances,
      getItemInstance,
      getCharacterName,
      getGroupName,
      giveContents,
    }),
  };
});

const { giveContentsCommand } = await import("../src/commands/give-contents.js");

const config = {
  lorenzoApiBaseUrl: "http://lorenzo-api.test",
  lorenzoTenantId: "tenant-1",
} as Config;

const ctx = { config, logger: {} as never };

const ROPE = {
  entity_id: "rope",
  title: "Rope",
  status: "ok",
  owner: { id: "char-2", name: "Brisk" },
};
const COIN = {
  entity_id: "coin",
  title: "Coin",
  status: "ok",
  owner: { id: "char-2", name: "Brisk" },
};
const POTION = {
  entity_id: "potion",
  title: "Potion",
  status: "kept",
  owner: { id: "pia", name: "Pia" },
  problem: { type: "item-not-yours-to-give", title: "Forbidden", status: 403 },
};

function fakeInteraction() {
  const interaction = {
    user: { id: "discord-user-1" },
    options: {
      getString: vi.fn((name: string) => (name === "container" ? "backpack" : "char-2")),
    },
    deferReply: vi.fn(async () => undefined),
    editReply: vi.fn(async () => undefined),
  };
  return interaction as unknown as ChatInputCommandInteraction & {
    editReply: ReturnType<typeof vi.fn>;
  };
}

function fakeButton(customId: string) {
  return {
    user: { id: "discord-user-1" },
    customId,
    update: vi.fn(async () => undefined),
    editReply: vi.fn(async () => undefined),
  } as unknown as ButtonInteraction & {
    update: ReturnType<typeof vi.fn>;
    editReply: ReturnType<typeof vi.fn>;
  };
}

beforeEach(() => {
  vi.clearAllMocks();
  getValidAccessToken.mockResolvedValue("token-123");
  getItemInstance.mockResolvedValue({
    data: { entity_id: "backpack", title: "Backpack", quantity: null },
    etag: "etag-1",
  });
  getCharacterName.mockResolvedValue("Brisk");
});

describe("giveContentsCommand.execute (the question)", () => {
  it("asks from a dry run, and gives nothing yet", async () => {
    giveContents.mockResolvedValue([ROPE, COIN, POTION]);
    const interaction = fakeInteraction();

    await giveContentsCommand.execute(interaction, ctx);

    expect(giveContents).toHaveBeenCalledTimes(1);
    expect(giveContents).toHaveBeenCalledWith("tenant-1", "backpack", "char-2", "token-123", {
      dryRun: true,
    });
    const [{ content, components }] = interaction.editReply.mock.calls[0] as [
      {
        content: string;
        components: { toJSON(): { components: { custom_id: string; label: string }[] } }[];
      },
    ];
    expect(content).toBe(
      "Give **2 things** inside **Backpack** to **Brisk**? 1 thing inside stays Pia's.",
    );
    expect(components[0]?.toJSON().components.map((b) => [b.label, b.custom_id])).toEqual([
      ["Give", "give-contents:ok:backpack:char-2"],
      ["Cancel", GIVE_CONTENTS_CANCEL_CUSTOM_ID],
    ]);
  });

  it("says so, without a question, when nothing inside can be given", async () => {
    giveContents.mockResolvedValue([POTION]);
    const interaction = fakeInteraction();

    await giveContentsCommand.execute(interaction, ctx);

    expect(interaction.editReply).toHaveBeenCalledWith(
      "Nothing inside Backpack can be given. 1 thing inside stays Pia's.",
    );
  });

  it("says when a container is out of reach", async () => {
    giveContents.mockRejectedValue(
      new LorenzoApiError("nope", 403, "item-instance-management-forbidden"),
    );
    const interaction = fakeInteraction();

    await giveContentsCommand.execute(interaction, ctx);

    expect(interaction.editReply).toHaveBeenCalledWith(
      "That's not a container you can reach from any of your characters.",
    );
  });

  it("prompts to /link without a valid access token", async () => {
    getValidAccessToken.mockResolvedValue(null);
    const interaction = fakeInteraction();

    await giveContentsCommand.execute(interaction, ctx);

    expect(interaction.editReply).toHaveBeenCalledWith(
      expect.stringContaining("run `/link` first"),
    );
    expect(giveContents).not.toHaveBeenCalled();
  });
});

describe("giveContentsCommand.onButton (the give)", () => {
  it("gives what's inside, says what stayed, and records no Undo", async () => {
    giveContents.mockResolvedValue([ROPE, POTION]);
    const button = fakeButton("give-contents:ok:backpack:char-2");

    await giveContentsCommand.onButton?.(button, ctx);

    expect(button.update).toHaveBeenCalledWith({ content: "Giving…", components: [] });
    expect(giveContents).toHaveBeenCalledWith("tenant-1", "backpack", "char-2", "token-123");
    expect(button.editReply).toHaveBeenCalledWith(
      "Gave 1 thing inside Backpack to Brisk. 1 thing inside stays Pia's.",
    );
    expect(recordUndo).not.toHaveBeenCalled();
  });

  it("cancels without touching the API", async () => {
    const button = fakeButton(GIVE_CONTENTS_CANCEL_CUSTOM_ID);

    await giveContentsCommand.onButton?.(button, ctx);

    expect(button.update).toHaveBeenCalledWith({
      content: "Cancelled — nothing was given.",
      components: [],
    });
    expect(giveContents).not.toHaveBeenCalled();
  });

  it("refuses a malformed confirm id instead of guessing", async () => {
    const button = fakeButton("give-contents:ok:backpack");

    await giveContentsCommand.onButton?.(button, ctx);

    expect(button.update).toHaveBeenCalledWith(
      expect.objectContaining({ content: expect.stringContaining("isn't valid anymore") }),
    );
    expect(giveContents).not.toHaveBeenCalled();
  });
});

describe("giveContentsCommand.autocomplete", () => {
  it("suggests only the caller's containers that hold something", async () => {
    getMyItemInstances.mockResolvedValue([
      { entityId: "backpack", title: "Backpack", quantity: null, isContainer: true, slug: null },
      { entityId: "sword", title: "Sword", quantity: null, isContainer: null, slug: null },
    ]);
    const interaction = {
      user: { id: "discord-user-1" },
      options: {
        getFocused: vi.fn(() => ({ name: "container", value: "" })),
        getString: vi.fn(() => null),
      },
      respond: vi.fn(async () => undefined),
    } as unknown as AutocompleteInteraction & { respond: ReturnType<typeof vi.fn> };

    await giveContentsCommand.autocomplete?.(interaction, ctx);

    expect(interaction.respond).toHaveBeenCalledWith([{ name: "Backpack", value: "backpack" }]);
  });
});
