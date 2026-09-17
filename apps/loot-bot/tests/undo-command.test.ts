import { beforeEach, describe, expect, it, vi } from "vitest";
import type { ChatInputCommandInteraction } from "../src/commands/types.js";
import type { Config } from "../src/config.js";

const { getValidAccessToken } = vi.hoisted(() => ({ getValidAccessToken: vi.fn() }));
vi.mock("../src/token-provider.js", () => ({ getValidAccessToken }));

const { applyPendingUndo } = vi.hoisted(() => ({ applyPendingUndo: vi.fn() }));
vi.mock("../src/undo-actions.js", () => ({ applyPendingUndo }));

const { createLorenzoApiClient } = vi.hoisted(() => ({ createLorenzoApiClient: vi.fn() }));
vi.mock("../src/lorenzo-client.js", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../src/lorenzo-client.js")>();
  return { ...actual, createLorenzoApiClient: createLorenzoApiClient.mockReturnValue({}) };
});

const { undoCommand } = await import("../src/commands/undo.js");

const config = {
  lorenzoApiBaseUrl: "http://lorenzo-api.test",
  lorenzoTenantId: "tenant-1",
} as Config;

function fakeInteraction() {
  return {
    user: { id: "discord-user-1" },
    deferReply: vi.fn(async () => undefined),
    editReply: vi.fn(async () => undefined),
  } as unknown as ChatInputCommandInteraction & {
    deferReply: ReturnType<typeof vi.fn>;
    editReply: ReturnType<typeof vi.fn>;
  };
}

describe("undoCommand.execute", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("prompts to /link when there's no valid access token", async () => {
    getValidAccessToken.mockResolvedValue(null);
    const interaction = fakeInteraction();

    await undoCommand.execute(interaction, { config, logger: {} as never });

    expect(interaction.editReply).toHaveBeenCalledWith(
      expect.stringContaining("run `/link` first"),
    );
    expect(applyPendingUndo).not.toHaveBeenCalled();
  });

  it("tells the caller there's nothing to undo", async () => {
    getValidAccessToken.mockResolvedValue("token-123");
    applyPendingUndo.mockResolvedValue({ kind: "none" });
    const interaction = fakeInteraction();

    await undoCommand.execute(interaction, { config, logger: {} as never });

    expect(applyPendingUndo).toHaveBeenCalledWith({}, "tenant-1", "discord-user-1", "token-123");
    expect(interaction.editReply).toHaveBeenCalledWith("Nothing to undo.");
  });

  it("tells the caller the action is too old", async () => {
    getValidAccessToken.mockResolvedValue("token-123");
    applyPendingUndo.mockResolvedValue({ kind: "expired" });
    const interaction = fakeInteraction();

    await undoCommand.execute(interaction, { config, logger: {} as never });

    expect(interaction.editReply).toHaveBeenCalledWith("That action is too old to undo now.");
  });

  it("shows the outcome's own description when the undo succeeds", async () => {
    getValidAccessToken.mockResolvedValue("token-123");
    applyPendingUndo.mockResolvedValue({ kind: "undone", description: "Gave Torch back." });
    const interaction = fakeInteraction();

    await undoCommand.execute(interaction, { config, logger: {} as never });

    expect(interaction.editReply).toHaveBeenCalledWith("Gave Torch back.");
  });
});
