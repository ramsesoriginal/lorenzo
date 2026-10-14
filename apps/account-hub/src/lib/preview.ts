// What a reader sees when they look inside a repository before copying it (RFC 0038 §5, ADR 0293),
// as plain functions over what the API returns: the one line a level of the Owner's switch gets, an
// entry's lines (its kinds, its parents, its text rows, its stat values), the description a reader's
// language picks, and the paging of the list of every entry. No DOM and nothing but ./types and
// ./shelf, so they run under Node in the unit tests. The words are those of identity.md §14.3 and
// ADR 0194: library, repository, release, Owner, entry, copy; never "tenant", "grant" or
// "subscription". Nothing here decides what may be shown: the API answers only with what the reader
// may look at, and this renders that.

import { kindLabel } from './shelf';
import type {
  PreviewDescriptionOut,
  PreviewEntityOut,
  PreviewInformationOut,
  PreviewOut,
  PreviewStatOut,
} from './types';

// A holder is a library that holds access to the repository; a visitor is anyone else signed in.
export type Reader = 'visitor' | 'holder';

export type PreviewLevel = PreviewOut['preview'];

// ---------------------------------------------------------------------------------------------
// The words of the page.

export const PREVIEW_HEADING = 'Look inside';
export const PREVIEW_OFF = 'The Owner has not opened this repository for a look inside.';
export const PREVIEW_OFF_HOLDER =
  'The Owner has not opened the text of this repository for a look. You can see the names of its entries.';
export const SHOWCASE_EMPTY = 'The Owner has not chosen entries to show yet.';
export const FEATURED_LABEL = 'Featured';
export const ALL_ENTRIES_HEADING = 'All entries';
export const FIND_AN_ENTRY = 'Find an entry';
export const NO_ENTRY_MATCHES = 'No entry matches.';
export const TEXT_NOT_OPEN = 'The Owner has not opened the text of this entry for a look.';
export const NO_TEXT = 'Nothing has been written about this entry that is open to look at.';

// ---------------------------------------------------------------------------------------------
// The one line a level says, or null when there is something to show.

// What the preview of a repository says in words where it has nothing to list: the switch is off, or
// it is on `showcase` and the Owner has featured nothing. At `public` the list of every entry is
// there whether or not anything is featured, so nothing is said.
export function previewLine(
  preview: Pick<PreviewOut, 'preview' | 'entries'>,
  reader: Reader,
): string | null {
  if (preview.preview === 'off') return reader === 'holder' ? PREVIEW_OFF_HOLDER : PREVIEW_OFF;
  if (preview.preview === 'showcase' && preview.entries.length === 0) return SHOWCASE_EMPTY;

  return null;
}

// Whether a visitor is offered the list of every entry: only at `public`. A holder has the list of
// names already, on the repository's page, and asks the same route.
export function offersAllEntries(preview: Pick<PreviewOut, 'preview'>, reader: Reader): boolean {
  return reader === 'visitor' && preview.preview === 'public';
}

// ---------------------------------------------------------------------------------------------
// An entry.

// "Item, Being".
export function kindsLine(entry: Pick<PreviewEntityOut, 'kinds'>): string {
  return entry.kinds.map(kindLabel).join(', ');
}

// "Inherits from Weapon, Magic", the words Shelf's entry list uses; null for an entry with no parent.
export function parentsText(entry: Pick<PreviewEntityOut, 'parents'>): string | null {
  return entry.parents.length === 0
    ? null
    : `Inherits from ${entry.parents.map((parent) => parent.name).join(', ')}`;
}

// A value as it is read: numbers as they are, a switch as "Yes" or "No", text as it is.
export function statValueText(value: unknown): string {
  if (typeof value === 'boolean') return value ? 'Yes' : 'No';
  if (value === null || value === undefined) return '';

  return String(value);
}

export type StatGroup = { group: string; stats: { name: string; value: string }[] };

// The stat values the entry holds itself, by the group of the stat, in the order the API gave them
// (the vocabulary's own order): one heading for each group, its stats beneath.
export function statGroups(stats: readonly PreviewStatOut[]): StatGroup[] {
  const groups: StatGroup[] = [];

  for (const stat of stats) {
    let group = groups.find((candidate) => candidate.group === stat.group);

    if (!group) {
      group = { group: stat.group, stats: [] };
      groups.push(group);
    }

    group.stats.push({ name: stat.name, value: statValueText(stat.value) });
  }

  return groups;
}

// The description a reader reads: the one in their language if it has one, else one in the same
// language of another region ("de" for "de-AT"), else the first. Null for a row with no text.
export function pickDescription(
  descriptions: readonly PreviewDescriptionOut[],
  preferred: readonly string[],
): PreviewDescriptionOut | null {
  if (descriptions.length === 0) return null;

  const same = (a: string, b: string) => a.toLowerCase() === b.toLowerCase();
  const language = (locale: string) => locale.split('-')[0]?.toLowerCase() ?? '';

  for (const wanted of preferred) {
    const exact = descriptions.find((d) => same(d.locale, wanted));

    if (exact) return exact;
  }

  for (const wanted of preferred) {
    const near = descriptions.find((d) => language(d.locale) === language(wanted));

    if (near) return near;
  }

  return descriptions[0] ?? null;
}

export type TextLine = {
  id: string;
  title: string;
  text: string;
  pictures: PreviewInformationOut['pictures'];
};

// The rows of text to show: each one's title, the description the reader's language picks, and its
// pictures. A row with neither text nor a picture is still shown by its title, so a visitor sees that
// it is there.
export function textLines(
  entry: Pick<PreviewEntityOut, 'information'>,
  preferred: readonly string[],
): TextLine[] {
  return entry.information.map((row) => ({
    id: row.id,
    title: row.title,
    text: pickDescription(row.descriptions, preferred)?.content ?? '',
    pictures: row.pictures,
  }));
}

// The sentence under an entry that shows no text: either the reader may not read it (a holder, for an
// entry that is not featured) or there is none open to look at. Null where the text is shown.
export function textNote(
  entry: Pick<PreviewEntityOut, 'text_visible' | 'information' | 'stats'>,
): string | null {
  if (!entry.text_visible) return TEXT_NOT_OPEN;
  if (entry.information.length === 0 && entry.stats.length === 0) return NO_TEXT;

  return null;
}

// ---------------------------------------------------------------------------------------------
// The list of every entry.

// A page of the list: names are small, and a phone scrolls a long list without trouble.
export const ENTRY_PAGE_SIZE = 20;

// "20 of 134 entries", or "1 entry".
export function listCount(shown: number, total: number): string {
  if (total === 1) return '1 entry';
  if (shown >= total) return `${total} entries`;

  return `${shown} of ${total} entries`;
}

// The languages a reader prefers, from the browser: the order they are set in.
export function preferredLocales(languages: readonly string[] | undefined): string[] {
  return [...(languages ?? [])].filter((locale) => locale.trim() !== '');
}
