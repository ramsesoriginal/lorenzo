import { type Client, Events, type Interaction } from "discord.js";
import { linkCommand } from "./link.js";
import { pingCommand } from "./ping.js";
import type { Command, CommandContext } from "./types.js";

export type { Command, CommandContext } from "./types.js";

// New commands (e.g. `link`, `inventory`) are added to this list only -
// registration (scripts/register-commands.ts) and dispatch (below) both
// derive from it, so there's exactly one place a new command gets wired in.
const commands: readonly Command[] = [pingCommand, linkCommand];

export const commandDefinitions = commands.map((c) => c.definition.toJSON());

const commandsByName = new Map(commands.map((c) => [c.definition.name, c]));

/**
 * Wires interactionCreate dispatch onto an already-constructed discord.js
 * Client. Enforces the one-bot-one-guild invariant defensively (ADR 0029) -
 * command registration already scopes commands to DISCORD_GUILD_ID, but a
 * stray interaction from elsewhere is ignored rather than trusted.
 */
export function attachCommandHandlers(client: Client, ctx: CommandContext): void {
  client.on(Events.InteractionCreate, (interaction: Interaction) => {
    void handleInteraction(interaction, ctx);
  });
}

async function handleInteraction(interaction: Interaction, ctx: CommandContext): Promise<void> {
  if (!interaction.isChatInputCommand()) return;

  if (interaction.guildId !== ctx.config.discordGuildId) {
    ctx.logger.warn(
      { guildId: interaction.guildId },
      "ignoring interaction from an unconfigured guild",
    );
    return;
  }

  const command = commandsByName.get(interaction.commandName);
  if (!command) {
    ctx.logger.warn({ commandName: interaction.commandName }, "unknown command");
    return;
  }

  try {
    await command.execute(interaction, ctx);
  } catch (error) {
    ctx.logger.error({ err: error, commandName: interaction.commandName }, "command failed");
    const payload = { content: "Something went wrong running that command.", ephemeral: true };
    if (interaction.deferred || interaction.replied) {
      await interaction.followUp(payload);
    } else {
      await interaction.reply(payload);
    }
  }
}
