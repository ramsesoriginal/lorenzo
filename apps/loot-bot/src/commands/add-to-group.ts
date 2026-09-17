import { SlashCommandBuilder } from "discord.js";
import {
  type ControlledCharacter,
  LorenzoApiError,
  createLorenzoApiClient,
} from "../lorenzo-client.js";
import { getValidAccessToken } from "../token-provider.js";
import { filterChoices } from "./autocomplete.js";
import { findGmControlledCharacters } from "./gm-roster.js";
import { resolveOrCreateGroup } from "./group-lookup.js";
import type { Command } from "./types.js";

/**
 * `/add-to-group` - adds one character to a group, creating the group
 * first if no group with that exact name exists yet (ADR 0068, consuming
 * main's new group-write API, ADR 0064). Not GM-gated in this bot: the
 * real authorization is `can_manage_character` on the character being
 * added - self, that character's GM, or orga/owner - already permissive
 * enough for a player adding their *own* character, matching the "bot-side
 * gate matches the backend's own permissiveness, not stricter" precedent
 * `/give`/`/move`/`/merge`/`/rename` already established. A GM adding
 * someone else's character just works the same way, no separate code path.
 */
export const addToGroupCommand: Command = {
  definition: new SlashCommandBuilder()
    .setName("add-to-group")
    .setDescription("Add a character to a group, creating it if it doesn't exist yet.")
    .addStringOption((opt) =>
      opt
        .setName("character")
        .setDescription("The character to add")
        .setRequired(true)
        .setAutocomplete(true),
    )
    .addStringOption((opt) =>
      opt
        .setName("group")
        .setDescription("The group's name - an existing one, or a new one to create")
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

    if (focused.name === "character") {
      // Every character the caller could plausibly add: their own, plus
      // any they GM - can_manage_character covers both server-side, so
      // this union is exactly the set of options that stand a real chance
      // of succeeding, not the caller's own characters alone.
      const [own, gmd] = await Promise.all([
        client.getControlledCharacters(tenantId, accessToken),
        findGmControlledCharacters(client, tenantId, accessToken),
      ]);
      const byId = new Map<string, ControlledCharacter>(
        [...own, ...gmd].map((character) => [character.entityId, character]),
      );
      const choices = [...byId.values()].map((c) => ({ name: c.name, value: c.entityId }));
      await interaction.respond(filterChoices(choices, focused.value));
      return;
    }

    if (focused.name === "group") {
      const groups = await client.listGroups(tenantId, accessToken);
      const choices = groups.map((group) => ({ name: group.name, value: group.name }));
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

    const characterEntityId = interaction.options.getString("character", true);
    const groupName = interaction.options.getString("group", true);
    const client = createLorenzoApiClient(ctx.config.lorenzoApiBaseUrl);
    const tenantId = ctx.config.lorenzoTenantId;

    try {
      const { group, created } = await resolveOrCreateGroup(
        client,
        tenantId,
        groupName,
        accessToken,
        [characterEntityId],
      );
      if (!created) {
        await client.addGroupMember(tenantId, group.entityId, characterEntityId, accessToken);
      }

      const characterName = await client
        .getCharacterName(tenantId, characterEntityId, accessToken)
        .catch(() => "that character");
      await interaction.editReply(
        created
          ? `Created "${group.name}" with ${characterName} as its first member.`
          : `Added ${characterName} to "${group.name}".`,
      );
    } catch (error) {
      if (error instanceof LorenzoApiError) {
        await interaction.editReply(describeAddToGroupError(error));
        return;
      }
      throw error;
    }
  },
};

function describeAddToGroupError(error: LorenzoApiError): string {
  switch (error.status) {
    case 403:
      return "You can't add that character — you don't manage it (not your own, not a campaign you GM).";
    case 404:
      return "Couldn't find that group anymore — run `/add-to-group` again and re-pick from the suggestions.";
    case 422:
      return `Couldn't do that: ${error.message}`;
    default:
      return "Something went wrong adding that character to the group.";
  }
}
