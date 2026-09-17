import { SlashCommandBuilder } from "discord.js";
import { formatWhoamiEmbed } from "../format-whoami.js";
import { createLorenzoApiClient } from "../lorenzo-client.js";
import { getValidAccessToken } from "../token-provider.js";
import type { Command } from "./types.js";

/**
 * `/whoami` (ADR 0050) - confirms which Lorenzo identity a Discord account
 * is actually linked to, and what it can see in this server's own tenant:
 * `/me`, presented nicely instead of raw JSON. Reaches for the same
 * "haven't linked yet" message every other command already uses (`/link`
 * first) rather than a bespoke one.
 */
export const whoamiCommand: Command = {
  definition: new SlashCommandBuilder()
    .setName("whoami")
    .setDescription("Check which Lorenzo identity your Discord account is linked to."),
  async execute(interaction, ctx) {
    await interaction.deferReply({ ephemeral: true });

    const accessToken = await getValidAccessToken(interaction.user.id);
    if (!accessToken) {
      await interaction.editReply("You haven't linked your account yet — run `/link` first.");
      return;
    }

    const client = createLorenzoApiClient(ctx.config.lorenzoApiBaseUrl);
    const profile = await client.getMyProfile(ctx.config.lorenzoTenantId, accessToken);

    await interaction.editReply({ embeds: [formatWhoamiEmbed(profile)] });
  },
};
