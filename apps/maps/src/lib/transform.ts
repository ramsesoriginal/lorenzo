// Mirror, turn and copy (ADR 0490): a drawing reflected or turned about the sheet's middle, point
// by point, with what each part carries kept; and whether a drawing of cells lands on cells. Pure.
import type { BBox, Geometry, GridSpec, Part, Point } from '@lorenzo/map-renderer';
import { cellsOf } from './cells-edit';

/** How a drawing is moved: reflected left to right, top to bottom, or both, which is a half turn. */
export type Transform = 'across' | 'down' | 'turn';

/** What a person calls each, for a history step and a sentence. */
export const TRANSFORM_WORDS: Record<Transform, string> = {
  across: 'mirrored across',
  down: 'mirrored down',
  turn: 'turned 180°',
};

/** To six decimals, the most the format holds; never -0. */
const tidy = (n: number) => Math.round(n * 1e6) / 1e6 || 0;

/** A point moved by a transform about the middle of a sheet. */
export function movePoint(how: Transform, [x0, y0, x1, y1]: BBox, [x, y]: Point): Point {
  const mx = how === 'down' ? x : x0 + x1 - x;
  const my = how === 'across' ? y : y0 + y1 - y;

  return [tidy(mx), tidy(my)];
}

/** A part moved by a transform, carrying its height and unit along. */
function movePart(how: Transform, sheet: BBox, part: Part): Part {
  const at = (p: Point) => movePoint(how, sheet, p);

  switch (part.shape) {
    case 'point':
    case 'circle':
      return { ...part, at: at(part.at) };
    case 'polyline':
      return { ...part, pts: part.pts.map(at) };
    case 'bezier':
      return {
        ...part,
        start: at(part.start),
        segs: part.segs.map((seg) => [at(seg[0]), at(seg[1]), at(seg[2])] as const),
      };
    case 'polygon':
      return { ...part, rings: part.rings.map((ring) => ring.map(at)) };
  }
}

/** A geometry moved by a transform about the middle of a sheet (ADR 0490). */
export function transformed(how: Transform, sheet: BBox, geometry: Geometry): Geometry {
  return {
    format: geometry.format,
    parts: geometry.parts.map((part) => movePart(how, sheet, part)),
  };
}

/**
 * A drawing moved, or why it may not be: a drawing of cells stays cells only where it lands on
 * whole cells, which hexes, whose rows or columns are offset, and a sheet not a whole number of
 * cells across often do not give (ADR 0490).
 */
export function moved(
  how: Transform,
  sheet: BBox,
  geometry: Geometry,
  grid: GridSpec | null,
): { ok: true; geometry: Geometry } | { ok: false; why: string } {
  const next = transformed(how, sheet, geometry);

  if (grid && cellsOf(geometry, grid, sheet) && !cellsOf(next, grid, sheet)) {
    return {
      ok: false,
      why: `${capital(TRANSFORM_WORDS[how])}, its cells would not land on whole cells of this grid. Nothing was changed.`,
    };
  }

  return { ok: true, geometry: next };
}

const capital = (words: string) => words.charAt(0).toUpperCase() + words.slice(1);
