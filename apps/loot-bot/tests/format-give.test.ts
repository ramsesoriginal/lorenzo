import { describe, expect, it } from "vitest";
import {
  buildGiveConfirmComponents,
  buildGiveConfirmCustomId,
  buildGiveWithContentsCustomId,
  formatGivePrompt,
  GIVE_CANCEL_CUSTOM_ID,
  parseGiveConfirmCustomId,
  parseGiveWithContentsCustomId,
} from "../src/format-give.js";

const ITEM = "11111111-1111-1111-1111-111111111111";
const TARGET = "22222222-2222-2222-2222-222222222222";

describe("give confirm customId", () => {
  it("round-trips a quantity", () => {
    const id = buildGiveConfirmCustomId({
      itemEntityId: ITEM,
      targetCharacterId: TARGET,
      quantity: 3,
    });

    expect(id).toBe(`give:ok:${ITEM}:${TARGET}:3`);
    expect(parseGiveConfirmCustomId(id)).toEqual({
      itemEntityId: ITEM,
      targetCharacterId: TARGET,
      quantity: 3,
    });
  });

  it("round-trips 'all of it' (no quantity)", () => {
    const id = buildGiveConfirmCustomId({
      itemEntityId: ITEM,
      targetCharacterId: TARGET,
      quantity: null,
    });

    expect(id.endsWith(":all")).toBe(true);
    expect(parseGiveConfirmCustomId(id)?.quantity).toBeNull();
  });

  it("fits Discord's 100-character customId limit even at the largest quantity an integer option carries", () => {
    const id = buildGiveConfirmCustomId({
      itemEntityId: ITEM,
      targetCharacterId: TARGET,
      quantity: Number.MAX_SAFE_INTEGER,
    });

    expect(id.length).toBeLessThanOrEqual(100);
    expect(parseGiveConfirmCustomId(id)?.quantity).toBe(Number.MAX_SAFE_INTEGER);
  });

  it.each([
    ["the cancel id", GIVE_CANCEL_CUSTOM_ID],
    ["another command's id", `drop:take:${ITEM}`],
    ["a missing quantity", `give:ok:${ITEM}:${TARGET}`],
    ["a missing target", `give:ok:${ITEM}`],
    ["a non-numeric quantity", `give:ok:${ITEM}:${TARGET}:banana`],
    ["a zero quantity", `give:ok:${ITEM}:${TARGET}:0`],
    ["a negative quantity", `give:ok:${ITEM}:${TARGET}:-2`],
    ["a fractional quantity", `give:ok:${ITEM}:${TARGET}:1.5`],
    ["a quantity past what's safely an integer", `give:ok:${ITEM}:${TARGET}:99999999999999999999`],
    ["trailing junk", `give:ok:${ITEM}:${TARGET}:2:extra`],
  ])("rejects %s", (_label, id) => {
    expect(parseGiveConfirmCustomId(id)).toBeUndefined();
  });
});

describe("give-with-contents customId (ADR 0125)", () => {
  it("round-trips the item and its target, and fits Discord's limit", () => {
    const id = buildGiveWithContentsCustomId({ itemEntityId: ITEM, targetCharacterId: TARGET });

    expect(id).toBe(`give:okc:${ITEM}:${TARGET}`);
    expect(id.length).toBeLessThanOrEqual(100);
    expect(parseGiveWithContentsCustomId(id)).toEqual({
      itemEntityId: ITEM,
      targetCharacterId: TARGET,
    });
  });

  it.each([
    ["a plain confirm id", `give:ok:${ITEM}:${TARGET}:all`],
    ["the cancel id", GIVE_CANCEL_CUSTOM_ID],
    ["a missing target", `give:okc:${ITEM}`],
    ["trailing junk", `give:okc:${ITEM}:${TARGET}:all`],
  ])("rejects %s", (_label, id) => {
    expect(parseGiveWithContentsCustomId(id)).toBeUndefined();
  });

  it("isn't taken for a plain confirm", () => {
    expect(parseGiveConfirmCustomId(`give:okc:${ITEM}:${TARGET}`)).toBeUndefined();
  });
});

describe("buildGiveConfirmComponents", () => {
  it("offers giving with what's inside between Give and Cancel, when asked to", () => {
    const rows = buildGiveConfirmComponents(
      { itemEntityId: ITEM, targetCharacterId: TARGET, quantity: null },
      { withContents: true },
    );

    const buttons = rows[0]?.toJSON().components as { label: string; custom_id: string }[];
    expect(buttons.map((b) => [b.label, b.custom_id])).toEqual([
      ["Give", `give:ok:${ITEM}:${TARGET}:all`],
      ["Give with what's inside", `give:okc:${ITEM}:${TARGET}`],
      ["Cancel", GIVE_CANCEL_CUSTOM_ID],
    ]);
  });

  it("is one row: a Give button carrying the intent, and a Cancel button", () => {
    const rows = buildGiveConfirmComponents({
      itemEntityId: ITEM,
      targetCharacterId: TARGET,
      quantity: null,
    });

    expect(rows).toHaveLength(1);
    const buttons = rows[0]?.toJSON().components as { label: string; custom_id: string }[];
    expect(buttons.map((b) => [b.label, b.custom_id])).toEqual([
      ["Give", `give:ok:${ITEM}:${TARGET}:all`],
      ["Cancel", GIVE_CANCEL_CUSTOM_ID],
    ]);
  });
});

describe("formatGivePrompt", () => {
  it("names a lone item plainly", () => {
    expect(formatGivePrompt("Sword", null, null, "Sam")).toBe("Give **Sword** to **Sam**?");
  });

  it("shows a whole stack's size", () => {
    expect(formatGivePrompt("Torch", 5, null, "Sam")).toBe("Give **Torch ×5** to **Sam**?");
  });

  it("treats a quantity that covers the stack as giving all of it", () => {
    expect(formatGivePrompt("Torch", 5, 5, "Sam")).toBe("Give **Torch ×5** to **Sam**?");
    expect(formatGivePrompt("Torch", 5, 9, "Sam")).toBe("Give **Torch ×5** to **Sam**?");
  });

  it("says how many of how many for a partial give", () => {
    expect(formatGivePrompt("Torch", 5, 2, "Sam")).toBe(
      "Give **2 of Torch** (you have 5) to **Sam**?",
    );
  });

  it("doesn't call a stack of one a stack", () => {
    expect(formatGivePrompt("Torch", 1, null, "Sam")).toBe("Give **Torch** to **Sam**?");
  });
});
