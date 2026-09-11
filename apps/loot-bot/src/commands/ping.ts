import { SlashCommandBuilder } from "discord.js";
import type { Command } from "./types.js";

export const pingCommand: Command = {
  definition: new SlashCommandBuilder()
    .setName("ping")
    .setDescription("Check that the bot is alive."),
  async execute(interaction) {
    await interaction.reply({ content: "Pong.", ephemeral: true });
  },
};
