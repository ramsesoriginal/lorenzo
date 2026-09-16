import { beforeEach, describe, expect, it, vi } from "vitest";
import type { ItemInstanceOut, LorenzoApiClient } from "../src/lorenzo-client.js";

function fakeClient(): LorenzoApiClient {
  return {
    splitItemInstance: vi.fn(),
    setItemInstanceOwner: vi.fn(),
  } as unknown as LorenzoApiClient;
}

function item(overrides: Partial<ItemInstanceOut> = {}): ItemInstanceOut {
  return {
    entity_id: "item-1",
    title: "Torch",
    quantity: null,
    owner_entity_id: null,
    ...overrides,
  } as ItemInstanceOut;
}

describe("transferItem", () => {
  let client: LorenzoApiClient;

  beforeEach(() => {
    client = fakeClient();
  });

  it("rejects a requested quantity against a non-stacked item without calling the API", async () => {
    const { transferItem } = await import("../src/commands/item-transfer.js");

    const result = await transferItem(
      client,
      "tenant-1",
      item({ quantity: null }),
      "etag-1",
      1,
      "char-2",
      "token-123",
    );

    expect(result).toEqual({ kind: "not-a-stack" });
    expect(client.splitItemInstance).not.toHaveBeenCalled();
    expect(client.setItemInstanceOwner).not.toHaveBeenCalled();
  });

  it("transfers the whole instance outright when no quantity is given", async () => {
    const { transferItem } = await import("../src/commands/item-transfer.js");
    vi.mocked(client.setItemInstanceOwner).mockResolvedValue(
      item({ owner_entity_id: "char-2" }) as never,
    );

    const result = await transferItem(
      client,
      "tenant-1",
      item({ quantity: 5 }),
      "etag-1",
      null,
      "char-2",
      "token-123",
    );

    expect(client.splitItemInstance).not.toHaveBeenCalled();
    expect(client.setItemInstanceOwner).toHaveBeenCalledWith(
      "tenant-1",
      "item-1",
      "char-2",
      "token-123",
      "etag-1",
    );
    expect(result).toMatchObject({ kind: "transferred", splitting: false });
  });

  it("transfers the whole instance outright when the requested quantity covers all of it", async () => {
    const { transferItem } = await import("../src/commands/item-transfer.js");
    vi.mocked(client.setItemInstanceOwner).mockResolvedValue(item() as never);

    const result = await transferItem(
      client,
      "tenant-1",
      item({ quantity: 5 }),
      "etag-1",
      5,
      "char-2",
      "token-123",
    );

    expect(client.splitItemInstance).not.toHaveBeenCalled();
    expect(result).toMatchObject({ kind: "transferred", splitting: false });
  });

  it("silently caps an over-large requested quantity to a whole transfer", async () => {
    const { transferItem } = await import("../src/commands/item-transfer.js");
    vi.mocked(client.setItemInstanceOwner).mockResolvedValue(item() as never);

    const result = await transferItem(
      client,
      "tenant-1",
      item({ quantity: 5 }),
      "etag-1",
      99,
      "char-2",
      "token-123",
    );

    expect(client.splitItemInstance).not.toHaveBeenCalled();
    expect(result).toMatchObject({ kind: "transferred", splitting: false });
  });

  it("splits with the owner in one call for a partial request (ADR 0044 split-with-owner)", async () => {
    const { transferItem } = await import("../src/commands/item-transfer.js");
    vi.mocked(client.splitItemInstance).mockResolvedValue({
      data: item({ entity_id: "item-2", quantity: 2, owner_entity_id: "char-2" }),
      etag: "etag-2",
    } as never);

    const result = await transferItem(
      client,
      "tenant-1",
      item({ quantity: 5 }),
      "etag-1",
      2,
      "char-2",
      "token-123",
    );

    expect(client.splitItemInstance).toHaveBeenCalledWith(
      "tenant-1",
      "item-1",
      2,
      "token-123",
      "etag-1",
      "char-2",
    );
    expect(client.setItemInstanceOwner).not.toHaveBeenCalled();
    expect(result).toMatchObject({ kind: "transferred", splitting: true, requestedQuantity: 2 });
  });

  it("sends undefined If-Match when the given etag is null", async () => {
    const { transferItem } = await import("../src/commands/item-transfer.js");
    vi.mocked(client.setItemInstanceOwner).mockResolvedValue(item() as never);

    await transferItem(
      client,
      "tenant-1",
      item({ quantity: 5 }),
      null,
      null,
      "char-2",
      "token-123",
    );

    expect(client.setItemInstanceOwner).toHaveBeenCalledWith(
      "tenant-1",
      "item-1",
      "char-2",
      "token-123",
      undefined,
    );
  });
});
