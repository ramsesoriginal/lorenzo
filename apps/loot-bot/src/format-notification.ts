import { EmbedBuilder } from "discord.js";

/**
 * How Lorenzo notifications look in Discord (ADR 0095) - pure builders, no
 * Discord API calls, mirroring format-drop.ts's split from drop.ts.
 */

// Discord's own limits: 256 for an embed title, 4096 for its description,
// 2000 for a plain message's content.
const MAX_TITLE_LENGTH = 256;
const MAX_DESCRIPTION_LENGTH = 4096;
const MAX_MESSAGE_LENGTH = 2000;

/** Each notification's own line in the banner - a snippet, since the whole
 * text is one click away in Lorenzo itself. */
const BANNER_SNIPPET_LENGTH = 160;

/** How many undelivered notifications one banner lists; the rest are
 * counted and shown on later commands. */
export const BANNER_MAX_ENTRIES = 5;

export type NotificationText = Readonly<{ title: string; body: string }>;

function truncate(text: string, max: number): string {
  return text.length <= max ? text : `${text.slice(0, max - 1)}…`;
}

/** The DM itself: the notification's own title and body, as a Discord embed. */
export function buildNotificationEmbed(
  notification: NotificationText & Readonly<{ scope: string }>,
): EmbedBuilder {
  return new EmbedBuilder()
    .setTitle(truncate(notification.title, MAX_TITLE_LENGTH))
    .setDescription(truncate(notification.body, MAX_DESCRIPTION_LENGTH))
    .setFooter({ text: `Lorenzo · ${notification.scope} notification` });
}

export type UndeliveredNotice = NotificationText & Readonly<{ notificationId: string }>;

export type BannerContent = Readonly<{
  content: string;
  /** Which notifications the text actually shows - the only ones that may be
   * marked as noticed; the rest stay queued for the next command. */
  shownIds: readonly string[];
}>;

/**
 * The ephemeral "couldn't DM you" banner shown after a user's next command
 * when Discord wouldn't let the bot message them (ADR 0095). It exists so a
 * missed award is "found out, just not by DM" instead of silently missed.
 *
 * Lists up to {@link BANNER_MAX_ENTRIES} notifications, oldest first, each as
 * title plus a snippet; if more are waiting it says so rather than dropping
 * them (they appear on later commands). Always fits Discord's 2000-character
 * message limit. Returns `undefined` when there's nothing to show.
 */
export function buildUndeliveredBanner(
  notices: readonly UndeliveredNotice[],
): BannerContent | undefined {
  if (notices.length === 0) return undefined;

  const shown = notices.slice(0, BANNER_MAX_ENTRIES);
  const lines = shown.map((notice) => {
    const snippet = truncate(notice.body.replace(/\s+/g, " ").trim(), BANNER_SNIPPET_LENGTH);
    return snippet ? `• **${notice.title}** — ${snippet}` : `• **${notice.title}**`;
  });

  const noun = notices.length === 1 ? "notification" : "notifications";
  const intro = `**Couldn't DM you.** Lorenzo has ${notices.length} ${noun} for you that Discord wouldn't let me send privately (your DMs from server members may be off). Here ${notices.length === 1 ? "it is" : "they are"}:`;
  const remaining = notices.length - shown.length;
  const outro =
    remaining > 0
      ? `…and ${remaining} more, which I'll show on your next commands. They're all in your Lorenzo notifications too.`
      : "They're in your Lorenzo notifications too.";

  return {
    content: truncate([intro, ...lines, outro].join("\n"), MAX_MESSAGE_LENGTH),
    shownIds: shown.map((notice) => notice.notificationId),
  };
}
