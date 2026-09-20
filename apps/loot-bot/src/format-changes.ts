import { EmbedBuilder } from "discord.js";

/** How many changes one `/changes` reply lists. */
export const MAX_CHANGES_SHOWN = 25;

// 25 lines of this plus the framing lines stay inside an embed description's 4096.
const MAX_LINE_LENGTH = 150;

/** Shown on every reply, empty or not: `/changes` can only report what this
 * bot itself saw (ADR 0096), and an empty list must not read as "nothing
 * happened". */
export const COVERAGE_NOTE =
  "Only changes made through this bot are shown — anything done in the web apps won't appear here.";

export type ChangeLine = Readonly<{ summary: string; createdAt: Date }>;

function relativeTimestamp(date: Date): string {
  // Discord renders <t:UNIX:R> as "3 hours ago" in each viewer's own locale.
  return `<t:${Math.floor(date.getTime() / 1000)}:R>`;
}

function line(change: ChangeLine): string {
  const text = `${relativeTimestamp(change.createdAt)} — ${change.summary}`;
  return text.length <= MAX_LINE_LENGTH ? text : `${text.slice(0, MAX_LINE_LENGTH - 1)}…`;
}

/**
 * The `/changes` reply (ADR 0096). Pure - no Discord or database calls.
 *
 * - `since` is when the user last looked (`undefined` for a first look, or
 *   when they asked for `history`).
 * - `total` counts every matching change, so it can say how many a
 *   {@link MAX_CHANGES_SHOWN}-line reply left out.
 */
export function buildChangesEmbed(args: {
  changes: readonly ChangeLine[];
  total: number;
  since: Date | undefined;
  history: boolean;
}): EmbedBuilder {
  const embed = new EmbedBuilder()
    .setTitle(args.history ? "Recent changes" : "What's changed")
    .setFooter({ text: COVERAGE_NOTE });

  if (args.changes.length === 0) {
    if (args.history || !args.since) {
      return embed.setDescription("Nothing recorded yet.");
    }
    return embed.setDescription(
      `Nothing new since you last looked ${relativeTimestamp(args.since)}. Run \`/changes history:true\` to see the recent past.`,
    );
  }

  const lines = args.changes.map(line);
  const omitted = args.total - args.changes.length;
  if (omitted > 0) {
    lines.push(`…and ${omitted} older ${omitted === 1 ? "change" : "changes"} not shown.`);
  }
  if (!args.history && args.since) {
    lines.unshift(`Since you last looked ${relativeTimestamp(args.since)}:`);
  }
  return embed.setDescription(lines.join("\n"));
}
