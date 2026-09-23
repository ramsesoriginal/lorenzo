import { describe, expect, it, vi } from "vitest";
import { dispatchInteraction } from "../src/commands/index.js";
import type { ChatInputCommandInteraction, CommandContext } from "../src/commands/types.js";
import type { Config } from "../src/config.js";

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
    const housekeeping = embed.fields.find((f: { name: string }) => f.name === "Housekeeping");
    expect(housekeeping.value).toContain("`/ping`");
    expect(housekeeping.value).toContain("`/help`");
  });
});
