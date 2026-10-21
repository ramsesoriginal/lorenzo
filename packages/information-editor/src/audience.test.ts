import { describe, expect, it } from 'vitest';
import { audienceWithRecipients } from './index';

describe('explicit audience selection', () => {
  it('retains player grants and deduplicates group/character ids without broadening sharing', () => {
    expect(
      audienceWithRecipients(
        { is_public: false, entity_ids: [], player_ids: ['seat'] },
        ['group', 'character', 'group'],
        ['seat'],
      ),
    ).toEqual({
      is_public: false,
      entity_ids: ['character', 'group'],
      player_ids: ['seat'],
    });
  });
  it('does not clear explicit grants when everyone is selected', () => {
    expect(audienceWithRecipients({ is_public: true }, ['character'], ['seat'])).toEqual({
      is_public: true,
      entity_ids: ['character'],
      player_ids: ['seat'],
    });
  });
});

it('retains a live participant audience when editing explicit recipients', () => {
  expect(
    audienceWithRecipients({ is_public: false, shared_with_participants: true }, ['being'], []),
  ).toEqual({
    is_public: false,
    shared_with_participants: true,
    entity_ids: ['being'],
    player_ids: [],
  });
});
