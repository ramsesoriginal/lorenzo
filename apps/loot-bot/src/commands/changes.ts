import { SlashCommandBuilder } from "discord.js";
import { getChangesSeenAt, setChangesSeenAt } from "../db.js";
import { MAX_CHANGES_SHOWN, buildChangesEmbed, describeChange } from "../format-changes.js";
import { createLorenzoApiClient } from "../lorenzo-client.js";
import { getValidAccessToken } from "../token-provider.js";
import type { Command } from "./types.js";

/**
 * `/changes` - what happened to your characters' belongings since you last
 * looked (ADR 0097, now reading ADR 0099's `GET /me/changes` - see the ADR
 * 0097 addendum): gives (made or received), awards, confiscations,
 * reassignments, splits, merges, moves, renames, and deletions. Distinct
 * from a GM's tenant activity log (ADR 0063), which is admin-only and names
 * the actor for every entry.
 *
 * "Since you last looked" is a per-user marker moved each time this runs,
 * read and written locally (`changes_seen`) since the API only offers a
 * `since` filter, not a stored read-position of its own; `history:true`
 * ignores it and doesn't move it. Private (ephemeral).
 */
export const changesCommand: Command = {
  definition: new SlashCommandBuilder()
    .setName("changes")
    .setDescription("What's happened to your characters' belongings since you last looked.")
    .addBooleanOption((opt) =>
      opt
        .setName("history")
        .setDescription("Show the recent past instead of only what's new")
        .setRequired(false),
    ),

  async execute(interaction, ctx) {
    await interaction.deferReply({ ephemeral: true });

    const accessToken = await getValidAccessToken(interaction.user.id);
    if (!accessToken) {
      await interaction.editReply("You haven't linked your account yet — run `/link` first.");
      return;
    }

    const client = createLorenzoApiClient(ctx.config.lorenzoApiBaseUrl);
    const tenantId = ctx.config.lorenzoTenantId;

    const history = interaction.options.getBoolean("history") === true;
    // Taken *before* reading, so a change recorded while this runs is newer
    // than the marker and shows up next time rather than being skipped.
    const lookedAt = new Date();
    const since = history ? undefined : await getChangesSeenAt(interaction.user.id);

    const rows = await client.listMyChanges(tenantId, accessToken, since);
    const shown = rows.slice(0, MAX_CHANGES_SHOWN);

    // One name lookup per distinct character, not per row - several rows
    // commonly share one (a player with few characters, or several changes
    // to the same item over time).
    const names = new Map(
      await Promise.all(
        [...new Set(shown.map((row) => row.character_entity_id))].map(async (characterId) => {
          const name = await client
            .getCharacterName(tenantId, characterId, accessToken)
            .catch(() => null);
          return [characterId, name ?? "another character"] as const;
        }),
      ),
    );

    const changes = shown.map((row) => ({
      summary: describeChange({
        kind: row.kind,
        entityName: row.entity_name,
        detail: row.detail,
        character: names.get(row.character_entity_id) ?? "another character",
        actorVisible: row.actor_user_id !== null,
      }),
      createdAt: new Date(row.occurred_at),
    }));

    await interaction.editReply({
      embeds: [buildChangesEmbed({ changes, total: rows.length, since, history })],
    });

    // Housekeeping after the user has their answer: a failure to move the
    // marker is logged, never shown. Retention is the API's own job now
    // (ADR 0099) - nothing left here to prune.
    if (!history) {
      try {
        await setChangesSeenAt(interaction.user.id, lookedAt);
      } catch (error) {
        ctx.logger.warn({ err: error }, "couldn't update /changes bookkeeping");
      }
    }
  },
};
