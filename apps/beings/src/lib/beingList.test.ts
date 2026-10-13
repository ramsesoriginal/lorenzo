import { describe, expect, it, vi } from 'vitest';

// The sign-in library needs a browser; nothing here signs in.
vi.mock('./auth', () => ({ getAccessToken: vi.fn() }));

import { filterBeings, isCharacter, kindLabel, NO_FILTERS } from './beingList';

const beings = [
  { entity_id: 'a', name: 'Ashfang', is_pc: true },
  { entity_id: 'b', name: 'Borin', is_pc: true },
  { entity_id: 'c', name: 'Goblin Chief', is_pc: false },
  { entity_id: 'd', name: 'A bare stub', is_pc: null },
];

describe('filterBeings', () => {
  it('lists every being by name when nothing is filtered', () => {
    expect(filterBeings(beings, NO_FILTERS).map((b) => b.name)).toEqual([
      'A bare stub',
      'Ashfang',
      'Borin',
      'Goblin Chief',
    ]);
  });

  it('searches the name, ignoring case', () => {
    expect(
      filterBeings(beings, { ...NO_FILTERS, search: ' GOB ' }).map((b) => b.entity_id),
    ).toEqual(['c']);
  });

  it('keeps characters, or everything else as NPCs', () => {
    const ids = (kind: 'character' | 'npc') =>
      filterBeings(beings, { ...NO_FILTERS, kind }).map((b) => b.entity_id);

    expect(ids('character')).toEqual(['a', 'b']);
    expect(ids('npc')).toEqual(['d', 'c']);
  });

  it('keeps the ones the viewer plays, and a campaign roster, together', () => {
    const filters = {
      ...NO_FILTERS,
      mine: new Set(['a', 'c']),
      campaign: new Set(['a', 'b']),
    };

    expect(filterBeings(beings, filters).map((b) => b.entity_id)).toEqual(['a']);
  });
});

describe('kindLabel', () => {
  it('calls a played one a character and any other an NPC', () => {
    expect(kindLabel(beings[0] as (typeof beings)[number])).toBe('Character');
    expect(kindLabel({ is_pc: null })).toBe('NPC');
    expect(isCharacter({ entity_id: 'x', name: 'x', is_pc: false })).toBe(false);
  });
});
