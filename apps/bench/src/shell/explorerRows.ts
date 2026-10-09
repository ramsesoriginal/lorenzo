// The explorer's rows, as plain data: the entries as a tree of what they inherit from (one row for
// each place an entry has), grouped by kind, or by name. No DOM, so it is tested alone.

import type { EntrySummary } from '../core/transport';

export type Order = 'inherits' | 'kind' | 'name';
export const ORDERS: readonly Order[] = ['inherits', 'kind', 'name'];

export type Row =
  | { type: 'header'; key: string; label: string }
  | {
      type: 'entry';
      /** One for each place: the same entry under two parents has two keys. */
      key: string;
      id: string;
      depth: number;
      /** It has entries under it in the tree (only in the tree order). */
      hasChildren: boolean;
      open: boolean;
      /** How many parents the entry has, when more than one: it shows in each place. */
      parentCount: number;
    };

const byName = (a: EntrySummary, b: EntrySummary) =>
  a.name.localeCompare(b.name, undefined, { sensitivity: 'base' }) || a.id.localeCompare(b.id);

/** Kinds in the order they are grouped; an entry that is none of them is a bare entry. */
const KIND_GROUPS: { kind: string | null; label: string }[] = [
  { kind: 'item', label: 'Items' },
  { kind: 'being', label: 'Beings' },
  { kind: 'item_instance', label: 'Inventory items' },
  { kind: 'character', label: 'Characters' },
  { kind: null, label: 'Bare entries' },
];

/** `collapsed` holds the ids of the entries whose children are hidden. */
export function buildRows(
  entries: readonly EntrySummary[],
  order: Order,
  collapsed: ReadonlySet<string> = new Set(),
): Row[] {
  const sorted = [...entries].sort(byName);
  const entry = (e: EntrySummary, key: string, depth = 0, extra = {}): Row => ({
    type: 'entry',
    key,
    id: e.id,
    depth,
    hasChildren: false,
    open: true,
    parentCount: e.parentIds.length > 1 ? e.parentIds.length : 0,
    ...extra,
  });

  if (order === 'name') return sorted.map((e) => entry(e, e.id));

  if (order === 'kind') {
    const rows: Row[] = [];
    for (const group of KIND_GROUPS) {
      const members = sorted.filter((e) =>
        group.kind === null ? e.kinds.length === 0 : e.kinds.includes(group.kind),
      );
      if (!members.length) continue;
      rows.push({ type: 'header', key: `kind:${group.kind}`, label: group.label });
      for (const e of members) rows.push(entry(e, `${group.kind}:${e.id}`, 1));
    }
    return rows;
  }

  const known = new Set(sorted.map((e) => e.id));
  const children = new Map<string, EntrySummary[]>();
  const roots: EntrySummary[] = [];
  for (const e of sorted) {
    const parents = e.parentIds.filter((p) => known.has(p) && p !== e.id);
    if (!parents.length) roots.push(e);
    for (const p of parents) children.set(p, [...(children.get(p) ?? []), e]);
  }
  const rows: Row[] = [];
  const reached = new Set<string>();
  const walk = (e: EntrySummary, path: readonly string[], key: string) => {
    const kids = (children.get(e.id) ?? []).filter((k) => !path.includes(k.id));
    const open = !collapsed.has(e.id);
    rows.push(entry(e, key, path.length, { hasChildren: kids.length > 0, open }));
    if (open) for (const k of kids) walk(k, [...path, e.id], `${key}/${k.id}`);
  };
  // What a root reaches, open or not: whatever is left is only reachable through a cycle.
  const reach = (e: EntrySummary) => {
    if (reached.has(e.id)) return;
    reached.add(e.id);
    for (const k of children.get(e.id) ?? []) reach(k);
  };
  for (const e of roots) {
    reach(e);
    walk(e, [], e.id);
  }
  // An entry that only a cycle reaches would never show: it is a root of its own.
  for (const e of sorted) {
    if (reached.has(e.id)) continue;
    reach(e);
    walk(e, [], e.id);
  }
  return rows;
}

/** How many entries, and how many rows they take (an entry with several parents takes several). */
export function counts(rows: readonly Row[]): { entries: number; places: number } {
  const entryRows = rows.filter((r) => r.type === 'entry');
  return { entries: new Set(entryRows.map((r) => r.id)).size, places: entryRows.length };
}
