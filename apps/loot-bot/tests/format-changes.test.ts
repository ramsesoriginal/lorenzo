import { describe, expect, it } from "vitest";
import { COVERAGE_NOTE, MAX_CHANGES_SHOWN, buildChangesEmbed } from "../src/format-changes.js";

const AT = new Date("2026-09-20T10:00:00Z");
const UNIX = Math.floor(AT.getTime() / 1000);

function change(summary: string, createdAt = AT) {
  return { summary, createdAt };
}

const embedOf = (args: Parameters<typeof buildChangesEmbed>[0]) => buildChangesEmbed(args).toJSON();

describe("buildChangesEmbed", () => {
  it("always says the view only covers changes made through the bot", () => {
    for (const args of [
      { changes: [change("a")], total: 1, since: undefined, history: false },
      { changes: [], total: 0, since: undefined, history: false },
      { changes: [], total: 0, since: AT, history: false },
      { changes: [], total: 0, since: undefined, history: true },
    ]) {
      expect(embedOf(args).footer?.text).toBe(COVERAGE_NOTE);
    }
    expect(COVERAGE_NOTE).toContain("through this bot");
  });

  it("lists each change with a relative timestamp", () => {
    const embed = embedOf({
      changes: [change("Frodo gave Torch to Sam.")],
      total: 1,
      since: undefined,
      history: false,
    });

    expect(embed.title).toBe("What's changed");
    expect(embed.description).toBe(`<t:${UNIX}:R> — Frodo gave Torch to Sam.`);
  });

  it("says when you last looked, when there's a marker", () => {
    const since = new Date("2026-09-19T10:00:00Z");

    const embed = embedOf({ changes: [change("a")], total: 1, since, history: false });

    expect(
      embed.description?.startsWith(
        `Since you last looked <t:${Math.floor(since.getTime() / 1000)}:R>:`,
      ),
    ).toBe(true);
  });

  it("titles the history view differently, and doesn't claim a 'since'", () => {
    const embed = embedOf({
      changes: [change("a")],
      total: 1,
      since: new Date("2026-09-19T10:00:00Z"),
      history: true,
    });

    expect(embed.title).toBe("Recent changes");
    expect(embed.description).not.toContain("Since you last looked");
  });

  it("says how many older changes a capped list left out", () => {
    const embed = embedOf({
      changes: [change("a"), change("b")],
      total: 5,
      since: undefined,
      history: false,
    });

    expect(embed.description).toContain("…and 3 older changes not shown.");
  });

  it("uses the singular for one left out", () => {
    const embed = embedOf({ changes: [change("a")], total: 2, since: undefined, history: false });

    expect(embed.description).toContain("…and 1 older change not shown.");
  });

  it("says there's nothing new since you last looked, and points at history", () => {
    const since = new Date("2026-09-19T10:00:00Z");

    const embed = embedOf({ changes: [], total: 0, since, history: false });

    expect(embed.description).toContain("Nothing new since you last looked");
    expect(embed.description).toContain("`/changes history:true`");
  });

  it("says nothing's been recorded on a first look, or an empty history", () => {
    expect(embedOf({ changes: [], total: 0, since: undefined, history: false }).description).toBe(
      "Nothing recorded yet.",
    );
    expect(embedOf({ changes: [], total: 0, since: new Date(), history: true }).description).toBe(
      "Nothing recorded yet.",
    );
  });

  it("keeps a very long summary to one line, and a full reply inside Discord's embed limit", () => {
    const many = Array.from({ length: MAX_CHANGES_SHOWN }, () => change("z".repeat(900)));

    const embed = embedOf({ changes: many, total: many.length, since: undefined, history: false });

    const lines = (embed.description ?? "").split("\n");
    expect(lines.every((l) => l.length <= 150)).toBe(true);
    expect((embed.description ?? "").length).toBeLessThanOrEqual(4096);
  });
});
