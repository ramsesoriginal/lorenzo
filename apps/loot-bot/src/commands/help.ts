import { EmbedBuilder, SlashCommandBuilder } from "discord.js";
import { filterChoices } from "./autocomplete.js";
import type { Command } from "./types.js";

/**
 * `/help` - lists every command grouped by what someone is trying to *do*,
 * with a short first-run intro on top, or (with the optional `command`
 * option) one command's full option list (ADR 0068, regrouped by task in
 * ADR 0089). No API call, no `/link` gate - this is pure local
 * documentation, same "works for anyone, no dependency" precedent `/ping`
 * already sets. That's also why the intro is the same for everyone rather
 * than tailored to whether you've linked: knowing that would need a
 * database read, and `/help` is the one command that must never depend on
 * anything being up.
 *
 * Reads `ctx.commands` (populated by `commands/index.ts`'s own
 * `dispatchInteraction`) rather than a second, hand-maintained
 * name/description list - the source of truth is each command's own
 * `SlashCommandBuilder`, the same one `register-commands.ts` sends to
 * Discord, so this can't drift from what's actually registered.
 *
 * Group membership *is* hand-maintained (`HELP_GROUPS` below, by command
 * name) since nothing about a `Command` object says what it's "for" - a
 * new command needs a line here to show up somewhere other than "Other"
 * (still shown, not dropped, so a missed entry is a cosmetic gap, not a
 * silent omission - and `help-command.test.ts` checks every registered
 * command has a group, so the gap is caught before it ships).
 *
 * No command is renamed or moved: this is a discoverability fix, not a
 * restructure - 26 commands people already know by muscle memory stay put.
 */

type HelpGroup = Readonly<{
  title: string;
  /** Shown above the group's commands - who a group is for, when that
   * isn't obvious from its title. */
  note?: string;
  commandNames: readonly string[];
}>;

const INTRO =
  "Lorenzo keeps track of what your characters carry. New here? Run `/link` to connect your Lorenzo account, then `/inventory` to see what you've got. The rest are grouped by what you're trying to do.";

export const HELP_GROUPS: readonly HelpGroup[] = [
  {
    title: "Getting started",
    commandNames: ["link", "whoami", "set-current", "introduce"],
  },
  {
    title: "See what you have",
    commandNames: ["inventory", "item", "sheet", "changes", "my-groups"],
  },
  {
    title: "Give, move, and tidy",
    commandNames: [
      "give",
      "give-bulk",
      "move",
      "move-bulk",
      "container-new",
      "merge",
      "rename",
      "undo",
    ],
  },
  {
    title: "Notes and groups",
    commandNames: ["note", "add-to-group"],
  },
  {
    title: "Loot drops",
    note: "Only a GM can start a drop; anyone can check what's outstanding.",
    commandNames: ["drop", "pending-claims"],
  },
  {
    title: "GM tools",
    note: "For a campaign's GM - these won't work for other players.",
    commandNames: ["award", "inspect", "confiscate", "reassign", "add-channel-to-group"],
  },
  {
    title: "Housekeeping",
    commandNames: ["unlink", "ping", "help"],
  },
];

/** A plain option, as `SlashCommandBuilder.toJSON()` actually returns them
 * for this bot - only ever a leaf string/integer/user option (ADR 0053's
 * own note: this bot never uses subcommands), so `required`/`description`
 * are always present without needing to narrow a wider option-type union. */
type SimpleOption = Readonly<{ name: string; description: string; required?: boolean }>;

function commandLine(command: Command): string {
  return `\`/${command.definition.name}\` — ${command.definition.description}`;
}

function buildOverviewEmbed(commands: readonly Command[]): EmbedBuilder {
  const byName = new Map(commands.map((c) => [c.definition.name, c]));
  const grouped = new Set(HELP_GROUPS.flatMap((group) => group.commandNames));

  const embed = new EmbedBuilder()
    .setTitle("Lorenzo — what would you like to do?")
    .setDescription(INTRO)
    .setFooter({ text: "Run /help command:<name> for that command's full options." });

  for (const group of HELP_GROUPS) {
    const lines = group.commandNames
      .map((name) => byName.get(name))
      .filter((c): c is Command => c !== undefined)
      .map(commandLine);
    if (lines.length > 0) {
      embed.addFields({
        name: group.title,
        value: group.note ? `*${group.note}*\n${lines.join("\n")}` : lines.join("\n"),
      });
    }
  }

  // Anything not yet sorted into a group above still shows up, rather
  // than silently vanishing from /help the moment someone adds a command
  // and forgets to update HELP_GROUPS.
  const ungrouped = commands.filter((c) => !grouped.has(c.definition.name));
  if (ungrouped.length > 0) {
    embed.addFields({ name: "Other", value: ungrouped.map(commandLine).join("\n") });
  }

  return embed;
}

function buildDetailEmbed(command: Command): EmbedBuilder {
  const definition = command.definition.toJSON();
  const embed = new EmbedBuilder()
    .setTitle(`/${definition.name}`)
    .setDescription(definition.description);

  const options = (definition.options ?? []) as readonly SimpleOption[];
  if (options.length > 0) {
    embed.addFields({
      name: "Options",
      value: options
        .map(
          (opt) =>
            `**${opt.name}** (${opt.required ? "required" : "optional"}) — ${opt.description}`,
        )
        .join("\n"),
    });
  }

  // Which part of the overview this lives under, so someone who arrived
  // here by name can find its neighbours ("what else can I do with my
  // items?") without going back to the full list.
  const group = HELP_GROUPS.find((g) => g.commandNames.includes(definition.name));
  if (group) embed.setFooter({ text: `Part of: ${group.title} — run /help for the rest.` });

  return embed;
}

export const helpCommand: Command = {
  definition: new SlashCommandBuilder()
    .setName("help")
    .setDescription("New here? Start with this: every command, grouped by what you want to do.")
    .addStringOption((opt) =>
      opt
        .setName("command")
        .setDescription("Show this command's full options")
        .setRequired(false)
        .setAutocomplete(true),
    ),

  async autocomplete(interaction, ctx) {
    const focused = interaction.options.getFocused(true);
    const commands = ctx.commands ?? [];
    const choices = commands.map((c) => ({
      name: `/${c.definition.name}`,
      value: c.definition.name,
    }));
    await interaction.respond(filterChoices(choices, focused.value));
  },

  async execute(interaction, ctx) {
    const commands = ctx.commands ?? [];
    if (commands.length === 0) {
      await interaction.reply({ content: "Command list unavailable right now.", ephemeral: true });
      return;
    }

    const chosenName = interaction.options.getString("command");
    if (!chosenName) {
      await interaction.reply({ embeds: [buildOverviewEmbed(commands)], ephemeral: true });
      return;
    }

    const command = commands.find((c) => c.definition.name === chosenName);
    if (!command) {
      await interaction.reply({
        content: `Unknown command \`/${chosenName}\` — run \`/help\` with no options to see the full list.`,
        ephemeral: true,
      });
      return;
    }

    await interaction.reply({ embeds: [buildDetailEmbed(command)], ephemeral: true });
  },
};
