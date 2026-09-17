import { SlashCommandBuilder } from "discord.js";
import { LorenzoApiError, createLorenzoApiClient } from "../lorenzo-client.js";
import { getValidAccessToken } from "../token-provider.js";
import { filterChoices, formatItemChoiceName } from "./autocomplete.js";
import type { Command } from "./types.js";

/**
 * `/move-bulk` - empties every item directly inside one container into
 * another, in a single call (ADR 0065/0068). No interactive multi-select
 * needed, unlike `/give-bulk`: the API's own `from_container_entity_id`
 * mode already resolves "everything in here" server-side, so this is
 * just two container options, same shape as `/move` itself.
 *
 * Self-service, not GM-gated - each item's own move is still authorized
 * individually (self-or-managed, unchanged), exactly like `/move`'s
 * single-item write; the `from` container itself isn't an authorization
 * boundary, just a filter, so this can empty any reachable container's
 * *reachable* contents, not only ones the caller strictly "owns."
 */
export const moveBulkCommand: Command = {
  definition: new SlashCommandBuilder()
    .setName("move-bulk")
    .setDescription("Empty one of your containers into another, in one call.")
    .addStringOption((opt) =>
      opt
        .setName("from")
        .setDescription("The container to empty")
        .setRequired(true)
        .setAutocomplete(true),
    )
    .addStringOption((opt) =>
      opt
        .setName("to")
        .setDescription("Where to move everything")
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
    const containers = items.filter((item) => item.isContainer);
    const choices = containers.map((item) => ({
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

    const fromContainerEntityId = interaction.options.getString("from", true);
    const toContainerEntityId = interaction.options.getString("to", true);
    if (fromContainerEntityId === toContainerEntityId) {
      await interaction.editReply("Pick two different containers — that would just be a no-op.");
      return;
    }

    const client = createLorenzoApiClient(ctx.config.lorenzoApiBaseUrl);
    const tenantId = ctx.config.lorenzoTenantId;

    try {
      const results = await client.bulkMoveItemInstancesFromContainer(
        tenantId,
        fromContainerEntityId,
        toContainerEntityId,
        accessToken,
      );
      const succeeded = results.filter((r) => r.status === "ok").length;
      const failed = results.length - succeeded;

      if (results.length === 0) {
        await interaction.editReply("That container was already empty — nothing to move.");
        return;
      }

      const lines = [`Moved ${succeeded} item${succeeded === 1 ? "" : "s"}.`];
      if (failed > 0) {
        lines.push(`${failed} couldn't be moved — they may not be reachable from you.`);
      }
      await interaction.editReply(lines.join("\n"));
    } catch (error) {
      if (error instanceof LorenzoApiError) {
        await interaction.editReply(describeMoveBulkError(error));
        return;
      }
      throw error;
    }
  },
};

function describeMoveBulkError(error: LorenzoApiError): string {
  switch (error.status) {
    case 404:
      return "Couldn't find one of those containers anymore — run `/move-bulk` again and re-pick from the suggestions.";
    case 422:
      return `Couldn't do that: ${error.message}`;
    default:
      return "Something went wrong moving those items.";
  }
}
