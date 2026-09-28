// Groups (ADR 0028/0045) can own things (ADR 0124): they're offered wherever a
// being is given something, and a member opens their group's board.
import { client, fetchAllPages, MAX_PAGE_SIZE, unwrap } from './api';
import type { BeingRef, CharacterSummary } from './types';

const tenantGroups = new Map<string, Promise<BeingRef[]>>();

/** Every group in the tenant (any participant may list them), fetched once per page. */
export function listGroups(tenantId: string): Promise<BeingRef[]> {
  const known = tenantGroups.get(tenantId);
  if (known) return known;
  const loading = fetchAllPages(async (page) =>
    unwrap(
      await client.GET('/tenants/{tenant_id}/groups', {
        params: { path: { tenant_id: tenantId }, query: { page, size: MAX_PAGE_SIZE } },
      }),
    ),
  ).then((groups) => groups.map((g) => ({ entity_id: g.id, name: g.name })));
  loading.catch(() => tenantGroups.delete(tenantId));
  tenantGroups.set(tenantId, loading);
  return loading;
}

/** The groups any of `characters` belongs to, each once, by name. */
export async function groupsOf(
  tenantId: string,
  characters: CharacterSummary[],
): Promise<BeingRef[]> {
  const perCharacter = await Promise.all(
    characters.map(async (character) =>
      unwrap(
        await client.GET('/tenants/{tenant_id}/characters/{character_id}/groups', {
          params: { path: { tenant_id: tenantId, character_id: character.entity_id } },
        }),
      ),
    ),
  );
  const byId = new Map<string, BeingRef>();
  for (const group of perCharacter.flat()) {
    byId.set(group.id, { entity_id: group.id, name: group.name });
  }
  return [...byId.values()].sort((a, b) => a.name.localeCompare(b.name));
}

/** Groups whose name contains `query`, case-insensitively - for a being search. */
export function matchingGroups(groups: BeingRef[], query: string): BeingRef[] {
  const wanted = query.trim().toLowerCase();
  if (!wanted) return [];
  return groups.filter((g) => g.name.toLowerCase().includes(wanted));
}
