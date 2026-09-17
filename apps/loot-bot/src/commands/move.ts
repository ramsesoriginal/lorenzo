import { SlashCommandBuilder } from "discord.js";
import { LorenzoApiError, createLorenzoApiClient } from "../lorenzo-client.js";
import { getValidAccessToken } from "../token-provider.js";
import { recordUndo } from "../undo-actions.js";
import { filterChoices, formatItemChoiceName } from "./autocomplete.js";
import type { Command } from "./types.js";

/**
 * `/move` - moves one of the caller's own items into another container
 * they own. Self-service only - self-or-managed's "self" branch already
 * covers "rearrange your own stuff," no GM gate needed. `item` suggests
 * everything owned; `container` narrows to `isContainer === true` (ADR
 * 0068, consuming main's own `is_container` computed field, ADR 0066) -
 * closing the gap this docstring used to flag directly: "nothing in the
 * real API flags which owned items are actually container-capable."
 * Still just a suggestion, not a restriction - free-typing any owned
 * entity id still works, same convention every other autocomplete here
 * follows.
 */
export const moveCommand: Command = {
  definition: new SlashCommandBuilder()
    .setName("move")
    .setDescription("Move one of your items into another container you own.")
    .addStringOption((opt) =>
      opt
        .setName("item")
        .setDescription("The item to move")
        .setRequired(true)
        .setAutocomplete(true),
    )
    .addStringOption((opt) =>
      opt
        .setName("container")
        .setDescription("Where to move it")
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
    const candidates = focused.name === "container" ? items.filter((i) => i.isContainer) : items;
    const choices = candidates.map((item) => ({
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
    const containerEntityId = interaction.options.getString("container", true);
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
      const moved = await client.setItemInstanceContainer(
        tenantId,
        itemEntityId,
        containerEntityId,
        accessToken,
        etag ?? undefined,
      );

      await recordUndo(interaction.user.id, {
        kind: "restore-container",
        entityId: itemEntityId,
        previousContainerEntityId: current.container_entity_id,
      });

      await interaction.editReply(`Moved ${moved.title ?? "(untitled)"}.`);
    } catch (error) {
      if (error instanceof LorenzoApiError) {
        await interaction.editReply(describeMoveError(error));
        return;
      }
      throw error;
    }
  },
};

function describeMoveError(error: LorenzoApiError): string {
  switch (error.status) {
    case 403:
      return "That's not something you can move — it isn't reachable from any of your characters.";
    case 404:
      return "Couldn't find that item or that container anymore — run `/move` again and re-pick from the suggestions.";
    case 412:
      return "Someone else changed that item just now — run `/move` again to try again.";
    case 422:
      return `Couldn't do that: ${error.message}`;
    default:
      return "Something went wrong moving that item.";
  }
}
