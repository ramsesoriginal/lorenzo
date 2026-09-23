import { beforeEach, describe, expect, it, vi } from "vitest";

const { insertCharacterEvents } = vi.hoisted(() => ({ insertCharacterEvents: vi.fn() }));
vi.mock("../src/db.js", () => ({ insertCharacterEvents }));

const {
  awardEvent,
  bulkGiveEvent,
  claimHonoredEvent,
  confiscateEvent,
  describeItem,
  giveEvent,
  nameCharacter,
  reassignEvent,
  recordCharacterEvents,
  takeEvent,
} = await import("../src/character-events.js");

const FRODO = { id: "char-1", name: "Frodo" };
const SAM = { id: "char-2", name: "Sam" };

describe("describeItem", () => {
  it("shows a stack's size, but not for a lone item", () => {
    expect(describeItem("Torch", 5)).toBe("Torch ×5");
    expect(describeItem("Sword", null)).toBe("Sword");
    expect(describeItem("Rope", 1)).toBe("Rope");
    expect(describeItem("Rope", undefined as unknown as null)).toBe("Rope");
  });
});

describe("nameCharacter", () => {
  it("pairs an id with its name", () => {
    expect(nameCharacter("char-1", "Frodo")).toEqual(FRODO);
  });

  it("keeps the id, and a neutral name, when the name lookup failed", () => {
    expect(nameCharacter("char-1", null)).toEqual({ id: "char-1", name: "another character" });
  });

  it("is null when there's no character at all", () => {
    expect(nameCharacter(null, "Frodo")).toBeNull();
    expect(nameCharacter(undefined, undefined)).toBeNull();
  });
});

describe("the event describers", () => {
  it("names both sides of a give, and files it under both characters", () => {
    expect(giveEvent({ giver: FRODO, receiver: SAM, item: "Torch ×5" })).toEqual({
      kind: "gave",
      summary: "Frodo gave Torch ×5 to Sam.",
      characterEntityIds: ["char-1", "char-2"],
    });
  });

  it("copes with a give from nobody in particular", () => {
    expect(giveEvent({ giver: null, receiver: SAM, item: "Sword" })).toEqual({
      kind: "gave",
      summary: "Someone gave Sword to Sam.",
      characterEntityIds: ["char-2"],
    });
  });

  it("lists a bulk give, capping the names shown but not the count", () => {
    const items = ["A", "B", "C", "D", "E", "F", "G"];

    expect(bulkGiveEvent({ receiver: SAM, items }).summary).toBe(
      "Sam was given 7 items: A, B, C, D, E, and 2 more.",
    );
    expect(bulkGiveEvent({ receiver: SAM, items: ["Sword"] }).summary).toBe("Sam was given Sword.");
    expect(bulkGiveEvent({ receiver: SAM, items: ["A", "B"] }).characterEntityIds).toEqual([
      "char-2",
    ]);
  });

  it("describes a reassignment without any GM in it", () => {
    expect(reassignEvent({ from: FRODO, to: SAM, item: "Torch" })).toEqual({
      kind: "reassigned",
      summary: "Torch was reassigned from Frodo to Sam.",
      characterEntityIds: ["char-1", "char-2"],
    });
    expect(reassignEvent({ from: null, to: SAM, item: "Torch" }).summary).toBe(
      "Torch was assigned to Sam.",
    );
  });

  it("describes an award, a confiscation, a take and an honored claim for one character", () => {
    expect(awardEvent({ character: FRODO, item: "Sword" })).toEqual({
      kind: "awarded",
      summary: "Frodo was awarded Sword.",
      characterEntityIds: ["char-1"],
    });
    expect(confiscateEvent({ character: FRODO, item: "2 of Torch" })).toEqual({
      kind: "confiscated",
      summary: "2 of Torch was taken from Frodo.",
      characterEntityIds: ["char-1"],
    });
    expect(takeEvent({ character: FRODO, item: "Torch" }).summary).toBe(
      "Frodo took Torch from a loot drop.",
    );
    expect(claimHonoredEvent({ character: FRODO, item: "Sword" }).summary).toBe(
      "Frodo received Sword from a loot drop claim.",
    );
  });
});

describe("recordCharacterEvents", () => {
  const warn = vi.fn();
  const logger = { warn } as never;

  beforeEach(() => {
    vi.clearAllMocks();
    insertCharacterEvents.mockResolvedValue(undefined);
  });

  it("writes one row per affected character, all sharing one event id", async () => {
    await recordCharacterEvents(
      [giveEvent({ giver: FRODO, receiver: SAM, item: "Torch" })],
      logger,
    );

    const [rows] = insertCharacterEvents.mock.calls[0] as [
      { eventId: string; characterEntityId: string; kind: string; summary: string }[],
    ];
    expect(rows.map((r) => r.characterEntityId)).toEqual(["char-1", "char-2"]);
    expect(rows[0]?.eventId).toBe(rows[1]?.eventId);
    expect(rows.every((r) => r.kind === "gave" && r.summary === "Frodo gave Torch to Sam.")).toBe(
      true,
    );
  });

  it("gives separate events separate ids", async () => {
    await recordCharacterEvents(
      [awardEvent({ character: FRODO, item: "A" }), awardEvent({ character: SAM, item: "B" })],
      logger,
    );

    const [rows] = insertCharacterEvents.mock.calls[0] as [{ eventId: string }[]];
    expect(rows).toHaveLength(2);
    expect(rows[0]?.eventId).not.toBe(rows[1]?.eventId);
  });

  it("files an event once per character even if the same one is named twice", async () => {
    await recordCharacterEvents(
      [giveEvent({ giver: FRODO, receiver: FRODO, item: "Torch" })],
      logger,
    );

    const [rows] = insertCharacterEvents.mock.calls[0] as [unknown[]];
    expect(rows).toHaveLength(1);
  });

  it("truncates a runaway summary", async () => {
    await recordCharacterEvents([awardEvent({ character: FRODO, item: "x".repeat(2000) })], logger);

    const [rows] = insertCharacterEvents.mock.calls[0] as [{ summary: string }[]];
    expect(rows[0]?.summary).toHaveLength(500);
    expect(rows[0]?.summary.endsWith("…")).toBe(true);
  });

  it("writes nothing for no events", async () => {
    await recordCharacterEvents([], logger);

    expect(insertCharacterEvents).not.toHaveBeenCalled();
  });

  it("never throws - it runs after the real write succeeded, so a failure is only logged", async () => {
    insertCharacterEvents.mockRejectedValue(new Error("db down"));

    await expect(
      recordCharacterEvents([awardEvent({ character: FRODO, item: "Sword" })], logger),
    ).resolves.toBeUndefined();

    expect(warn).toHaveBeenCalledTimes(1);
  });
});
