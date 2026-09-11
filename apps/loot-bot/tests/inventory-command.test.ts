import type { ChatInputCommandInteraction } from "discord.js";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { Config } from "../src/config.js";
import { LorenzoApiError } from "../src/lorenzo-client.js";

const { getValidAccessToken } = vi.hoisted(() => ({ getValidAccessToken: vi.fn() }));
vi.mock("../src/token-provider.js", () => ({ getValidAccessToken }));

const { getControlledCharacters, getItemInstancesOwnedBy, createLorenzoApiClient } = vi.hoisted(
  () => ({
    getControlledCharacters: vi.fn(),
    getItemInstancesOwnedBy: vi.fn(),
    createLorenzoApiClient: vi.fn(),
  }),
);
vi.mock("../src/lorenzo-client.js", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../src/lorenzo-client.js")>();
  return {
    ...actual,
    createLorenzoApiClient: createLorenzoApiClient.mockReturnValue({
      getControlledCharacters,
      getItemInstancesOwnedBy,
    }),
  };
});

const { inventoryCommand } = await import("../src/commands/inventory.js");

const config = {
  lorenzoApiBaseUrl: "http://lorenzo-api.test",
  lorenzoTenantId: "tenant-1",
} as Config;

function fakeInteraction(userId = "discord-user-1") {
  return {
    user: { id: userId },
    deferReply: vi.fn(async () => undefined),
    editReply: vi.fn(async () => undefined),
  } as unknown as ChatInputCommandInteraction & {
    deferReply: ReturnType<typeof vi.fn>;
    editReply: ReturnType<typeof vi.fn>;
  };
}

describe("inventoryCommand", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("prompts to /link when there's no valid access token", async () => {
    getValidAccessToken.mockResolvedValue(null);
    const interaction = fakeInteraction();

    await inventoryCommand.execute(interaction, { config, logger: {} as never });

    expect(interaction.editReply).toHaveBeenCalledWith(
      expect.stringContaining("run `/link` first"),
    );
    expect(getControlledCharacters).not.toHaveBeenCalled();
  });

  it("tells the player they control no characters yet", async () => {
    getValidAccessToken.mockResolvedValue("token-123");
    getControlledCharacters.mockResolvedValue([]);
    const interaction = fakeInteraction();

    await inventoryCommand.execute(interaction, { config, logger: {} as never });

    expect(interaction.editReply).toHaveBeenCalledWith(
      expect.stringContaining("don't control any characters"),
    );
    expect(getItemInstancesOwnedBy).not.toHaveBeenCalled();
  });

  it("replies with one embed per controlled character", async () => {
    getValidAccessToken.mockResolvedValue("token-123");
    getControlledCharacters.mockResolvedValue([
      { entityId: "char-1", name: "Frodo" },
      { entityId: "char-2", name: "Sam" },
    ]);
    getItemInstancesOwnedBy.mockImplementation(async (_tenantId: string, characterId: string) => ({
      groups: [{ container: null, item_instances: [] }],
      characterId,
    }));

    const interaction = fakeInteraction();
    await inventoryCommand.execute(interaction, { config, logger: {} as never });

    expect(getItemInstancesOwnedBy).toHaveBeenCalledTimes(2);
    expect(getItemInstancesOwnedBy).toHaveBeenCalledWith("tenant-1", "char-1", "token-123");
    const call = interaction.editReply.mock.calls[0]?.[0];
    expect(call.embeds).toHaveLength(2);
    expect(call.embeds[0].data.title).toBe("Frodo");
    expect(call.embeds[1].data.title).toBe("Sam");
  });

  it("caps at 10 embeds and says so, rather than silently dropping the rest", async () => {
    getValidAccessToken.mockResolvedValue("token-123");
    getControlledCharacters.mockResolvedValue(
      Array.from({ length: 12 }, (_, i) => ({ entityId: `char-${i}`, name: `Character ${i}` })),
    );
    getItemInstancesOwnedBy.mockResolvedValue({ groups: [] });

    const interaction = fakeInteraction();
    await inventoryCommand.execute(interaction, { config, logger: {} as never });

    const call = interaction.editReply.mock.calls[0]?.[0];
    expect(call.embeds).toHaveLength(10);
    expect(call.content).toContain("Showing 10 of 12 characters");
  });

  it("gives a specific message when the backend contract 404s (not yet shipped)", async () => {
    getValidAccessToken.mockResolvedValue("token-123");
    getControlledCharacters.mockRejectedValue(new LorenzoApiError("nope", 404, "not-found"));

    const interaction = fakeInteraction();
    await inventoryCommand.execute(interaction, { config, logger: {} as never });

    expect(interaction.editReply).toHaveBeenCalledWith(expect.stringContaining("isn't available"));
  });

  it("lets a non-404 error propagate to the command dispatcher's own handler", async () => {
    getValidAccessToken.mockResolvedValue("token-123");
    getControlledCharacters.mockRejectedValue(new LorenzoApiError("server exploded", 500));

    const interaction = fakeInteraction();
    await expect(
      inventoryCommand.execute(interaction, { config, logger: {} as never }),
    ).rejects.toThrow("server exploded");
  });
});
