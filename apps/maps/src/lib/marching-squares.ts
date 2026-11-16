// Marching squares: the outlines of where a field of numbers is above a level, as closed rings.
// The Cave system uses it (ADR 0476), and the fill generator after it. Pure and exact in its
// order: the same field gives the same rings, point for point.

type Pt = readonly [number, number];

/**
 * The rings along which a field crosses `level`. The field is `cols` by `rows` numbers, row by row,
 * and a ring's points are in the field's own coordinates: `[2.5, 3]` is half-way between the
 * third and the fourth number of the fourth row. A crossing lies along the edge between two
 * numbers, where the level falls between them.
 *
 * Every number at the edge of the field must be at or below the level, so that every outline
 * closes; a field that breaks this throws. No number may equal the level exactly where a ring
 * passes, or two rings could meet in a point: the caller picks a level its numbers cannot take.
 * A square whose corners alternate is decided by the mean of the four.
 */
export function outlines(
  field: ArrayLike<number>,
  cols: number,
  rows: number,
  level: number,
): Pt[][] {
  if (field.length !== cols * rows) throw new RangeError('the field is not cols by rows');

  const at = (i: number, j: number): number => field[j * cols + i] as number;
  const above = (i: number, j: number): boolean => at(i, j) > level;

  for (let i = 0; i < cols; i += 1) {
    if (above(i, 0) || above(i, rows - 1)) throw new RangeError('the field is open at its edge');
  }

  for (let j = 0; j < rows; j += 1) {
    if (above(0, j) || above(cols - 1, j)) throw new RangeError('the field is open at its edge');
  }

  // An edge between two neighbouring numbers has a key: twice the place of its first number, and
  // one more when it runs down and not across.
  const across = (i: number, j: number): number => 2 * (j * cols + i);
  const down = (i: number, j: number): number => 2 * (j * cols + i) + 1;
  const links = new Map<number, number[]>();
  const join = (a: number, b: number): void => {
    const one = links.get(a);
    const other = links.get(b);

    if (one) one.push(b);
    else links.set(a, [b]);

    if (other) other.push(a);
    else links.set(b, [a]);
  };

  for (let j = 0; j + 1 < rows; j += 1) {
    for (let i = 0; i + 1 < cols; i += 1) {
      const a = above(i, j);
      const b = above(i + 1, j);
      const c = above(i + 1, j + 1);
      const d = above(i, j + 1);
      const top = across(i, j);
      const right = down(i + 1, j);
      const bottom = across(i, j + 1);
      const left = down(i, j);

      switch ((a ? 8 : 0) + (b ? 4 : 0) + (c ? 2 : 0) + (d ? 1 : 0)) {
        case 1:
        case 14:
          join(left, bottom);
          break;
        case 2:
        case 13:
          join(bottom, right);
          break;
        case 3:
        case 12:
          join(left, right);
          break;
        case 4:
        case 11:
          join(top, right);
          break;
        case 6:
        case 9:
          join(top, bottom);
          break;
        case 7:
        case 8:
          join(top, left);
          break;
        case 5:
        case 10: {
          // Corners alternate. When the middle is above the level the two that are above are one
          // region and each of the others is cut off alone; otherwise the other way about.
          const joined = (at(i, j) + at(i + 1, j) + at(i + 1, j + 1) + at(i, j + 1)) / 4 > level;
          const aloneAtTopLeft = a ? !joined : joined;

          if (aloneAtTopLeft) {
            join(top, left);
            join(bottom, right);
          } else {
            join(top, right);
            join(left, bottom);
          }

          break;
        }
        default:
          break;
      }
    }
  }

  const point = (key: number): Pt => {
    const place = key >> 1;
    const i = place % cols;
    const j = (place - i) / cols;
    const from = at(i, j);

    if (key % 2 === 0) {
      const to = at(i + 1, j);

      return [i + (level - from) / (to - from), j];
    }

    const to = at(i, j + 1);

    return [i, j + (level - from) / (to - from)];
  };

  const rings: Pt[][] = [];
  const seen = new Set<number>();

  for (const start of [...links.keys()].sort((x, y) => x - y)) {
    if (seen.has(start)) continue;

    const ring: Pt[] = [];
    let key: number | undefined = start;

    while (key !== undefined && !seen.has(key)) {
      seen.add(key);
      ring.push(point(key));
      key = (links.get(key) ?? []).find((next) => !seen.has(next));
    }

    rings.push(ring);
  }

  return rings;
}

/** Whether `p` is inside a ring (even-odd). */
export function ringHolds(ring: readonly Pt[], p: Pt): boolean {
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

/** The area a ring encloses. */
export function ringArea(ring: readonly Pt[]): number {
  let twice = 0;

  for (let i = 0, j = ring.length - 1; i < ring.length; j = i, i += 1) {
    const a = ring[j] as Pt;
    const b = ring[i] as Pt;

    twice += a[0] * b[1] - b[0] * a[1];
  }

  return Math.abs(twice) / 2;
}

/**
 * Rings that do not cross, as areas: each an outline followed by the holes that lie directly in
 * it. A ring inside a hole is an area of its own. A hole belongs to the smallest outline that
 * holds it. The areas keep the order of their outlines.
 */
export function nested(rings: readonly (readonly Pt[])[]): Pt[][][] {
  const holders = rings.map((ring, index) =>
    rings.flatMap((other, at) => (at !== index && ringHolds(other, ring[0] as Pt) ? [at] : [])),
  );
  const areas = new Map<number, Pt[][]>();

  rings.forEach((ring, index) => {
    if ((holders[index] as number[]).length % 2 === 0) areas.set(index, [[...ring]]);
  });

  rings.forEach((ring, index) => {
    const around = holders[index] as number[];

    if (around.length % 2 === 0) return;

    // The outline directly around a hole is the one with one ring fewer around it.
    const parent = around.find((at) => (holders[at] as number[]).length === around.length - 1);

    if (parent !== undefined) areas.get(parent)?.push([...ring]);
  });

  return [...areas.values()];
}
