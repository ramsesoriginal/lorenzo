// Where an entry sits among the entries it inherits from, as plain data: no DOM, so it is tested
// alone. Used by the breadcrumb over an entry, and by the ancestry graph.

import type { EntrySummary } from '../core/transport';

/**
 * The entries `id` inherits from, farthest first, following the first parent each time (the order
 * the explorer lists them in). Stops at a loop. An entry with several parents shows one path here;
 * the rest are in the Parents pane.
 */
export function ancestorPath(entries: readonly EntrySummary[], id: string): EntrySummary[] {
  const byId = new Map(entries.map((e) => [e.id, e]));
  const path: EntrySummary[] = [];
  const seen = new Set([id]);
  for (let at = byId.get(id)?.parentIds[0]; at && !seen.has(at); at = byId.get(at)?.parentIds[0]) {
    const e = byId.get(at);
    if (!e) break;
    seen.add(at);
    path.unshift(e);
  }
  return path;
}

/** The entries that have `id` as a parent, by name. */
export function childrenOf(entries: readonly EntrySummary[], id: string): EntrySummary[] {
  return entries
    .filter((e) => e.parentIds.includes(id))
    .sort((a, b) => a.name.localeCompare(b.name, undefined, { sensitivity: 'base' }));
}
