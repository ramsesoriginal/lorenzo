// What a campaign calls its game master (ADR 0294). A campaign carries `gm_title` and
// `gm_title_plural`, always set by the API ("GM" and "GMs" until the campaign names its own), so
// nothing here defaults them per campaign. A text about a being whose campaigns agree takes their
// words; a text about no one campaign, or about several that disagree, says "GM".

// The two fields a campaign row carries (CampaignOut, CampaignSummaryOut).
export type GmTitled = Readonly<{ gm_title: string; gm_title_plural: string }>;

// The words for a game master, in the singular and the plural. Written as the campaign wrote
// them: a text is worded so they read right at the start of a sentence and in the middle of one.
export type GmWords = Readonly<{ title: string; plural: string }>;

// The word of the API, of a repository's entries and of every text about no one campaign.
export const DEFAULT_GM_WORDS: GmWords = { title: 'GM', plural: 'GMs' };

/**
 * The words for the game masters of `campaigns`: their own when every campaign involved has the
 * same ones, otherwise (no campaign, or two that disagree) "GM" and "GMs". The one place that
 * decides, so no surface decides alone.
 */
export function gmWords(campaigns: readonly GmTitled[]): GmWords {
  const [first, ...rest] = campaigns;

  if (!first) return DEFAULT_GM_WORDS;

  const same = rest.every(
    (campaign) =>
      campaign.gm_title === first.gm_title && campaign.gm_title_plural === first.gm_title_plural,
  );

  return same ? { title: first.gm_title, plural: first.gm_title_plural } : DEFAULT_GM_WORDS;
}

/**
 * The words for the game masters of the campaigns a character plays in (its roster's), out of the
 * campaigns the viewer can list. A being that is no character, or in no campaign, says "GM"; so
 * does one in a campaign the viewer can't list, since then not every campaign involved is known.
 */
export function gmWordsOfBeing(
  character: Readonly<{ players: readonly Readonly<{ campaign_id: string }>[] }> | null,
  campaigns: readonly (GmTitled & Readonly<{ id: string }>)[],
): GmWords {
  if (!character) return DEFAULT_GM_WORDS;

  const involved = [...new Set(character.players.map((player) => player.campaign_id))];
  const known = involved.flatMap((id) => campaigns.filter((campaign) => campaign.id === id));

  return known.length === involved.length ? gmWords(known) : DEFAULT_GM_WORDS;
}
