// What Studio's "What people can look at" card says and does (RFC 0038 §5, ADR 0293), as plain
// functions: the sentence under the featured entries, the moves on the list (up, down, remove, add),
// what a search offers, and what a refusal means. No DOM and nothing but ./types, so they run under
// Node in the unit tests. The three choices of the switch are those of the "Make public" dialog
// (lib/visibility.ts: PREVIEW_CHOICES), so the Owner reads the same words in both. The words are
// those of identity.md §14.3: library, repository, release, Owner, entry; never "tenant", "grant" or
// "subscription".

export const LOOK_HEADING = 'What people can look at';
export const FEATURED_HEADING = 'Featured entries';
export const FEATURED_NONE = 'No entries are featured yet.';
export const ADD_LABEL = 'Add an entry';
export const ADD_HINT = 'Type part of its name.';
export const ADD_NONE = 'No entry with that name is left to add.';
export const SAVED = 'Saved.';

// What a visitor reads is the latest release, not what the Owner edits meanwhile.
export const RELEASE_NOTE =
  'Visitors read the latest release, so an entry you add is shown from the next release.';

// An Owner features entries for the readers the switch lets look at them.
export const LOOK_EXPLANATION =
  'The text of the entries you feature can be looked at before copying, as the choice above says. GM only text is never shown.';

export function limitLine(limit: number): string {
  return `You can feature up to ${limit} entries.`;
}

// "3 of 12 entries featured", "1 of 12 entries featured".
export function featuredCount(count: number, limit: number): string {
  return `${count} of ${limit} entries featured`;
}

export function canAdd(featured: readonly unknown[], limit: number): boolean {
  return featured.length < limit;
}

// The list with the entry at `index` one place earlier or later, or the same list where it cannot
// move.
export function moved<T>(list: readonly T[], index: number, by: -1 | 1): T[] {
  const next = [...list];
  const to = index + by;

  if (index < 0 || index >= next.length || to < 0 || to >= next.length) return next;

  const [item] = next.splice(index, 1);

  next.splice(to, 0, item as T);

  return next;
}

export function removedAt<T>(list: readonly T[], index: number): T[] {
  return list.filter((_, at) => at !== index);
}

// The list with `entry` added at the end, unless it is there or the limit is reached.
export function added<T extends { id: string }>(list: readonly T[], entry: T, limit: number): T[] {
  if (list.length >= limit || list.some((existing) => existing.id === entry.id)) return [...list];

  return [...list, entry];
}

// What a search found, without what is featured already.
export function candidates<T extends { id: string }>(
  found: readonly T[],
  featured: readonly { id: string }[],
): T[] {
  const taken = new Set(featured.map((entry) => entry.id));

  return found.filter((entry) => !taken.has(entry.id));
}

// "Move up: Owlbear": the name of a button for a screen reader.
export function actionLabel(action: string, name: string): string {
  return `${action}: ${name}`;
}

export function refusal(problemType: string | undefined): string | null {
  return problemType === 'showcase-invalid'
    ? 'Those entries cannot be featured: at most 12, and each one an entry of this repository. Nothing was changed.'
    : null;
}
