import { describe, expect, it, vi } from "vitest";

const { editOriginalInteractionResponse, sendInteractionFollowUp } = vi.hoisted(() => ({
  editOriginalInteractionResponse: vi.fn(async () => ({ id: "message-1" })),
  sendInteractionFollowUp: vi.fn(async () => ({ id: "followup-1" })),
}));
vi.mock("../src/discord-rest.js", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../src/discord-rest.js")>();
  return { ...actual, editOriginalInteractionResponse, sendInteractionFollowUp };
});

const { buildAdapterInteraction, isPing, pongResponse } = await import(
  "../src/interaction-adapter.js"
);
type RawInteractionPayload = Parameters<typeof buildAdapterInteraction>[0];

const APPLICATION_ID = "app-1";
const TOKEN = "token-1";

function basePayload(overrides: Record<string, unknown> = {}): RawInteractionPayload {
  return {
    id: "interaction-1",
    application_id: APPLICATION_ID,
    token: TOKEN,
    guild_id: "guild-1",
    member: { user: { id: "user-1" } },
    ...overrides,
  } as RawInteractionPayload;
}

describe("buildAdapterInteraction - chat input (type 2)", () => {
  function chatInputPayload(options: readonly Record<string, unknown>[] = []) {
    return basePayload({
      type: 2,
      channel_id: "channel-1",
      data: { name: "give", options },
    });
  }

  it("reads required and optional string/integer options", () => {
    const built = buildAdapterInteraction(
      chatInputPayload([
        { name: "item", value: "sword" },
        { name: "quantity", value: 3 },
      ]),
    );
    const interaction = built?.interaction;
    if (!interaction || !interaction.isChatInputCommand()) throw new Error("expected chat input");

    expect(interaction.options.getString("item", true)).toBe("sword");
    expect(interaction.options.getString("missing")).toBeNull();
    expect(interaction.options.getInteger("quantity", true)).toBe(3);
    expect(interaction.options.getInteger("missing")).toBeNull();
    expect(() => interaction.options.getString("missing", true)).toThrow();
  });

  it("reads an optional boolean option: its value when given, null when Discord omitted it", () => {
    const built = buildAdapterInteraction(
      chatInputPayload([
        { name: "history", value: true },
        { name: "off", value: false },
        { name: "item", value: "sword" },
      ]),
    );
    const interaction = built?.interaction;
    if (!interaction || !interaction.isChatInputCommand()) throw new Error("expected chat input");

    expect(interaction.options.getBoolean("history")).toBe(true);
    expect(interaction.options.getBoolean("off")).toBe(false);
    expect(interaction.options.getBoolean("missing")).toBeNull();
    // A non-boolean value under that name isn't mistaken for one.
    expect(interaction.options.getBoolean("item")).toBeNull();
  });

  it("resolves the first-response gate with deferReply's body, then editReply edits it", async () => {
    const built = buildAdapterInteraction(chatInputPayload());
    const interaction = built?.interaction;
    if (!interaction || !built || !interaction.isChatInputCommand())
      throw new Error("expected chat input");

    await interaction.deferReply({ ephemeral: true });
    const firstResponse = await built.firstResponse;
    expect(firstResponse).toEqual({ type: 5, data: { flags: 1 << 6 } });
    expect(interaction.deferred).toBe(true);

    const sent = await interaction.editReply("done");
    expect(sent).toEqual({ id: "message-1" });
    expect(editOriginalInteractionResponse).toHaveBeenCalledWith(APPLICATION_ID, TOKEN, {
      content: "done",
    });
  });

  it("reply() answers directly without a defer step", async () => {
    const built = buildAdapterInteraction(chatInputPayload());
    const interaction = built?.interaction;
    if (!interaction || !built || !interaction.isChatInputCommand())
      throw new Error("expected chat input");

    await interaction.reply({ content: "hi", ephemeral: true });
    expect(await built.firstResponse).toEqual({
      type: 4,
      data: { content: "hi", flags: 1 << 6 },
    });
    expect(interaction.replied).toBe(true);
  });

  it("followUp sends a new webhook message after the first response", async () => {
    const built = buildAdapterInteraction(chatInputPayload());
    const interaction = built?.interaction;
    if (!interaction || !built || !interaction.isChatInputCommand())
      throw new Error("expected chat input");

    await interaction.deferReply();
    const result = await interaction.followUp({ content: "extra", ephemeral: true });
    expect(result).toEqual({ id: "followup-1" });
    expect(sendInteractionFollowUp).toHaveBeenCalledWith(APPLICATION_ID, TOKEN, {
      content: "extra",
      flags: 1 << 6,
    });
  });

  it("only honors the first response method called, even if a second is called too", async () => {
    const built = buildAdapterInteraction(chatInputPayload());
    const interaction = built?.interaction;
    if (!interaction || !built || !interaction.isChatInputCommand())
      throw new Error("expected chat input");

    await interaction.deferReply();
    await interaction.reply("too late");
    expect(await built.firstResponse).toEqual({ type: 5, data: { flags: undefined } });
  });

  it("reads the invoking user from a top-level `user` when there's no `member` (DM-shaped payload)", () => {
    const built = buildAdapterInteraction({
      id: "i",
      application_id: APPLICATION_ID,
      token: TOKEN,
      type: 2,
      user: { id: "dm-user" },
      data: { name: "ping", options: [] },
    });
    expect(built?.interaction.user.id).toBe("dm-user");
  });
});

