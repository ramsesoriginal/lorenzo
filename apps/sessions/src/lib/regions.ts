// The parts of a Session page, the views that show some of them, and the views a person names (CS4,
// CS6, screens 15 to 18). A view only says what is drawn: hiding a part deletes nothing and changes no
// permission. Pure, but for the one place a person's own views are kept in this browser.
export const PARTS = [
  { key: 'details', label: 'Details', regions: ['details'] },
  { key: 'roster', label: 'Roster', regions: ['roster'] },
  { key: 'notes', label: 'Notes', regions: ['notes'] },
  { key: 'references', label: 'References', regions: ['references'] },
  { key: 'gametime', label: 'Game time', regions: ['coverage'] },
  { key: 'scenes', label: 'Scenes', regions: ['scenes', 'adder'] },
  { key: 'played', label: 'Played', regions: ['play'] },
  { key: 'campaign', label: 'Campaign order', regions: ['sequence'] },
  { key: 'lived', label: 'Lived order', regions: ['lived'] },
] as const;

export type PartKey = (typeof PARTS)[number]['key'];
const ALL: PartKey[] = PARTS.map((p) => p.key);

/** The views every Session page has. A Session opens in Prepare, every time (CS7). */
export const BUILT_IN: Record<'Prepare' | 'Played' | 'All', PartKey[]> = {
  Prepare: ['details', 'roster', 'notes', 'scenes'],
  Played: ['played', 'notes'],
  All: ALL,
};

/** The part a region of the page belongs to; the page's head belongs to none and is always shown. */
export function partOf(region: string): PartKey | undefined {
  return PARTS.find((p) => (p.regions as readonly string[]).includes(region))?.key;
}

export type SavedView = { name: string; parts: PartKey[] };

const same = (a: readonly PartKey[], b: readonly PartKey[]) =>
  a.length === b.length && a.every((k) => b.includes(k));

/** The name of the view a set of parts is: a built-in, one the person named, or Custom. */
export function viewName(visible: readonly PartKey[], saved: readonly SavedView[]): string {
  for (const [name, parts] of Object.entries(BUILT_IN)) if (same(visible, parts)) return name;
  return saved.find((v) => same(visible, v.parts))?.name ?? 'Custom';
}

/** What the foot of the page says is hidden, or nothing when every part is there. */
export function footLine(visible: readonly PartKey[]): string {
  const hidden = PARTS.filter((p) => !visible.includes(p.key)).map((p) => p.label);
  return hidden.length
    ? `Hidden: ${hidden.join(', ')}. Hiding a part hides only the drawing; nothing is deleted and nothing about who may see it changes.`
    : '';
}

/** A part turned on or off. */
export function toggled(visible: readonly PartKey[], key: PartKey): PartKey[] {
  return visible.includes(key) ? visible.filter((k) => k !== key) : [...visible, key];
}

/** The person's own views as read back: anything that is not a name with known parts is left out. */
export function parseViews(raw: string | null): SavedView[] {
  if (!raw) return [];
  try {
    const list: unknown = JSON.parse(raw);
    if (!Array.isArray(list)) return [];
    const views: SavedView[] = [];
    for (const item of list) {
      const name = typeof item?.name === 'string' ? item.name.trim() : '';
      const parts: unknown = item?.parts;
      if (!name || !Array.isArray(parts)) continue;
      views.push({
        name: name.slice(0, 40),
        parts: parts.filter((p): p is PartKey => ALL.includes(p as PartKey)),
      });
    }
    return views;
  } catch {
    return [];
  }
}

/** A view named: the same name again replaces it, and the built-in names are not taken. */
export function withView(
  saved: readonly SavedView[],
  name: string,
  parts: readonly PartKey[],
): SavedView[] | null {
  const clean = name.trim().slice(0, 40);
  if (!clean || clean in BUILT_IN || clean === 'Custom') return null;
  return [...saved.filter((v) => v.name !== clean), { name: clean, parts: [...parts] }];
}

const KEY = 'lorenzo:sessions:views';

export function readViews(): SavedView[] {
  try {
    return parseViews(localStorage.getItem(KEY));
  } catch {
    // A blocked store leaves the person with the built-in views.
    return [];
  }
}

export function writeViews(views: readonly SavedView[]): void {
  try {
    localStorage.setItem(KEY, JSON.stringify(views));
  } catch {
    // The view still applies for this visit.
  }
}
