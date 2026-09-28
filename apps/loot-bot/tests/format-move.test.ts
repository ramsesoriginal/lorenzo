import { describe, expect, it } from "vitest";
import {
  buildMoveAnywayComponents,
  buildMoveAnywayCustomId,
  parseMoveAnywayCustomId,
} from "../src/format-move.js";

const ITEM = "11111111-1111-1111-1111-111111111111";
const CONTAINER = "22222222-2222-2222-2222-222222222222";
const MOVE = { itemEntityId: ITEM, containerEntityId: CONTAINER };

describe("move-anyway customId", () => {
  it.each([
    [false, `move:force:${ITEM}:${CONTAINER}`],
    [true, `move:lift:${ITEM}:${CONTAINER}`],
  ])("round-trips the move, lifting %s, and fits Discord's limit", (lift, expected) => {
    const id = buildMoveAnywayCustomId({ ...MOVE, lift });

    expect(id).toBe(expected);
    expect(id.length).toBeLessThanOrEqual(100);
    expect(parseMoveAnywayCustomId(id)).toEqual({ ...MOVE, lift });
  });

  it.each([
    "move:force",
    `move:force:${ITEM}`,
    `move:force:${ITEM}:${CONTAINER}:extra`,
    `give:force:${ITEM}:${CONTAINER}`,
    `move:ok:${ITEM}:${CONTAINER}`,
  ])("reads %s as nothing", (customId) => {
    expect(parseMoveAnywayCustomId(customId)).toBeUndefined();
  });

  it("builds one danger button for what doesn't fit", () => {
    const [row] = buildMoveAnywayComponents(MOVE, { offerLift: false });
    const buttons = row?.toJSON().components ?? [];

    expect(buttons).toHaveLength(1);
    expect(buttons[0]).toMatchObject({
      custom_id: `move:force:${ITEM}:${CONTAINER}`,
      label: "Move anyway",
      style: 4,
    });
  });

  it("offers lifting a binding beside it", () => {
    const [row] = buildMoveAnywayComponents(MOVE, { offerLift: true });
    const buttons = row?.toJSON().components ?? [];

    expect(buttons.map((b) => ("label" in b ? b.label : undefined))).toEqual([
      "Move anyway",
      "Move and lift binding",
    ]);
    expect(buttons[1]).toMatchObject({ custom_id: `move:lift:${ITEM}:${CONTAINER}` });
  });
});
