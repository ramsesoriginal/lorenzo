// The Cave system generator (ADR 0476): a seeded field of rock and open ground over a region,
// settled by a cellular automaton and traced into areas. A pure function of the region, the
// options and the seed (ADR 0475): no `Math.random`, no clock, and only whole-number hashing, the
// four operations and comparisons, so every browser draws the same caves.
import { type Geometry, type Part, seeded } from '@lorenzo/map-renderer';
import { decimalsFor, fieldOver, onSheet } from './field';
import type { Region } from './generator';
import { nested, outlines } from './marching-squares';

export type CaveOptions = {
  /** The cells across the box around the region. */
  size: number;
  /** The chance a cell begins as rock. */
  density: number;
  /** How many times the automaton is run. */
  passes: number;
  /** A pocket or a pillar of fewer cells than this is taken away. */
  smallest: number;
};

export type Caves = {
  /** One polygon part a cave, its pillars as holes; null when there is no cave. */
  geometry: Geometry | null;
  caves: number;
};

/** The groups of touching cells (by their sides) that `wanted` picks, each a list of places. */
function groups(cols: number, rows: number, wanted: (place: number) => boolean): number[][] {
  const seen = new Uint8Array(cols * rows);
  const found: number[][] = [];

  for (let start = 0; start < cols * rows; start += 1) {
    if (seen[start] || !wanted(start)) continue;

    const group = [start];

    seen[start] = 1;

    for (let at = 0; at < group.length; at += 1) {
      const place = group[at] as number;
      const i = place % cols;
      const next = [
        i > 0 ? place - 1 : -1,
        i + 1 < cols ? place + 1 : -1,
        place - cols,
        place + cols,
      ];

      for (const other of next) {
        if (other < 0 || other >= cols * rows || seen[other] || !wanted(other)) continue;

        seen[other] = 1;
        group.push(other);
      }
    }

    found.push(group);
  }

  return found;
}

/**
 * The softened field holds ninths, so a crossing of the half-way level lies at one of a few
 * fractions of a cell's edge, no two of them nearer than a seventy-second of it: what the sheet's
 * decimals must keep apart.
 */
const APART = 72;

export function caveSystem(region: Region, options: CaveOptions, seed: number): Caves {
  // 1. The field, and the rock that never changes: its edge, a cell outside the region, and a
  // cell beside one, so that an outline between two cells stays within the region.
  const field = fieldOver(region, Math.round(options.size));

  if (!field) return { geometry: null, caves: 0 };

  const { cols, rows, wall } = field;
  const count = cols * rows;

  // 2. Every other cell is rock with the chance Density, drawn in order from the seed.
  const next = seeded(`cave:${seed}`);
  let rock = new Uint8Array(count);

  for (let place = 0; place < count; place += 1) {
    rock[place] = wall[place] || next() < options.density ? 1 : 0;
  }

  // 3. The automaton: rock where five or more of the nine cells around and under a cell are rock.
  for (let pass = 0; pass < options.passes; pass += 1) {
    const settled = new Uint8Array(count);

    for (let place = 0; place < count; place += 1) {
      if (wall[place]) {
        settled[place] = 1;
        continue;
      }

      const i = place % cols;
      let around = 0;

      for (let dj = -1; dj <= 1; dj += 1) {
        for (let di = -1; di <= 1; di += 1)
          around += rock[place + dj * cols + i + di - i] as number;
      }

      settled[place] = around >= 5 ? 1 : 0;
    }

    rock = settled;
  }

  // 4. A pocket of fewer cells than Smallest cave is filled, and a pillar of fewer is opened.
  for (const pocket of groups(cols, rows, (place) => !rock[place])) {
    if (pocket.length < options.smallest) for (const place of pocket) rock[place] = 1;
  }

  for (const pillar of groups(cols, rows, (place) => rock[place] === 1)) {
    if (pillar.length < options.smallest && !pillar.some((place) => wall[place])) {
      for (const place of pillar) rock[place] = 0;
    }
  }

  // 5. Softened once, so an outline is no staircase: a cell is the share of open ground among its
  // nine. The level 0.5 is none of the ninths, so no outline passes through a cell's middle.
  const soft = new Float64Array(count);

  for (let place = 0; place < count; place += 1) {
    if (wall[place]) continue;

    const i = place % cols;
    let open = 0;

    for (let dj = -1; dj <= 1; dj += 1) {
      for (let di = -1; di <= 1; di += 1)
        open += 1 - (rock[place + dj * cols + i + di - i] as number);
    }

    soft[place] = open / 9;
  }

  // 6. Traced, put on the sheet to two decimals, and nested: a pillar in the cave that holds it.
  const rings = onSheet(field, outlines(soft, cols, rows, 0.5), decimalsFor(field, APART));
  const parts = nested(rings).map((area): Part => ({ shape: 'polygon', rings: area }));

  return parts.length === 0
    ? { geometry: null, caves: 0 }
    : { geometry: { format: 'lorenzo.geometry/1', parts }, caves: parts.length };
}
