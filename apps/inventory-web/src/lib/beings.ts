import { client, fetchAllPages, MAX_PAGE_SIZE, unwrap } from './api';
import { isTenantMember } from './me';
import type { BeingSummary, Page } from './types';

// GET /tenants/{t}/beings (ADR 0078) - every Being in the tenant: PCs,
// NPCs, and bare beings with no Character row at all, invisible to
// GET .../characters. The "pick a being" discovery step for a GM
// assigning loot to an NPC that was never promoted into a tracked
// Character. Supports search (`q`), unlike the old characters roster.
//
// It needs a tenant membership, which a player doesn't have. A player
// searches the tenant's characters instead, which any participant may
// list, so they can still give something to the rest of the party.
export async function listBeings(tenantId: string, query = ''): Promise<Page<BeingSummary>> {
  if (!(await isTenantMember(tenantId))) return searchCharacters(tenantId, query);
  return unwrap(
    await client.GET('/tenants/{tenant_id}/beings', {
      params: { path: { tenant_id: tenantId }, query: { q: query || undefined } },
    }),
  );
}

async function searchCharacters(tenantId: string, query: string): Promise<Page<BeingSummary>> {
  const characters = await fetchAllPages(async (page) =>
    unwrap(
      await client.GET('/tenants/{tenant_id}/characters', {
        params: { path: { tenant_id: tenantId }, query: { page, size: MAX_PAGE_SIZE } },
      }),
    ),
  );
  const wanted = query.trim().toLowerCase();
  const items = characters.filter((character) => character.name.toLowerCase().includes(wanted));
  return { items, total: items.length, page: 1, size: items.length, pages: 1 };
}
