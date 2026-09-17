import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import {
  clearPendingBulkGivesForTests,
  consumePendingBulkGive,
  storePendingBulkGive,
} from "../src/pending-bulk-give.js";

describe("pending-bulk-give", () => {
  beforeEach(() => {
    clearPendingBulkGivesForTests();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("returns undefined for an unknown token", () => {
    expect(consumePendingBulkGive("unknown-token")).toBeUndefined();
  });

  it("stores and consumes an entry exactly once", () => {
    const token = storePendingBulkGive({
      discordUserId: "user-1",
      itemEntityIds: ["item-1", "item-2"],
    });

    const consumed = consumePendingBulkGive(token);
    expect(consumed).toEqual({ discordUserId: "user-1", itemEntityIds: ["item-1", "item-2"] });

    expect(consumePendingBulkGive(token)).toBeUndefined();
  });

  it("expires an entry after its TTL elapses", () => {
    vi.useFakeTimers();
    const token = storePendingBulkGive({ discordUserId: "user-1", itemEntityIds: ["item-1"] });

    vi.advanceTimersByTime(6 * 60 * 1000);

    expect(consumePendingBulkGive(token)).toBeUndefined();
  });
});
