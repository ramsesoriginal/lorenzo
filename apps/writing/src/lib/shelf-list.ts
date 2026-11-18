// What the shelf shows and remembers, apart from the page (ADR 0494, W1).
export type Kind = 'scene' | 'book' | 'chapter' | 'carrier' | 'biography';

export type Work = { id: string; name: string; kind: string };

export const FILTERS: { id: string; label: string; kinds: string[] }[] = [
  { id: 'all', label: 'All', kinds: [] },
  { id: 'book', label: 'Books', kinds: ['book'] },
  { id: 'chapter', label: 'Chapters', kinds: ['chapter'] },
  { id: 'scene', label: 'Scenes', kinds: ['scene', 'scene_telling'] },
  { id: 'carrier', label: 'Carriers', kinds: ['carrier'] },
  { id: 'biography', label: 'Biographies', kinds: ['biography'] },
];

/** The other four ways to start, each with one plain line (WR12, A1). */
export const STARTS: { kind: Kind; label: string; line: string }[] = [
  { kind: 'chapter', label: 'Chapter', line: 'A part of a story, with Scenes or text in it' },
  { kind: 'book', label: 'Book', line: 'Chapters in order, with Editions and contents' },
  { kind: 'carrier', label: 'Carrier', line: 'A letter, a song, a sign: writing inside the world' },
  { kind: 'biography', label: 'Character biography', line: 'What is known of one being' },
];

const LAST = 'lorenzo:writing:last';

export type Last = { tenant: string; entry: string };

/** The work last opened in this browser (ADR 0494, Q4: no last-edited time yet). */
export function rememberWork(tenant: string, entry: string) {
  try {
    localStorage.setItem(LAST, JSON.stringify({ tenant, entry }));
  } catch {
    // Remembering is a convenience.
  }
}

export function lastWork(): Last | null {
  try {
    const value = JSON.parse(localStorage.getItem(LAST) ?? 'null');
    return value && typeof value.tenant === 'string' && typeof value.entry === 'string'
      ? value
      : null;
  } catch {
    return null;
  }
}

/** What stays on the shelf for a filter and a search: by kind, then by the words in the name. */
export function shown(works: Work[], filter: string, query: string): Work[] {
  const kinds = FILTERS.find((f) => f.id === filter)?.kinds ?? [];
  const words = query.trim().toLocaleLowerCase().split(/\s+/).filter(Boolean);
  return works.filter(
    (w) =>
      (kinds.length === 0 || kinds.includes(w.kind)) &&
      words.every((word) => w.name.toLocaleLowerCase().includes(word)),
  );
}

export type Layout = 'source' | 'split' | 'live';

/** How a text is shown for writing: its source with a preview tab, beside a preview, or live. */
export const LAYOUTS: [Layout, string][] = [
  ['source', 'Source'],
  ['split', 'Split'],
  ['live', 'Live'],
];

const LAYOUT = 'lorenzo:writing:layout';

export function savedLayout(): Layout {
  try {
    const value = localStorage.getItem(LAYOUT);
    return value === 'split' || value === 'live' ? value : 'source';
  } catch {
    return 'source';
  }
}

export function rememberLayout(layout: Layout) {
  try {
    localStorage.setItem(LAYOUT, layout);
  } catch {
    // A convenience only.
  }
}
