import { awardCommand } from "./award.js";
import { dropCommand } from "./drop.js";
import { giveCommand } from "./give.js";
import { inventoryCommand } from "./inventory.js";
import { itemCommand } from "./item.js";
import { linkCommand } from "./link.js";
import { moveCommand } from "./move.js";
import { noteCommand } from "./note.js";
import { pingCommand } from "./ping.js";
import { setCurrentCommand } from "./set-current.js";
import type { AnyInteraction, Command, CommandContext } from "./types.js";
import { unlinkCommand } from "./unlink.js";

export type { AnyInteraction, Command, CommandContext } from "./types.js";

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
  moveCommand,
  noteCommand,
  unlinkCommand,
];

export const commandDefinitions = commands.map((c) => c.definition.toJSON());

const commandsByName = new Map(commands.map((c) => [c.definition.name, c]));

/**
 * Dispatches one already-verified, already-adapted interaction (ADR 0053 -
 * built by `interaction-adapter.ts` from a raw HTTP Interactions Endpoint
 * payload, no Gateway `Client` involved). The one-bot-one-guild invariant
 * (ADR 0050) is checked by `interactions-route.ts` before this is ever
 * called - not repeated here, since by this point some response must
 * always be sent within Discord's response window, and a silent early
 * return would leave that window's promise unresolved.
 */
export async function dispatchInteraction(
  interaction: AnyInteraction,
  ctx: CommandContext,
): Promise<void> {
  // Chat-input/autocomplete are keyed by commandName; components/modals by
  // their own customId's namespace prefix (ADR 0052 - "<command name>:
  // <action>:<...ids>"), both resolving into the same commandsByName map.
  // Checked directly via these three guards (rather than through a
  // separate helper predicate) so TypeScript can actually narrow the
  // `else` branch down to the two commandName-bearing kinds.
  const commandName =
    interaction.isStringSelectMenu() || interaction.isButton() || interaction.isModalSubmit()
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
      // Autocomplete has no error-reply channel of its own (ADR 0051's own
      // note on types.ts's Command.autocomplete) - an empty choice list is
      // the only graceful failure mode; the real error still surfaces when
      // the user actually submits the command.
      ctx.logger.error({ err: error, commandName }, "autocomplete handler failed");
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
