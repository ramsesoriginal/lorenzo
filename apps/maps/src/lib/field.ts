// A field of square cells over a region (ADR 0476, ADR 0477): what the generators that trace
// outlines share. Which cells may never be part of what is drawn, where a cell is on the sheet, and
// traced rings put back on the sheet. Pure.
import type { Region } from './generator';

type Pt = readonly [number, number];

export type Field = {
  cols: number;
  rows: number;
  /** The side of a cell, in drawing units. */
  cell: number;
  /** The near corner of the box around the region. */
  x0: number;
  y0: number;
  /**
   * 1 for a cell that takes no part: at the edge of the field, with its middle outside the
   * region, or beside such a cell. An outline runs between the middles of two cells, so with
   * these left out it stays within the region.
   */
  wall: Uint8Array;
};

/** The fewest rows a field has, so a very wide region still has room. */
const MIN_ROWS = 4;

/** A field `cols` cells across the box around a region; null when the region has no room. */
export function fieldOver(region: Region, cols: number): Field | null {
  const [x0, y0, x1, y1] = region.bounds;
  const cell = (x1 - x0) / cols;

  if (!(cell > 0) || !(y1 > y0) || cols < 3) return null;

  const rows = Math.max(MIN_ROWS, Math.ceil((y1 - y0) / cell));
  const count = cols * rows;
  const outside = new Uint8Array(count);

  for (let place = 0; place < count; place += 1) {
    const i = place % cols;
    const j = (place - i) / cols;

    if (
      i === 0 ||
      j === 0 ||
      i === cols - 1 ||
      j === rows - 1 ||
      !region.contains([x0 + (i + 0.5) * cell, y0 + (j + 0.5) * cell])
    ) {
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

  return { cols, rows, cell, x0, y0, wall };
}

/**
 * Beyond this size a coordinate with decimals is not always one the validator takes: it checks a
 * number to a ten-thousandth of a millionth, and from 1,048,576 on there are numbers of two
 * decimals that cannot be held that exactly. A field that reaches out there is drawn in whole
 * units, which are far finer than its cells.
 */
const WHOLE_BEYOND = 1_000_000;

/**
 * How many decimals a field's outlines are kept to on the sheet: two, as the editor keeps
 * (ADR 0353); none for a field so far out that decimals are not safe; and, with `steps`, more than
 * two for a field so fine that points a step of a cell apart would merge, up to the six the
 * format holds (ADR 0337).
 */
export function decimalsFor(field: Field, steps?: number): number {
  const far = Math.max(
    Math.abs(field.x0),
    Math.abs(field.y0),
    Math.abs(field.x0 + field.cols * field.cell),
    Math.abs(field.y0 + field.rows * field.cell),
  );

  if (far > WHOLE_BEYOND) return 0;

  let decimals = 2;
  let unit = 0.01;

  while (steps !== undefined && field.cell / steps < 4 * unit && decimals < 6) {
    decimals += 1;
    unit /= 10;
  }

  return decimals;
}

/**
 * Rings in the field's own coordinates as rings on the sheet, to the decimals the field is kept to
 * unless others are asked for: a point equal to the one before it is dropped, and a ring of fewer than three points
 * with it.
 */
export function onSheet(
  field: Field,
  rings: readonly (readonly Pt[])[],
  decimals = decimalsFor(field),
): Pt[][] {
  let scale = 1;

  for (let d = 0; d < decimals; d += 1) scale *= 10;

  const rounded = (n: number): number => Math.round(n * scale) / scale;

  return rings
    .map((ring) => {
      const pts: Pt[] = [];

      for (const [fx, fy] of ring) {
        const p: Pt = [
          rounded(field.x0 + (fx + 0.5) * field.cell),
          rounded(field.y0 + (fy + 0.5) * field.cell),
        ];
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
}
