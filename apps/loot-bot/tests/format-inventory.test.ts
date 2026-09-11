import { describe, expect, it } from "vitest";
import { formatInventoryEmbed } from "../src/format-inventory.js";
import type { ItemInstanceOut, OwnedByResponse } from "../src/lorenzo-client.js";

function item(title: string | null): ItemInstanceOut {
  return {
    entity_id: crypto.randomUUID(),
    owner_entity_id: null,
    title,
    weight: null,
    height: null,
    price: null,
    rarity: null,
    hp: null,
    armor: null,
    container_entity_id: null,
    is_magical: null,
    is_cursed: null,
    descriptions: [],
    pictures: [],
    physical_stats: [],
    economic_stats: [],
    destroyable_stats: [],
    damaging_stats: [],
    tags: [],
  };
}

describe("formatInventoryEmbed", () => {
  it("renders one field per non-empty container, in order", () => {
    const response: OwnedByResponse = {
      groups: [
        {
          container: { id: crypto.randomUUID(), name: "Backpack" },
          item_instances: [item("Sword"), item("Shield")],
        },
        { container: null, item_instances: [item("Torch")] },
      ],
    };

    const embed = formatInventoryEmbed("Frodo", response).toJSON();

    expect(embed.title).toBe("Frodo");
    expect(embed.fields).toEqual([
      { name: "Backpack", value: "• Sword\n• Shield" },
      { name: "Not in a container", value: "• Torch" },
    ]);
  });

  it("shows 'No items.' when there are no groups at all", () => {
    const embed = formatInventoryEmbed("Frodo", { groups: [] }).toJSON();
    expect(embed.description).toBe("No items.");
    expect(embed.fields ?? []).toHaveLength(0);
  });

  it("shows 'No items.' when every group is empty (an owned-but-empty container)", () => {
    const response: OwnedByResponse = {
      groups: [{ container: { id: crypto.randomUUID(), name: "Empty chest" }, item_instances: [] }],
    };
    const embed = formatInventoryEmbed("Frodo", response).toJSON();
    expect(embed.description).toBe("No items.");
  });

  it("falls back to '(untitled)' for an item with no title", () => {
    const response: OwnedByResponse = {
      groups: [{ container: null, item_instances: [item(null)] }],
    };
    const embed = formatInventoryEmbed("Frodo", response).toJSON();
    expect(embed.fields?.[0]?.value).toBe("• (untitled)");
  });

  it("truncates a container's item list to fit Discord's 1024-char field value limit", () => {
    const manyItems = Array.from({ length: 200 }, (_, i) => item(`Item number ${i}`));
    const response: OwnedByResponse = {
      groups: [{ container: null, item_instances: manyItems }],
    };
    const embed = formatInventoryEmbed("Frodo", response).toJSON();
    const value = embed.fields?.[0]?.value ?? "";
    expect(value.length).toBeLessThanOrEqual(1024);
    expect(value).toMatch(/…and \d+ more items\.$/);
  });

  it("truncates to 25 fields (Discord's own embed field limit) with a footer note", () => {
    const groups = Array.from({ length: 30 }, (_, i) => ({
      container: { id: crypto.randomUUID(), name: `Container ${i}` },
      item_instances: [item("Something")],
    }));
    const embed = formatInventoryEmbed("Frodo", { groups }).toJSON();
    expect(embed.fields).toHaveLength(25);
    expect(embed.footer?.text).toBe("…and 5 more containers, not shown.");
  });
});
