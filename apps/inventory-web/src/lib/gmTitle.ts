// What a campaign calls its game master (ADR 0294). A campaign carries `gm_title` and
// `gm_title_plural`, always set by the API ("GM" and "GMs" until the campaign names its own), so
// nothing here defaults them per campaign. Every text about a campaign's things takes its words
// from `gmWords`; a text about no one campaign, or about several that disagree, says "GM".
import { client, fetchAllPages, MAX_PAGE_SIZE, unwrap } from './api';
import { seatsIn } from './me';

// The two fields a campaign row carries (CampaignOut, CampaignSummaryOut).
export type GmTitled = Readonly<{ gm_title: string; gm_title_plural: string }>;

// The words for a game master, in the singular and the plural. Written as the campaign wrote
// them: a text is worded so they read right at the start of a sentence and in the middle of one.
export type GmWords = Readonly<{ title: string; plural: string }>;

// The word of the API, of a library's catalog and of every text about no one campaign.
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

// A tenant's campaigns, fetched once per page; a failure isn't kept.
const campaignLists = new Map<string, Promise<readonly (GmTitled & { id: string })[]>>();

function campaignsOf(tenantId: string) {
  let known = campaignLists.get(tenantId);

  if (!known) {
    known = fetchAllPages(async (page) =>
      unwrap(
        await client.GET('/tenants/{tenant_id}/campaigns', {
          params: { path: { tenant_id: tenantId }, query: { page, size: MAX_PAGE_SIZE } },
        }),
      ),
    );
    known.catch(() => campaignLists.delete(tenantId));
    campaignLists.set(tenantId, known);
  }

  return known;
}

// The campaigns a being plays in, as ids: its roster's, else the viewer's own seats that hold it.
async function campaignIdsOf(tenantId: string, entityId: string): Promise<string[]> {
  try {
    const character = await unwrap(
      await client.GET('/tenants/{tenant_id}/characters/{character_id}', {
        params: { path: { tenant_id: tenantId, character_id: entityId } },
      }),
    );

    return character.players.map((player) => player.campaign_id);
  } catch {
    const seats = await seatsIn(tenantId);

    return seats
      .filter((seat) => seat.characters.some((c) => c.entity_id === entityId))
      .map((seat) => seat.campaign_id);
  }
}

const beingWords = new Map<string, Promise<GmWords>>();

/**
 * The words for the game masters of the campaigns a being is in, which is what a text about it
 * or about what it holds says. "GM" when it has no known campaign (a bare being, none given) or
 * when they can't be read: never knowing is not a reason to fail a surface.
 */
export function gmWordsOfBeing(tenantId: string, entityId: string | null): Promise<GmWords> {
  if (!entityId) return Promise.resolve(DEFAULT_GM_WORDS);

  const key = `${tenantId}/${entityId}`;
  let known = beingWords.get(key);

  if (!known) {
    known = (async () => {
      try {
        const [campaigns, ids] = await Promise.all([
          campaignsOf(tenantId),
          campaignIdsOf(tenantId, entityId),
        ]);
        const wanted = new Set(ids);

        return gmWords(campaigns.filter((campaign) => wanted.has(campaign.id)));
      } catch {
        // Not remembered: the next surface asks again.
        beingWords.delete(key);

        return DEFAULT_GM_WORDS;
      }
    })();
    beingWords.set(key, known);
  }

  return known;
}
