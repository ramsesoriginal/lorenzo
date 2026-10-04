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
    created_by: null,
    updated_by: null,
    ...overrides,
  };
}

describe('rosterFromPlayers', () => {
  it('makes a roster entry of each player, in the campaign, with no names', () => {
    const cael = { entity_id: crypto.randomUUID(), name: 'Cael', is_pc: true };
    const pia = player({ characters: [cael], created_by: 'gm-1' });
    const [entry] = rosterFromPlayers('campaign-1', [pia]);
    expect(entry).toEqual({
      kind: 'player',
      user_id: pia.user_id,
      nickname: null,
      display_name: null,
      user_color: null,
      campaign_id: 'campaign-1',
      characters: [cael],
      created_by: 'gm-1',
      updated_by: null,
    });
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
