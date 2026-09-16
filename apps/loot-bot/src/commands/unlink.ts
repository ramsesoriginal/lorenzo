import { SlashCommandBuilder } from "discord.js";
import { deleteLinkedAccount, getLinkedAccount } from "../db.js";
import type { Command } from "./types.js";

/**
 * `/unlink` - deletes the caller's `linked_account` row. No Authgear-side
 * token revocation call - out of scope, same as `/link`'s own existing
 * scope (ADR 0042). Re-running `/link` already covers re-linking with a
 * different identity, so this is the one piece that was still missing:
 * disconnecting without immediately reconnecting.
 */
export const unlinkCommand: Command = {
  definition: new SlashCommandBuilder()
    .setName("unlink")
    .setDescription("Unlink your Discord account from your Lorenzo identity."),

  async execute(interaction) {
    await interaction.deferReply({ ephemeral: true });

    const existing = await getLinkedAccount(interaction.user.id);
    if (!existing) {
      await interaction.editReply("You don't have a linked account.");
      return;
    }

    await deleteLinkedAccount(interaction.user.id);
    await interaction.editReply("Unlinked your account. Run `/link` again to reconnect.");
  },
};
