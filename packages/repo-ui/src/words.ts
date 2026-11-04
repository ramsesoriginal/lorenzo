// The words of the review, in one place (ADR 0389, identity.md §14.3). A host overrides the ones it
// has a reason to say differently ("Mine" and "Theirs" in Bench) and nothing else.

import type { ReviewChange, ReviewValue, ReviewWords } from './types';

export const REVIEW_WORDS: ReviewWords = {
  was: 'Was',
  theirs: 'Now',
  mine: 'Yours',
  added: 'Added',
  removed: 'Removed',
  noValue: 'No value',
  deleted: 'Deleted',
  keepMine: 'Keep yours',
  takeTheirs: 'Take the update, and replace yours',
  choiceLegend: 'This is changed in your library too',
  chooseFor: (label) => `Choose for ${label}`,
  keptMine: (label) => `Keeping yours for ${label}.`,
  tookTheirs: (label) => `Taking the update for ${label}.`,
};

/** The defaults with a host's own words laid over them. */
export function reviewWords(overrides: Partial<ReviewWords> = {}): ReviewWords {
  const words: ReviewWords = { ...REVIEW_WORDS };

  for (const key of Object.keys(overrides) as (keyof ReviewWords)[]) {
    const value = overrides[key];

    // `exactOptionalPropertyTypes` keeps an explicit `undefined` out, but a plain object may carry one.
    if (value !== undefined) Object.assign(words, { [key]: value });
  }

  return words;
}

/** One value as the text a person reads. */
export function valueText(value: ReviewValue, words: ReviewWords): string {
  if (typeof value === 'string') return value;

  return value.kind === 'empty' ? words.noValue : words.deleted;
}

/** What a value is, for the stylesheet and the tests: words, or the lack of one. */
export function valueKind(value: ReviewValue): 'text' | 'empty' | 'deleted' {
  return typeof value === 'string' ? 'text' : value.kind;
}

export type ReviewRow = {
  readonly term: string;
  readonly text: string;
  readonly kind: 'text' | 'empty' | 'deleted';
};

// The pairs a change is drawn as: a field with one value reads Was, Now and, where the host changed
// it too, Yours; a set reads what was Added and what was Removed, leaving out a side with nothing.
export function reviewRows(change: ReviewChange, words: ReviewWords): ReviewRow[] {
  if (change.kind === 'set') {
    const rows: ReviewRow[] = [];

    if (change.added.length > 0) {
      rows.push({ term: words.added, text: change.added.join(', '), kind: 'text' });
    }

    if (change.removed.length > 0) {
      rows.push({ term: words.removed, text: change.removed.join(', '), kind: 'text' });
    }

    return rows;
  }

  const row = (term: string, value: ReviewValue): ReviewRow => ({
    term,
    text: valueText(value, words),
    kind: valueKind(value),
  });

  return [
    row(words.was, change.was),
    row(words.theirs, change.theirs),
    ...(change.mine === undefined ? [] : [row(words.mine, change.mine)]),
  ];
}
