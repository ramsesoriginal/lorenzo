import { describe, expect, it } from "vitest";
import { formatItemEmbed } from "../src/format-item.js";
import type { EntityDetailOut } from "../src/lorenzo-client.js";

function entity(overrides: Partial<EntityDetailOut> = {}): EntityDetailOut {
  return {
    id: "item-1",
    name: "Ashfang",
    created_at: "2026-01-01T00:00:00Z",
    updated_at: "2026-01-01T00:00:00Z",
    stats: [],
    stat_groups: [],
    information: [],
    prototypes: [],
    instances: [],
    parent: null,
    quantity: null,
    children: [],
    ...overrides,
  } as EntityDetailOut;
}

// Row metadata every InformationOut/PayloadOut carries (ADR 0101) - not
// what these tests are about.
const infoMeta = { is_public: false, order: 0, updated_at: "2026-01-01T00:00:00Z" };
const payloadMeta = { id: "payload-1", order: 0, updated_at: "2026-01-01T00:00:00Z" };

describe("formatItemEmbed", () => {
  it("uses the entity's name as the title", () => {
    const embed = formatItemEmbed(entity({ name: "Ashfang" }));

    expect(embed.data.title).toBe("Ashfang");
  });

  it("shows a friendly message when there's nothing visible", () => {
    const embed = formatItemEmbed(entity());

    expect(embed.data.description).toContain("No stats or notes visible");
  });

  it("renders stats as one field", () => {
    const embed = formatItemEmbed(
      entity({
        stats: [
          { name: "damage", value: 10, own: true },
          { name: "magical", value: true, own: false },
        ],
      }),
    );

    const statsField = embed.data.fields?.find((f) => f.name === "Stats");
    expect(statsField?.value).toBe("damage: 10\nmagical: true");
  });

  it("renders each Information entry as its own field", () => {
    const embed = formatItemEmbed(
      entity({
        information: [
          {
            id: "info-1",
            title: "Description",
            type: "description",
            ...infoMeta,
            payloads: [
              { ...payloadMeta, kind: "description", content: "A flaming sword.", locale: "en-US" },
            ],
          },
          {
            id: "info-2",
            title: "GM notes",
            type: "note",
            ...infoMeta,
            payloads: [
              { ...payloadMeta, kind: "description", content: "Secretly cursed.", locale: "en-US" },
            ],
          },
        ],
      }),
    );

    expect(embed.data.fields).toContainEqual({ name: "Description", value: "A flaming sword." });
    expect(embed.data.fields).toContainEqual({ name: "GM notes", value: "Secretly cursed." });
  });

  it("sets the first picture payload as the embed image", () => {
    const embed = formatItemEmbed(
      entity({
        information: [
          {
            id: "info-1",
            title: "Portrait",
            type: "picture",
            ...infoMeta,
            payloads: [
              {
                ...payloadMeta,
                kind: "picture",
                url: "https://example.test/sword.png",
                file_type: "image/png",
              },
            ],
          },
        ],
      }),
    );

    expect(embed.data.image?.url).toBe("https://example.test/sword.png");
  });

  it("renders a document payload as a link", () => {
    const embed = formatItemEmbed(
      entity({
        information: [
          {
            id: "info-1",
            title: "Lore",
            type: "document",
            ...infoMeta,
            payloads: [
              {
                ...payloadMeta,
                kind: "document",
                url: "https://example.test/lore.pdf",
                filename: "lore.pdf",
                file_type: "application/pdf",
              },
            ],
          },
        ],
      }),
    );

    const field = embed.data.fields?.find((f) => f.name === "Lore");
    expect(field?.value).toBe("[lore.pdf](https://example.test/lore.pdf)");
  });

  it("notes when information entries are omitted past the field cap", () => {
    const information = Array.from({ length: 27 }, (_, i) => ({
      id: `info-${i}`,
      title: `Note ${i}`,
      type: "note",
      ...infoMeta,
      payloads: [{ ...payloadMeta, kind: "description" as const, content: "x", locale: "en-US" }],
    }));

    const embed = formatItemEmbed(entity({ information }));

    expect(embed.data.footer?.text).toContain("2 more notes");
  });
});
