import type { BBox, Part, Placement, Point } from './types';

/** Decimals kept in every number of a Scene. */
const DECIMALS = 100;

/** A finite number rounded to two decimals, with no negative zero; anything else throws. */
export function num(n: number, what = 'number'): number {
  if (typeof n !== 'number' || !Number.isFinite(n)) {
    throw new RangeError(`map-renderer: ${what} is not a finite number`);
  }

  const v = Math.round(n * DECIMALS) / DECIMALS;

  return v === 0 ? 0 : v;
}

export function finitePoint(p: Point, what: string): Point {
  if (!Array.isArray(p) || p.length < 2) {
    throw new RangeError(`map-renderer: ${what} is not a point`);
  }

  const x = p[0];
  const y = p[1];

  if (!Number.isFinite(x) || !Number.isFinite(y)) {
    throw new RangeError(`map-renderer: ${what} is not finite`);
  }

  return [x, y];
}

/** Segments one cubic is cut into for bounding boxes and hit tests. */
export const CUBIC_STEPS = 12;

export function cubicAt(p0: Point, p1: Point, p2: Point, p3: Point, t: number): Point {
  const u = 1 - t;
  const a = u * u * u;
  const b = 3 * u * u * t;
  const c = 3 * u * t * t;
  const d = t * t * t;

  return [
    a * p0[0] + b * p1[0] + c * p2[0] + d * p3[0],
    a * p0[1] + b * p1[1] + c * p2[1] + d * p3[1],
  ];
}

/** The points of a cubic after its start, `steps` of them, the last being `p3` itself. */
export function flattenCubic(
  p0: Point,
  p1: Point,
  p2: Point,
  p3: Point,
  steps = CUBIC_STEPS,
): Point[] {
  const out: Point[] = [];

  for (let i = 1; i < steps; i += 1) out.push(cubicAt(p0, p1, p2, p3, i / steps));

  out.push(p3);

  return out;
}

export function bboxOf(points: readonly Point[]): BBox {
  let x0 = Number.POSITIVE_INFINITY;
  let y0 = Number.POSITIVE_INFINITY;
  let x1 = Number.NEGATIVE_INFINITY;
  let y1 = Number.NEGATIVE_INFINITY;

  for (const [x, y] of points) {
    if (x < x0) x0 = x;
    if (x > x1) x1 = x;
    if (y < y0) y0 = y;
    if (y > y1) y1 = y;
  }

  return [x0, y0, x1, y1];
}

export function growBBox(box: BBox, by: number): BBox {
  return [box[0] - by, box[1] - by, box[2] + by, box[3] + by];
}

/** Whether `p` lies in the polygon whose rings are given, by the even-odd rule. */
export function pointInRings(p: Point, rings: readonly (readonly Point[])[]): boolean {
  const [x, y] = p;
  let inside = false;

  for (const ring of rings) {
    for (let i = 0, j = ring.length - 1; i < ring.length; j = i, i += 1) {
      const a = ring[i];
      const b = ring[j];

      if (!a || !b) continue;

      if (a[1] > y !== b[1] > y && x < ((b[0] - a[0]) * (y - a[1])) / (b[1] - a[1]) + a[0]) {
        inside = !inside;
      }
    }
  }

  return inside;
}

/** Distance from `p` to the segment `a`-`b`. */
export function distanceToSegment(p: Point, a: Point, b: Point): number {
  const dx = b[0] - a[0];
  const dy = b[1] - a[1];
  const len2 = dx * dx + dy * dy;
  let t = len2 === 0 ? 0 : ((p[0] - a[0]) * dx + (p[1] - a[1]) * dy) / len2;

  t = Math.max(0, Math.min(1, t));

  return Math.hypot(p[0] - (a[0] + t * dx), p[1] - (a[1] + t * dy));
}

/** The flattened outline of a bezier part, in drawing units. */
export function bezierPoints(part: Extract<Part, { shape: 'bezier' }>): Point[] {
  const out: Point[] = [part.start];
  let at = part.start;

  for (const seg of part.segs) {
    out.push(...flattenCubic(at, seg[0], seg[1], seg[2]));
    at = seg[2];
  }

  return out;
}

/** The rings of an area part (polygon, closed bezier) flattened, in drawing units, else null. */
export function areaRings(part: Part): Point[][] | null {
  if (part.shape === 'polygon') return part.rings.map((ring) => [...ring]);

  if (part.shape === 'bezier' && part.closed) return [bezierPoints(part)];

  return null;
}

/** A bounding box (a superset for curves) of a part, in drawing units. */
export function partBounds(part: Part): BBox | null {
  switch (part.shape) {
    case 'point':
      return [part.at[0], part.at[1], part.at[0], part.at[1]];
    case 'circle':
      return [part.at[0] - part.r, part.at[1] - part.r, part.at[0] + part.r, part.at[1] + part.r];
    case 'polyline':
      return part.pts.length > 0 ? bboxOf(part.pts) : null;
    case 'bezier':
      return bboxOf(bezierPoints(part));
    case 'polygon': {
      const all = part.rings.flat();

      return all.length > 0 ? bboxOf(all) : null;
    }
    default:
      return null;
  }
}

/** The centre of a placement's bounding box in drawing units, or null for one with no parts. */
export function placementCentre(placement: Placement): Point | null {
  let box: BBox | null = null;

  for (const part of placement.geometry.parts) {
    const b = partBounds(part);

    if (!b) continue;

    box = box
      ? [
          Math.min(box[0], b[0]),
          Math.min(box[1], b[1]),
          Math.max(box[2], b[2]),
          Math.max(box[3], b[3]),
        ]
      : b;
  }

  return box ? [(box[0] + box[2]) / 2, (box[1] + box[3]) / 2] : null;
}

export function unionBBox(a: BBox, b: BBox): BBox {
  return [Math.min(a[0], b[0]), Math.min(a[1], b[1]), Math.max(a[2], b[2]), Math.max(a[3], b[3])];
}

export function bboxesOverlap(a: BBox, b: BBox): boolean {
  return a[0] <= b[2] && a[2] >= b[0] && a[1] <= b[3] && a[3] >= b[1];
}

export type FlatPath = { pts: Point[]; closed: boolean }[];

/**
 * Reads the path data this package writes (absolute `M`, `L`, `C`, `Z`) back into polylines, a
 * curve cut into `CUBIC_STEPS` segments. It is the hit test's only use of path data.
 */
export function flattenPath(d: string): FlatPath {
  const tokens = d.match(/[MLCZ]|-?\d+(?:\.\d+)?/g) ?? [];
  const out: FlatPath = [];
  let current: { pts: Point[]; closed: boolean } | null = null;
  let i = 0;

  const read = (): Point => {
    const x = Number(tokens[i]);
    const y = Number(tokens[i + 1]);

    i += 2;

    return [x, y];
  };

  while (i < tokens.length) {
    const t = tokens[i];

    i += 1;

    if (t === 'M') {
      current = { pts: [read()], closed: false };
      out.push(current);
    } else if (t === 'L' && current) {
      current.pts.push(read());
    } else if (t === 'C' && current) {
      const c1 = read();
      const c2 = read();
      const end = read();
      const start = current.pts[current.pts.length - 1];

      if (start) current.pts.push(...flattenCubic(start, c1, c2, end));
    } else if (t === 'Z' && current) {
      current.closed = true;
    }
  }

  return out;
}
