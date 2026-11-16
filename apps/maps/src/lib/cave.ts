// The Cave system generator (ADR 0476): a seeded field of rock and open ground over a region,
// settled by a cellular automaton and traced into areas. A pure function of the region, the
// options and the seed (ADR 0475): no `Math.random`, no clock, and only whole-number hashing, the
// four operations and comparisons, so every browser draws the same caves.
import { type Geometry, type Part, seeded } from '@lorenzo/map-renderer';
import type { Region } from './generator';
import { nested, outlines } from './marching-squares';

type Pt = readonly [number, number];

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

/** The fewest rows a field has, so a very wide region still has room for a cave. */
const MIN_ROWS = 4;

const round2 = (n: number): number => Math.round(n * 100) / 100;

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

export function caveSystem(region: Region, options: CaveOptions, seed: number): Caves {
  const [x0, y0, x1, y1] = region.bounds;
  const cols = Math.round(options.size);
  const cell = (x1 - x0) / cols;

  if (!(cell > 0) || !(y1 > y0) || cols < 3) return { geometry: null, caves: 0 };

  const rows = Math.max(MIN_ROWS, Math.ceil((y1 - y0) / cell));
  const count = cols * rows;
  const middle = (place: number): Pt => {
    const i = place % cols;

    return [x0 + (i + 0.5) * cell, y0 + ((place - i) / cols + 0.5) * cell];
  };

  // 1. Rock that never changes: the edge of the field, a cell outside the region, and a cell
  // beside one, so that an outline between two cells stays within the region.
  const outside = new Uint8Array(count);

  for (let place = 0; place < count; place += 1) {
    const i = place % cols;
    const j = (place - i) / cols;

    if (i === 0 || j === 0 || i === cols - 1 || j === rows - 1 || !region.contains(middle(place))) {
      outside[place] = 1;
    }
  }

  const wall = new Uint8Array(count);

  for (let place = 0; place < count; place += 1) {
    const i = place % cols;
    const j = (place - i) / cols;

    for (let dj = -1; dj <= 1 && !wall[place]; dj += 1) {
      for (let di = -1; di <= 1; di += 1) {
        const oi = i + di;
        const oj = j + dj;

        if (oi < 0 || oj < 0 || oi >= cols || oj >= rows || outside[oj * cols + oi]) {
          wall[place] = 1;
          break;
        }
      }
    }
  }

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
  const field = new Float64Array(count);

  for (let place = 0; place < count; place += 1) {
    if (wall[place]) continue;

    const i = place % cols;
    let open = 0;

    for (let dj = -1; dj <= 1; dj += 1) {
      for (let di = -1; di <= 1; di += 1)
        open += 1 - (rock[place + dj * cols + i + di - i] as number);
    }

    field[place] = open / 9;
  }

  // 6. Traced, put on the sheet to two decimals, and nested: a pillar in the cave that holds it.
  const rings = outlines(field, cols, rows, 0.5)
    .map((ring) => {
      const pts: Pt[] = [];

      for (const [fx, fy] of ring) {
        const p: Pt = [round2(x0 + (fx + 0.5) * cell), round2(y0 + (fy + 0.5) * cell)];
        const last = pts[pts.length - 1];

        if (!last || last[0] !== p[0] || last[1] !== p[1]) pts.push(p);
      }

      const first = pts[0];
      const last = pts[pts.length - 1];

      if (pts.length > 1 && first && last && first[0] === last[0] && first[1] === last[1])
        pts.pop();

      return pts;
    })
    .filter((ring) => ring.length >= 3);
  const parts = nested(rings).map((area): Part => ({ shape: 'polygon', rings: area }));

  return parts.length === 0
    ? { geometry: null, caves: 0 }
    : { geometry: { format: 'lorenzo.geometry/1', parts }, caves: parts.length };
}
