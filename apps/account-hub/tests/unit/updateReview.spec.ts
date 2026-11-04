import { EMPTY } from '@lorenzo/repo-ui';
import { describe, expect, it } from 'vitest';
import type { FieldChangeOut } from '../../src/lib/types';
import { choiceOf, reviewItem, sideOf } from '../../src/lib/updateReview';
import { describeField } from '../../src/lib/updates';

const names = { 'e-weapon': 'Weapon', 'e-sword': 'Longsword' };

function field(overrides: Partial<FieldChangeOut> & { field: string }): FieldChangeOut {
  return {
    label: null,
    state: 'clean',
    base: null,
    upstream: null,
    local: null,
    added: null,
    removed: null,
    ...overrides,
  };
}

const item = (change: FieldChangeOut, chosen?: 'keep' | 'take') =>
  reviewItem(describeField(change, names), chosen);

describe('a changed field as the review element takes it', () => {
  it('is its name and what it was and is, with nothing asked of a clean field', () => {
    expect(item(field({ field: 'name', base: 'Sword', upstream: 'Longsword' }))).toEqual({
      id: 'name',
      label: 'Name',
      change: { kind: 'value', was: 'Sword', theirs: 'Longsword' },
    });
  });

  it('adds what the library has, and asks, for a conflict', () => {
    expect(
      item(
        field({
          field: 'name',
          state: 'conflict',
          base: 'Sword',
          upstream: 'Longsword',
          local: 'Blade',
        }),
      ),
    ).toEqual({
      id: 'name',
      label: 'Name',
      change: { kind: 'value', was: 'Sword', theirs: 'Longsword', mine: 'Blade' },
      choice: { chosen: null },
    });
  });

  it('carries what the page chose, keeping yours as mine and taking the update as theirs', () => {
    const conflict = field({
      field: 'name',
      state: 'conflict',
      base: 'a',
      upstream: 'b',
      local: 'c',
    });

    expect(item(conflict, 'keep').choice).toEqual({ chosen: 'mine' });
    expect(item(conflict, 'take').choice).toEqual({ chosen: 'theirs' });
    expect(sideOf(undefined)).toBeNull();
    expect(choiceOf('mine')).toBe('keep');
    expect(choiceOf('theirs')).toBe('take');
  });

  it('says a value with nothing in it as no value, and an empty yours too', () => {
    const view = item(
      field({ field: 'slug', state: 'conflict', base: null, upstream: 'longsword', local: null }),
    );

    expect(view.change).toEqual({ kind: 'value', was: EMPTY, theirs: 'longsword', mine: EMPTY });
  });

  it('is a set for what an entry gained and lost, by name, and asks for a choice when it conflicts', () => {
    expect(
      item(
        field({
          field: 'prototypes',
          state: 'conflict',
          added: ['e-weapon'],
          removed: ['e-sword'],
        }),
      ),
    ).toEqual({
      id: 'prototypes',
      label: 'Inherits from',
      change: { kind: 'set', added: ['Weapon'], removed: ['Longsword'] },
      choice: { chosen: null },
    });
  });

  it('keeps the sentence for a change that cannot be applied, and asks nothing', () => {
    const view = item(
      field({ field: 'value_type', state: 'not_applicable', base: 'number', upstream: 'text' }),
    );

    expect(view.note).toContain('cannot be applied');
    expect(view.choice).toBeUndefined();
  });

  it('has no note when there is nothing to say', () => {
    expect('note' in item(field({ field: 'name', base: 'a', upstream: 'b' }))).toBe(false);
  });
});
