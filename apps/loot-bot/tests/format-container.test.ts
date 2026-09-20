import { describe, expect, it } from "vitest";
import {
  MAX_FILL_OPTIONS,
  buildFillComponents,
  buildFillCustomId,
  parseFillCustomId,
} from "../src/format-container.js";

const SACK = "11111111-1111-1111-1111-111111111111";

function items(n: number) {
  return Array.from({ length: n }, (_, i) => ({
    entityId: `item-${i}`,
    title: `Thing ${i}`,
    quantity: null,
  }));
}

describe("fill customId", () => {
  it("round-trips the sack's id, and is what the command router prefixes on", () => {
    const id = buildFillCustomId(SACK);

    expect(id).toBe(`container-new:fill:${SACK}`);
    expect(id.split(":")[0]).toBe("container-new");
    expect(parseFillCustomId(id)).toBe(SACK);
  });

  it("fits Discord's 100-character customId limit", () => {
    expect(buildFillCustomId(SACK).length).toBeLessThanOrEqual(100);
  });

  it.each([
    ["another command's id", `drop:take:${SACK}`],
    ["another action", `container-new:other:${SACK}`],
    ["a missing sack id", "container-new:fill:"],
    ["no sack segment at all", "container-new:fill"],
    ["trailing junk", `container-new:fill:${SACK}:extra`],
  ])("rejects %s", (_label, id) => {
    expect(parseFillCustomId(id)).toBeUndefined();
  });
});

describe("buildFillComponents", () => {
  function menu(rows: ReturnType<typeof buildFillComponents>) {
    return rows[0]?.toJSON().components[0] as {
      custom_id: string;
      min_values: number;
      max_values: number;
      options: { label: string; value: string }[];
    };
  }

  it("is one multi-select carrying the sack in its id, offering each item by entity id", () => {
    const rows = buildFillComponents(SACK, items(3));

    expect(rows).toHaveLength(1);
    const m = menu(rows);
    expect(m.custom_id).toBe(buildFillCustomId(SACK));
    expect(m.options.map((o) => o.value)).toEqual(["item-0", "item-1", "item-2"]);
  });

  it("lets the player pick anywhere from one item to all of them", () => {
    const m = menu(buildFillComponents(SACK, items(4)));

    expect(m.min_values).toBe(1);
    expect(m.max_values).toBe(4);
  });

  it("shows only the first 25 when there are more, so the menu stays valid", () => {
    const m = menu(buildFillComponents(SACK, items(40)));

    expect(m.options).toHaveLength(MAX_FILL_OPTIONS);
    expect(m.max_values).toBe(MAX_FILL_OPTIONS);
  });

  it("shows a stack's size, but not for a lone item", () => {
    const m = menu(
      buildFillComponents(SACK, [
        { entityId: "a", title: "Torch", quantity: 5 },
        { entityId: "b", title: "Sword", quantity: null },
        { entityId: "c", title: "Rope", quantity: 1 },
      ]),
    );

    expect(m.options.map((o) => o.label)).toEqual(["Torch ×5", "Sword", "Rope"]);
  });

  it("caps a very long name to Discord's 100-character option label limit", () => {
    const m = menu(
      buildFillComponents(SACK, [{ entityId: "a", title: "x".repeat(300), quantity: null }]),
    );

    expect(m.options[0]?.label).toHaveLength(100);
  });
});
