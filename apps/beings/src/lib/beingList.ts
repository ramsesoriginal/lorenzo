// The list of beings in a library (ADR 0271): what the viewer may list, narrowed by a search and
// three filters, all in the browser over what the API gave. Who may see which being is the API's;
// nothing here widens it.
import { client, fetchAllPages, LorenzoApiError, MAX_PAGE_SIZE, unwrap } from './api';
import type { BeingSummary } from './types';

/** A being as listed: `is_pc` is null for a bare being, which no player plays. */
export type ListedBeing = BeingSummary;

export type Kind = 'all' | 'character' | 'npc';

export type Filters = {
  /** Case-insensitive part of the name. */
  search: string;
  /** A character is one a player plays; an NPC is any other being. */
  kind: Kind;
  /** Only these (the ones the viewer plays), or no such filter. */
  mine: ReadonlySet<string> | null;
  /** Only these (a campaign's roster), or no such filter. */
  campaign: ReadonlySet<string> | null;
};

export const NO_FILTERS: Filters = { search: '', kind: 'all', mine: null, campaign: null };

/** Whether a listed being is a character a player plays (not an NPC or a bare being). */
export const isCharacter = (being: ListedBeing): boolean => being.is_pc === true;

/** The beings that pass every filter, by name. */
export function filterBeings(beings: readonly ListedBeing[], filters: Filters): ListedBeing[] {
  const wanted = filters.search.trim().toLowerCase();

  return beings
    .filter((being) => {
      if (wanted && !being.name.toLowerCase().includes(wanted)) return false;
      if (filters.kind === 'character' && !isCharacter(being)) return false;
      if (filters.kind === 'npc' && isCharacter(being)) return false;
      if (filters.mine && !filters.mine.has(being.entity_id)) return false;
      if (filters.campaign && !filters.campaign.has(being.entity_id)) return false;
      return true;
    })
    .sort((a, b) => a.name.localeCompare(b.name));
}

/** What a being is called in a heading or a badge. */
export function kindLabel(being: Pick<ListedBeing, 'is_pc'>): string {
  return being.is_pc === true ? 'Character' : 'NPC';
}

/**
 * Every being the viewer may list. A library's Owners and Organizers and a campaign's GMs list
 * beings (ADR 0078, 0173); anyone else gets the library's characters, which any participant lists.
 */
export async function listBeings(tenantId: string): Promise<ListedBeing[]> {
  const path = { tenant_id: tenantId };

  try {
    return await fetchAllPages(async (page) =>
      unwrap(
        await client.GET('/tenants/{tenant_id}/beings', {
          params: { path, query: { page, size: MAX_PAGE_SIZE } },
        }),
      ),
    );
  } catch (error) {
    if (!(error instanceof LorenzoApiError) || (error.status !== 404 && error.status !== 403)) {
      throw error;
    }
  }

  return fetchAllPages(async (page) =>
    unwrap(
      await client.GET('/tenants/{tenant_id}/characters', {
        params: { path, query: { page, size: MAX_PAGE_SIZE } },
      }),
    ),
  );
}

/** The characters of a campaign's roster, by entity id (what the Campaign filter keeps). */
export async function campaignBeingIds(tenantId: string, campaignId: string): Promise<Set<string>> {
  const players = await fetchAllPages(async (page) =>
    unwrap(
      await client.GET('/tenants/{tenant_id}/campaigns/{campaign_id}/players', {
        params: {
          path: { tenant_id: tenantId, campaign_id: campaignId },
          query: { page, size: MAX_PAGE_SIZE },
        },
      }),
    ),
  );

  return new Set(
    players.flatMap((player) => player.characters.map((character) => character.entity_id)),
  );
}

/** The characters the viewer owns (mine=true, ADR 0049), by entity id. */
export async function ownedBeingIds(tenantId: string): Promise<Set<string>> {
  const owned = await fetchAllPages(async (page) =>
    unwrap(
      await client.GET('/tenants/{tenant_id}/characters', {
        params: { path: { tenant_id: tenantId }, query: { mine: true, page, size: MAX_PAGE_SIZE } },
      }),
    ),
  );

  return new Set(owned.map((character) => character.entity_id));
}