describe("buildAdapterInteraction - autocomplete (type 4)", () => {
  it("respond() resolves the gate with an autocomplete result and flips `responded`", async () => {
    const built = buildAdapterInteraction(
      basePayload({
        type: 4,
        data: { name: "give", options: [{ name: "item", value: "sw", focused: true }] },
      }),
    );
    const interaction = built?.interaction;
    if (!interaction || !built || !interaction.isAutocomplete())
      throw new Error("expected autocomplete");

    expect(interaction.options.getFocused(true)).toEqual({ name: "item", value: "sw" });
    expect(interaction.responded).toBe(false);

    await interaction.respond([{ name: "Sword", value: "sword-1" }]);
    expect(interaction.responded).toBe(true);
    expect(await built.firstResponse).toEqual({
      type: 8,
      data: { choices: [{ name: "Sword", value: "sword-1" }] },
    });
  });
});

describe("buildAdapterInteraction - message component (type 3)", () => {
  it("a string-select component exposes values/showModal/update/deferUpdate", async () => {
    const built = buildAdapterInteraction(
      basePayload({
        type: 3,
        data: { custom_id: "drop:take:drop-1", component_type: 3, values: ["item-1"] },
      }),
    );
    const interaction = built?.interaction;
    if (!interaction || !built || !interaction.isStringSelectMenu()) {
      throw new Error("expected select menu");
    }

    expect(interaction.customId).toBe("drop:take:drop-1");
    expect(interaction.values).toEqual(["item-1"]);

    await interaction.showModal({ toJSON: () => ({ custom_id: "modal-1" }) });
    expect(await built.firstResponse).toEqual({ type: 9, data: { custom_id: "modal-1" } });
  });

  it("a string-select's deferUpdate/update resolve the expected response types", async () => {
    const deferBuilt = buildAdapterInteraction(
      basePayload({ type: 3, data: { custom_id: "drop:claim:1", component_type: 3, values: [] } }),
    );
    const deferInteraction = deferBuilt?.interaction;
    if (!deferInteraction || !deferBuilt || !deferInteraction.isStringSelectMenu()) {
      throw new Error("expected select menu");
    }
    await deferInteraction.deferUpdate();
    expect(await deferBuilt.firstResponse).toEqual({ type: 6 });

    const updateBuilt = buildAdapterInteraction(
      basePayload({ type: 3, data: { custom_id: "drop:claim:1", component_type: 3, values: [] } }),
    );
    const updateInteraction = updateBuilt?.interaction;
    if (!updateInteraction || !updateBuilt || !updateInteraction.isStringSelectMenu()) {
      throw new Error("expected select menu");
    }
    await updateInteraction.update("refreshed");
    expect(await updateBuilt.firstResponse).toEqual({ type: 7, data: { content: "refreshed" } });
  });

  it("a select menu supports deferUpdate then editReply, editing the message it's on", async () => {
    const built = buildAdapterInteraction(
      basePayload({
        type: 3,
        data: { custom_id: "container-new:fill:sack-1", component_type: 3, values: ["a", "b"] },
      }),
    );
    const interaction = built?.interaction;
    if (!interaction || !built || !interaction.isStringSelectMenu()) {
      throw new Error("expected select menu");
    }

    await interaction.deferUpdate();
    expect(await built.firstResponse).toEqual({ type: 6 });
    await interaction.editReply({ content: "Put 2 items in.", components: [] });
    expect(editOriginalInteractionResponse).toHaveBeenCalledWith(APPLICATION_ID, TOKEN, {
      content: "Put 2 items in.",
      components: [],
    });
  });

  it("a button component supports deferUpdate then editReply", async () => {
    const built = buildAdapterInteraction(
      basePayload({ type: 3, data: { custom_id: "drop:apply:1", component_type: 2 } }),
    );
    const interaction = built?.interaction;
    if (!interaction || !built || !interaction.isButton()) throw new Error("expected button");

    await interaction.deferUpdate();
    expect(await built.firstResponse).toEqual({ type: 6 });
    await interaction.editReply("applied");
    expect(editOriginalInteractionResponse).toHaveBeenCalledWith(APPLICATION_ID, TOKEN, {
      content: "applied",
    });
  });

  it("an unrecognized component_type is not built at all", () => {
    const built = buildAdapterInteraction(
      basePayload({ type: 3, data: { custom_id: "x", component_type: 99 } }),
    );
    expect(built).toBeUndefined();
  });
});

