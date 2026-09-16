import type {
  AutocompleteInteraction,
  ChatInputCommandInteraction,
  SlashCommandBuilder,
  SlashCommandOptionsOnlyBuilder,
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
}>;
