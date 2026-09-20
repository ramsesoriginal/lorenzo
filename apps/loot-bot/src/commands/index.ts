import { showUndeliveredNotice } from "../undelivered-notice.js";
import { addChannelToGroupCommand } from "./add-channel-to-group.js";
import { addToGroupCommand } from "./add-to-group.js";
import { awardCommand } from "./award.js";
import { changesCommand } from "./changes.js";
import { confiscateCommand } from "./confiscate.js";
import { containerNewCommand } from "./container-new.js";
import { dropCommand } from "./drop.js";
import { giveBulkCommand } from "./give-bulk.js";
import { giveCommand } from "./give.js";
import { helpCommand } from "./help.js";
import { inspectCommand } from "./inspect.js";
import { introduceCommand } from "./introduce.js";
import { inventoryCommand } from "./inventory.js";
import { itemCommand } from "./item.js";
import { linkCommand } from "./link.js";
import { mergeCommand } from "./merge.js";
import { moveBulkCommand } from "./move-bulk.js";
import { moveCommand } from "./move.js";
import { myGroupsCommand } from "./my-groups.js";
import { noteCommand } from "./note.js";
import { pendingClaimsCommand } from "./pending-claims.js";
import { pingCommand } from "./ping.js";
import { reassignCommand } from "./reassign.js";
import { renameCommand } from "./rename.js";
import { setCurrentCommand } from "./set-current.js";
import type { AnyInteraction, Command, CommandContext } from "./types.js";
import { undoCommand } from "./undo.js";
import { unlinkCommand } from "./unlink.js";
import { whoamiCommand } from "./whoami.js";

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
  whoamiCommand,
  introduceCommand,
  inspectCommand,
  confiscateCommand,
  reassignCommand,
  pendingClaimsCommand,
  mergeCommand,
  renameCommand,
  giveBulkCommand,
  undoCommand,
  myGroupsCommand,
  moveBulkCommand,
  addToGroupCommand,
  addChannelToGroupCommand,
  containerNewCommand,
  changesCommand,
  helpCommand,
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
  // Every command sees the full list via ctx.commands, not just its own
  // definition - the one place this gets wired in, so `/help` (ADR 0068)
  // can describe every other command without a second, hand-maintained
  // list that could drift from this one.
  const ctxWithCommands: CommandContext = { ...ctx, commands };

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
      await command.autocomplete?.(interaction, ctxWithCommands);
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
      await command.onSelectMenu?.(interaction, ctxWithCommands);
    } else if (interaction.isButton()) {
      await command.onButton?.(interaction, ctxWithCommands);
    } else if (interaction.isModalSubmit()) {
      await command.onModalSubmit?.(interaction, ctxWithCommands);
    } else if (interaction.isChatInputCommand()) {
      await command.execute(interaction, ctxWithCommands);
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

  // The "couldn't DM you" fallback (ADR 0095): once a slash command has
  // answered, show any notifications Discord wouldn't let the bot DM this
  // user. Slash commands only - a button click or menu pick mid-flow isn't
  // "running a command", and would put a banner in the middle of one.
  if (interaction.isChatInputCommand()) {
    await showUndeliveredNotice(interaction, ctx.logger);
  }
}
