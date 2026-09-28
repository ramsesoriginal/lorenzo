import { describe, expect, it } from "vitest";
import { formatInventoryEmbed } from "../src/format-inventory.js";
import type { HeldByResponse, ItemInstanceOut } from "../src/lorenzo-client.js";

type HeldGroup = HeldByResponse["groups"][number];

const FRODO = { id: "frodo", name: "Frodo" };

function item(
  title: string,
  quantity: number | null = null,
  slug: string | null = null,
  owner: string | null = FRODO.id,
): ItemInstanceOut {
  return {
    entity_id: crypto.randomUUID(),
    owner_entity_id: owner,
    title,
    weight: null,
    height: null,
    price: null,
    rarity: null,
    hp: null,
    armor: null,
    container_entity_id: null,
    quantity,
    is_container: null,
    bound: false,
    created_by: null,
    updated_by: null,
    updated_at: "2026-01-01T00:00:00Z",
    slug,
    prototype_ids: [],
    descriptions: [],
    pictures: [],
    physical_stats: [],
    economic_stats: [],
    destroyable_stats: [],
    damaging_stats: [],
    tags: [],
  };
}

/** Frodo's own group (Equipped) holding `equipped`, then `others`. */
function held(
  equipped: ItemInstanceOut[],
  others: HeldGroup[] = [],
  owners = [FRODO],
): HeldByResponse {
  return {
    groups: [
      {
        container: FRODO,
        container_kind: "being",
        path: [],
        carried: true,
        item_instances: equipped,
      },
      ...others,
    ],
    owners,
  };
}

function container(
  name: string,
  items: ItemInstanceOut[],
  overrides: Partial<Omit<HeldGroup, "container" | "item_instances">> = {},
): HeldGroup {
  return {
    container: { id: crypto.randomUUID(), name },
    container_kind: "item_instance",
    path: [],
    carried: true,
    item_instances: items,
    ...overrides,
  };
}

describe("formatInventoryEmbed", () => {
  it("puts Equipped first, then what's carried, then what's held elsewhere", () => {
    const backpack = { id: "backpack", name: "Backpack" };
    const response = held(
      [item("Sword")],
      [
        container("Backpack", [item("Rope")]),
        container("Belt pouch", [item("Coin", 12)], { path: [backpack] }),
        container("Chest", [item("Map")], {
          carried: false,
          path: [
            { id: "carriage", name: "Carriage" },
            { id: "stable", name: "Stable" },
          ],
        }),
      ],
    );

    const embed = formatInventoryEmbed("Frodo", response).toJSON();

    expect(embed.title).toBe("Frodo");
    expect(embed.fields).toEqual([
      { name: "Equipped", value: "• Sword" },
      { name: "Backpack", value: "• Rope" },
      { name: "Belt pouch, in Backpack", value: "• Coin ×12" },
      { name: "Elsewhere: Chest, in Carriage, in Stable", value: "• Map" },
    ]);
  });

  it("says who has what's in another being's hands", () => {
    const response = held(
      [],
      [
        container("Sam", [item("Pan")], {
          container_kind: "being",
          carried: false,
          path: [{ id: "inn", name: "Prancing Pony" }],
        }),
      ],
    );
    const embed = formatInventoryEmbed("Frodo", response).toJSON();
    expect(embed.fields?.[1]).toEqual({
      name: "Elsewhere: Sam has these, in Prancing Pony",
      value: "• Pan",
    });
  });

  it("says whose an item is when it isn't the character's own", () => {
    const response = held(
      [item("Sting"), item("Mithril", null, null, "bilbo"), item("Lembas", 3, null, null)],
      [],
      [{ id: "bilbo", name: "Bilbo" }, FRODO],
    );
    const embed = formatInventoryEmbed("Frodo", response).toJSON();
    expect(embed.fields?.[0]?.value).toBe("• Sting\n• Mithril — Bilbo's\n• Lembas ×3 — No one's");
  });

  it("marks what's bound", () => {
    const response = held([{ ...item("Ring", null, "ring"), bound: true }, item("Rope")]);
    const embed = formatInventoryEmbed("Frodo", response).toJSON();
    expect(embed.fields?.[0]?.value).toBe("• Ring `ring` (bound)\n• Rope");
  });

  it("shows an instance's slug as a code span, and only when it has one", () => {
    const response = held([
      item("Goblin hoard", null, "goblin-hoard"),
      item("Torch", 5, "torches"),
      item("Rope"),
    ]);

    const embed = formatInventoryEmbed("Frodo", response).toJSON();

    expect(embed.fields?.[0]).toEqual({
      name: "Equipped",
      value: "• Goblin hoard `goblin-hoard`\n• Torch ×5 `torches`\n• Rope",
    });
  });

  it("always shows Equipped, saying so when it's empty", () => {
    const embed = formatInventoryEmbed("Frodo", held([])).toJSON();
    expect(embed.fields).toEqual([{ name: "Equipped", value: "Nothing equipped." }]);
  });

  it("leaves out a container whose items were all filtered away, and says so for Equipped", () => {
    const response = held([], [container("Empty chest", [])]);
    const embed = formatInventoryEmbed("Frodo", response, {
      emptyEquipped: "Nothing equipped matches.",
    }).toJSON();
    expect(embed.fields).toEqual([{ name: "Equipped", value: "Nothing equipped matches." }]);
  });

  it("shows a stack's quantity, but not for a lone item", () => {
    const response = held([item("Torch", 5), item("Sword", 1), item("Shield", null)]);
    const embed = formatInventoryEmbed("Frodo", response).toJSON();
    expect(embed.fields?.[0]?.value).toBe("• Torch ×5\n• Sword\n• Shield");
  });

  it("truncates a container's item list to fit Discord's 1024-char field value limit", () => {
    const manyItems = Array.from({ length: 200 }, (_, i) => item(`Item number ${i}`));
    const embed = formatInventoryEmbed("Frodo", held(manyItems)).toJSON();
    const value = embed.fields?.[0]?.value ?? "";
    expect(value.length).toBeLessThanOrEqual(1024);
    expect(value).toMatch(/…and \d+ more items\.$/);
  });

  it("truncates to 25 fields (Discord's own embed field limit) with a footer note", () => {
    const others = Array.from({ length: 30 }, (_, i) =>
      container(`Container ${i}`, [item("Something")]),
    );
    const embed = formatInventoryEmbed("Frodo", held([item("Sword")], others)).toJSON();
    expect(embed.fields).toHaveLength(25);
    expect(embed.footer?.text).toBe("…and 6 more containers, not shown.");
  });
});
