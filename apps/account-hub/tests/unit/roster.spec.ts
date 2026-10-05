import { describe, expect, it } from 'vitest';
import { playerIdForUser, rosterFromPlayers } from '../../src/lib/roster';
import type { PlayerSummaryOut } from '../../src/lib/types';

function player(overrides: Partial<PlayerSummaryOut> = {}): PlayerSummaryOut {
  return {
    id: crypto.randomUUID(),
    user_id: crypto.randomUUID(),
    nickname: null,
    display_name: null,
    user_color: null,
    characters: [],
    self_service: null,
    self_service_effective: true,
    created_by: null,
    updated_by: null,
    updated_at: '2026-10-05T12:00:00Z',
    ...overrides,
  };
}

describe('rosterFromPlayers', () => {
  it('makes a roster entry of each player, in the campaign, with the names the API gave', () => {
    const cael = { entity_id: crypto.randomUUID(), name: 'Cael', is_pc: true };
    const pia = player({
      characters: [cael],
      created_by: 'gm-1',
      nickname: 'pia',
      display_name: 'Pia Player',
      user_color: '#112233',
    });
    const [entry] = rosterFromPlayers('campaign-1', [pia]);
    expect(entry).toEqual({
      kind: 'player',
      user_id: pia.user_id,
      nickname: 'pia',
      display_name: 'Pia Player',
      user_color: '#112233',
      campaign_id: 'campaign-1',
      characters: [cael],
      created_by: 'gm-1',
      updated_by: null,
    });
  });

  it('has no names for a player who set none, and the user id then stands in for one', () => {
    const [entry] = rosterFromPlayers('campaign-1', [player()]);
    expect([entry?.nickname, entry?.display_name, entry?.user_color]).toEqual([null, null, null]);
  });

  it('keeps the order, and is empty for no players', () => {
    const [a, b] = [player(), player()];
    expect(rosterFromPlayers('c', [a, b]).map((e) => e.user_id)).toEqual([a.user_id, b.user_id]);
    expect(rosterFromPlayers('c', [])).toEqual([]);
  });
});

describe('playerIdForUser', () => {
  it("finds a player's own id from their user id", () => {
    const [a, b] = [player(), player()];
    expect(playerIdForUser([a, b], b.user_id)).toBe(b.id);
  });

  it('is null for someone who is not a player here', () => {
    expect(playerIdForUser([player()], crypto.randomUUID())).toBeNull();
    expect(playerIdForUser([], 'x')).toBeNull();
  });
});
