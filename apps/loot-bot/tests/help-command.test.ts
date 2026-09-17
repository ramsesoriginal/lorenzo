import { SlashCommandBuilder } from "discord.js";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type {
  AutocompleteInteraction,
  ChatInputCommandInteraction,
  Command,
} from "../src/commands/types.js";
import type { Config } from "../src/config.js";

const { helpCommand } = await import("../src/commands/help.js");

const config = {} as Config;

function fakeCommand(name: string, description: string, hasOptions = false): Command {
  const builder = new SlashCommandBuilder().setName(name).setDescription(description);
  if (hasOptions) {
    builder.addStringOption((opt) =>
      opt.setName("thing").setDescription("A thing").setRequired(true),
    );
  }
  return { definition: builder, execute: vi.fn() };
}

const fakeCommands: readonly Command[] = [
  fakeCommand("give", "Give an item to another character.", true),
  fakeCommand("ping", "Check that the bot is alive."),
  fakeCommand("help", "List every command."),
];

function fakeInteraction(commandValue: string | null = null) {
  return {
    options: { getString: vi.fn(() => commandValue) },
    reply: vi.fn(async () => undefined),
  } as unknown as ChatInputCommandInteraction & {
    options: { getString: ReturnType<typeof vi.fn> };
    reply: ReturnType<typeof vi.fn>;
  };
}

function fakeAutocomplete(value = "") {
  return {
    options: { getFocused: vi.fn(() => ({ name: "command", value })) },
    respond: vi.fn(async () => undefined),
  } as unknown as AutocompleteInteraction & { respond: ReturnType<typeof vi.fn> };
}

describe("helpCommand.execute", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("lists every command, grouped, when no command is given", async () => {
    const interaction = fakeInteraction();

    await helpCommand.execute(interaction, { config, logger: {} as never, commands: fakeCommands });

    const call = interaction.reply.mock.calls[0]?.[0];
    expect(call.ephemeral).toBe(true);
    const embed = call.embeds[0].data;
    const utilityField = embed.fields.find((f: { name: string }) => f.name === "Utility");
    expect(utilityField.value).toContain("`/ping` — Check that the bot is alive.");
    expect(utilityField.value).toContain("`/help` — List every command.");
  });

  it("puts an uncategorized command under 'Other' instead of dropping it", async () => {
    const interaction = fakeInteraction();
    const withMystery = [...fakeCommands, fakeCommand("mystery", "A brand-new command.")];

    await helpCommand.execute(interaction, { config, logger: {} as never, commands: withMystery });

    const call = interaction.reply.mock.calls[0]?.[0];
    const embed = call.embeds[0].data;
    const otherField = embed.fields.find((f: { name: string }) => f.name === "Other");
    expect(otherField.value).toContain("`/mystery` — A brand-new command.");
  });

  it("shows one command's full options when given a name", async () => {
    const interaction = fakeInteraction("give");

    await helpCommand.execute(interaction, { config, logger: {} as never, commands: fakeCommands });

    const call = interaction.reply.mock.calls[0]?.[0];
    const embed = call.embeds[0].data;
    expect(embed.title).toBe("/give");
    expect(embed.description).toBe("Give an item to another character.");
    expect(embed.fields[0].value).toContain("**thing** (required) — A thing");
  });

  it("tells the caller when the given command name doesn't exist", async () => {
    const interaction = fakeInteraction("not-a-real-command");

    await helpCommand.execute(interaction, { config, logger: {} as never, commands: fakeCommands });

    expect(interaction.reply).toHaveBeenCalledWith(
      expect.objectContaining({ content: expect.stringContaining("Unknown command") }),
    );
  });

  it("degrades gracefully when the command list wasn't injected", async () => {
    const interaction = fakeInteraction();

    await helpCommand.execute(interaction, { config, logger: {} as never });

    expect(interaction.reply).toHaveBeenCalledWith(
      expect.objectContaining({ content: expect.stringContaining("unavailable") }),
    );
  });
});

describe("helpCommand.autocomplete", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("suggests every command name", async () => {
    const interaction = fakeAutocomplete("gi");

    await helpCommand.autocomplete?.(interaction, {
      config,
      logger: {} as never,
      commands: fakeCommands,
    });

    expect(interaction.respond).toHaveBeenCalledWith([{ name: "/give", value: "give" }]);
  });
});
