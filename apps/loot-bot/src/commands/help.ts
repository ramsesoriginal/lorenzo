import { EmbedBuilder, SlashCommandBuilder } from "discord.js";
import { filterChoices } from "./autocomplete.js";
import type { Command } from "./types.js";

/**
 * `/help` - lists every command, grouped by what it's for, or (with the
 * optional `command` option) one command's full option list (ADR 0068).
 * No API call, no `/link` gate - this is pure local documentation, same
 * "works for anyone, no dependency" precedent `/ping` already sets.
 *
 * Reads `ctx.commands` (populated by `commands/index.ts`'s own
 * `dispatchInteraction`) rather than a second, hand-maintained
 * name/description list - the source of truth is each command's own
 * `SlashCommandBuilder`, the same one `register-commands.ts` sends to
 * Discord, so this can't drift from what's actually registered.
 *
 * Category membership *is* hand-maintained (`CATEGORIES` below, by command
 * name) since nothing about a `Command` object says what it's "for" - a
 * new command needs a line here to show up somewhere other than "General"
 * (still shown, not dropped, so a missed entry is a cosmetic gap, not a
 * silent omission).
 */

const CATEGORIES: readonly Readonly<{ title: string; commandNames: readonly string[] }>[] = [
  {
    title: "Account",
    commandNames: ["link", "unlink", "set-current", "whoami", "introduce"],
  },
  {
    title: "Inventory",
    commandNames: [
      "inventory",
      "item",
      "move",
      "move-bulk",
      "container-new",
      "merge",
      "rename",
      "give",
      "give-bulk",
      "note",
      "changes",
      "undo",
    ],
  },
  {
    title: "Groups",
    commandNames: ["my-groups", "add-to-group", "add-channel-to-group"],
  },
  {
    title: "GM tools",
    commandNames: ["award", "inspect", "confiscate", "reassign"],
  },
  {
    title: "Loot drops",
    commandNames: ["drop", "pending-claims"],
  },
  {
    title: "Utility",
    commandNames: ["ping", "help"],
  },
];

/** A plain option, as `SlashCommandBuilder.toJSON()` actually returns them
 * for this bot - only ever a leaf string/integer/user option (ADR 0053's
 * own note: this bot never uses subcommands), so `required`/`description`
 * are always present without needing to narrow a wider option-type union. */
type SimpleOption = Readonly<{ name: string; description: string; required?: boolean }>;

function buildOverviewEmbed(commands: readonly Command[]): EmbedBuilder {
  const byName = new Map(commands.map((c) => [c.definition.name, c]));
  const categorized = new Set(CATEGORIES.flatMap((category) => category.commandNames));

  const embed = new EmbedBuilder()
    .setTitle("Lorenzo bot — commands")
    .setFooter({ text: "Run /help command:<name> for that command's full options." });

  for (const category of CATEGORIES) {
    const lines = category.commandNames
      .map((name) => byName.get(name))
      .filter((c): c is Command => c !== undefined)
      .map((c) => `\`/${c.definition.name}\` — ${c.definition.description}`);
    if (lines.length > 0) {
      embed.addFields({ name: category.title, value: lines.join("\n") });
    }
  }

  // Anything not yet sorted into a category above still shows up, rather
  // than silently vanishing from /help the moment someone adds a command
  // and forgets to update CATEGORIES.
  const uncategorized = commands.filter((c) => !categorized.has(c.definition.name));
  if (uncategorized.length > 0) {
    embed.addFields({
      name: "Other",
      value: uncategorized
        .map((c) => `\`/${c.definition.name}\` — ${c.definition.description}`)
        .join("\n"),
    });
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

  return embed;
}

export const helpCommand: Command = {
  definition: new SlashCommandBuilder()
    .setName("help")
    .setDescription("List every command, or show one command's full options.")
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
