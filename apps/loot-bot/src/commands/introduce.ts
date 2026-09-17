import { SlashCommandBuilder } from "discord.js";
import { formatIntroduceEmbed } from "../format-introduce.js";
import { createLorenzoApiClient } from "../lorenzo-client.js";
import { getValidAccessToken } from "../token-provider.js";
import type { Command } from "./types.js";

/**
 * `/introduce` (ADR 0060) - posts a curated, public subset of the caller's
 * own profile to the channel: `/whoami`'s private answer, presented for
 * everyone else instead of just the caller (see format-introduce.ts for
 * exactly which fields, and why only those). Defers *ephemerally* even
 * though the actual introduction is public - not linked yet/no profile set
 * are both "something's not ready" states that should stay private, only
 * ever visible to the caller; the real post is a separate, independently-
 * flagged `followUp` (interaction-adapter.ts's own followUp always applies
 * whatever `ephemeral` *that* call gets, regardless of the original
 * deferReply's), sent only once there's actually something to show.
 */
export const introduceCommand: Command = {
  definition: new SlashCommandBuilder()
    .setName("introduce")
    .setDescription("Post your Lorenzo profile (name, pronouns, bio) to this channel."),
  async execute(interaction, ctx) {
    await interaction.deferReply({ ephemeral: true });

    const accessToken = await getValidAccessToken(interaction.user.id);
    if (!accessToken) {
      await interaction.editReply("You haven't linked your account yet — run `/link` first.");
      return;
    }

    const client = createLorenzoApiClient(ctx.config.lorenzoApiBaseUrl);
    const profile = await client.getMyProfile(ctx.config.lorenzoTenantId, accessToken);

    const embed = formatIntroduceEmbed(profile);
    if (!embed) {
      await interaction.editReply(
        "You haven't set a display name or nickname yet, so there's nothing to introduce yet.",
      );
      return;
    }

    await interaction.editReply("Posted below.");
    await interaction.followUp({ embeds: [embed], ephemeral: false });
  },
};
