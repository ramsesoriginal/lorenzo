// A conflict as the shared review element takes it (ADR 0389, packages/repo-ui): the field in a
// person's words and the three values as text, handed over as plain data. The dialog draws it, and
// the buttons act at once on the command layer.

import { EMPTY, type ReviewItem, type ReviewValue, type ReviewWords } from '@lorenzo/repo-ui';
import type { Command } from '../core/commands';

/**
 * Bench's own words for the review: it has always said Mine and Theirs, Keep mine and Use theirs,
 * and its entry's own conflict row says them too, so the two agree until the terminology sweep
 * (ADR 0194) settles one pair for every screen.
 */
export const BENCH_REVIEW_WORDS: Partial<ReviewWords> = {
  mine: 'Mine',
  theirs: 'Theirs',
  keepMine: 'Keep mine',
  takeTheirs: 'Use theirs',
  keptMine: (label) => `Keeping mine for ${label}.`,
  tookTheirs: (label) => `Using theirs for ${label}.`,
};

const capitalised = (text: string): string => text.charAt(0).toUpperCase() + text.slice(1);

/** A value that is not there is no value; any other is the text `show` gives it. */
export function reviewValue(value: unknown, show: (value: unknown) => string): ReviewValue {
  return value === undefined ? EMPTY : show(value);
}

/** One conflicting command: what it was, what the server has now and what the person wrote. */
export function conflictItem(
  command: Command,
  label: string,
  show: (value: unknown) => string,
): ReviewItem {
  return {
    id: String(command.id),
    label: capitalised(label),
    change: {
      kind: 'value',
      was: reviewValue(command.base, show),
      theirs: reviewValue(command.theirs, show),
      mine: reviewValue(command.mine, show),
    },
    choice: { chosen: null },
  };
}
