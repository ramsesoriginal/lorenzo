import { describe, expect, it } from "vitest";
import { DEFAULT_GM_WORDS, gmWords } from "../src/gm-title.js";

const GM = { gmTitle: "GM", gmTitlePlural: "GMs" };
const STORYTELLER = { gmTitle: "Storyteller", gmTitlePlural: "Storytellers" };
const NARRATOR = { gmTitle: "Narrator", gmTitlePlural: "Narrators" };

describe("gmWords (ADR 0294)", () => {
  it("says GM and GMs when no campaign is in play", () => {
    expect(gmWords([])).toEqual({ singular: "GM", plural: "GMs" });
    expect(DEFAULT_GM_WORDS).toEqual({ singular: "GM", plural: "GMs" });
  });

  it("says GM and GMs for a campaign that keeps the default", () => {
    expect(gmWords([GM])).toEqual({ singular: "GM", plural: "GMs" });
  });

  it("uses the title of one campaign, as written", () => {
    expect(gmWords([STORYTELLER])).toEqual({ singular: "Storyteller", plural: "Storytellers" });
    expect(gmWords([{ gmTitle: "dungeon keeper", gmTitlePlural: "keepers" }])).toEqual({
      singular: "dungeon keeper",
      plural: "keepers",
    });
  });

  it("uses the title when every campaign has the same one", () => {
    expect(gmWords([STORYTELLER, STORYTELLER, STORYTELLER])).toEqual({
      singular: "Storyteller",
      plural: "Storytellers",
    });
  });

  it("says GM and GMs when the campaigns differ", () => {
    expect(gmWords([STORYTELLER, NARRATOR])).toEqual(DEFAULT_GM_WORDS);
    expect(gmWords([STORYTELLER, GM])).toEqual(DEFAULT_GM_WORDS);
    expect(gmWords([GM, STORYTELLER])).toEqual(DEFAULT_GM_WORDS);
  });

  it("treats a different plural as a different title", () => {
    expect(gmWords([STORYTELLER, { gmTitle: "Storyteller", gmTitlePlural: "Tellers" }])).toEqual(
      DEFAULT_GM_WORDS,
    );
  });

  it("escapes Discord markdown in a title and leaves a name's punctuation alone", () => {
    expect(gmWords([{ gmTitle: "_Keeper_", gmTitlePlural: "_Keepers_" }])).toEqual({
      singular: "\\_Keeper\\_",
      plural: "\\_Keepers\\_",
    });
    expect(
      gmWords([
        { gmTitle: "Mistress of Ceremonies (MC)", gmTitlePlural: "Mistresses & Co. / MCs" },
      ]),
    ).toEqual({ singular: "Mistress of Ceremonies (MC)", plural: "Mistresses & Co. / MCs" });
  });
});