describe("buildAdapterInteraction - modal submit (type 5)", () => {
  function modalPayload(includeMessage: boolean) {
    return basePayload({
      type: 5,
      ...(includeMessage ? { message: { id: "message-1" } } : {}),
      data: {
        custom_id: "drop:take-modal:drop-1:item-1",
        components: [{ components: [{ custom_id: "quantity", value: "2" }] }],
      },
    });
  }

  it("reads a text input value out of the nested action-row components", () => {
    const built = buildAdapterInteraction(modalPayload(false));
    const interaction = built?.interaction;
    if (!interaction || !interaction.isModalSubmit()) throw new Error("expected modal submit");

    expect(interaction.fields.getTextInputValue("quantity")).toBe("2");
    expect(() => interaction.fields.getTextInputValue("missing")).toThrow();
  });

  it("isFromMessage() is false, and update/deferUpdate aren't present, without a `message` field", () => {
    const built = buildAdapterInteraction(modalPayload(false));
    const interaction = built?.interaction;
    if (!interaction || !interaction.isModalSubmit()) throw new Error("expected modal submit");

    expect(interaction.isFromMessage()).toBe(false);
    expect("update" in interaction).toBe(false);
  });

  it("isFromMessage() is true, and update/deferUpdate work, with a `message` field", async () => {
    const built = buildAdapterInteraction(modalPayload(true));
    const interaction = built?.interaction;
    if (!interaction || !built || !interaction.isModalSubmit() || !interaction.isFromMessage()) {
      throw new Error("expected a message-attached modal submit");
    }

    await interaction.update("refreshed the drop message");
    expect(await built.firstResponse).toEqual({
      type: 7,
      data: { content: "refreshed the drop message" },
    });
  });
});

describe("isPing/pongResponse", () => {
  it("recognizes a PING (type 1) and answers with PONG", () => {
    expect(isPing(basePayload({ type: 1 }))).toBe(true);
    expect(isPing(basePayload({ type: 2 }))).toBe(false);
    expect(pongResponse).toEqual({ type: 1 });
  });
});
