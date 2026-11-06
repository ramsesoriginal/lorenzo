import { cos, sin, TAU } from '../math';
import type { Engine, LayoutGraph, Positions } from '../types';

export function adjacency(graph: LayoutGraph): number[][] {
  const next: number[][] = graph.ids.map(() => []);
  for (const [a, b] of graph.pairs) {
    next[a]?.push(b);
    next[b]?.push(a);
  }
  for (const row of next) row.sort((x, y) => x - y);
  return next;
}

/** Steps from `start` to every node; nodes it cannot reach are -1. */
export function steps(next: readonly (readonly number[])[], start: number): number[] {
  const dist = next.map(() => -1);
  dist[start] = 0;
  const queue = [start];
  for (let head = 0; head < queue.length; head += 1) {
    const node = queue[head] as number;
    for (const other of next[node] ?? []) {
      if (dist[other] === -1) {
        dist[other] = (dist[node] as number) + 1;
        queue.push(other);
      }
    }
  }
  return dist;
}

/** Polar rings by steps from the focus: the focus at the centre, each step a ring further out,
 * what it cannot reach on the outermost ring. */
export const radial: Engine = (graph: LayoutGraph) => {
  const count = graph.ids.length;
  if (count === 0) return [];
  const dist = steps(adjacency(graph), graph.focus);
  const reach = Math.max(0, ...dist);
  const rings: number[][] = [];
  for (let i = 0; i < count; i += 1) {
    const ring = (dist[i] as number) === -1 ? reach + 1 : (dist[i] as number);
    const row = rings[ring] ?? [];
    row.push(i);
    rings[ring] = row;
  }
  const out: Positions = graph.ids.map(() => ({ x: 0, y: 0 }));
  rings.forEach((members, ring) => {
    if (!members || ring === 0) return;
    // Rings are widened so neighbours on one ring keep about a unit between them.
    const radius = Math.max(2 * ring, (members.length * 1.2) / TAU);
    members.forEach((node, index) => {
      const angle = (TAU * (index + (ring % 2) * 0.5)) / members.length - TAU / 4;
      out[node] = { x: radius * cos(angle), y: radius * sin(angle) };
    });
  });
  return out;
};
