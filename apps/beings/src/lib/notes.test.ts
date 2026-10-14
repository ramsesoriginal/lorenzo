import { describe, expect, it, vi } from 'vitest';

// The sign-in library needs a browser; nothing here signs in.
vi.mock('./auth', () => ({ getAccessToken: vi.fn() }));

import {
  audienceLabel,
  audienceOf,
  EVERYONE_NOTE_IN_REPOSITORY,
  type Knower,
  moved,
  planAudience,
  reordered,
  showsLock,
} from './notes';

const entity = (id: string): Knower => ({
  kind: 'entity',
  knower_entity_id: id,
  name: id,
  granted_at: '',
});
const player = (id: string): Knower => ({
  kind: 'player',
  player_id: id,
  name: id,
  granted_at: '',
});

describe('audienceOf', () => {
  it('reads the four audiences from is_public and the knowers', () => {
    expect(audienceOf({ is_public: true }, [], 'b')).toBe('everyone');
    expect(audienceOf({ is_public: false }, [], 'b')).toBe('gm');
    expect(audienceOf({ is_public: false }, [entity('b')], 'b')).toBe('player');
    expect(audienceOf({ is_public: false }, [entity('c')], 'b')).toBe('some');
    expect(audienceOf({ is_public: false }, [entity('b'), entity('c')], 'b')).toBe('some');
    expect(audienceOf({ is_public: false }, [player('p')], 'b')).toBe('some');
  });

  it('says it is shared when the viewer cannot list who was told', () => {
    expect(audienceLabel(audienceOf({ is_public: false }, null, 'b'))).toBe('Shared with you');
    expect(audienceLabel('player')).toBe('Player note');
  });
});

describe('planAudience', () => {
  it('makes a GM-only note by taking everyone told away', () => {
    expect(
      planAudience({ audience: 'gm', characters: [] }, [entity('c'), player('p')], 'b'),
    ).toEqual({
      isPublic: false,
      add: [],
      remove: ['c'],
      removePlayers: ['p'],
    });
  });

  it('tells the being for a player note, and only the chosen for some characters', () => {
    expect(planAudience({ audience: 'player', characters: [] }, [], 'b')).toMatchObject({
      isPublic: false,
      add: ['b'],
    });
    expect(
      planAudience({ audience: 'some', characters: ['c', 'd'] }, [entity('c'), entity('e')], 'b'),
    ).toEqual({ isPublic: false, add: ['d'], remove: ['e'], removePlayers: [] });
  });

  it('keeps the knowers when it becomes public, and wants a character for some', () => {
    expect(planAudience({ audience: 'everyone', characters: [] }, [entity('c')], 'b')).toEqual({
      isPublic: true,
      add: [],
      remove: [],
      removePlayers: [],
    });
    expect(() => planAudience({ audience: 'some', characters: [] }, [], 'b')).toThrow(
      /at least one/,
    );
  });
});

describe('order', () => {
  it('puts the notes in their new order in the places notes held', () => {
    expect(reordered(['d', 'n1', 'p', 'n2'], ['n2', 'n1'])).toEqual(['d', 'n2', 'p', 'n1']);
  });

  it('moves one up or down, and leaves the ends alone', () => {
    expect(moved(['a', 'b', 'c'], 2, 1)).toEqual(['a', 'c', 'b']);
    expect(moved(['a', 'b', 'c'], 0, -1)).toEqual(['a', 'b', 'c']);
    expect(moved(['a', 'b', 'c'], 2, 3)).toEqual(['a', 'b', 'c']);
  });
});

describe('the lock on a note', () => {
  it("is on an Everyone's note in a repository, and nowhere else", () => {
    expect(showsLock(true, { is_public: true })).toBe(true);
    expect(showsLock(true, { is_public: false })).toBe(false);
    expect(showsLock(false, { is_public: true })).toBe(false);
    expect(showsLock(undefined, { is_public: true })).toBe(false);
    expect(EVERYONE_NOTE_IN_REPOSITORY).toBe('Visible to libraries that copy this');
  });
});
