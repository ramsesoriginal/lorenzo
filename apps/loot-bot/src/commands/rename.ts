import { SlashCommandBuilder } from "discord.js";
import { LorenzoApiError, createLorenzoApiClient } from "../lorenzo-client.js";
import { getValidAccessToken } from "../token-provider.js";
import { recordUndo } from "../undo-actions.js";
import { filterChoices, formatItemChoiceName } from "./autocomplete.js";
import type { Command } from "./types.js";

/**
 * `/rename` - gives one of the caller's own item instances a custom name
 * (ADR 0068). No new API capability: `PATCH .../item-instances/{id}`
 * already accepts `name` (`ItemInstanceUpdate`), just never wrapped or
 * exposed by this bot before. Useful for telling apart two instances of
 * the same catalog item ("Longsword" -> "Grandfather's Longsword").
 */
export const renameCommand: Command = {
  definition: new SlashCommandBuilder()
    .setName("rename")
    .setDescription("Give one of your own items a custom name.")
    .addStringOption((opt) =>
      opt
        .setName("item")
        .setDescription("The item to rename")
        .setRequired(true)
        .setAutocomplete(true),
    )
    .addStringOption((opt) => opt.setName("name").setDescription("The new name").setRequired(true)),

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
    await interaction.deferReply({ ephemeral: true });

    const accessToken = await getValidAccessToken(interaction.user.id);
    if (!accessToken) {
      await interaction.editReply("You haven't linked your account yet — run `/link` first.");
      return;
    }

    const itemEntityId = interaction.options.getString("item", true);
    const name = interaction.options.getString("name", true);
    const client = createLorenzoApiClient(ctx.config.lorenzoApiBaseUrl);
    const tenantId = ctx.config.lorenzoTenantId;

    try {
      // Fresh etag, not whatever autocomplete last showed - same
      // re-validate-before-writing discipline every other write command
      // in this bot already follows.
      const { data: current, etag } = await client.getItemInstance(
        tenantId,
        itemEntityId,
        accessToken,
      );
      const renamed = await client.renameItemInstance(
        tenantId,
        itemEntityId,
        name,
        accessToken,
        etag ?? undefined,
      );

      await recordUndo(interaction.user.id, {
        kind: "restore-name",
        entityId: itemEntityId,
        previousTitle: current.title,
      });

      await interaction.editReply(`Renamed to ${renamed.title ?? "(untitled)"}.`);
    } catch (error) {
      if (error instanceof LorenzoApiError) {
        await interaction.editReply(describeRenameError(error));
        return;
      }
      throw error;
    }
  },
};

function describeRenameError(error: LorenzoApiError): string {
  switch (error.status) {
    case 403:
      return "You can't rename that — it isn't reachable from any of your characters.";
    case 404:
      return "Couldn't find that item anymore — run `/rename` again and re-pick from the suggestions.";
    case 412:
      return "Someone else changed that item just now — run `/rename` again to try again.";
    case 422:
      return `Couldn't do that: ${error.message}`;
    default:
      return "Something went wrong renaming that item.";
  }
}
