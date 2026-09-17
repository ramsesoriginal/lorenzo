import { EmbedBuilder, SlashCommandBuilder } from "discord.js";
import { createLorenzoApiClient } from "../lorenzo-client.js";
import { getValidAccessToken } from "../token-provider.js";
import type { Command } from "./types.js";

/**
 * `/my-groups` - lists which groups each of the caller's own characters
 * belongs to (ADR 0064). No new API capability: `GET .../characters/{id}/
 * groups` already exists (ADR 0045's own "reverse direction" addition),
 * just never wrapped or exposed by this bot before.
 */
export const myGroupsCommand: Command = {
  definition: new SlashCommandBuilder()
    .setName("my-groups")
    .setDescription("List which groups your characters belong to."),

  async execute(interaction, ctx) {
    await interaction.deferReply({ ephemeral: true });

    const accessToken = await getValidAccessToken(interaction.user.id);
    if (!accessToken) {
      await interaction.editReply("You haven't linked your account yet — run `/link` first.");
      return;
    }

    const client = createLorenzoApiClient(ctx.config.lorenzoApiBaseUrl);
    const tenantId = ctx.config.lorenzoTenantId;
    const characters = await client.getControlledCharacters(tenantId, accessToken);

    if (characters.length === 0) {
      await interaction.editReply("You don't control any characters in this campaign yet.");
      return;
    }

    // Resolved in parallel, but the embed's own fields are built afterward
    // in the original character order - `Promise.all` settling order isn't
    // guaranteed to match input order, and this is a display list, not a
    // race.
    const fields = await Promise.all(
      characters.map(async (character) => {
        const groups = await client.getCharacterGroups(tenantId, character.entityId, accessToken);
        return {
          name: character.name,
          value: groups.length > 0 ? groups.map((group) => group.name).join(", ") : "No groups.",
        };
      }),
    );

    const embed = new EmbedBuilder().setTitle("Your groups").addFields(fields);
    await interaction.editReply({ embeds: [embed] });
  },
};
