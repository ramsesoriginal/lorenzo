import { beforeEach, describe, expect, it, vi } from "vitest";
import { dispatchInteraction } from "../src/commands/index.js";
import type { ChatInputCommandInteraction, CommandContext } from "../src/commands/types.js";
import type { Config } from "../src/config.js";

const { showUndeliveredNotice } = vi.hoisted(() => ({ showUndeliveredNotice: vi.fn() }));
vi.mock("../src/undelivered-notice.js", () => ({ showUndeliveredNotice }));

function fakeHelpInteraction() {
  return {
    isChatInputCommand: () => true,
    isAutocomplete: () => false,
    isStringSelectMenu: () => false,
    isButton: () => false,
    isModalSubmit: () => false,
    user: { id: "user-1" },
    guildId: "guild-1",
    channelId: "channel-1",
    commandName: "help",
    options: { getString: () => null, getInteger: () => null, getFocused: () => "" },
    deferred: false,
    replied: false,
    deferReply: vi.fn(async () => undefined),
    editReply: vi.fn(async () => undefined),
    reply: vi.fn(async () => undefined),
    followUp: vi.fn(async () => ({ id: "message-1" })),
  } as unknown as ChatInputCommandInteraction;
}

describe("dispatchInteraction", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("injects the full command list into ctx before running a command", async () => {
    // /help is the one real command that surfaces ctx.commands in its own
    // reply, which makes it a convenient end-to-end proof that
    // dispatchInteraction actually wires the list in - not just that
    // *some* command received *a* list.
    const interaction = fakeHelpInteraction();
    const ctx: CommandContext = {
      config: {} as Config,
      logger: { warn: vi.fn(), error: vi.fn() } as never,
    };

    await dispatchInteraction(interaction, ctx);

    const call = (interaction.reply as ReturnType<typeof vi.fn>).mock.calls[0]?.[0];
    const embed = call.embeds[0].data;
    const utilityField = embed.fields.find((f: { name: string }) => f.name === "Utility");
    expect(utilityField.value).toContain("`/ping`");
    expect(utilityField.value).toContain("`/help`");
  });

  describe("the 'couldn't DM you' banner (ADR 0095)", () => {
    const ctx: CommandContext = {
      config: {} as Config,
      logger: { warn: vi.fn(), error: vi.fn() } as never,
    };

    it("shows it after a slash command has answered", async () => {
      const interaction = fakeHelpInteraction();

      await dispatchInteraction(interaction, ctx);

      expect(showUndeliveredNotice).toHaveBeenCalledWith(interaction, ctx.logger);
      // ...after the command's own reply, never before it.
      expect(
        (interaction.reply as ReturnType<typeof vi.fn>).mock.invocationCallOrder[0],
      ).toBeLessThan(showUndeliveredNotice.mock.invocationCallOrder[0] as number);
    });

    it("shows it even when the command itself failed - the user still gets to learn what they missed", async () => {
      const interaction = fakeHelpInteraction();
      (interaction.reply as ReturnType<typeof vi.fn>).mockRejectedValueOnce(new Error("boom"));

      await dispatchInteraction(interaction, ctx);

      expect(showUndeliveredNotice).toHaveBeenCalledTimes(1);
    });

    it("does not show it after autocomplete, a button click, or a menu pick", async () => {
      const base = fakeHelpInteraction() as unknown as Record<string, unknown>;
      const autocomplete = {
        ...base,
        isChatInputCommand: () => false,
        isAutocomplete: () => true,
        responded: false,
        respond: vi.fn(async () => undefined),
      };
      const button = {
        ...base,
        isChatInputCommand: () => false,
        isButton: () => true,
        customId: "help:x",
      };
      const menu = {
        ...base,
        isChatInputCommand: () => false,
        isStringSelectMenu: () => true,
        customId: "help:x",
        values: [],
      };

      for (const interaction of [autocomplete, button, menu]) {
        await dispatchInteraction(interaction as never, ctx);
      }

      expect(showUndeliveredNotice).not.toHaveBeenCalled();
    });
  });
});
