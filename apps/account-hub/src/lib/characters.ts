import { client, unwrap } from './api';
import { cached } from './cache';
import type {
  BeingSummaryOut,
  CharacterCreate,
  CharacterOut,
  CharacterUpdate,
  Page,
} from './types';

// No pager UI yet (matches notifications.ts/tenants.ts's own precedent).
const PAGE_SIZE = 50;

// Every Being in the tenant, not just ones with a Character row - see ADR
// 0078/0079. Replaces an earlier list-characters-and-filter workaround
// from before this endpoint existed.
export async function listBeings(tenantId: string, q?: string): Promise<Page<BeingSummaryOut>> {
  const fetchBeings = async () =>
    unwrap(
      await client.GET('/tenants/{tenant_id}/beings', {
        params: { path: { tenant_id: tenantId }, query: { page: 1, size: PAGE_SIZE, q } },
      }),
    );

  // Only the whole list is held; what a search turns up is asked for each time.
  return q ? fetchBeings() : cached(`beings:${tenantId}`, fetchBeings);
}

export async function createCharacter(
  tenantId: string,
  body: CharacterCreate,
): Promise<CharacterOut> {
  return unwrap(
    await client.POST('/tenants/{tenant_id}/characters', {
      params: { path: { tenant_id: tenantId } },
      body: body,
    }),
  );
}

export async function updateCharacter(
  tenantId: string,
  characterId: string,
  body: CharacterUpdate,
): Promise<CharacterOut> {
  return unwrap(
    await client.PATCH('/tenants/{tenant_id}/characters/{character_id}', {
      params: { path: { tenant_id: tenantId, character_id: characterId } },
      body: body,
    }),
  );
}

// Roster-link a character to an additional player row - idempotent (ADR
// 0036/RFC 0007). Shared by both RFC 0014 roster-reuse sub-slices: a
// player reusing their own character across campaigns, and a GM handing
// an existing being to a player (see ADR 0079).
export async function linkCharacterToPlayer(
  tenantId: string,
  characterId: string,
  playerId: string,
): Promise<CharacterOut> {
  return unwrap(
    await client.PUT('/tenants/{tenant_id}/characters/{character_id}/players/{player_id}', {
      params: { path: { tenant_id: tenantId, character_id: characterId, player_id: playerId } },
    }),
  );
}

// Readable by any tenant participant, a player included, and the only place a
// character's owner_player_id is given.
export async function getCharacter(tenantId: string, characterId: string): Promise<CharacterOut> {
  return cached(`character:${tenantId}:${characterId}`, async () =>
    unwrap(
      await client.GET('/tenants/{tenant_id}/characters/{character_id}', {
        params: { path: { tenant_id: tenantId, character_id: characterId } },
      }),
    ),
  );
}

// The reverse of linkCharacterToPlayer (ADR 0079): removes one roster link and
// leaves the character, and every other link, alone. Who may: the player whose
// row it is, or whoever can manage that player's campaign.
export async function unlinkCharacterFromPlayer(
  tenantId: string,
  characterId: string,
  playerId: string,
): Promise<CharacterOut> {
  return unwrap(
    await client.DELETE('/tenants/{tenant_id}/characters/{character_id}/players/{player_id}', {
      params: { path: { tenant_id: tenantId, character_id: characterId, player_id: playerId } },
    }),
  );
}
