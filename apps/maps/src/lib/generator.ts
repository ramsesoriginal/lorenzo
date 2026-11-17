// What the generators share (ADR 0475): the seed, the region one works on, the check that a result
// is one the API will take, and the name of the history step an Apply makes. Pure: nothing here
// touches the page, and nothing here is random.
import type { Geometry } from '@lorenzo/map-renderer';
import { checkGeometry, LIMITS } from './validate';

type Pt = readonly [number, number];
type Box = readonly [number, number, number, number];

/** A seed is a whole number from 0 to this. */
export const SEED_MOST = 999_999;

/** A typed seed as a seed, or null: not a whole number, or out of range. */
export function seedOf(text: string): number | null {
  const typed = text.trim();

  if (!/^\d+$/.test(typed)) return null;

  const seed = Number(typed);

  return seed <= SEED_MOST ? seed : null;
}

/** The seed a Roll takes: the next number, and 0 after the last. */
export const nextSeed = (seed: number): number => (seed >= SEED_MOST ? 0 : seed + 1);

/**
 * A first seed from a number the page drew (32 random bits from the browser's `crypto`). The
 * drawing is the page's; a generator only ever sees the seed.
 */
export const seedFrom = (bits: number): number => (bits >>> 0) % (SEED_MOST + 1);

/** Where a generator works: the whole sheet, or inside one area or one circle. */
export type Region = {
  kind: 'sheet' | 'area' | 'circle';
  /** The box around it, `[x0, y0, x1, y1]`. */
  bounds: Box;
  /** Whether a point of the drawing is in it; an edge counts as outside for an area. */
  contains(p: Pt): boolean;
  /** How a history step and a status line say it: "the whole sheet", "Old Town". */
  words: string;
};

function inRing(ring: readonly Pt[], p: Pt): boolean {
  let inside = false;

  for (let i = 0, j = ring.length - 1; i < ring.length; j = i, i += 1) {
    const a = ring[i] as Pt;
    const b = ring[j] as Pt;

    if (
      a[1] > p[1] !== b[1] > p[1] &&
      p[0] < ((b[0] - a[0]) * (p[1] - a[1])) / (b[1] - a[1]) + a[0]
    ) {
      inside = !inside;
    }
  }

  return inside;
}

/**
 * The region of a selection: the selected placement when it is one area without holes or one
 * circle, and otherwise the whole sheet. What is already drawn there is not looked at.
 */
export function regionOf(
  selected: { name: string; geometry: Geometry } | null,
  sheet: Box,
): Region {
  const only = selected?.geometry.parts.length === 1 ? selected.geometry.parts[0] : undefined;

  if (selected && only?.shape === 'polygon' && only.rings.length === 1) {
    const ring = only.rings[0] as readonly Pt[];
    const xs = ring.map((p) => p[0]);
    const ys = ring.map((p) => p[1]);

    return {
      kind: 'area',
      bounds: [Math.min(...xs), Math.min(...ys), Math.max(...xs), Math.max(...ys)],
      contains: (p) => inRing(ring, p),
      words: selected.name,
    };
  }

  if (selected && only?.shape === 'circle') {
    const { at, r } = only;

    return {
      kind: 'circle',
      bounds: [at[0] - r, at[1] - r, at[0] + r, at[1] + r],
      contains: (p) => (p[0] - at[0]) * (p[0] - at[0]) + (p[1] - at[1]) * (p[1] - at[1]) < r * r,
      words: selected.name,
    };
  }

  return {
    kind: 'sheet',
    bounds: sheet,
    contains: (p) => p[0] >= sheet[0] && p[0] <= sheet[2] && p[1] >= sheet[1] && p[1] <= sheet[3],
    words: 'the whole sheet',
  };
}

/** What a tool says to change when a result is over a limit: one sentence for each. */
export type Hints = {
  /** More than a placement's vertices (ADR 0337, ADR 0481). */
  vertices: string;
  /** More than a placement's parts. */
  parts: string;
  /** More than a placement's bytes. */
  bytes: string;
  /** A polygon the API would refuse: one that touches or crosses itself, or a stray hole. */
  shape: string;
};

export type Fit = { ok: true } | { ok: false; why: string };

/**
 * Whether a result can be applied: the API would take it. A result that does not fit is never
 * offered and never made coarser on its own; the answer names the limit and what to change.
 */
export function fits(geometry: Geometry | null, hints: Hints): Fit {
  if (!geometry || geometry.parts.length === 0) {
    return { ok: false, why: 'There is nothing to draw with these options. Try another seed.' };
  }

  if (geometry.parts.length > LIMITS.parts) {
    return {
      ok: false,
      why: `This is ${geometry.parts.length} pieces, and a drawing holds ${LIMITS.parts}. ${hints.parts}`,
    };
  }

  const checked = checkGeometry(geometry);

  if (checked.ok) return { ok: true };

  if (checked.why.includes('vertices')) {
    return {
      ok: false,
      why: `This has more than the ${LIMITS.vertices} points a drawing holds. ${hints.vertices}`,
    };
  }

  if (checked.why.includes('a value') || checked.why.includes('a unit')) {
    return { ok: false, why: 'A height is larger than the Map can hold, or its unit is too long.' };
  }

  if (checked.why.includes('too large')) {
    return { ok: false, why: `This is larger than a drawing may be. ${hints.bytes}` };
  }

  return { ok: false, why: `One of its areas is not a shape the Map can hold. ${hints.shape}` };
}

/**
 * The name of the history step an Apply makes: the tool, the seed, how much it drew and where.
 * "Drew a cave system, seed 4821: 6 caves in the whole sheet".
 */
export function stepName(what: string, seed: number, count: string, region: Region): string {
  return `Drew ${what}, seed ${seed}: ${count} in ${region.words}`;
}

/** A count with its noun: "1 cave", "6 caves". */
export const counted = (n: number, one: string, many: string): string =>
  `${n} ${n === 1 ? one : many}`;
