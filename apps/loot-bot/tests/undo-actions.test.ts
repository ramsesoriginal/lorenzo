import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const { getPendingUndo, setPendingUndo, deletePendingUndo } = vi.hoisted(() => ({
  getPendingUndo: vi.fn(),
  setPendingUndo: vi.fn(),
  deletePendingUndo: vi.fn(),
}));
vi.mock("../src/db.js", () => ({ getPendingUndo, setPendingUndo, deletePendingUndo }));

const { applyPendingUndo, recordUndo } = await import("../src/undo-actions.js");

function fakeClient() {
  return {
    setItemInstanceOwner: vi.fn(async () => ({ entity_id: "item-1", title: "Torch" })),
    setItemInstanceContainer: vi.fn(async () => ({ entity_id: "item-1", title: "Torch" })),
    renameItemInstance: vi.fn(async () => ({ entity_id: "item-1", title: "Old Name" })),
    splitItemInstance: vi.fn(async () => ({
      data: { entity_id: "item-3", title: "Arrows" },
      etag: null,
    })),
    // biome-ignore lint/suspicious/noExplicitAny: minimal fake, not the real client type
  } as any;
}

describe("recordUndo", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("JSON-encodes the payload and stores it under the action's own kind", async () => {
    await recordUndo("user-1", {
      kind: "restore-owner",
      entityId: "item-1",
      previousOwnerCharacterId: "char-1",
    });

    expect(setPendingUndo).toHaveBeenCalledWith("user-1", {
      actionType: "restore-owner",
      payload: JSON.stringify({
        kind: "restore-owner",
        entityId: "item-1",
        previousOwnerCharacterId: "char-1",
      }),
    });
  });
});

describe("applyPendingUndo", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("returns 'none' when there's nothing pending, without touching the API", async () => {
    getPendingUndo.mockResolvedValue(undefined);
    const client = fakeClient();

    const outcome = await applyPendingUndo(client, "tenant-1", "user-1", "token-123");

    expect(outcome).toEqual({ kind: "none" });
    expect(deletePendingUndo).not.toHaveBeenCalled();
  });

  it("returns 'expired' and still clears the row when the TTL has elapsed", async () => {
    getPendingUndo.mockResolvedValue({
      discordUserId: "user-1",
      actionType: "restore-owner",
      payload: JSON.stringify({
        kind: "restore-owner",
        entityId: "item-1",
        previousOwnerCharacterId: "char-1",
      }),
      createdAt: new Date(Date.now() - 10 * 60 * 1000),
    });
    const client = fakeClient();

    const outcome = await applyPendingUndo(client, "tenant-1", "user-1", "token-123");

    expect(outcome).toEqual({ kind: "expired" });
    expect(deletePendingUndo).toHaveBeenCalledWith("user-1");
    expect(client.setItemInstanceOwner).not.toHaveBeenCalled();
  });

  it("reverses a restore-owner action", async () => {
    getPendingUndo.mockResolvedValue({
      discordUserId: "user-1",
      actionType: "restore-owner",
      payload: JSON.stringify({
        kind: "restore-owner",
        entityId: "item-1",
        previousOwnerCharacterId: "char-1",
      }),
      createdAt: new Date(),
    });
    const client = fakeClient();

    const outcome = await applyPendingUndo(client, "tenant-1", "user-1", "token-123");

    expect(client.setItemInstanceOwner).toHaveBeenCalledWith(
      "tenant-1",
      "item-1",
      "char-1",
      "token-123",
    );
    expect(outcome).toEqual({ kind: "undone", description: "Gave Torch back." });
    expect(deletePendingUndo).toHaveBeenCalledWith("user-1");
  });

  it("reverses a restore-container action", async () => {
    getPendingUndo.mockResolvedValue({
      discordUserId: "user-1",
      actionType: "restore-container",
      payload: JSON.stringify({
        kind: "restore-container",
        entityId: "item-1",
        previousContainerEntityId: "container-1",
      }),
      createdAt: new Date(),
    });
    const client = fakeClient();

    const outcome = await applyPendingUndo(client, "tenant-1", "user-1", "token-123");

    expect(client.setItemInstanceContainer).toHaveBeenCalledWith(
      "tenant-1",
      "item-1",
      "container-1",
      "token-123",
    );
    expect(outcome).toEqual({ kind: "undone", description: "Moved Torch back." });
  });

  it("degrades gracefully when a restore-container action had no previous container", async () => {
    getPendingUndo.mockResolvedValue({
      discordUserId: "user-1",
      actionType: "restore-container",
      payload: JSON.stringify({
        kind: "restore-container",
        entityId: "item-1",
        previousContainerEntityId: null,
      }),
      createdAt: new Date(),
    });
    const client = fakeClient();

    const outcome = await applyPendingUndo(client, "tenant-1", "user-1", "token-123");

    expect(client.setItemInstanceContainer).not.toHaveBeenCalled();
    expect(outcome.kind).toBe("undone");
    if (outcome.kind === "undone") {
      expect(outcome.description).toContain("nothing more this bot can undo automatically");
    }
  });

  it("reverses a restore-name action", async () => {
    getPendingUndo.mockResolvedValue({
      discordUserId: "user-1",
      actionType: "restore-name",
      payload: JSON.stringify({
        kind: "restore-name",
        entityId: "item-1",
        previousTitle: "Old Name",
      }),
      createdAt: new Date(),
    });
    const client = fakeClient();

    const outcome = await applyPendingUndo(client, "tenant-1", "user-1", "token-123");

    expect(client.renameItemInstance).toHaveBeenCalledWith(
      "tenant-1",
      "item-1",
      "Old Name",
      "token-123",
    );
    expect(outcome).toEqual({ kind: "undone", description: "Renamed back to Old Name." });
  });

  it("reverses an undo-merge action by splitting the quantity back out", async () => {
    getPendingUndo.mockResolvedValue({
      discordUserId: "user-1",
      actionType: "undo-merge",
      payload: JSON.stringify({
        kind: "undo-merge",
        intoEntityId: "item-2",
        quantity: 3,
        ownerCharacterId: "char-1",
      }),
      createdAt: new Date(),
    });
    const client = fakeClient();

    const outcome = await applyPendingUndo(client, "tenant-1", "user-1", "token-123");

    expect(client.splitItemInstance).toHaveBeenCalledWith(
      "tenant-1",
      "item-2",
      3,
      "token-123",
      undefined,
      "char-1",
    );
    expect(outcome.kind).toBe("undone");
    if (outcome.kind === "undone") {
      expect(outcome.description).toContain("can't be perfectly reversed");
    }
  });
});
