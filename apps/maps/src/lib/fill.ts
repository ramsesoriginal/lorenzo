// The Fill by marching squares generator (ADR 0477): smooth noise from a seed over a region, traced
// at a level into areas and, when asked, into height lines above it. A pure function of the region,
// the options and the seed (ADR 0475): no `Math.random`, no clock, and only whole-number hashing,
// the four operations and comparisons.
import { type Geometry, type Part, seeded } from '@lorenzo/map-renderer';
import { decimalsFor, type Field, fieldOver, onSheet, pathsOnSheet } from './field';
import type { Region } from './generator';
import { nested, outlines, ringArea } from './marching-squares';

type Pt = readonly [number, number];

export type FillOptions = {
  /** How many cells of the coarse noise lie across the region: 2 is a few large shapes. */
  scale: number;
  /** The areas are where the field is above this, from 0 to 1. */
  level: number;
  /** An area or a hole of fewer cells than this is left out. */
  smallest: number;
  /** How many height lines are traced above the level. */
  lines: number;
  /** The height of the first line, of each next one more, and their unit: all three, or none. */
  first: number | null;
  step: number | null;
  unit: string | null;
};

export type Fill = {
  /**
   * A polygon part an area, then a polyline a height line: closed, or ending at the region's edge.
   * Null when there is nothing.
   */
  geometry: Geometry | null;
  areas: number;
  lines: number;
  /** Height lines were asked for without their heights: they are previewed, and not to be written. */
  needsHeights: boolean;
};

/** The cells across the box around the region: fine enough for a smooth outline. */
export const FILL_COLS = 64;

/**
 * A crossing of an outline is put on one of this many steps along a cell's edge, so that no two
 * points of a result are nearer than a sixteenth of a cell and rounding cannot fold a ring.
 */
const STEPS = 16;

/** Smooth noise between 0 and 1 for every cell: a coarse lattice and, half as strong, a finer one. */
function noise(field: Field, scale: number, seed: number): Float64Array {
  const { cols, rows } = field;
  const next = seeded(`fill:${seed}`);
  const out = new Float64Array(cols * rows);

  for (const [fineness, weight] of [
    [1, 2 / 3],
    [2, 1 / 3],
  ] as const) {
    const across = scale * fineness;
    const nx = across + 2;
    const ny = Math.ceil((rows * across) / cols) + 2;
    const lattice = new Float64Array(nx * ny);

    for (let k = 0; k < nx * ny; k += 1) lattice[k] = next();

    for (let j = 0; j < rows; j += 1) {
      for (let i = 0; i < cols; i += 1) {
        const u = (i * across) / cols;
        const v = (j * across) / cols;
        const iu = Math.floor(u);
        const iv = Math.floor(v);
        const fu = u - iu;
        const fv = v - iv;
        // Eased, so the joins of the lattice do not show.
        const su = fu * fu * (3 - 2 * fu);
        const sv = fv * fv * (3 - 2 * fv);
        const a = lattice[iv * nx + iu] as number;
        const b = lattice[iv * nx + iu + 1] as number;
        const c = lattice[(iv + 1) * nx + iu] as number;
        const d = lattice[(iv + 1) * nx + iu + 1] as number;
        const top = a + (b - a) * su;
        const bottom = c + (d - c) * su;

        out[j * cols + i] = (out[j * cols + i] as number) + (top + (bottom - top) * sv) * weight;
      }
    }
  }

  return out;
}

/** The rings of a field at a level, without the small ones, on the sheet. */
function traced(field: Field, values: Float64Array, level: number, smallest: number): Pt[][] {
  // No value may be the level itself, or two rings could meet in a point.
  const apart = values.map((value) => (value === level ? value - 1e-9 : value));

  return onSheet(
    field,
    outlines(apart, field.cols, field.rows, level, STEPS).filter(
      (ring) => ringArea(ring) >= smallest,
    ),
    decimalsFor(field, STEPS),
  );
}

/** Whether a point of a ring lies between a cell that takes no part and one that does. */
function atEdge(field: Field, [x, y]: Pt): boolean {
  // A crossing lies on the edge between two neighbouring cells: across when y is whole, down when
  // x is, and never on a cell's middle.
  const across = Number.isInteger(y);
  const i = Math.floor(x);
  const j = Math.floor(y);
  const one = j * field.cols + i;
  const other = across ? one + 1 : one + field.cols;

  return field.wall[one] === 1 || field.wall[other] === 1;
}

/**
 * The height lines of a field at a level, on the sheet. A line that stays inside the region goes
 * round and ends where it began. Where the region's edge cuts one, the stretch that would run
 * along the edge is left out: the line ends at the edge, and goes on where it leaves it again.
 */
function heightLines(field: Field, values: Float64Array, level: number, smallest: number): Pt[][] {
  const apart = values.map((value) => (value === level ? value - 1e-9 : value));
  const paths: Pt[][] = [];

  for (const ring of outlines(apart, field.cols, field.rows, level, STEPS)) {
    if (ringArea(ring) < smallest) continue;

    const edge = ring.map((p) => atEdge(field, p));
    const start = edge.indexOf(true);

    if (start < 0) {
      paths.push([...ring, ring[0] as Pt]);
      continue;
    }

    // From a point at the edge, round the ring: each run of points inside the region is a line,
    // with the edge point before it and the one after it as its ends.
    let run: Pt[] = [ring[start] as Pt];

    for (let k = 1; k <= ring.length; k += 1) {
      const at = (start + k) % ring.length;
      const p = ring[at] as Pt;

      run.push(p);

      if (edge[at]) {
        if (run.length > 2) paths.push(run);

        run = [p];
      }
    }
  }

  return pathsOnSheet(field, paths, decimalsFor(field, STEPS));
}

export function fill(region: Region, options: FillOptions, seed: number): Fill {
  const none: Fill = { geometry: null, areas: 0, lines: 0, needsHeights: false };
  const field = fieldOver(region, FILL_COLS);

  if (!field) return none;

  const values = noise(field, Math.round(options.scale), seed);

  // A cell that takes no part holds 0, so every outline closes inside the region.
  for (let place = 0; place < values.length; place += 1) if (field.wall[place]) values[place] = 0;

  const areas = nested(traced(field, values, options.level, options.smallest)).map(
    (rings): Part => ({ shape: 'polygon', rings }),
  );

  if (areas.length === 0) return none;

  const count = Math.max(0, Math.round(options.lines));
  const { first, step, unit } = options;
  const heights = first !== null && step !== null && unit !== null && unit !== '';
  const lines: Part[] = [];

  for (let k = 1; k <= count; k += 1) {
    const level = options.level + ((1 - options.level) * k) / (count + 1);

    for (const pts of heightLines(field, values, level, options.smallest)) {
      lines.push({
        shape: 'polyline',
        pts,
        ...(heights
          ? {
              value: Math.round(((first as number) + (k - 1) * (step as number)) * 1e6) / 1e6,
              unit: unit as string,
            }
          : {}),
      });
    }
  }

  return {
    geometry: { format: 'lorenzo.geometry/1', parts: [...areas, ...lines] },
    areas: areas.length,
    lines: lines.length,
    needsHeights: lines.length > 0 && !heights,
  };
}
