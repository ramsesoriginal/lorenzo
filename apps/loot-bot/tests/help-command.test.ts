import { SlashCommandBuilder } from "discord.js";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type {
  AutocompleteInteraction,
  ChatInputCommandInteraction,
  Command,
} from "../src/commands/types.js";
import type { Config } from "../src/config.js";

const { helpCommand, HELP_GROUPS } = await import("../src/commands/help.js");
const { commandDefinitions } = await import("../src/commands/index.js");

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
    const housekeeping = embed.fields.find((f: { name: string }) => f.name === "Housekeeping");
    expect(housekeeping.value).toContain("`/ping` — Check that the bot is alive.");
    expect(housekeeping.value).toContain("`/help` — List every command.");
  });

  it("opens with a first-run intro that says where to start", async () => {
    const interaction = fakeInteraction();

    await helpCommand.execute(interaction, { config, logger: {} as never, commands: fakeCommands });

    const embed = interaction.reply.mock.calls[0]?.[0].embeds[0].data;
    expect(embed.description).toContain("`/link`");
    expect(embed.description).toContain("`/inventory`");
  });

  it("puts each group's audience note above its commands", async () => {
    const interaction = fakeInteraction();
    const withGmTool = [...fakeCommands, fakeCommand("award", "Award a new item to a character.")];

    await helpCommand.execute(interaction, {
      config,
      logger: {} as never,
      commands: withGmTool,
    });

    const embed = interaction.reply.mock.calls[0]?.[0].embeds[0].data;
    const gm = embed.fields.find((f: { name: string }) => f.name === "GM tools");
    expect(gm.value.startsWith("*For a campaign's GM")).toBe(true);
    expect(gm.value).toContain("`/award` — Award a new item to a character.");
  });

  it("omits a group none of whose commands are registered", async () => {
    const interaction = fakeInteraction();

    await helpCommand.execute(interaction, { config, logger: {} as never, commands: fakeCommands });

    const embed = interaction.reply.mock.calls[0]?.[0].embeds[0].data;
    const titles = embed.fields.map((f: { name: string }) => f.name);
    expect(titles).not.toContain("GM tools");
    expect(titles).not.toContain("Loot drops");
  });

  it("lists the groups in the order a newcomer needs them", async () => {
    const interaction = fakeInteraction();
    const all = HELP_GROUPS.flatMap((g) => g.commandNames).map((n) => fakeCommand(n, "x"));

    await helpCommand.execute(interaction, { config, logger: {} as never, commands: all });

    const embed = interaction.reply.mock.calls[0]?.[0].embeds[0].data;
    expect(embed.fields.map((f: { name: string }) => f.name)).toEqual([
      "Getting started",
      "See what you have",
      "Give, move, and tidy",
      "Notes and groups",
      "Loot drops",
      "GM tools",
      "Housekeeping",
    ]);
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

  it("says which group a command belongs to, so its neighbours are findable", async () => {
    const interaction = fakeInteraction("give");

    await helpCommand.execute(interaction, { config, logger: {} as never, commands: fakeCommands });

    const embed = interaction.reply.mock.calls[0]?.[0].embeds[0].data;
    expect(embed.footer.text).toBe("Part of: Give, move, and tidy — run /help for the rest.");
  });

  it("has no group footer for a command that isn't in any group", async () => {
    const interaction = fakeInteraction("mystery");
    const withMystery = [...fakeCommands, fakeCommand("mystery", "A brand-new command.")];

    await helpCommand.execute(interaction, { config, logger: {} as never, commands: withMystery });

    const embed = interaction.reply.mock.calls[0]?.[0].embeds[0].data;
    expect(embed.footer).toBeUndefined();
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

// Checked against the real registered commands, not fixtures: the `Other`
// fallback keeps a forgotten command visible, but a test is what keeps it
// from shipping under "Other" in the first place - and catches a typo'd
// name in HELP_GROUPS that would otherwise quietly show nothing.
describe("HELP_GROUPS against the real command list", () => {
  const registered = commandDefinitions.map((d) => d.name);
  const grouped = HELP_GROUPS.flatMap((g) => g.commandNames);

  it("gives every registered command a group", () => {
    expect(registered.filter((name) => !grouped.includes(name))).toEqual([]);
  });

  it("names only commands that are actually registered", () => {
    expect(grouped.filter((name) => !registered.includes(name))).toEqual([]);
  });

  it("lists each command exactly once", () => {
    expect(grouped.filter((name, i) => grouped.indexOf(name) !== i)).toEqual([]);
  });

  it("renders the full overview within Discord's embed limits, with no 'Other' bucket", async () => {
    const interaction = fakeInteraction();
    const real = commandDefinitions.map((d) => fakeCommand(d.name, d.description));

    await helpCommand.execute(interaction, { config, logger: {} as never, commands: real });

    const embed = interaction.reply.mock.calls[0]?.[0].embeds[0].data;
    const fields = embed.fields as { name: string; value: string }[];
    expect(fields.map((f) => f.name)).not.toContain("Other");
    expect(fields.length).toBeLessThanOrEqual(25);
    for (const field of fields) expect(field.value.length).toBeLessThanOrEqual(1024);
    const total =
      (embed.title?.length ?? 0) +
      (embed.description?.length ?? 0) +
      (embed.footer?.text.length ?? 0) +
      fields.reduce((sum, f) => sum + f.name.length + f.value.length, 0);
    expect(total).toBeLessThanOrEqual(6000);
  });

  it("keeps every command's own description within Discord's 100-character limit", () => {
    for (const definition of commandDefinitions) {
      expect(definition.description.length, definition.name).toBeLessThanOrEqual(100);
    }
  });
});
