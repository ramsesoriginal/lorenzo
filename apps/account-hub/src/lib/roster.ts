// Pure helpers over a campaign's players, for the roster view's controls
// (ADR 0170). Dependency-free like format.ts.
import type { PlayerRosterEntryOut, PlayerSummaryOut } from './types';

// A campaign's players as roster entries, for a GM with no library membership:
// the roster itself is a library admins' read, but GET .../players is open to
// whoever can reach the campaign, and carries each player's names since ADR 0176
// (null when they set none, which resolveDisplayName then shows as the user id).
export function rosterFromPlayers(
  campaignId: string,
  players: PlayerSummaryOut[],
): PlayerRosterEntryOut[] {
  return players.map((player) => ({
    kind: 'player',
    user_id: player.user_id,
    nickname: player.nickname,
    display_name: player.display_name,
    user_color: player.user_color,
    campaign_id: campaignId,
    characters: player.characters,
    created_by: player.created_by,
    updated_by: player.updated_by,
  }));
}

// A roster entry has a user id and no player id, and removing a player (or a
// character link) needs the player's own id. One user is at most one player in
// a campaign, so the campaign's players (GET .../players) give it by user id.
export function playerIdForUser(players: PlayerSummaryOut[], userId: string): string | null {
  return players.find((player) => player.user_id === userId)?.id ?? null;
}
