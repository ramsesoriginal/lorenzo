import { EmbedBuilder } from "discord.js";

/** How many changes one `/changes` reply lists. */
export const MAX_CHANGES_SHOWN = 25;

// 25 lines of this plus the framing lines stay inside an embed description's 4096.
const MAX_LINE_LENGTH = 150;

export type ChangeLine = Readonly<{ summary: string; createdAt: Date }>;

function relativeTimestamp(date: Date): string {
  // Discord renders <t:UNIX:R> as "3 hours ago" in each viewer's own locale.
  return `<t:${Math.floor(date.getTime() / 1000)}:R>`;
}

function line(change: ChangeLine): string {
  const text = `${relativeTimestamp(change.createdAt)} — ${change.summary}`;
  return text.length <= MAX_LINE_LENGTH ? text : `${text.slice(0, MAX_LINE_LENGTH - 1)}…`;
}

const QUANTITY_DETAIL = /^quantity=(\d+)$/;

function parseQuantity(detail: string | null): number | null {
  const match = detail ? QUANTITY_DETAIL.exec(detail) : null;
  return match?.[1] ? Number(match[1]) : null;
}

/**
 * One `GET /me/changes` row (ADR 0099), turned into a one-line description
 * from the perspective of the character it concerns - see the ADR 0097
 * addendum on the switch from this bot's own event log to the API feed.
 *
 * The actor is never named, even when `actorVisible` is true: the API only
 * gives an Authgear user id for the actor, and this bot has no endpoint
 * that turns an arbitrary id into a display name (unlike a *character*
 * name, which every other command here already resolves). "Another player"
 * is the most it can honestly say - still meaningfully different from
 * silence, since a hidden actor means a GM or tenant administrator instead.
 */
export function describeChange(args: {
  kind: string;
  entityName: string;
  detail: string | null;
  character: string;
  actorVisible: boolean;
}): string {
  const { kind, entityName, detail, character, actorVisible } = args;
  const qty = parseQuantity(detail);
  const item = qty !== null ? `${entityName} ×${qty}` : entityName;
  switch (kind) {
    case "received":
      return actorVisible
        ? `${character} received ${entityName} from another player.`
        : `${character} received ${entityName}.`;
    case "given_away":
      return actorVisible
        ? `${entityName} was taken from ${character} by another player.`
        : `${entityName} was taken from ${character}.`;
    case "moved":
      return `${character}'s ${entityName} was moved.`;
    case "split":
      return `${character}'s ${item} was split off.`;
    case "merged":
      return `${character}'s ${item} was merged in.`;
    case "renamed":
      return `${character}'s item was renamed to ${entityName}.`;
    case "deleted":
      return `${character}'s ${entityName} was deleted.`;
    default:
      return `${character}'s ${entityName} changed.`;
  }
}

/**
 * The `/changes` reply (ADR 0097, now reading ADR 0099's API feed). Pure -
 * no Discord or database calls.
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
  const embed = new EmbedBuilder().setTitle(args.history ? "Recent changes" : "What's changed");

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
