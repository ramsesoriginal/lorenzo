import type { Engine, LayoutGraph, Positions } from '../types';
import { adjacency, steps } from './radial';

const SWEEPS = 6;
const RANK_GAP = 2.4;
const NODE_GAP = 1.8;

/** Ranks by longest path over the one-way ties, with back edges (a cycle) cut in index order so the
 * result is the same every time; a tie of no direction keeps its two nodes on one rank. */
export function rankOf(graph: LayoutGraph): number[] {
  const count = graph.ids.length;
  const out: number[][] = graph.ids.map(() => []);
  for (const [from, to] of graph.arcs) out[from]?.push(to);
  // Depth-first from every node in order; an arc to a node on the current path is a back edge.
  const state = new Array<number>(count).fill(0);
  const kept: [number, number][] = [];
  const visit = (node: number) => {
    state[node] = 1;
    for (const to of out[node] ?? []) {
      if (state[to] === 1) continue;
      kept.push([node, to]);
      if (state[to] === 0) visit(to);
    }
    state[node] = 2;
  };
  for (let n = 0; n < count; n += 1) if (state[n] === 0) visit(n);
  const rank = new Array<number>(count).fill(0);
  // Longest path: relax as many times as there are nodes, which a DAG needs at most.
  for (let round = 0; round < count; round += 1) {
    let changed = false;
    for (const [from, to] of kept) {
      if ((rank[to] as number) < (rank[from] as number) + 1) {
        rank[to] = (rank[from] as number) + 1;
        changed = true;
      }
    }
    if (!changed) break;
  }
  // Partners (a tie with no direction) share a rank: the lower one is lifted to the higher.
  const tied = new Set(graph.arcs.map(([a, b]) => `${Math.min(a, b)}:${Math.max(a, b)}`));
  for (let round = 0; round < count; round += 1) {
    let changed = false;
    for (const [a, b] of graph.pairs) {
      if (tied.has(`${a}:${b}`)) continue;
      const high = Math.max(rank[a] as number, rank[b] as number);
      if (rank[a] !== high || rank[b] !== high) {
        rank[a] = high;
        rank[b] = high;
        changed = true;
      }
    }
    if (!changed) break;
  }
  return rank;
}

/** Layered: each rank a row, the one-way ties pointing down (a parent above a child), the order in
 * a row from a fixed number of barycentre sweeps. With no one-way ties it is rows by steps from the
 * focus. Built for family trees and lineage (ADR 0407). */
export const layered: Engine = (graph: LayoutGraph) => {
  const count = graph.ids.length;
  if (count === 0) return [];
  const rank =
    graph.arcs.length > 0
      ? rankOf(graph)
      : steps(adjacency(graph), graph.focus).map((d) => Math.max(0, d));
  const rows: number[][] = [];
  for (let n = 0; n < count; n += 1) {
    const row = rows[rank[n] as number] ?? [];
    row.push(n);
    rows[rank[n] as number] = row;
  }
  const next = adjacency(graph);
  const place = new Array<number>(count).fill(0);
  rows.forEach((row) => {
    row?.forEach((node, i) => {
      place[node] = i;
    });
  });
  // Barycentre sweeps down and up, stable by index.
  for (let sweep = 0; sweep < SWEEPS; sweep += 1) {
    const order = sweep % 2 === 0 ? rows.keys() : [...rows.keys()].reverse();
    for (const r of order) {
      const row = rows[r];
      if (!row) continue;
      const score = (node: number) => {
        const others = (next[node] ?? []).filter((o) => rank[o] !== rank[node]);
        if (others.length === 0) return place[node] as number;
        return others.reduce((sum, o) => sum + (place[o] as number), 0) / others.length;
      };
      row.sort((a, b) => score(a) - score(b) || a - b);
      row.forEach((node, i) => {
        place[node] = i;
      });
    }
  }
  const out: Positions = new Array(count);
  rows.forEach((row, r) => {
    if (!row) return;
    const width = (row.length - 1) * NODE_GAP;
    row.forEach((node, i) => {
      out[node] = { x: i * NODE_GAP - width / 2, y: r * RANK_GAP };
    });
  });
  return out;
};
