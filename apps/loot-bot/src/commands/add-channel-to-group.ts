import { SlashCommandBuilder } from "discord.js";
import { getRecentChannelAuthorIds } from "../discord-rest.js";
import { LorenzoApiError, createLorenzoApiClient } from "../lorenzo-client.js";
import { getValidAccessToken } from "../token-provider.js";
import { filterChoices } from "./autocomplete.js";
import { resolveOrCreateGroup } from "./group-lookup.js";
import type { Command } from "./types.js";

/**
 * `/add-channel-to-group` - adds every controlled character of everyone
 * who's recently posted in this channel to a group, creating the group
 * first if needed (ADR 0068). GM-gated (unlike `/add-to-group`): this
 * sweeps in *other* players' characters, which only ever succeeds for
 * someone with real standing over them (`can_manage_character`, almost
 * always meaning "is their campaign's GM") - the same "fast, friendly
 * rejection matching the backend's own permissiveness" precedent
 * `/award`/`/drop` already established, not a stricter bot-only rule.
 *
 * "Recently active" is deliberately "posted a message here recently"
 * (`discord-rest.ts`'s new `getRecentChannelAuthorIds`, a bot-token REST
 * read of message history) - this bot has no persistent Gateway
 * connection (ADR 0053), so it has no notion of live channel presence to
 * ask instead; message history is the one thing an HTTP-only bot can
 * still see without one. Each poster's *own* controlled characters are
 * resolved using *their own* stored token (`token-provider.ts`'s
 * `getValidAccessToken`, keyed by any Discord user id, not just the
 * caller's - the same trick `/drop`'s own message-refresh already uses
 * for its drop's creator), never the invoking GM's - only the final
 * group-membership write runs as the GM. Anyone not linked, or with no
 * controlled characters, contributes nothing and isn't treated as an error.
 */
export const addChannelToGroupCommand: Command = {
  definition: new SlashCommandBuilder()
    .setName("add-channel-to-group")
    .setDescription("GM-only: add every recently-active poster's characters here to a group.")
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
    const groups = await client.listGroups(ctx.config.lorenzoTenantId, accessToken);
    const choices = groups.map((group) => ({ name: group.name, value: group.name }));
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
    if (!(await client.isCampaignGm(accessToken))) {
      await interaction.editReply("Only a GM can add a whole channel's characters to a group.");
      return;
    }

    const groupName = interaction.options.getString("group", true);
    const tenantId = ctx.config.lorenzoTenantId;

    let authorIds: readonly string[];
    try {
      authorIds = await getRecentChannelAuthorIds(
        ctx.config.discordBotToken,
        interaction.channelId,
      );
    } catch {
      await interaction.editReply(
        "Couldn't read this channel's recent messages — the bot may be missing the Read Message History permission here.",
      );
      return;
    }

    const perAuthorCharacterIds = await Promise.all(
      authorIds.map(async (authorId) => {
        const authorToken = await getValidAccessToken(authorId);
        if (!authorToken) return [];
        return client
          .getControlledCharacters(tenantId, authorToken)
          .then((characters) => characters.map((c) => c.entityId))
          .catch(() => []);
      }),
    );
    const characterIds = [...new Set(perAuthorCharacterIds.flat())];

    if (characterIds.length === 0) {
      await interaction.editReply(
        "No linked characters found among recent posters in this channel.",
      );
      return;
    }

    try {
      const { group, created } = await resolveOrCreateGroup(
        client,
        tenantId,
        groupName,
        accessToken,
        characterIds,
      );

      if (created) {
        await interaction.editReply(
          `Created "${group.name}" with ${characterIds.length} character${characterIds.length === 1 ? "" : "s"}.`,
        );
        return;
      }

      const results = await client.bulkAddGroupMembers(
        tenantId,
        group.entityId,
        characterIds,
        accessToken,
      );
      const succeeded = results.filter((r) => r.status === "ok").length;
      const failed = results.length - succeeded;
      const lines = [
        `Added ${succeeded} character${succeeded === 1 ? "" : "s"} to "${group.name}".`,
      ];
      if (failed > 0) {
        lines.push(`${failed} couldn't be added — not every character found is one you manage.`);
      }
      await interaction.editReply(lines.join("\n"));
    } catch (error) {
      if (error instanceof LorenzoApiError) {
        await interaction.editReply(`Couldn't do that: ${error.message}`);
        return;
      }
      throw error;
    }
  },
};
