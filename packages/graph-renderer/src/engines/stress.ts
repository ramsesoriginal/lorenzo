import type { Engine, LayoutGraph, Point, Positions } from '../types';
import { onCircle } from './circle';
import { adjacency, steps } from './radial';

const ITERATIONS = 120;

/** All-pairs steps; a pair with no path is one step further than the longest that exists. */
export function distances(graph: LayoutGraph): number[][] {
  const next = adjacency(graph);
  const rows = next.map((_, start) => steps(next, start));
  const longest = Math.max(1, ...rows.map((row) => Math.max(...row)));
  return rows.map((row) => row.map((d) => (d === -1 ? longest + 1 : d)));
}

/** Stress majorization (SMACOF with the localized update): positions whose distances match the
 * steps between nodes. Pinned nodes stay put and the rest settle around them. */
export const stress: Engine = (graph: LayoutGraph) => {
  const count = graph.ids.length;
  if (count < 2) return onCircle(count);
  const dist = distances(graph);
  const pos: Positions = onCircle(count);
  for (const [index, point] of graph.pins) pos[index] = { ...point };
  for (let round = 0; round < ITERATIONS; round += 1) {
    for (let i = 0; i < count; i += 1) {
      if (graph.pins.has(i)) continue;
      let sumX = 0;
      let sumY = 0;
      let weights = 0;
      const here = pos[i] as Point;
      for (let j = 0; j < count; j += 1) {
        if (i === j) continue;
        const other = pos[j] as Point;
        const want = (dist[i] as number[])[j] as number;
        const weight = 1 / (want * want);
        const dx = here.x - other.x;
        const dy = here.y - other.y;
        const have = Math.sqrt(dx * dx + dy * dy) || 1e-6;
        sumX += weight * (other.x + (want * dx) / have);
        sumY += weight * (other.y + (want * dy) / have);
        weights += weight;
      }
      pos[i] = { x: sumX / weights, y: sumY / weights };
    }
  }
  return pos;
};
