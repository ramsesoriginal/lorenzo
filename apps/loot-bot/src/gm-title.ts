import { escapeMarkdown } from "discord.js";

/**
 * A campaign's own word for its game master (ADR 0294): `gm_title` and
 * `gm_title_plural` as `apps/api` sends them on every campaign it reads - always
 * set, "GM" and "GMs" while the campaign keeps the default.
 */
export type GmTitled = Readonly<{ gmTitle: string; gmTitlePlural: string }>;

/** The words a reply uses for a game master: the singular and the plural. */
export type GmWords = Readonly<{ singular: string; plural: string }>;

/** What the bot says wherever no one campaign is in play (ADR 0294): a library's
 * campaigns, a command that works across them, the registered slash commands. */
export const DEFAULT_GM_WORDS: GmWords = { singular: "GM", plural: "GMs" };

/**
 * The one place the bot decides what to call a game master (ADR 0294). Given the
 * campaigns a reply is about:
 *
 * - none: "GM" and "GMs" - there is no campaign whose title could apply;
 * - one, or several that all use the same title: that title;
 * - several with different titles: "GM" and "GMs", the word the API shares.
 *
 * The title is spelled as written, never re-cased. `apps/api` already refuses
 * markup in it, but it is escaped for Discord anyway so that a title can never
 * become formatting; for every character the API allows this changes nothing.
 * Wording around the result must not need an article ("a GM"), because the
 * title may begin with a vowel or be a phrase.
 */
export function gmWords(campaigns: readonly GmTitled[]): GmWords {
  const [first, ...rest] = campaigns;
  if (first === undefined) return DEFAULT_GM_WORDS;
  const same = rest.every(
    (campaign) =>
      campaign.gmTitle === first.gmTitle && campaign.gmTitlePlural === first.gmTitlePlural,
  );
  if (!same) return DEFAULT_GM_WORDS;
  return {
    singular: escapeMarkdown(first.gmTitle),
    plural: escapeMarkdown(first.gmTitlePlural),
  };
}
