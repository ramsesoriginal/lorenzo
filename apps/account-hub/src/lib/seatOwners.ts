import { getCharacter } from './characters';
import type { MeOut } from './types';

// Who owns each character on the caller's seats in one library: the one fact
// "Stop using here" needs, and only a character read gives. A character whose
// owner could not be read is left out of the map, and gets no button rather
// than a guess.
export async function loadSeatOwners(
  tenantId: string,
  me: Pick<MeOut, 'players'>,
): Promise<Map<string, string | null>> {
  const owners = new Map<string, string | null>();
  const characterIds = new Set(
    me.players
      .filter((p) => p.tenant_id === tenantId)
      .flatMap((p) => p.characters.map((c) => c.entity_id)),
  );
  await Promise.all(
    [...characterIds].map(async (characterId) => {
      try {
        owners.set(characterId, (await getCharacter(tenantId, characterId)).owner_player_id);
      } catch {
        // Unknown: no button for it, rather than a guess.
      }
    }),
  );
  return owners;
}
