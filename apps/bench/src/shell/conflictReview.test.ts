import { EMPTY } from '@lorenzo/repo-ui';
import { describe, expect, it } from 'vitest';
import type { Command } from '../core/commands';
import { BENCH_REVIEW_WORDS, conflictItem, reviewValue } from './conflictReview';

const show = (value: unknown) => (typeof value === 'string' ? `“${value}”` : String(value));
const conflict = (over: Partial<Command>) =>
  ({
    id: 1,
    state: 'conflict',
    base: 'Wolf',
    mine: 'Hound',
    theirs: 'Coyote',
    ...over,
  }) as Command;

describe('a conflict as the review takes it', () => {
  it('is the field, capitalised, and what it was, what the server has and what was written', () => {
    expect(conflictItem(conflict({}), 'name', show)).toEqual({
      id: '1',
      label: 'Name',
      change: { kind: 'value', was: '“Wolf”', theirs: '“Coyote”', mine: '“Hound”' },
      choice: { chosen: null },
    });
  });

  it('keeps a label that is already capitalised, such as a stat', () => {
    expect(conflictItem(conflict({}), 'Weight', show).label).toBe('Weight');
  });

  it('says a missing value as no value, and a number and null as the host reads them', () => {
    expect(reviewValue(undefined, show)).toEqual(EMPTY);
    expect(reviewValue(12, show)).toBe('12');
    expect(reviewValue(null, () => 'nothing of its own (inherited)')).toBe(
      'nothing of its own (inherited)',
    );
    expect(
      conflictItem(conflict({ theirs: undefined as never }), 'name', show).change,
    ).toMatchObject({
      theirs: EMPTY,
    });
  });
});

describe('Bench’s words', () => {
  it('are Mine, Theirs, Keep mine and Use theirs, as its other conflict row says them', () => {
    expect(BENCH_REVIEW_WORDS).toMatchObject({
      mine: 'Mine',
      theirs: 'Theirs',
      keepMine: 'Keep mine',
      takeTheirs: 'Use theirs',
    });
    expect(BENCH_REVIEW_WORDS.keptMine?.('Name')).toBe('Keeping mine for Name.');
    expect(BENCH_REVIEW_WORDS.tookTheirs?.('Name')).toBe('Using theirs for Name.');
  });
});
