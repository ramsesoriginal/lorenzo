import { describe, expect, it } from "vitest";
import {
  buildGiveContentsComponents,
  buildGiveContentsCustomId,
  formatContentsGiven,
  formatGiveContentsPrompt,
  formatGivenWithContents,
  formatKeptNote,
  formatNothingInsideToGive,
  formatWithContentsNote,
  GIVE_CONTENTS_CANCEL_CUSTOM_ID,
  parseGiveContentsCustomId,
} from "../src/format-give-contents.js";
import type { ContentsResultItem } from "../src/lorenzo-client.js";

const CONTAINER = "11111111-1111-1111-1111-111111111111";
const TARGET = "22222222-2222-2222-2222-222222222222";

function given(title: string): ContentsResultItem {
  return { entity_id: title, title, status: "ok", owner: { id: "brisk", name: "Brisk" } };
}

function kept(title: string, owner: string | null): ContentsResultItem {
  return {
    entity_id: title,
    title,
    status: "kept",
    owner: owner ? { id: owner, name: owner } : null,
    problem: { type: "item-not-yours-to-give", title: "Forbidden", status: 403 },
  };
}

describe("give-contents customId", () => {
  it("round-trips the container and its target, and fits Discord's limit", () => {
    const id = buildGiveContentsCustomId({
      containerEntityId: CONTAINER,
      targetCharacterId: TARGET,
    });

    expect(id).toBe(`give-contents:ok:${CONTAINER}:${TARGET}`);
    expect(id.length).toBeLessThanOrEqual(100);
    expect(parseGiveContentsCustomId(id)).toEqual({
      containerEntityId: CONTAINER,
      targetCharacterId: TARGET,
    });
  });

  it.each([
    ["the cancel id", GIVE_CONTENTS_CANCEL_CUSTOM_ID],
    ["/give's id", `give:ok:${CONTAINER}:${TARGET}:all`],
    ["a missing target", `give-contents:ok:${CONTAINER}`],
    ["trailing junk", `give-contents:ok:${CONTAINER}:${TARGET}:x`],
  ])("rejects %s", (_label, id) => {
    expect(parseGiveContentsCustomId(id)).toBeUndefined();
  });

  it("is one row: Give carrying the intent, and Cancel", () => {
    const rows = buildGiveContentsComponents({
      containerEntityId: CONTAINER,
      targetCharacterId: TARGET,
    });

    const buttons = rows[0]?.toJSON().components as { label: string; custom_id: string }[];
    expect(buttons.map((b) => [b.label, b.custom_id])).toEqual([
      ["Give", `give-contents:ok:${CONTAINER}:${TARGET}`],
      ["Cancel", GIVE_CONTENTS_CANCEL_CUSTOM_ID],
    ]);
  });
});

describe("formatKeptNote", () => {
  it("says nothing when everything goes", () => {
    expect(formatKeptNote([given("Rope")])).toBeNull();
  });

  it("says whose what stays is", () => {
    expect(formatKeptNote([given("Rope"), kept("Potion", "Pia")])).toBe(
      "1 thing inside stays Pia's.",
    );
    expect(formatKeptNote([kept("Potion", "Pia"), kept("Ring", "Pia")])).toBe(
      "2 things inside stay Pia's.",
    );
  });

  it("counts by owner when there are several", () => {
    expect(formatKeptNote([kept("Potion", "Pia"), kept("Ring", "Pia"), kept("Map", "Oskar")])).toBe(
      "3 things inside stay with their owners: 2 are Pia's, 1 is Oskar's.",
    );
  });

  it("names no one for something nobody owns", () => {
    expect(formatKeptNote([kept("Gem", null)])).toBe("1 thing inside stays no one's.");
  });
});

describe("/give-contents' wording", () => {
  it("asks about what goes, and says what stays", () => {
    expect(
      formatGiveContentsPrompt("Backpack", "Brisk", [
        given("Rope"),
        given("Coin"),
        kept("Potion", "Pia"),
      ]),
    ).toBe("Give **2 things** inside **Backpack** to **Brisk**? 1 thing inside stays Pia's.");
  });

  it("says when there's nothing inside, or nothing inside that can go", () => {
    expect(formatNothingInsideToGive("Backpack", "Brisk", [])).toBe(
      "There's nothing inside Backpack to give to Brisk.",
    );
    expect(formatNothingInsideToGive("Backpack", "Brisk", [kept("Potion", "Pia")])).toBe(
      "Nothing inside Backpack can be given. 1 thing inside stays Pia's.",
    );
  });

  it("says what went", () => {
    expect(formatContentsGiven("Backpack", "Brisk", [given("Rope")])).toBe(
      "Gave 1 thing inside Backpack to Brisk.",
    );
  });
});

describe("/give's wording for a container", () => {
  it("says what giving with what's inside adds", () => {
    expect(formatWithContentsNote([given("Rope"), given("Coin"), kept("Potion", "Pia")])).toBe(
      `"Give with what's inside" also gives 2 things inside it. 1 thing inside stays Pia's.`,
    );
  });

  it("says what went along", () => {
    expect(
      formatGivenWithContents("Backpack", "Brisk", [given("Rope"), kept("Potion", "Pia")]),
    ).toBe("Gave Backpack to Brisk, with 1 thing inside. 1 thing inside stays Pia's.");
    expect(formatGivenWithContents("Backpack", "Brisk", [])).toBe("Gave Backpack to Brisk.");
  });
});
