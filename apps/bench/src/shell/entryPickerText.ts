// The text side of the entry picker: where the person is in a `[[` link they are typing, and what
// choosing an entry makes of it. No DOM, so it is tested alone.

import { slugify } from '@lorenzo/lorenzoscript';
import type { EntrySummary } from '../core/transport';

/** An unfinished `[[` before the caret: where it starts, and what has been typed after it. */
export interface PickerContext {
  start: number;
  query: string;
}

/** Null when the caret is not inside a link being typed: none open, already closed, or on another line. */
export function pickerContext(text: string, caret: number): PickerContext | null {
  const before = text.slice(0, caret);
  const start = before.lastIndexOf('[[');
  if (start < 0) return null;
  const query = before.slice(start + 2);
  if (/[\]\n]/.test(query)) return null;
  return { start, query };
}

/** What choosing `name` makes of the text: the whole link, and the caret after it. */
export function applyPick(
  text: string,
  caret: number,
  context: PickerContext,
  name: string,
): { text: string; caret: number } {
  // A `]]` the editor or the person already typed after the caret is part of this link.
  const end = text.slice(caret, caret + 2) === ']]' ? caret + 2 : caret;
  const link = `[[${name}]]`;
  return {
    text: text.slice(0, context.start) + link + text.slice(end),
    caret: context.start + link.length,
  };
}

const MAX_CHOICES = 8;

/**
 * The entries to offer for what was typed, by name: those that start with it first, then those
 * that contain it. An entry whose name cannot be written between `[[` and `]]`, or has nothing a
 * link name can be made of, is left out.
 */
export function choices(entries: readonly EntrySummary[], query: string): EntrySummary[] {
  const q = query.trim().toLowerCase();
  const usable = entries.filter((e) => !/[[\]]/.test(e.name) && slugify(e.name) !== '');
  const rank = (e: EntrySummary) => {
    const name = e.name.toLowerCase();
    return name.startsWith(q) ? 0 : name.includes(q) ? 1 : 2;
  };
  return usable
    .filter((e) => !q || rank(e) < 2)
    .sort(
      (a, b) =>
        rank(a) - rank(b) || a.name.localeCompare(b.name, undefined, { sensitivity: 'base' }),
    )
    .slice(0, MAX_CHOICES);
}
