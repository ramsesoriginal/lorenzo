import type { ChatInputCommandInteraction } from "discord.js";
import { beforeEach, describe, expect, it, vi } from "vitest";

const { getLinkedAccount, deleteLinkedAccount } = vi.hoisted(() => ({
  getLinkedAccount: vi.fn(),
  deleteLinkedAccount: vi.fn(),
}));
vi.mock("../src/db.js", () => ({ getLinkedAccount, deleteLinkedAccount }));

const { unlinkCommand } = await import("../src/commands/unlink.js");

function fakeInteraction() {
  return {
    user: { id: "user-1" },
    deferReply: vi.fn(async () => undefined),
    editReply: vi.fn(async () => undefined),
  } as unknown as ChatInputCommandInteraction & {
    deferReply: ReturnType<typeof vi.fn>;
    editReply: ReturnType<typeof vi.fn>;
  };
}

describe("unlinkCommand.execute", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("tells the caller they weren't linked, without deleting anything", async () => {
    getLinkedAccount.mockResolvedValue(undefined);
    const interaction = fakeInteraction();

    await unlinkCommand.execute(interaction, { config: {} as never, logger: {} as never });

    expect(deleteLinkedAccount).not.toHaveBeenCalled();
    expect(interaction.editReply).toHaveBeenCalledWith("You don't have a linked account.");
  });

  it("deletes the linked account and confirms", async () => {
    getLinkedAccount.mockResolvedValue({ discordUserId: "user-1" });
    const interaction = fakeInteraction();

    await unlinkCommand.execute(interaction, { config: {} as never, logger: {} as never });

    expect(deleteLinkedAccount).toHaveBeenCalledWith("user-1");
    expect(interaction.editReply).toHaveBeenCalledWith(
      expect.stringContaining("Unlinked your account"),
    );
  });
});
