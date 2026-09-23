import { beforeEach, describe, expect, it, vi } from "vitest";
import { LorenzoApiError } from "../src/lorenzo-client.js";
import type { LorenzoApiClient } from "../src/lorenzo-client.js";

const { getContainerPrototypeId, setContainerPrototypeId } = vi.hoisted(() => ({
  getContainerPrototypeId: vi.fn(),
  setContainerPrototypeId: vi.fn(),
}));
vi.mock("../src/db.js", () => ({ getContainerPrototypeId, setContainerPrototypeId }));

const { resolveSackPrototype } = await import("../src/commands/sack-prototype.js");

const findItemsByName = vi.fn();
const createItem = vi.fn();
const client = { findItemsByName, createItem } as unknown as LorenzoApiClient;

const resolve = () => resolveSackPrototype(client, "tenant-1", "token-1");

describe("resolveSackPrototype", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    getContainerPrototypeId.mockResolvedValue(undefined);
  });

  it("uses the stored prototype without touching the catalog - so a player with no catalog access works", async () => {
    getContainerPrototypeId.mockResolvedValue("stored-1");

    await expect(resolve()).resolves.toEqual({ kind: "ok", prototypeId: "stored-1" });

    expect(findItemsByName).not.toHaveBeenCalled();
    expect(createItem).not.toHaveBeenCalled();
    expect(getContainerPrototypeId).toHaveBeenCalledWith("tenant-1");
  });

  it("finds an existing 'Sack' by title, case-insensitively, and remembers it", async () => {
    findItemsByName.mockResolvedValue([{ entity_id: "found-1", title: "sack" }]);

    await expect(resolve()).resolves.toEqual({ kind: "ok", prototypeId: "found-1" });

    expect(findItemsByName).toHaveBeenCalledWith("tenant-1", "Sack", "token-1");
    expect(createItem).not.toHaveBeenCalled();
    expect(setContainerPrototypeId).toHaveBeenCalledWith("tenant-1", "found-1");
  });

  it("doesn't take a merely similar name for the sack (the search is a substring match)", async () => {
    findItemsByName.mockResolvedValue([
      { entity_id: "cart-1", title: "Sack cart" },
      { entity_id: "sackbut-1", title: "Sackbut" },
    ]);
    createItem.mockResolvedValue({ entity_id: "new-1", title: "Sack" });

    await expect(resolve()).resolves.toEqual({ kind: "ok", prototypeId: "new-1" });

    expect(createItem).toHaveBeenCalledWith("tenant-1", "Sack", "token-1");
  });

  it("creates one when the catalog has none, and remembers it", async () => {
    findItemsByName.mockResolvedValue([]);
    createItem.mockResolvedValue({ entity_id: "new-1", title: "Sack" });

    await expect(resolve()).resolves.toEqual({ kind: "ok", prototypeId: "new-1" });

    expect(setContainerPrototypeId).toHaveBeenCalledWith("tenant-1", "new-1");
  });

  it.each([404, 403])(
    "reports 'needs catalog access' on a %i - an ordinary player can't even list the catalog",
    async (status) => {
      findItemsByName.mockRejectedValue(new LorenzoApiError("nope", status));

      await expect(resolve()).resolves.toEqual({ kind: "needs-catalog-access" });

      expect(createItem).not.toHaveBeenCalled();
      expect(setContainerPrototypeId).not.toHaveBeenCalled();
    },
  );

  it("reports 'needs catalog access' when the lookup works but creating is refused", async () => {
    findItemsByName.mockResolvedValue([]);
    createItem.mockRejectedValue(new LorenzoApiError("forbidden", 403));

    await expect(resolve()).resolves.toEqual({ kind: "needs-catalog-access" });

    expect(setContainerPrototypeId).not.toHaveBeenCalled();
  });

  it("lets an unexpected API error through rather than pretending it's a permissions problem", async () => {
    findItemsByName.mockRejectedValue(new LorenzoApiError("boom", 500));

    await expect(resolve()).rejects.toThrow("boom");
  });
});
