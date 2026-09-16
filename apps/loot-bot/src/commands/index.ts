import { type Client, Events, type Interaction } from "discord.js";
import { awardCommand } from "./award.js";
import { dropCommand } from "./drop.js";
import { giveCommand } from "./give.js";
import { inventoryCommand } from "./inventory.js";
import { itemCommand } from "./item.js";
import { linkCommand } from "./link.js";
import { pingCommand } from "./ping.js";
import { setCurrentCommand } from "./set-current.js";
import type { Command, CommandContext } from "./types.js";

export type { Command, CommandContext } from "./types.js";

// New commands (e.g. `link`, `inventory`) are added to this list only -
// registration (scripts/register-commands.ts) and dispatch (below) both
// derive from it, so there's exactly one place a new command gets wired in.
const commands: readonly Command[] = [
  pingCommand,
  linkCommand,
  inventoryCommand,
  giveCommand,
  setCurrentCommand,
  dropCommand,
  awardCommand,
  itemCommand,
];

export const commandDefinitions = commands.map((c) => c.definition.toJSON());

const commandsByName = new Map(commands.map((c) => [c.definition.name, c]));

/**
 * Wires interactionCreate dispatch onto an already-constructed discord.js
 * Client. Enforces the one-bot-one-guild invariant defensively (ADR 0042) -
 * command registration already scopes commands to DISCORD_GUILD_ID, but a
 * stray interaction from elsewhere is ignored rather than trusted.
 */
export function attachCommandHandlers(client: Client, ctx: CommandContext): void {
  client.on(Events.InteractionCreate, (interaction: Interaction) => {
    void handleInteraction(interaction, ctx);
  });
}

const isComponentOrModal = (
  interaction: Interaction,
): interaction is Interaction & { customId: string } =>
  interaction.isStringSelectMenu() || interaction.isButton() || interaction.isModalSubmit();

async function handleInteraction(interaction: Interaction, ctx: CommandContext): Promise<void> {
  if (
    !interaction.isChatInputCommand() &&
    !interaction.isAutocomplete() &&
    !isComponentOrModal(interaction)
  ) {
    return;
  }

  if (interaction.guildId !== ctx.config.discordGuildId) {
    ctx.logger.warn(
      { guildId: interaction.guildId },
      "ignoring interaction from an unconfigured guild",
    );
    return;
  }

  // Chat-input/autocomplete are keyed by commandName; components/modals by
  // their own customId's namespace prefix (ADR 0044 - "<command name>:
  // <action>:<...ids>"), both resolving into the same commandsByName map.
  const commandName = isComponentOrModal(interaction)
    ? (interaction.customId.split(":")[0] ?? "")
    : interaction.commandName;
  const command = commandsByName.get(commandName);
  if (!command) {
    ctx.logger.warn({ commandName }, "unknown command");
    return;
  }

  if (interaction.isAutocomplete()) {
    try {
      await command.autocomplete?.(interaction, ctx);
    } catch (error) {
      // Autocomplete has no error-reply channel of its own (ADR 0043's own
      // note on types.ts's Command.autocomplete) - an empty choice list is
      // the only graceful failure mode; the real error still surfaces when
      // the user actually submits the command.
      ctx.logger.error(
        { err: error, commandName: interaction.commandName },
        "autocomplete handler failed",
      );
      if (!interaction.responded) await interaction.respond([]);
    }
    return;
  }

  try {
    if (interaction.isStringSelectMenu()) {
      await command.onSelectMenu?.(interaction, ctx);
    } else if (interaction.isButton()) {
      await command.onButton?.(interaction, ctx);
    } else if (interaction.isModalSubmit()) {
      await command.onModalSubmit?.(interaction, ctx);
    } else if (interaction.isChatInputCommand()) {
      await command.execute(interaction, ctx);
    }
  } catch (error) {
    ctx.logger.error({ err: error, commandName }, "command failed");
    const payload = { content: "Something went wrong running that command.", ephemeral: true };
    if (interaction.deferred || interaction.replied) {
      await interaction.followUp(payload);
    } else {
      await interaction.reply(payload);
    }
  }
}
