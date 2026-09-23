import { SlashCommandBuilder } from "discord.js";
import { confiscateEvent, nameCharacter, recordCharacterEvents } from "../character-events.js";
import { LorenzoApiError, createLorenzoApiClient } from "../lorenzo-client.js";
import { getValidAccessToken } from "../token-provider.js";
import { filterChoices, formatItemChoiceName } from "./autocomplete.js";
import { findGmControlledCharacters } from "./gm-roster.js";
import { destroyItem } from "./item-transfer.js";
import type { Command } from "./types.js";

/**
 * `/confiscate` - a GM takes an item away from a character, permanently
 * (ADR 0068). No new API capability: `DELETE .../item-instances/{id}`
 * already exists and is already GM-permissive (`_authorize_instance_write`),
 * just never wrapped or exposed by this bot before. Optional `quantity`
 * confiscates part of a stack instead of the whole instance, reusing
 * `destroyItem`'s split-then-delete-the-split-off-piece shape from
 * `item-transfer.ts`.
 */
export const confiscateCommand: Command = {
  definition: new SlashCommandBuilder()
    .setName("confiscate")
    .setDescription("GM-only: take an item away from a character, permanently.")
    .addStringOption((opt) =>
      opt
        .setName("character")
        .setDescription("Whose item to take")
        .setRequired(true)
        .setAutocomplete(true),
    )
    .addStringOption((opt) =>
      opt
        .setName("item")
        .setDescription("The item to confiscate")
        .setRequired(true)
        .setAutocomplete(true),
    )
    .addIntegerOption((opt) =>
      opt
        .setName("quantity")
        .setDescription("How many to take, for a stack (default: all of it)")
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

    if (focused.name === "character") {
      const characters = await findGmControlledCharacters(client, tenantId, accessToken);
      const choices = characters.map((c) => ({ name: c.name, value: c.entityId }));
      await interaction.respond(filterChoices(choices, focused.value));
      return;
    }

    if (focused.name === "item") {
      const characterEntityId = interaction.options.getString("character");
      if (!characterEntityId) {
        await interaction.respond([]);
        return;
      }
      const response = await client.getItemInstancesOwnedBy(
        tenantId,
        characterEntityId,
        accessToken,
      );
      const items = response.groups.flatMap((group) => group.item_instances);
      const choices = items.map((item) => ({
        name: formatItemChoiceName(item.title ?? "(untitled)", item.quantity),
        value: item.entity_id,
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

    const client = createLorenzoApiClient(ctx.config.lorenzoApiBaseUrl);
    if (!(await client.isCampaignGm(accessToken))) {
      await interaction.editReply("Only a GM can confiscate items.");
      return;
    }

    const characterEntityId = interaction.options.getString("character", true);
    const itemEntityId = interaction.options.getString("item", true);
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

      const result = await destroyItem(
        client,
        tenantId,
        current,
        etag,
        requestedQuantity,
        accessToken,
      );

      if (result.kind === "not-a-stack") {
        await interaction.editReply(
          "That item isn't a stack — omit the quantity to confiscate the whole thing.",
        );
        return;
      }

      const characterLookup = await client
        .getCharacterName(tenantId, characterEntityId, accessToken)
        .catch(() => null);
      const characterName = characterLookup ?? "them";
      const amount = result.requestedQuantity !== null ? `${result.requestedQuantity} of ` : "";

      // For `/changes` (ADR 0097): the player whose item was taken should be
      // able to find out. The GM who did it is deliberately not named.
      const character = nameCharacter(characterEntityId, characterLookup);
      if (character) {
        await recordCharacterEvents(
          [confiscateEvent({ character, item: `${amount}${result.destroyedTitle}` })],
          ctx.logger,
        );
      }

      await interaction.editReply(
        `Confiscated ${amount}${result.destroyedTitle} from ${characterName}.`,
      );
    } catch (error) {
      if (error instanceof LorenzoApiError) {
        await interaction.editReply(describeConfiscateError(error));
        return;
      }
      throw error;
    }
  },
};

function describeConfiscateError(error: LorenzoApiError): string {
  switch (error.status) {
    case 403:
      return "You can't confiscate that — it isn't reachable from any campaign you GM.";
    case 404:
      return "Couldn't find that item or that character anymore — run `/confiscate` again and re-pick from the suggestions.";
    case 412:
      return "Someone else changed that item just now — run `/confiscate` again to try again.";
    case 422:
      return `Couldn't do that: ${error.message}`;
    default:
      return "Something went wrong confiscating that item.";
  }
}
