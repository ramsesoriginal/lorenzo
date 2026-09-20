import { SlashCommandBuilder } from "discord.js";
import {
  getChangesSeenAt,
  listCharacterEvents,
  pruneCharacterEvents,
  setChangesSeenAt,
} from "../db.js";
import { MAX_CHANGES_SHOWN, buildChangesEmbed } from "../format-changes.js";
import { createLorenzoApiClient } from "../lorenzo-client.js";
import { getValidAccessToken } from "../token-provider.js";
import type { Command } from "./types.js";

/** How long recorded changes are kept. The log is a convenience view, not a
 * ledger, so it doesn't grow forever. */
const RETENTION_MS = 90 * 24 * 60 * 60 * 1000;

/**
 * `/changes` - what happened to your characters' belongings since you last
 * looked (ADR 0096): gives (made or received), bulk gives, awards,
 * confiscations, reassignments, and loot drop takes and honored claims.
 * Distinct from a GM's tenant activity log (ADR 0063), which is admin-only
 * and covers none of these.
 *
 * **Bot-recorded only, and it says so** (every reply carries a note): the
 * API has no per-player change feed, so anything done through the web apps or
 * the API directly can't appear here. RFC 0022 is the proposal that would
 * make it complete.
 *
 * Reads events for *the caller's own characters* (`getControlledCharacters`,
 * as the caller) - the bot can't look up who plays a character, but a player
 * can always list theirs. "Since you last looked" is a per-user marker moved
 * each time this runs; `history:true` ignores it and doesn't move it.
 * Private (ephemeral).
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
    const characters = await client.getControlledCharacters(
      ctx.config.lorenzoTenantId,
      accessToken,
    );
    if (characters.length === 0) {
      await interaction.editReply("You don't control any characters here yet.");
      return;
    }

    const history = interaction.options.getBoolean("history") === true;
    // Taken *before* reading, so a change recorded while this runs is newer
    // than the marker and shows up next time rather than being skipped.
    const lookedAt = new Date();
    const since = history ? undefined : await getChangesSeenAt(interaction.user.id);

    const { events, total } = await listCharacterEvents(
      characters.map((c) => c.entityId),
      { since, limit: MAX_CHANGES_SHOWN },
    );

    await interaction.editReply({
      embeds: [
        buildChangesEmbed({
          changes: events.map((e) => ({ summary: e.summary, createdAt: e.createdAt })),
          total,
          since,
          history,
        }),
      ],
    });

    // Housekeeping after the user has their answer: a failure to move the
    // marker or prune old rows is logged, never shown.
    try {
      if (!history) await setChangesSeenAt(interaction.user.id, lookedAt);
      await pruneCharacterEvents(new Date(lookedAt.getTime() - RETENTION_MS));
    } catch (error) {
      ctx.logger.warn({ err: error }, "couldn't update /changes bookkeeping");
    }
  },
};
