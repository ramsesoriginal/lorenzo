import { describe, expect, it, vi } from 'vitest';

// The sign-in library needs a browser; nothing here signs in.
vi.mock('./auth', () => ({ getAccessToken: vi.fn() }));

import { DEFAULT_GM_WORDS } from './gmTitle';
import {
  audienceLabel,
  audienceOf,
  audienceTexts,
  EVERYONE_NOTE_IN_REPOSITORY,
  type Knower,
  moved,
  planAudience,
  reordered,
  showsLock,
} from './notes';

const GMS = DEFAULT_GM_WORDS;
const STORYTELLERS = { title: 'Storyteller', plural: 'Storytellers' };

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
    expect(audienceLabel(audienceOf({ is_public: false }, null, 'b'), GMS)).toBe('Shared with you');
    expect(audienceLabel('player', GMS)).toBe('Player note');
  });
});

describe('planAudience', () => {
  it('makes a GM-only note by taking everyone told away', () => {
    expect(
      planAudience({ audience: 'gm', characters: [] }, [entity('c'), player('p')], 'b', GMS),
    ).toEqual({
      isPublic: false,
      add: [],
      remove: ['c'],
      removePlayers: ['p'],
    });
  });

  it('tells the being for a player note, and only the chosen for some characters', () => {
    expect(planAudience({ audience: 'player', characters: [] }, [], 'b', GMS)).toMatchObject({
      isPublic: false,
      add: ['b'],
    });
    expect(
      planAudience(
        { audience: 'some', characters: ['c', 'd'] },
        [entity('c'), entity('e')],
        'b',
        GMS,
      ),
    ).toEqual({ isPublic: false, add: ['d'], remove: ['e'], removePlayers: [] });
  });

  it('keeps the knowers when it becomes public, and wants a character for some', () => {
    expect(planAudience({ audience: 'everyone', characters: [] }, [entity('c')], 'b', GMS)).toEqual(
      {
        isPublic: true,
        add: [],
        remove: [],
        removePlayers: [],
      },
    );
    expect(() => planAudience({ audience: 'some', characters: [] }, [], 'b', GMS)).toThrow(
      'Choose at least one character, or make it GM only.',
    );
    expect(() => planAudience({ audience: 'some', characters: [] }, [], 'b', STORYTELLERS)).toThrow(
      'Choose at least one character, or make it Storyteller only.',
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

describe('the audiences name the game masters by the campaign', () => {
  it('reads "GM only" and the GMs by default', () => {
    expect(audienceTexts('gm', GMS)).toEqual({
      label: 'GM only',
      hint: 'Only the GMs of the campaign can read it.',
    });
    expect(audienceTexts('some', GMS).hint).toBe(
      'The GMs and the characters you choose can read it.',
    );
    expect(audienceTexts('player', GMS).hint).toBe("The GMs and this being's players can read it.");
  });

  it("reads the campaign's own title, in the singular and in the plural", () => {
    expect(audienceTexts('gm', STORYTELLERS)).toEqual({
      label: 'Storyteller only',
      hint: 'Only the Storytellers of the campaign can read it.',
    });
    expect(audienceTexts('some', STORYTELLERS).hint).toBe(
      'The Storytellers and the characters you choose can read it.',
    );
    expect(audienceTexts('player', STORYTELLERS).hint).toBe(
      "The Storytellers and this being's players can read it.",
    );
    expect(audienceLabel('gm', STORYTELLERS)).toBe('Storyteller only');
  });

  it('keeps the audiences that name no game master as they are', () => {
    expect(audienceTexts('everyone', STORYTELLERS)).toEqual({
      label: 'Everyone',
      hint: 'Anyone with access to the library can read it.',
    });
    expect(audienceTexts('some', STORYTELLERS).label).toBe('Some characters');
    expect(audienceTexts('player', STORYTELLERS).label).toBe('Player note');
    expect(audienceLabel('shared', STORYTELLERS)).toBe('Shared with you');
  });
});
