import type {
  AutocompleteInteraction,
  ButtonInteraction,
  ChatInputCommandInteraction,
  ModalSubmitInteraction,
  SlashCommandBuilder,
  SlashCommandOptionsOnlyBuilder,
  StringSelectMenuInteraction,
} from "discord.js";
import type { Logger } from "pino";
import type { Config } from "../config.js";

export type CommandContext = Readonly<{
  config: Config;
  logger: Logger;
}>;

export type Command = Readonly<{
  // A bare SlashCommandBuilder (no options chained, e.g. ping.ts) narrows
  // to SlashCommandOptionsOnlyBuilder the moment .addStringOption(...) etc.
  // is called (discord.js's own type-level way of forbidding mixing plain
  // options with subcommands) - accepting either is what lets both shapes
  // satisfy this one field.
  definition: SlashCommandBuilder | SlashCommandOptionsOnlyBuilder;
  execute: (interaction: ChatInputCommandInteraction, ctx: CommandContext) => Promise<void>;
  /** Optional - only commands with an autocompleted option (ADR 0043's
   * `/give`) need one. Must itself call `interaction.respond([...])`
   * (discord.js gives autocomplete no other way to reply) within Discord's
   * ~3s window - never let it throw uncaught (see commands/index.ts's
   * dispatcher, which treats a thrown autocomplete handler as "respond
   * with no choices" rather than a failed interaction). */
  autocomplete?: (interaction: AutocompleteInteraction, ctx: CommandContext) => Promise<void>;

  /**
   * Optional - only commands with their own persistent, interactive
   * message need these (ADR 0044's `/drop`). Every `customId` this bot
   * ever creates is namespaced `"<this command's own definition.name>:
   * <action>:<...ids>"`; commands/index.ts's dispatcher extracts the part
   * before the first `:` and routes to whichever of these three is
   * relevant, on this same command - one dispatch convention, not a
   * parallel routing table per interaction kind.
   */
  onSelectMenu?: (interaction: StringSelectMenuInteraction, ctx: CommandContext) => Promise<void>;
  onButton?: (interaction: ButtonInteraction, ctx: CommandContext) => Promise<void>;
  onModalSubmit?: (interaction: ModalSubmitInteraction, ctx: CommandContext) => Promise<void>;
}>;
