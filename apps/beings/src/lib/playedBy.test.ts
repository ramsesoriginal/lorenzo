import { describe, expect, it } from 'vitest';
import { playedByOf, playedByText } from './playedBy';

describe('playedByOf', () => {
  it('names the players of each character, once', () => {
    const found = playedByOf([
      [{ display_name: 'Ana', characters: [{ entity_id: 'a' }, { entity_id: 'b' }] }],
      [
        { nickname: 'Joss', characters: [{ entity_id: 'b' }] },
        { display_name: 'Ana', characters: [{ entity_id: 'a' }] },
        { characters: [{ entity_id: 'c' }] },
      ],
    ]);

    expect(found.get('a')).toEqual(['Ana']);
    expect(found.get('b')).toEqual(['Ana', 'Joss']);
    expect(found.get('c')).toEqual(['A player']);
  });
});

describe('playedByText', () => {
  it('says who, or that nobody does, or nothing where the rosters are unknown', () => {
    expect(playedByText(['Ana', 'Joss'], true, true)).toBe('Ana, Joss');
    expect(playedByText(undefined, false, true)).toBe('Not played');
    expect(playedByText(undefined, true, true)).toBe('—');
    expect(playedByText(undefined, false, false)).toBe('—');
  });
});
