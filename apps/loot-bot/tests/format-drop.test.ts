import { describe, expect, it } from "vitest";
import type { LootClaim } from "../src/db.js";
import {
  availableDropItems,
  buildApplySummaryEmbed,
  buildDropComponents,
  buildDropEmbed,
  buildQuantityModal,
} from "../src/format-drop.js";
import type { ItemInstanceOut } from "../src/lorenzo-client.js";

function item(overrides: Partial<ItemInstanceOut> = {}): ItemInstanceOut {
  return {
    entity_id: "item-1",
    title: "Torch",
    quantity: null,
    owner_entity_id: null,
    ...overrides,
  } as ItemInstanceOut;
}

// discord.js's own builder types narrow `.data` to a union that excludes
// custom_id for a premium/SKU button - never actually built here, so this
// reaches past that for test-only assertions rather than threading a cast
// through every call site.
// biome-ignore lint/suspicious/noExplicitAny: see above
function customIdOf(component: { data: any } | undefined): string | undefined {
  return component?.data.custom_id;
}

function claim(overrides: Partial<LootClaim> = {}): LootClaim {
  return {
    lootDropId: "drop-1",
    itemEntityId: "item-1",
    discordUserId: "user-1",
    characterEntityId: "char-1",
    quantity: null,
    createdAt: new Date(),
    ...overrides,
  } as LootClaim;
}

describe("availableDropItems", () => {
  it("keeps only items with no owner", () => {
    const items = [
      item({ entity_id: "item-1", owner_entity_id: null }),
      item({ entity_id: "item-2", owner_entity_id: "char-1" }),
    ];

    expect(availableDropItems(items).map((i) => i.entityId)).toEqual(["item-1"]);
  });

  it("defaults a missing title to (untitled)", () => {
    const items = [item({ title: null })];

    expect(availableDropItems(items)[0]?.title).toBe("(untitled)");
  });
});

describe("buildDropEmbed", () => {
  it("shows a friendly message when nothing is left", () => {
    const embed = buildDropEmbed([], []);

    expect(embed.data.description).toContain("Nothing left unclaimed");
  });

  it("shows quantity only for a stack greater than one", () => {
    const embed = buildDropEmbed(
      [
        { entityId: "item-1", title: "Torch", quantity: 5 },
        { entityId: "item-2", title: "Sword", quantity: null },
      ],
      [],
    );

    expect(embed.data.description).toContain("**Torch** ×5");
    expect(embed.data.description).toContain("**Sword**");
    expect(embed.data.description).not.toContain("Sword ×");
  });

  it("annotates an item with everyone who's claimed it", () => {
    const embed = buildDropEmbed(
      [{ entityId: "item-1", title: "Torch", quantity: 5 }],
      [
        claim({ discordUserId: "user-1", quantity: 2 }),
        claim({ discordUserId: "user-2", quantity: null }),
      ],
    );

    expect(embed.data.description).toContain("claimed by <@user-1> (2), <@user-2>");
  });

  it("doesn't annotate an item nobody has claimed", () => {
    const embed = buildDropEmbed(
      [{ entityId: "item-1", title: "Torch", quantity: 5 }],
      [claim({ itemEntityId: "item-2" })],
    );

    expect(embed.data.description).not.toContain("claimed by");
  });
});

describe("buildDropComponents", () => {
  it("returns only the apply-claims button when nothing is left", () => {
    const rows = buildDropComponents("drop-1", []);

    expect(rows).toHaveLength(1);
    expect(customIdOf(rows[0]?.components[0])).toBe("drop:apply:drop-1");
  });

  it("returns take/claim menus plus the apply button when items remain", () => {
    const rows = buildDropComponents("drop-1", [
      { entityId: "item-1", title: "Torch", quantity: 5 },
    ]);

    expect(rows).toHaveLength(3);
    const [takeRow, claimRow, applyRow] = rows;
    expect(customIdOf(takeRow?.components[0])).toBe("drop:take:drop-1");
    expect(customIdOf(claimRow?.components[0])).toBe("drop:claim:drop-1");
    expect(customIdOf(applyRow?.components[0])).toBe("drop:apply:drop-1");
  });

  it("caps select menu options at 25", () => {
    const items = Array.from({ length: 30 }, (_, i) => ({
      entityId: `item-${i}`,
      title: `Item ${i}`,
      quantity: null,
    }));

    const [takeRow] = buildDropComponents("drop-1", items);
    const menu = takeRow?.components[0];
    // biome-ignore lint/suspicious/noExplicitAny: see customIdOf above
    expect((menu?.toJSON() as any).options).toHaveLength(25);
  });
});

describe("buildQuantityModal", () => {
  it("namespaces the customId with action, dropId, and itemEntityId", () => {
    const modal = buildQuantityModal("take", "drop-1", "item-1");

    expect(modal.data.custom_id).toBe("drop:take-modal:drop-1:item-1");
  });

  it("uses a distinct customId for claim", () => {
    const modal = buildQuantityModal("claim", "drop-1", "item-1");

    expect(modal.data.custom_id).toBe("drop:claim-modal:drop-1:item-1");
  });
});

describe("buildApplySummaryEmbed", () => {
  it("shows a friendly message when there were no claims", () => {
    const embed = buildApplySummaryEmbed([]);

    expect(embed.data.description).toContain("No claims were outstanding");
  });

  it("describes a successful whole-item claim", () => {
    const embed = buildApplySummaryEmbed([
      { discordUserId: "user-1", itemTitle: "Sword", status: "given", quantity: null },
    ]);

    expect(embed.data.description).toBe("<@user-1> got **Sword**.");
  });

  it("describes a successful partial claim", () => {
    const embed = buildApplySummaryEmbed([
      { discordUserId: "user-1", itemTitle: "Torch", status: "given", quantity: 2 },
    ]);

    expect(embed.data.description).toBe("<@user-1> got 2 of **Torch**.");
  });

  it("describes a failed claim with its reason", () => {
    const embed = buildApplySummaryEmbed([
      { discordUserId: "user-1", itemTitle: "Sword", status: "already-taken", quantity: null },
      { discordUserId: "user-2", itemTitle: "Torch", status: "not-enough-left", quantity: 10 },
    ]);

    expect(embed.data.description).toContain("already taken");
    expect(embed.data.description).toContain("not enough left");
  });
});
