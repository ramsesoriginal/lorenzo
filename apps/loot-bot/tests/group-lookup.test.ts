import { describe, expect, it, vi } from "vitest";
import { resolveOrCreateGroup } from "../src/commands/group-lookup.js";

function fakeClient() {
  return {
    listGroups: vi.fn(),
    createGroup: vi.fn(),
    // biome-ignore lint/suspicious/noExplicitAny: minimal fake, not the real client type
  } as any;
}

describe("resolveOrCreateGroup", () => {
  it("returns the existing group on an exact name match, without creating anything", async () => {
    const client = fakeClient();
    client.listGroups.mockResolvedValue([
      { entityId: "group-1", name: "The Fellowship" },
      { entityId: "group-2", name: "Villains" },
    ]);

    const result = await resolveOrCreateGroup(client, "tenant-1", "The Fellowship", "token-123", [
      "char-1",
    ]);

    expect(result).toEqual({
      group: { entityId: "group-1", name: "The Fellowship" },
      created: false,
    });
    expect(client.createGroup).not.toHaveBeenCalled();
  });

  it("creates a new group with the initial members when no name matches", async () => {
    const client = fakeClient();
    client.listGroups.mockResolvedValue([{ entityId: "group-2", name: "Villains" }]);
    client.createGroup.mockResolvedValue({ entityId: "group-3", name: "The Fellowship" });

    const result = await resolveOrCreateGroup(client, "tenant-1", "The Fellowship", "token-123", [
      "char-1",
      "char-2",
    ]);

    expect(client.createGroup).toHaveBeenCalledWith(
      "tenant-1",
      "The Fellowship",
      ["char-1", "char-2"],
      "token-123",
    );
    expect(result).toEqual({
      group: { entityId: "group-3", name: "The Fellowship" },
      created: true,
    });
  });
});
