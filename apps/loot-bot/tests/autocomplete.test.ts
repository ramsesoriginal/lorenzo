import { describe, expect, it } from "vitest";
import { formatChoiceNameWithSlug } from "../src/commands/autocomplete.js";

describe("formatChoiceNameWithSlug", () => {
  it("is just the item choice name when there's no slug", () => {
    expect(formatChoiceNameWithSlug("Torch", null, null)).toBe("Torch");
    expect(formatChoiceNameWithSlug("Torch", 5, null)).toBe("Torch ×5");
  });

  it("appends the slug in brackets", () => {
    expect(formatChoiceNameWithSlug("Goblin hoard", null, "goblin-hoard")).toBe(
      "Goblin hoard [goblin-hoard]",
    );
    expect(formatChoiceNameWithSlug("Torch", 5, "torches")).toBe("Torch ×5 [torches]");
  });

  it("truncates the title, never the slug, to stay within Discord's 100-character limit", () => {
    const name = formatChoiceNameWithSlug("x".repeat(200), null, "keep-me");

    expect(name).toHaveLength(100);
    expect(name.endsWith(" [keep-me]")).toBe(true);
  });

  it("still truncates a long name that has no slug", () => {
    expect(formatChoiceNameWithSlug("y".repeat(200), null, null)).toHaveLength(100);
  });
});
