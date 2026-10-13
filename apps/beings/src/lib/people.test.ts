import { describe, expect, it, vi } from 'vitest';

// The sign-in library needs a browser; nothing here signs in.
vi.mock('./auth', () => ({ getAccessToken: vi.fn() }));

import { describePeople, playerName, seatOptions } from './people';

const seat = (id: string, campaign_id: string) => ({
  id,
  campaign_id,
  tenant_id: 't',
  characters: [],
});

describe('describePeople', () => {
  const character = {
    owner_player_id: 'p2',
    players: [seat('p1', 'c1'), seat('p2', 'c1'), seat('p3', 'c2')],
  };
  const people = describePeople(
    character,
    new Map([
      ['p1', 'Oskar'],
      ['p2', 'Pia'],
    ]),
    new Map([['c1', 'Hood']]),
    new Set(['p1']),
  );

  it('puts the owner first, then the others by name', () => {
    expect(people.map((p) => p.playerId)).toEqual(['p2', 'p3', 'p1']);
  });

  it('names who the viewer may not read as a player, and marks the viewer', () => {
    expect(people.find((p) => p.playerId === 'p3')).toMatchObject({
      name: 'A player',
      campaign: null,
    });
    expect(people.find((p) => p.playerId === 'p1')).toMatchObject({ you: true, campaign: 'Hood' });
    expect(people[0]).toMatchObject({ owner: true, name: 'Pia' });
  });
});

describe('playerName', () => {
  it('prefers the display name, then the nickname', () => {
    expect(playerName({ display_name: 'Pia', nickname: 'P' })).toBe('Pia');
    expect(playerName({ display_name: null, nickname: 'P' })).toBe('P');
    expect(playerName(undefined)).toBe('A player');
  });
});

describe('seatOptions', () => {
  const names = new Map([
    ['c1', 'The Sunken Crown'],
    ['c2', 'Ashes of Verrin'],
  ]);

  it("names each of the viewer's seats by its campaign, by name", () => {
    expect(
      seatOptions(
        [
          { id: 's1', campaign_id: 'c1' },
          { id: 's2', campaign_id: 'c2' },
        ],
        names,
      ),
    ).toEqual([
      { seatId: 's2', label: 'Ashes of Verrin' },
      { seatId: 's1', label: 'The Sunken Crown' },
    ]);
  });

  it('falls back to the campaign id where the campaign cannot be listed', () => {
    expect(seatOptions([{ id: 's9', campaign_id: 'c-unknown' }], names)).toEqual([
      { seatId: 's9', label: 'c-unknown' },
    ]);
  });
});
