import { SlashCommandBuilder } from "discord.js";
import { formatItemEmbed } from "../format-item.js";
import { LorenzoApiError, createLorenzoApiClient } from "../lorenzo-client.js";
import { getValidAccessToken } from "../token-provider.js";
import { filterChoices, formatItemChoiceName } from "./autocomplete.js";
import type { Command } from "./types.js";

/**
 * `/item` - shows an item's full description, stats, and every note the
 * caller is allowed to see, in the channel (public - the point is other
 * players see it too, e.g. showing off a find). Autocomplete only
 * suggests the caller's own items (there's no item-instance search
 * endpoint), but the option itself accepts any entity id - free-typing
 * one not in the suggestion list (someone else's item, an NPC's gear)
 * still works, same "autocomplete is a convenience, not a restriction"
 * principle `/give` already established.
 */
export const itemCommand: Command = {
  definition: new SlashCommandBuilder()
    .setName("item")
    .setDescription("Display an item's description, stats, and notes.")
    .addStringOption((opt) =>
      opt
        .setName("item")
        .setDescription("The item to display")
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

    const items = await client.getMyItemInstances(tenantId, accessToken);
    const choices = items.map((item) => ({
      name: formatItemChoiceName(item.title, item.quantity),
      value: item.entityId,
    }));
    await interaction.respond(filterChoices(choices, focused.value));
  },

  async execute(interaction, ctx) {
    await interaction.deferReply(); // public - showing it off is the point

    const accessToken = await getValidAccessToken(interaction.user.id);
    if (!accessToken) {
      await interaction.editReply("You haven't linked your account yet — run `/link` first.");
      return;
    }

    const entityId = interaction.options.getString("item", true);
    const client = createLorenzoApiClient(ctx.config.lorenzoApiBaseUrl);
    const tenantId = ctx.config.lorenzoTenantId;

    try {
      const entity = await client.getEntity(tenantId, entityId, accessToken);
      await interaction.editReply({ embeds: [formatItemEmbed(entity)] });
    } catch (error) {
      if (error instanceof LorenzoApiError && error.status === 404) {
        await interaction.editReply("Couldn't find that item — check the id and try again.");
        return;
      }
      throw error;
    }
  },
};
