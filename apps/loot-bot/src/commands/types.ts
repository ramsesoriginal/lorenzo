import type { ChatInputCommandInteraction, SlashCommandBuilder } from "discord.js";
import type { Logger } from "pino";
import type { Config } from "../config.js";

export type CommandContext = Readonly<{
  config: Config;
  logger: Logger;
}>;

export type Command = Readonly<{
  definition: SlashCommandBuilder;
  execute: (interaction: ChatInputCommandInteraction, ctx: CommandContext) => Promise<void>;
}>;
