import { SlashCommandBuilder } from "discord.js";
import { LorenzoApiError, createLorenzoApiClient } from "../lorenzo-client.js";
import { getValidAccessToken } from "../token-provider.js";
import { filterChoices, formatItemChoiceName } from "./autocomplete.js";
import type { Command } from "./types.js";

/**
 * `/merge` - combines two of the caller's own stacks of the same item into
 * one (ADR 0064). No new API capability: `POST .../item-instances/{id}/merge`
 * already exists (ADR 0044's split's own inverse), just never wrapped or
 * exposed by this bot before. `item` is the stack that gets consumed;
 * `into` is the surviving stack, which keeps its own existing container
 * untouched - that's what already satisfies "a merge has to end up in a
 * container," not a separate mechanism this command needs to build.
 */
export const mergeCommand: Command = {
  definition: new SlashCommandBuilder()
    .setName("merge")
    .setDescription("Combine two of your own stacks of the same item into one.")
    .addStringOption((opt) =>
      opt
        .setName("item")
        .setDescription("The stack to merge (this one gets consumed)")
        .setRequired(true)
        .setAutocomplete(true),
    )
    .addStringOption((opt) =>
      opt
        .setName("into")
        .setDescription("The stack to merge it into (this one survives)")
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

    if (focused.name === "item") {
      const choices = items.map((item) => ({
        name: formatItemChoiceName(item.title, item.quantity),
        value: item.entityId,
      }));
      await interaction.respond(filterChoices(choices, focused.value));
      return;
    }

    if (focused.name === "into") {
      const chosenItemId = interaction.options.getString("item");
      const chosen = chosenItemId
        ? items.find((item) => item.entityId === chosenItemId)
        : undefined;
      // Narrowed to other stacks sharing the same title, when we can tell
      // which one that is - autocomplete is a convenience, never
      // authoritative (matching /give's own precedent); the server's own
      // merge validation is the real guard either way.
      const candidates = chosen
        ? items.filter((item) => item.entityId !== chosen.entityId && item.title === chosen.title)
        : items;
      const choices = candidates.map((item) => ({
        name: formatItemChoiceName(item.title, item.quantity),
        value: item.entityId,
      }));
      await interaction.respond(filterChoices(choices, focused.value));
    }
  },

  async execute(interaction, ctx) {
    await interaction.deferReply({ ephemeral: true });

    const accessToken = await getValidAccessToken(interaction.user.id);
    if (!accessToken) {
      await interaction.editReply("You haven't linked your account yet — run `/link` first.");
      return;
    }

    const itemEntityId = interaction.options.getString("item", true);
    const intoEntityId = interaction.options.getString("into", true);
    const client = createLorenzoApiClient(ctx.config.lorenzoApiBaseUrl);
    const tenantId = ctx.config.lorenzoTenantId;

    if (itemEntityId === intoEntityId) {
      await interaction.editReply("Pick two different stacks — a stack can't merge into itself.");
      return;
    }

    try {
      // Fresh etag, not whatever autocomplete last showed - same
      // re-validate-before-writing discipline every other write command
      // in this bot already follows.
      const { etag } = await client.getItemInstance(tenantId, itemEntityId, accessToken);
      const merged = await client.mergeItemInstance(
        tenantId,
        itemEntityId,
        intoEntityId,
        accessToken,
        etag ?? undefined,
      );
      await interaction.editReply(`Merged into ${merged.title ?? "(untitled)"}.`);
    } catch (error) {
      if (error instanceof LorenzoApiError) {
        await interaction.editReply(describeMergeError(error));
        return;
      }
      throw error;
    }
  },
};

function describeMergeError(error: LorenzoApiError): string {
  switch (error.status) {
    case 403:
      return "You can't merge that — one of those stacks isn't reachable from any of your characters.";
    case 404:
      return "Couldn't find one of those stacks anymore — run `/merge` again and re-pick from the suggestions.";
    case 412:
      return "Someone else changed that stack just now — run `/merge` again to try again.";
    case 422:
      return `Couldn't do that: ${error.message}`;
    default:
      return "Something went wrong merging those stacks.";
  }
}
