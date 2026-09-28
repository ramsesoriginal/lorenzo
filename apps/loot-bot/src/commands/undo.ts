import { SlashCommandBuilder } from "discord.js";
import { LorenzoApiError, createLorenzoApiClient } from "../lorenzo-client.js";
import { getValidAccessToken } from "../token-provider.js";
import { applyPendingUndo } from "../undo-actions.js";
import type { Command } from "./types.js";

/**
 * `/undo` - reverses the caller's own last undoable write (ADR 0068):
 * `/give`, `/reassign`, `/move`, `/rename`, or `/merge`. Not `/confiscate`
 * (a destroyed instance's id is gone - see `undo-actions.ts`'s own
 * docstring) and not older than a short TTL - this is "I just made a
 * mistake," not a history browser.
 */
export const undoCommand: Command = {
  definition: new SlashCommandBuilder()
    .setName("undo")
    .setDescription("Undo your own last give, reassign, move, rename, or merge."),

  async execute(interaction, ctx) {
    await interaction.deferReply({ ephemeral: true });

    const accessToken = await getValidAccessToken(interaction.user.id);
    if (!accessToken) {
      await interaction.editReply("You haven't linked your account yet — run `/link` first.");
      return;
    }

    const client = createLorenzoApiClient(ctx.config.lorenzoApiBaseUrl);
    const tenantId = ctx.config.lorenzoTenantId;
    let outcome: Awaited<ReturnType<typeof applyPendingUndo>>;
    try {
      outcome = await applyPendingUndo(client, tenantId, interaction.user.id, accessToken);
    } catch (error) {
      // Undoing a give is giving it back, which only its new owner or a GM may (ADR 0124).
      if (error instanceof LorenzoApiError && error.problemType === "item-not-yours-to-give") {
        await interaction.editReply(
          "That's someone else's now — only its new owner or a GM can give it back.",
        );
        return;
      }
      // What's bound or doesn't fit, in the API's words (ADR 0128, 0129).
      if (error instanceof LorenzoApiError && error.status === 409) {
        await interaction.editReply(error.message);
        return;
      }
      throw error;
    }

    switch (outcome.kind) {
      case "none":
        await interaction.editReply("Nothing to undo.");
        return;
      case "expired":
        await interaction.editReply("That action is too old to undo now.");
        return;
      case "undone":
        await interaction.editReply(outcome.description);
    }
  },
};
