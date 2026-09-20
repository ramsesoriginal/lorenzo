import { SlashCommandBuilder } from "discord.js";
import {
  describeItem,
  giveEvent,
  nameCharacter,
  recordCharacterEvents,
} from "../character-events.js";
import {
  type ControlledCharacter,
  type LorenzoApiClient,
  LorenzoApiError,
  createLorenzoApiClient,
} from "../lorenzo-client.js";
import { getValidAccessToken } from "../token-provider.js";
import { recordUndo } from "../undo-actions.js";
import { filterChoices, formatItemChoiceName } from "./autocomplete.js";
import { transferItem } from "./item-transfer.js";
import type { Command } from "./types.js";

/**
 * `/give` - loot-splitting (ADR 0051). No `quantity`, or one that covers
 * the whole stack, transfers the source instance's ownership outright;
 * a smaller `quantity` splits that amount off first (POST .../split) and
 * transfers only the split-off instance - see ADR 0051 for the full
 * split-vs-transfer reasoning and why the item's container is left
 * untouched either way.
 */
export const giveCommand: Command = {
  definition: new SlashCommandBuilder()
    .setName("give")
    .setDescription("Give one of your items to another character.")
    .addStringOption((opt) =>
      opt
        .setName("item")
        .setDescription("The item to give")
        .setRequired(true)
        .setAutocomplete(true),
    )
    .addStringOption((opt) =>
      opt.setName("to").setDescription("Who to give it to").setRequired(true).setAutocomplete(true),
    )
    .addIntegerOption((opt) =>
      opt
        .setName("quantity")
        .setDescription("How many to give, for a stack (default: all of it)")
        .setRequired(false)
        .setMinValue(1),
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

    if (focused.name === "item") {
      const items = await client.getMyItemInstances(tenantId, accessToken);
      const choices = items.map((item) => ({
        name: formatItemChoiceName(item.title, item.quantity),
        value: item.entityId,
      }));
      await interaction.respond(filterChoices(choices, focused.value));
      return;
    }

    if (focused.name === "to") {
      const chosenItemId = interaction.options.getString("item");
      const characters = await findGiveTargets(client, tenantId, accessToken, chosenItemId);
      const choices = characters.map((c) => ({ name: c.name, value: c.entityId }));
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
    const targetCharacterId = interaction.options.getString("to", true);
    const requestedQuantity = interaction.options.getInteger("quantity");

    const client = createLorenzoApiClient(ctx.config.lorenzoApiBaseUrl);
    const tenantId = ctx.config.lorenzoTenantId;

    try {
      // Fresh state, not whatever autocomplete last showed - the quantity
      // decision below has to be correct now, not a moment ago (ADR 0051).
      const { data: current, etag } = await client.getItemInstance(
        tenantId,
        itemEntityId,
        accessToken,
      );

      const result = await transferItem(
        client,
        tenantId,
        current,
        etag,
        requestedQuantity,
        targetCharacterId,
        accessToken,
      );

      if (result.kind === "not-a-stack") {
        await interaction.editReply(
          "That item isn't a stack — omit the quantity to give the whole thing.",
        );
        return;
      }

      if (current.owner_entity_id) {
        await recordUndo(interaction.user.id, {
          kind: "restore-owner",
          entityId: result.given.entity_id,
          previousOwnerCharacterId: current.owner_entity_id,
        });
      }

      const targetLookup = await client
        .getCharacterName(tenantId, targetCharacterId, accessToken)
        .catch(() => null);
      const targetName = targetLookup ?? "them";
      const itemName = result.given.title ?? "(untitled)";
      const amount = result.splitting ? `${result.requestedQuantity} of ` : "";

      // For `/changes` (ADR 0096): both the giver's and the receiver's
      // players will see this. Best-effort, after the give itself succeeded.
      const giverId = current.owner_entity_id;
      const giverLookup = giverId
        ? await client.getCharacterName(tenantId, giverId, accessToken).catch(() => null)
        : null;
      const receiver = nameCharacter(targetCharacterId, targetLookup);
      if (receiver) {
        await recordCharacterEvents(
          [
            giveEvent({
              giver: nameCharacter(giverId, giverLookup),
              receiver,
              item: describeItem(itemName, result.given.quantity),
            }),
          ],
          ctx.logger,
        );
      }

      await interaction.editReply(`Gave ${amount}${itemName} to ${targetName}.`);
    } catch (error) {
      if (error instanceof LorenzoApiError) {
        await interaction.editReply(describeGiveError(error));
        return;
      }
      throw error;
    }
  },
};

async function findGiveTargets(
  client: LorenzoApiClient,
  tenantId: string,
  accessToken: string,
  chosenItemId: string | null,
): Promise<readonly ControlledCharacter[]> {
  const players = await client.getMyPlayers(tenantId, accessToken);
  let campaignIds: readonly string[] = players.map((player) => player.campaignId);

  if (chosenItemId) {
    // Narrow to the chosen item's own campaign, if we can tell which one -
    // autocomplete is a convenience, never authoritative (ADR 0051), so a
    // failed/ambiguous lookup here just falls back to "every campaign I'm
    // in" rather than failing the whole autocomplete request.
    try {
      const { data: item } = await client.getItemInstance(tenantId, chosenItemId, accessToken);
      const owningPlayer = players.find((player) =>
        player.characters.some((c) => c.entityId === item.owner_entity_id),
      );
      if (owningPlayer) campaignIds = [owningPlayer.campaignId];
    } catch {
      // fall through to the unnarrowed campaignIds above
    }
  }

  const rosters = await Promise.all(
    campaignIds.map((campaignId) => client.getCampaignPlayers(tenantId, campaignId, accessToken)),
  );
  const byId = new Map(rosters.flat().map((character) => [character.entityId, character]));
  return [...byId.values()];
}

function describeGiveError(error: LorenzoApiError): string {
  switch (error.status) {
    case 403:
      return "That's not something you can give away — it isn't reachable from any of your characters.";
    case 404:
      return "Couldn't find that item or that character anymore — run `/give` again and re-pick from the suggestions.";
    case 412:
      return "Someone else changed that item just now — run `/give` again to pick it up with the current state.";
    case 422:
      return `Couldn't do that: ${error.message}`;
    default:
      return "Something went wrong giving that item away.";
  }
}
