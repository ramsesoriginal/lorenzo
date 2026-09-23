import { SlashCommandBuilder } from "discord.js";
import { formatItemEmbed } from "../format-item.js";
import { LorenzoApiError, createLorenzoApiClient } from "../lorenzo-client.js";
import { resolveCurrentCharacter } from "../preferences.js";
import { getValidAccessToken } from "../token-provider.js";
import { filterChoices } from "./autocomplete.js";
import type { Command } from "./types.js";

/**
 * `/sheet` - a character's resolved stats and whatever lore/backstory the
 * caller is cleared to read (ADR 0090). The same `GET .../entities/{id}` read
 * `/item` uses, pointed at a *character*: stats are the effective values
 * after prototype inheritance (ADR 0037/0039), and `information` is already
 * filtered server-side to what this user may see (`information_visibility.py`,
 * ADR 0035) - so, as with every command here, nothing is filtered by the bot
 * and the API call is made as the person who ran it (ADR 0050). A GM-only
 * secret on your own character simply isn't in the response.
 *
 * What it adds over typing an id into `/item`: `character` autocompletes
 * from the caller's own characters and defaults sensibly (the stored
 * `/set-current` character, else the only one they control), and the reply is
 * private - a sheet is for the player, not the channel.
 */
export const sheetCommand: Command = {
  definition: new SlashCommandBuilder()
    .setName("sheet")
    .setDescription("Your character's stats and the notes you're cleared to see.")
    .addStringOption((opt) =>
      opt
        .setName("character")
        .setDescription("Which character (default: your current one)")
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
    const characters = await client.getControlledCharacters(
      ctx.config.lorenzoTenantId,
      accessToken,
    );
    const choices = characters.map((c) => ({ name: c.name, value: c.entityId }));
    await interaction.respond(filterChoices(choices, focused.value));
  },

  async execute(interaction, ctx) {
    await interaction.deferReply({ ephemeral: true });

    const accessToken = await getValidAccessToken(interaction.user.id);
    if (!accessToken) {
      await interaction.editReply("You haven't linked your account yet — run `/link` first.");
      return;
    }

    const client = createLorenzoApiClient(ctx.config.lorenzoApiBaseUrl);
    const tenantId = ctx.config.lorenzoTenantId;

    // Explicit option, then the stored default (`/set-current`, ADR 0068),
    // then - so a player with one character never has to configure anything
    // - the only character they control.
    let characterEntityId = await resolveCurrentCharacter(
      interaction.user.id,
      interaction.channelId,
      interaction.options.getString("character"),
    );
    if (!characterEntityId) {
      const mine = await client.getControlledCharacters(tenantId, accessToken);
      if (mine.length === 0) {
        await interaction.editReply("You don't control any characters here yet.");
        return;
      }
      if (mine.length > 1) {
        await interaction.editReply(
          "You have more than one character — pick one with the `character` option, or set a default with `/set-current`.",
        );
        return;
      }
      characterEntityId = mine[0]?.entityId;
    }
    if (!characterEntityId) return;

    try {
      const entity = await client.getEntity(tenantId, characterEntityId, accessToken);
      await interaction.editReply({ embeds: [formatItemEmbed(entity)] });
    } catch (error) {
      if (error instanceof LorenzoApiError && (error.status === 404 || error.status === 403)) {
        await interaction.editReply(
          "Couldn't open that character's sheet — check the name and try again.",
        );
        return;
      }
      throw error;
    }
  },
};
