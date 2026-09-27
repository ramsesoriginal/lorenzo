import { describe, expect, it } from "vitest";
import {
  buildMoveAnywayComponents,
  buildMoveAnywayCustomId,
  parseMoveAnywayCustomId,
} from "../src/format-move.js";

const ITEM = "11111111-1111-1111-1111-111111111111";
const CONTAINER = "22222222-2222-2222-2222-222222222222";

describe("move-anyway customId", () => {
  it("round-trips the item and the container, and fits Discord's limit", () => {
    const id = buildMoveAnywayCustomId({ itemEntityId: ITEM, containerEntityId: CONTAINER });

    expect(id).toBe(`move:force:${ITEM}:${CONTAINER}`);
    expect(id.length).toBeLessThanOrEqual(100);
    expect(parseMoveAnywayCustomId(id)).toEqual({
      itemEntityId: ITEM,
      containerEntityId: CONTAINER,
    });
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

  it("builds one danger button", () => {
    const [row] = buildMoveAnywayComponents({ itemEntityId: ITEM, containerEntityId: CONTAINER });
    const buttons = row?.toJSON().components ?? [];

    expect(buttons).toHaveLength(1);
    expect(buttons[0]).toMatchObject({
      custom_id: `move:force:${ITEM}:${CONTAINER}`,
      label: "Move anyway",
      style: 4,
    });
  });
});
