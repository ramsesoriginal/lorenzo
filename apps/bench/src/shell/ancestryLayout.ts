// The ancestry graph's layout, as plain data: what an entry inherits from above it, what inherits
// from it below, laid out in rows. No DOM, so it is tested alone.

import type { EntrySummary } from '../core/transport';

export interface Node {
  id: string;
  name: string;
  x: number;
  y: number;
  w: number;
  h: number;
  selected: boolean;
}
export interface Edge {
  /** The one that inherits. */
  from: string;
  /** What it inherits from. */
  to: string;
}
export interface Layout {
  nodes: Node[];
  edges: Edge[];
  width: number;
  height: number;
  /** Children of the entry that did not fit in the row. */
  hidden: number;
}

const NODE_H = 24;
const GAP_X = 16;
const GAP_Y = 36;
const PAD = 12;
const CHAR_W = 7;
const MAX_ROW = 6;
const MAX_LEVELS = 4;

const widthOf = (name: string) => Math.max(48, Math.min(180, name.length * CHAR_W + 16));

/**
 * The entry, everything it inherits from (up to four rows above) and the entries directly under
 * it: its line, and nothing else. Its siblings and its relatives are not shown (they are in the
 * explorer). A row holds at most six; the entry's children that do not fit are counted.
 */
export function ancestryLayout(entries: readonly EntrySummary[], id: string): Layout {
  const byId = new Map(entries.map((e) => [e.id, e]));
  if (!byId.has(id)) return { nodes: [], edges: [], width: 0, height: 0, hidden: 0 };

  // Everything above, with how many steps up (the farthest way, so a diamond sits below both).
  const up = new Map<string, number>();
  const climb = (at: string, depth: number, trail: Set<string>) => {
    for (const p of byId.get(at)?.parentIds ?? []) {
      if (trail.has(p) || !byId.has(p) || depth >= MAX_LEVELS) continue;
      up.set(p, Math.max(up.get(p) ?? 0, depth + 1));
      climb(p, depth + 1, new Set(trail).add(p));
    }
  };
  climb(id, 0, new Set([id]));

  const top = Math.max(0, ...up.values());
  const rowOf = new Map<string, number>([[id, top]]);
  for (const [a, steps] of up) rowOf.set(a, top - steps);

  const byName = (a: EntrySummary, b: EntrySummary) =>
    a.name.localeCompare(b.name, undefined, { sensitivity: 'base' });
  const own = entries.filter((e) => e.parentIds.includes(id) && e.id !== id).sort(byName);
  for (const c of own.slice(0, MAX_ROW)) if (!rowOf.has(c.id)) rowOf.set(c.id, top + 1);
  const hidden = Math.max(0, own.length - MAX_ROW);

  const rows = new Map<number, EntrySummary[]>();
  for (const [eid, row] of rowOf) {
    const e = byId.get(eid);
    if (e) rows.set(row, [...(rows.get(row) ?? []), e]);
  }
  for (const list of rows.values()) list.sort(byName);

  const rowWidths = new Map(
    [...rows].map(([r, list]) => [
      r,
      list.reduce((n, e) => n + widthOf(e.name), 0) + GAP_X * (list.length - 1),
    ]),
  );
  const width = Math.max(120, ...rowWidths.values()) + PAD * 2;
  const nodes: Node[] = [];
  for (const [r, list] of rows) {
    let x = PAD + (width - PAD * 2 - (rowWidths.get(r) ?? 0)) / 2;
    for (const e of list) {
      const w = widthOf(e.name);
      nodes.push({
        id: e.id,
        name: e.name,
        x,
        y: PAD + r * (NODE_H + GAP_Y),
        w,
        h: NODE_H,
        selected: e.id === id,
      });
      x += w + GAP_X;
    }
  }
  const shown = new Set(nodes.map((n) => n.id));
  const edges: Edge[] = [];
  for (const n of nodes)
    for (const p of byId.get(n.id)?.parentIds ?? [])
      if (shown.has(p)) edges.push({ from: n.id, to: p });
  const maxRow = Math.max(...rows.keys());
  return {
    nodes,
    edges,
    width,
    height: PAD * 2 + (maxRow + 1) * NODE_H + maxRow * GAP_Y,
    hidden,
  };
}
