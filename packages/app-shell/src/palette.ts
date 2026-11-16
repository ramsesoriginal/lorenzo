// What the palette finds and in what order (ADR 0414): entries across apps, apps ("Go to") and actions,
// narrowed by a scope. No page needed, so it is tested without a browser. The palette's own dialog is
// palette-ui.ts.

export type PaletteScope = 'Everything' | 'Entries' | 'Apps' | 'Actions';

/** Tab goes through these, in this order. */
export const SCOPES: PaletteScope[] = ['Everything', 'Entries', 'Apps', 'Actions'];

export type PaletteGroup = 'Recent' | 'Entries' | 'Go to' | 'Actions';

/** What the right-hand pane shows for the selected row, on a wide screen. */
export type PalettePreview = { title: string; subtitle?: string; blurb?: string };

export type PaletteItem = {
  /** Stable, so a recent one can be found again, e.g. "beings.new" or "entry:mara-quill". */
  id: string;
  group: Exclude<PaletteGroup, 'Recent'>;
  name: string;
  /** What kind of thing it is, small and muted after the name ("Character"). */
  kind?: string;
  /** Where it lives, at the right ("Beings"). */
  app?: string;
  /** An id in the brand's icons.svg without the `icon-` prefix. */
  icon?: string;
  /** A key or a two-key chord shown at the right ("N", "G S"). */
  keys?: string;
  /** Other words that find it. */
  keywords?: string[];
  /** Opens a confirmation: shown with a word as well as the danger colour. */
  danger?: boolean;
  preview?: PalettePreview;
  run(): void;
};

export type Scored = { item: PaletteItem; ranges: [number, number][]; recent?: boolean };
export type Section = { group: PaletteGroup; rows: Scored[] };

const ENTRY_LIMIT = 6;

const SCOPE_GROUP: Record<PaletteScope, PaletteGroup | null> = {
  Everything: null,
  Entries: 'Entries',
  Apps: 'Go to',
  Actions: 'Actions',
};

/** The next scope, wrapping, for Tab (and Shift Tab with -1). */
export function nextScope(scope: PaletteScope, direction: 1 | -1 = 1): PaletteScope {
  const index = SCOPES.indexOf(scope);

  return SCOPES[(index + direction + SCOPES.length) % SCOPES.length] as PaletteScope;
}

/** Move a selection by `delta`, wrapping at both ends; with nothing to select, 0. */
export function moveSelection(index: number, delta: number, length: number): number {
  if (length <= 0) return 0;

  return (((index + delta) % length) + length) % length;
}

function words(query: string): string[] {
  return query.toLowerCase().split(/\s+/).filter(Boolean);
}

/**
 * Where the query's words sit in a name, as [start, end) pairs, to draw them in bold. A word that is
 * not in the name (it may match a keyword) is not marked.
 */
export function matchRanges(name: string, query: string): [number, number][] {
  const lower = name.toLowerCase();
  const ranges: [number, number][] = [];

  for (const word of words(query)) {
    const at = lower.indexOf(word);

    if (at !== -1) ranges.push([at, at + word.length]);
  }

  return mergeRanges(ranges);
}

function mergeRanges(ranges: [number, number][]): [number, number][] {
  const sorted = [...ranges].sort((a, b) => a[0] - b[0]);
  const out: [number, number][] = [];

  for (const range of sorted) {
    const last = out[out.length - 1];

    if (last && range[0] <= last[1]) last[1] = Math.max(last[1], range[1]);
    else out.push([range[0], range[1]]);
  }

  return out;
}

/** Lower is better: a name that starts with the query, then a word that does, then anywhere. */
function score(item: PaletteItem, query: string): number | null {
  const name = item.name.toLowerCase();
  const extra = (item.keywords ?? []).join(' ').toLowerCase();
  let total = 0;

  for (const word of words(query)) {
    const at = name.indexOf(word);

    if (at === 0) total += 0;
    else if (at > 0 && /\s/.test(name[at - 1] ?? '')) total += 1;
    else if (at > 0) total += 2;
    else if (extra.includes(word)) total += 3;
    else return null;
  }

  return total;
}

/**
 * The sections of the palette for a query and a scope. With no query and "Everything", the recent
 * items come first (the ones whose ids are in `recent`, in that order); with a query they do not.
 * Entries are cut to a few, since an entry search can match a library's worth.
 */
export function search(
  items: PaletteItem[],
  query: string,
  scope: PaletteScope,
  recent: string[] = [],
): Section[] {
  const only = SCOPE_GROUP[scope];
  const sections: Section[] = [];
  const q = query.trim();

  if (q === '' && scope === 'Everything') {
    const rows = recent.flatMap((id) => {
      const item = items.find((i) => i.id === id);

      return item ? [{ item, ranges: [] as [number, number][], recent: true }] : [];
    });

    if (rows.length > 0) sections.push({ group: 'Recent', rows });
  }

  for (const group of ['Entries', 'Go to', 'Actions'] as const) {
    if (only && only !== group) continue;
    // Entries are only found by searching for them; the other groups list themselves.
    if (group === 'Entries' && q === '') continue;

    const rows = items
      .filter((item) => item.group === group)
      .flatMap((item) => {
        const s = q === '' ? 0 : score(item, q);

        return s === null ? [] : [{ item, ranges: matchRanges(item.name, q), s }];
      })
      .sort((a, b) => a.s - b.s)
      .map(({ item, ranges }) => ({ item, ranges }));
    const shown = group === 'Entries' ? rows.slice(0, ENTRY_LIMIT) : rows;

    if (shown.length > 0) sections.push({ group, rows: shown });
  }

  return sections;
}

/** The rows in the order they are drawn, for the arrow keys. */
export function flatten(sections: Section[]): Scored[] {
  return sections.flatMap((section) => section.rows);
}

/** Remember an id as the most recent, keeping `max` of them and no repeats. */
export function pushRecent(recent: string[], id: string, max = 3): string[] {
  return [id, ...recent.filter((r) => r !== id)].slice(0, max);
}
