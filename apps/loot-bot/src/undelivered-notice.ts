import type { Logger } from "pino";
import type { ChatInputCommandInteraction } from "./commands/types.js";
import { listUndeliveredNotifications, markNotificationsNoticed } from "./db.js";
import { buildUndeliveredBanner } from "./format-notification.js";

/**
 * The "couldn't DM you" fallback (ADR 0095): after any command a user runs,
 * if the notification bridge has notifications Discord wouldn't let it DM
 * them, show them once, privately, right here.
 *
 * Without this, a user with DMs closed would simply never learn they'd been
 * awarded something - the difference between "missed it silently" and "found
 * out, just not by DM".
 *
 * Sent as an ephemeral follow-up *after* the command has answered, not
 * spliced into the command's own reply: commands own their replies, and a
 * follow-up works the same for every one of them. Marked as noticed only
 * once it has actually been sent.
 *
 * Best-effort by design: it runs after the user's real command already
 * succeeded, so any failure (the database, Discord) is logged and swallowed
 * - a notice problem must never turn a working command into an error.
 */
export async function showUndeliveredNotice(
  interaction: ChatInputCommandInteraction,
  logger: Logger,
): Promise<void> {
  try {
    // A follow-up needs the interaction to have been answered already.
    if (!interaction.deferred && !interaction.replied) return;

    const undelivered = await listUndeliveredNotifications(interaction.user.id);
    const banner = buildUndeliveredBanner(
      undelivered.map((row) => ({
        notificationId: row.notificationId,
        title: row.title ?? "(untitled)",
        body: row.body ?? "",
      })),
    );
    if (!banner) return;

    await interaction.followUp({ content: banner.content, ephemeral: true });
    await markNotificationsNoticed(interaction.user.id, banner.shownIds);
  } catch (error) {
    logger.warn(
      { err: error, discordUserId: interaction.user.id },
      "couldn't show undelivered notice",
    );
  }
}
