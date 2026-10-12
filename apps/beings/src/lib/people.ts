// Who plays a being, and handing one over (ADR 0271, 0272). The reads are the ones account-hub's
// /beings page uses (ADR 0079, 0176); who may hand over, and to whom, is the API's to say.
import { client, fetchAllPages, MAX_PAGE_SIZE, unwrap } from './api';
import { getMe, listCampaigns } from './me';
import type { CampaignPlayer, Character } from './types';

export type Person = {
  playerId: string;
  /** The player's name where the viewer may read it; "A player" where not. */
  name: string;
  campaign: string | null;
  /** The owner: the one whose character it is. The others share it (ADR 0036). */
  owner: boolean;
  you: boolean;
};

/** What a player is called: their display name, else the nickname their GM gave them. */
export const playerName = (
  player: Pick<CampaignPlayer, 'display_name' | 'nickname'> | undefined,
): string => player?.display_name || player?.nickname || 'A player';

/** The people of a character, owner first. Pure: the lookups are done by `whoPlays`. */
export function describePeople(
  character: Pick<Character, 'owner_player_id' | 'players'>,
  names: ReadonlyMap<string, string>,
  campaigns: ReadonlyMap<string, string>,
  mySeats: ReadonlySet<string>,
): Person[] {
  const people = character.players.map((seat) => ({
    playerId: seat.id,
    name: names.get(seat.id) ?? 'A player',
    campaign: campaigns.get(seat.campaign_id) ?? null,
    owner: seat.id === character.owner_player_id,
    you: mySeats.has(seat.id),
  }));

  return people.sort((a, b) => Number(b.owner) - Number(a.owner) || a.name.localeCompare(b.name));
}

/** The players of a campaign, with their names where the viewer may read them (ADR 0176). */
export async function listCampaignPlayers(
  tenantId: string,
  campaignId: string,
): Promise<CampaignPlayer[]> {
  return fetchAllPages(async (page) =>
    unwrap(
      await client.GET('/tenants/{tenant_id}/campaigns/{campaign_id}/players', {
        params: {
          path: { tenant_id: tenantId, campaign_id: campaignId },
          query: { page, size: MAX_PAGE_SIZE },
        },
      }),
    ),
  );
}

/** Who plays `character`, named as far as the viewer may know. */
export async function whoPlays(tenantId: string, character: Character): Promise<Person[]> {
  const campaignIds = [...new Set(character.players.map((seat) => seat.campaign_id))];
  const [me, campaigns, rosters] = await Promise.all([
    getMe(),
    listCampaigns(tenantId).catch(() => []),
    // A roster the viewer may not read is left out, and its players are "A player".
    Promise.all(
      campaignIds.map((id) =>
        listCampaignPlayers(tenantId, id).catch(() => [] as CampaignPlayer[]),
      ),
    ),
  ]);
  const names = new Map(rosters.flat().map((player) => [player.id, playerName(player)]));

  return describePeople(
    character,
    names,
    new Map(campaigns.map((campaign) => [campaign.id, campaign.name])),
    new Set(me.players.map((seat) => seat.id)),
  );
}

/** A new character for the library, played by nobody yet: an NPC until it is handed over. */
export async function createBeing(tenantId: string, name: string): Promise<Character> {
  return unwrap(
    await client.POST('/tenants/{tenant_id}/characters', {
      params: { path: { tenant_id: tenantId } },
      body: { name, player_ids: [] },
    }),
  );
}

/** A seat the viewer has in the library, as a choice of "which campaign is this character for". */
export type SeatOption = { seatId: string; label: string };

/**
 * One option per seat of the viewer's own, named by its campaign where the campaign can be listed
 * (the id otherwise), by name. Pure: the reads are done by the caller.
 */
export function seatOptions(
  seats: readonly { id: string; campaign_id: string }[],
  campaigns: ReadonlyMap<string, string>,
): SeatOption[] {
  return seats
    .map((seat) => ({
      seatId: seat.id,
      label: campaigns.get(seat.campaign_id) ?? seat.campaign_id,
    }))
    .sort((a, b) => a.label.localeCompare(b.label));
}

/**
 * A new character the viewer plays: made with their own seat as its owner, which the API accepts
 * from a player for a seat that is theirs (ADR 0036), so no hand-over is needed.
 */
export async function createOwnCharacter(
  tenantId: string,
  name: string,
  seatId: string,
): Promise<Character> {
  return unwrap(
    await client.POST('/tenants/{tenant_id}/characters', {
      params: { path: { tenant_id: tenantId } },
      body: { name, owner_player_id: seatId, player_ids: [] },
    }),
  );
}

/** Renames a being (its character row's own name, ADR 0079). */
export async function renameBeing(tenantId: string, entityId: string, name: string) {
  return unwrap(
    await client.PATCH('/tenants/{tenant_id}/characters/{character_id}', {
      params: { path: { tenant_id: tenantId, character_id: entityId } },
      body: { name },
    }),
  );
}

/**
 * Hands a being to a player as a played character: first it joins the player's roster, then the
 * player becomes its owner - in that order, since a linked being that isn't owned yet is
 * recoverable and the reverse is not (ADR 0079).
 */
export async function handOver(tenantId: string, entityId: string, playerId: string) {
  const path = { tenant_id: tenantId, character_id: entityId };

  await unwrap(
    await client.PUT('/tenants/{tenant_id}/characters/{character_id}/players/{player_id}', {
      params: { path: { ...path, player_id: playerId } },
    }),
  );

  return unwrap(
    await client.PATCH('/tenants/{tenant_id}/characters/{character_id}', {
      params: { path },
      body: { owner_player_id: playerId },
    }),
  );
}
