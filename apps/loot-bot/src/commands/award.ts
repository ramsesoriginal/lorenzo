import { SlashCommandBuilder } from "discord.js";
import { awardEvent, nameCharacter, recordCharacterEvents } from "../character-events.js";
import { LorenzoApiError, createLorenzoApiClient } from "../lorenzo-client.js";
import { getValidAccessToken } from "../token-provider.js";
import { filterChoices } from "./autocomplete.js";
import { findGmControlledCharacters } from "./gm-roster.js";
import type { Command } from "./types.js";

/**
 * `/award` - a GM gives a character a brand-new item instance straight
 * from the catalog, e.g. a quest reward. No `quantity` option: it isn't a
 * creation-time field at all (ADR 0041 - it lives on `Containment`, not
 * `ItemInstance`), and this command has no way to resolve which container
 * to attach one to - the target is a character the GM picked from a
 * roster, and this bot has no reverse lookup from a character back to
 * whichever Discord user's own `/set-current` preference might apply.
 * Awarding a stack is a `/drop` scenario instead.
 */
export const awardCommand: Command = {
  definition: new SlashCommandBuilder()
    .setName("award")
    .setDescription("Award a new item to a character.")
    .addStringOption((opt) =>
      opt
        .setName("item")
        .setDescription("The item to award")
        .setRequired(true)
        .setAutocomplete(true),
    )
    .addStringOption((opt) =>
      opt
        .setName("character")
        .setDescription("Who to award it to")
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

    if (focused.name === "item") {
      const items = await client.listItems(tenantId, accessToken);
      const choices = items.map((item) => ({
        name: item.title ?? "(untitled)",
        value: item.entity_id,
      }));
      await interaction.respond(filterChoices(choices, focused.value));
      return;
    }

    if (focused.name === "character") {
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
      await interaction.editReply("Only a GM can award items.");
      return;
    }

    const prototypeId = interaction.options.getString("item", true);
    const characterEntityId = interaction.options.getString("character", true);
    const tenantId = ctx.config.lorenzoTenantId;

    try {
      const given = await client.createItemInstance(
        tenantId,
        prototypeId,
        characterEntityId,
        undefined,
        accessToken,
      );
      const characterLookup = await client
        .getCharacterName(tenantId, characterEntityId, accessToken)
        .catch(() => null);
      const characterName = characterLookup ?? "them";

      // For `/changes` (ADR 0097): the awarded player can find out even if
      // they missed the announcement. The GM isn't named.
      const character = nameCharacter(characterEntityId, characterLookup);
      if (character) {
        await recordCharacterEvents(
          [awardEvent({ character, item: given.title ?? "(untitled)" })],
          ctx.logger,
        );
      }

      await interaction.editReply(`Awarded ${given.title ?? "(untitled)"} to ${characterName}.`);
    } catch (error) {
      if (error instanceof LorenzoApiError) {
        await interaction.editReply(describeAwardError(error));
        return;
      }
      throw error;
    }
  },
};

function describeAwardError(error: LorenzoApiError): string {
  switch (error.status) {
    case 403:
      return "You can't award to that character — you're not a GM of any campaign it's in.";
    case 404:
      return "Couldn't find that item or that character anymore — run `/award` again and re-pick from the suggestions.";
    case 422:
      return `Couldn't do that: ${error.message}`;
    default:
      return "Something went wrong awarding that item.";
  }
}
