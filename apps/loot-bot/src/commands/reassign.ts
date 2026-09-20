import { SlashCommandBuilder } from "discord.js";
import {
  describeItem,
  nameCharacter,
  reassignEvent,
  recordCharacterEvents,
} from "../character-events.js";
import {
  type ControlledCharacter,
  LorenzoApiError,
  createLorenzoApiClient,
} from "../lorenzo-client.js";
import { getValidAccessToken } from "../token-provider.js";
import { recordUndo } from "../undo-actions.js";
import { filterChoices, formatItemChoiceName } from "./autocomplete.js";
import { findGmControlledCharacters } from "./gm-roster.js";
import { transferItem } from "./item-transfer.js";
import type { Command } from "./types.js";

/**
 * `/reassign` - a GM moves an item from whichever character currently owns
 * it to another character (ADR 0068) - structurally `/give.ts` with both
 * ends widened from "the caller's own stuff"/"the caller's own campaigns"
 * to "any character in a campaign I GM." No new API capability:
 * `PUT .../item-instances/{id}/owner` is the exact same GM-permissive write
 * `/give` already calls via {@link transferItem}, reused unchanged here.
 */
export const reassignCommand: Command = {
  definition: new SlashCommandBuilder()
    .setName("reassign")
    .setDescription("GM-only: move an item from one character to another.")
    .addStringOption((opt) =>
      opt
        .setName("item")
        .setDescription("The item to reassign")
        .setRequired(true)
        .setAutocomplete(true),
    )
    .addStringOption((opt) =>
      opt.setName("to").setDescription("Who to give it to").setRequired(true).setAutocomplete(true),
    )
    .addIntegerOption((opt) =>
      opt
        .setName("quantity")
        .setDescription("How many to move, for a stack (default: all of it)")
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
      const items = await findGmOwnedItems(client, tenantId, accessToken);
      const choices = items.map((item) => ({
        name: formatItemChoiceName(item.title, item.quantity),
        value: item.entityId,
      }));
      await interaction.respond(filterChoices(choices, focused.value));
      return;
    }

    if (focused.name === "to") {
      const characters = await findGmControlledCharacters(client, tenantId, accessToken);
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

    const client = createLorenzoApiClient(ctx.config.lorenzoApiBaseUrl);
    if (!(await client.isCampaignGm(accessToken))) {
      await interaction.editReply("Only a GM can reassign items between characters.");
      return;
    }

    const itemEntityId = interaction.options.getString("item", true);
    const targetCharacterId = interaction.options.getString("to", true);
    const requestedQuantity = interaction.options.getInteger("quantity");
    const tenantId = ctx.config.lorenzoTenantId;

    try {
      // Fresh state, not whatever autocomplete last showed - same
      // re-validate-before-writing discipline every other write command
      // in this bot already follows.
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
          "That item isn't a stack — omit the quantity to reassign the whole thing.",
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

      // For `/changes` (ADR 0097): the former and the new owner's players
      // both see this. The GM who did it is deliberately not named.
      const fromId = current.owner_entity_id;
      const fromLookup = fromId
        ? await client.getCharacterName(tenantId, fromId, accessToken).catch(() => null)
        : null;
      const to = nameCharacter(targetCharacterId, targetLookup);
      if (to) {
        await recordCharacterEvents(
          [
            reassignEvent({
              from: nameCharacter(fromId, fromLookup),
              to,
              item: describeItem(itemName, result.given.quantity),
            }),
          ],
          ctx.logger,
        );
      }

      await interaction.editReply(`Reassigned ${amount}${itemName} to ${targetName}.`);
    } catch (error) {
      if (error instanceof LorenzoApiError) {
        await interaction.editReply(describeReassignError(error));
        return;
      }
      throw error;
    }
  },
};

/** Every item instance owned by any character in a campaign the caller
 * GMs, deduplicated - the same fan-out shape `findGmControlledCharacters`
 * already uses for characters, one level further (roster -> each
 * character's own owned-by listing). */
async function findGmOwnedItems(
  client: ReturnType<typeof createLorenzoApiClient>,
  tenantId: string,
  accessToken: string,
): Promise<readonly { entityId: string; title: string; quantity: number | null }[]> {
  const characters = await findGmControlledCharacters(client, tenantId, accessToken);
  const perCharacter = await Promise.all(
    characters.map(async (character: ControlledCharacter) => {
      const response = await client.getItemInstancesOwnedBy(
        tenantId,
        character.entityId,
        accessToken,
      );
      return response.groups.flatMap((group) =>
        group.item_instances.map((item) => ({
          entityId: item.entity_id,
          title: item.title ?? "(untitled)",
          quantity: item.quantity,
        })),
      );
    }),
  );
  const byId = new Map(perCharacter.flat().map((item) => [item.entityId, item]));
  return [...byId.values()];
}

function describeReassignError(error: LorenzoApiError): string {
  switch (error.status) {
    case 403:
      return "You can't reassign that — it isn't reachable from any campaign you GM.";
    case 404:
      return "Couldn't find that item or that character anymore — run `/reassign` again and re-pick from the suggestions.";
    case 412:
      return "Someone else changed that item just now — run `/reassign` again to pick it up with the current state.";
    case 422:
      return `Couldn't do that: ${error.message}`;
    default:
      return "Something went wrong reassigning that item.";
  }
}
