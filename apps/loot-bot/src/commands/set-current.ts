import { SlashCommandBuilder } from "discord.js";
import { getPreference, setPreference } from "../db.js";
import { type LorenzoApiClient, createLorenzoApiClient } from "../lorenzo-client.js";
import { getValidAccessToken } from "../token-provider.js";
import { filterChoices, formatItemChoiceName } from "./autocomplete.js";
import type { Command } from "./types.js";

/**
 * `/set-current` - stores which character, and optionally which container,
 * every other command should default to when its own character/container
 * option is left unset (`preferences.ts`'s `resolveCurrentCharacter`/
 * `resolveCurrentContainer` is where that fallback actually happens).
 * Either option alone is a valid call - `/set-current container:<x>` just
 * updates the container, leaving whichever character was already current
 * untouched (`setPreference`'s own "only touch fields given" behavior).
 *
 * `container` has no dedicated "is this a container" signal to filter
 * autocomplete by (nothing in the real API exposes one) - it suggests
 * every item instance the resolved character owns, container-capable or
 * not, and trusts the player to pick something sensible.
 */
export const setCurrentCommand: Command = {
  definition: new SlashCommandBuilder()
    .setName("set-current")
    .setDescription("Set your current character and/or default container.")
    .addStringOption((opt) =>
      opt
        .setName("character")
        .setDescription("Your current character")
        .setRequired(false)
        .setAutocomplete(true),
    )
    .addStringOption((opt) =>
      opt
        .setName("container")
        .setDescription("Your default container (e.g. a backpack)")
        .setRequired(false)
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
      const players = await client.getMyPlayers(tenantId, accessToken);
      const choices = players
        .flatMap((player) => player.characters)
        .map((c) => ({ name: c.name, value: c.entityId }));
      await interaction.respond(filterChoices(choices, focused.value));
      return;
    }

    if (focused.name === "container") {
      const characterId = await resolveAutocompleteCharacter(
        interaction.options.getString("character"),
        interaction.user.id,
      );
      if (!characterId) {
        await interaction.respond([]);
        return;
      }
      const items = await findOwnedItems(client, tenantId, characterId, accessToken);
      const choices = items.map((item) => ({
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

    const characterEntityId = interaction.options.getString("character") ?? undefined;
    const containerEntityId = interaction.options.getString("container") ?? undefined;

    if (characterEntityId === undefined && containerEntityId === undefined) {
      await interaction.editReply("Give me a character and/or a container to set.");
      return;
    }

    await setPreference(interaction.user.id, {
      ...(characterEntityId !== undefined ? { characterEntityId } : {}),
      ...(containerEntityId !== undefined ? { containerEntityId } : {}),
    });

    const client = createLorenzoApiClient(ctx.config.lorenzoApiBaseUrl);
    const tenantId = ctx.config.lorenzoTenantId;
    const parts = await Promise.all([
      characterEntityId
        ? client
            .getCharacterName(tenantId, characterEntityId, accessToken)
            .catch(() => "that character")
        : undefined,
      containerEntityId
        ? client
            .getItemInstance(tenantId, containerEntityId, accessToken)
            .then(({ data }) => data.title ?? "(untitled)")
            .catch(() => "that container")
        : undefined,
    ]);
    const [characterName, containerName] = parts;

    const summary = [
      characterName ? `current character: ${characterName}` : undefined,
      containerName ? `default container: ${containerName}` : undefined,
    ]
      .filter((line) => line !== undefined)
      .join(", ");
    await interaction.editReply(`Set your ${summary}.`);
  },
};

/** Autocomplete's own "which character" resolution for the `container`
 * option - the `character` option in the *same* interaction if it's
 * already been typed, otherwise whatever `/set-current` last stored.
 * Never the explicit-then-stored-preference fallback from preferences.ts:
 * that's for *other* commands defaulting an unset option at execute time,
 * this is autocomplete narrowing a suggestion list, a different concern
 * that happens to look similar. */
async function resolveAutocompleteCharacter(
  chosenInThisInteraction: string | null,
  discordUserId: string,
): Promise<string | undefined> {
  if (chosenInThisInteraction) return chosenInThisInteraction;
  const preference = await getPreference(discordUserId);
  return preference?.currentCharacterEntityId ?? undefined;
}

async function findOwnedItems(
  client: LorenzoApiClient,
  tenantId: string,
  characterEntityId: string,
  accessToken: string,
): Promise<readonly { entityId: string; title: string; quantity: number | null }[]> {
  const response = await client.getItemInstancesOwnedBy(tenantId, characterEntityId, accessToken);
  return response.groups.flatMap((group) =>
    group.item_instances.map((item) => ({
      entityId: item.entity_id,
      title: item.title ?? "(untitled)",
      quantity: item.quantity,
    })),
  );
}
