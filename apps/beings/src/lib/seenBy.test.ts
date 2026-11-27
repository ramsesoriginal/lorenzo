import { describe, expect, it } from 'vitest';
import { audienceFor, whoOf, whoText } from './seenBy';

const open = { is_public: true, entity_ids: [], player_ids: [] };
const closed = { is_public: false, entity_ids: [], player_ids: [] };
const some = { is_public: false, entity_ids: [], player_ids: ['p1'] };

describe('who sees a being', () => {
  it('reads an audience as everyone, game masters only, or named people', () => {
    expect(whoOf(open)).toBe('everyone');
    expect(whoOf(closed)).toBe('gm');
    expect(whoOf(some)).toBe('named');
    expect(whoOf({ is_public: false })).toBe('gm');
  });

  it('says the audience a choice means, and keeps named people as they were', () => {
    expect(audienceFor('everyone', some)).toEqual(open);
    expect(audienceFor('gm', some)).toEqual(closed);
    expect(audienceFor('named', some)).toBe(some);
  });

  it('names the game masters as the campaign does', () => {
    expect(whoText('gm', { title: 'Narrator', plural: 'Narrators' }).label).toBe('Narrators only');
    expect(whoText('everyone', { title: 'GM', plural: 'GMs' }).label).toBe('Everyone');
  });
});
