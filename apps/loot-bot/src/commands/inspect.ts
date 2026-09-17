import { SlashCommandBuilder } from "discord.js";
import { formatInventoryEmbed } from "../format-inventory.js";
import { createLorenzoApiClient } from "../lorenzo-client.js";
import { getValidAccessToken } from "../token-provider.js";
import { filterChoices } from "./autocomplete.js";
import { findGmControlledCharacters } from "./gm-roster.js";
import type { Command } from "./types.js";

/**
 * `/inspect` - a GM's read-only look at another character's inventory
 * (ADR 0064), the GM-facing counterpart to `/inventory`. Needs no new API
 * capability: `GET .../item-instances/owned-by/{id}` is already
 * GM-permissive (ADR 0040's `gm_reachable_entity_ids`), so this just points
 * the same `getItemInstancesOwnedBy`/`formatInventoryEmbed` pair `/inventory`
 * already uses at a character the GM picked instead of the caller's own.
 * Private (ephemeral) - this is a GM utility, not something to show off in
 * the channel.
 */
export const inspectCommand: Command = {
  definition: new SlashCommandBuilder()
    .setName("inspect")
    .setDescription("GM-only: look at a character's inventory.")
    .addStringOption((opt) =>
      opt
        .setName("character")
        .setDescription("The character to inspect")
        .setRequired(true)
        .setAutocomplete(true),
    ),

  async autocomplete(interaction, ctx) {
    const focused = interaction.options.getFocused(true);
    const accessToken = await getValidAccessToken(interaction.user.id);
    if (!accessToken) {
      await interaction.respond([]);
      return;
    }

    const client = createLorenzoApiClient(ctx.config.lorenzoApiBaseUrl);
    const tenantId = ctx.config.lorenzoTenantId;

    const characters = await findGmControlledCharacters(client, tenantId, accessToken);
    const choices = characters.map((c) => ({ name: c.name, value: c.entityId }));
    await interaction.respond(filterChoices(choices, focused.value));
  },

  async execute(interaction, ctx) {
    await interaction.deferReply({ ephemeral: true });

    const accessToken = await getValidAccessToken(interaction.user.id);
    if (!accessToken) {
      await interaction.editReply("You haven't linked your account yet — run `/link` first.");
      return;
    }

    const client = createLorenzoApiClient(ctx.config.lorenzoApiBaseUrl);
    if (!(await client.isCampaignGm(accessToken))) {
      await interaction.editReply("Only a GM can inspect another character's inventory.");
      return;
    }

    const characterEntityId = interaction.options.getString("character", true);
    const tenantId = ctx.config.lorenzoTenantId;

    const characterName = await client
      .getCharacterName(tenantId, characterEntityId, accessToken)
      .catch(() => "that character");
    const response = await client.getItemInstancesOwnedBy(tenantId, characterEntityId, accessToken);

    await interaction.editReply({ embeds: [formatInventoryEmbed(characterName, response)] });
  },
};
