// The text side of the entry picker: where the person is in a `[[` link they are typing, and what
// choosing an entry makes of it. No DOM, so it is tested alone.

import { slugify } from '@lorenzo/lorenzoscript';
import type { EntrySummary } from '../core/transport';

/**
 * An unfinished `[[` before the caret: where it starts, and what has been typed after it. With a
 * `!` in front (`![[`) it is a picture being chosen, and `start` is the place of the `!`.
 */
export interface PickerContext {
  start: number;
  query: string;
  image: boolean;
}

/** Null when the caret is not inside a link being typed: none open, already closed, or on another line. */
export function pickerContext(text: string, caret: number): PickerContext | null {
  const before = text.slice(0, caret);
  const open = before.lastIndexOf('[[');
  if (open < 0) return null;
  const query = before.slice(open + 2);
  if (/[\]\n]/.test(query)) return null;
  const image = open > 0 && before[open - 1] === '!';
  return { start: image ? open - 1 : open, query, image };
}

/**
 * The link to write for an entry: `[[Name]]` when its link name is the one its name makes (which
 * is what `[[Name]]` means), else `[Name](link-name)`. An entry with no link name gets `[[Name]]`,
 * which the preview says does not reach it.
 */
export function linkFor(name: string, slug: string | null): string {
  if (!slug || slug === slugify(name)) return `[[${name}]]`;
  return `[${name}](${slug})`;
}

/**
 * The picture to write for an entry: `![Name](link-name)`, always written out, since a picture has
 * no `[[ ]]` form. An entry with no link name gets the one its name makes, which the preview says
 * does not reach it.
 */
export function imageFor(name: string, slug: string | null): string {
  return `![${name}](${slug || slugify(name)})`;
}

/** What choosing an entry makes of the text: the whole link written for it, and the caret after it. */
export function applyPick(
  text: string,
  caret: number,
  context: PickerContext,
  link: string,
): { text: string; caret: number } {
  // A `]]` the editor or the person already typed after the caret is part of this link.
  const end = text.slice(caret, caret + 2) === ']]' ? caret + 2 : caret;
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

/**
 * What a toolbar button makes of the text: it opens a link (`[[`) or a picture (`![[`) at the
 * caret, in front of what is selected, so the picker has something to offer from, and leaves the
 * caret after what it wrote. The picker takes it from there.
 */
export function openLink(
  text: string,
  from: number,
  to: number,
  image: boolean,
): { text: string; caret: number } {
  const open = image ? '![[' : '[[';
  return {
    text: text.slice(0, from) + open + text.slice(from, to) + text.slice(to),
    caret: to + open.length,
  };
}
