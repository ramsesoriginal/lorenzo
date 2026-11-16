// The Spline tool's curve (ADR 0471): a smooth line through points, written as one open bezier part
// and read back from one. Pure: nothing here touches the page.
import type { Part } from '@lorenzo/map-renderer';

type Pt = readonly [number, number];
type Bezier = Extract<Part, { shape: 'bezier' }>;

/**
 * The start and three for every segment count toward a placement's 2,000 vertices (ADR 0337), so a
 * spline has at most 666 segments: this many points.
 */
export const SPLINE_MAX_POINTS = 667;

/** How near a stored control must be to the spline's own, in drawing units, to be read as a spline. */
const NEAR = 0.02;

const round2 = (n: number): number => Math.round(n * 100) / 100;

/**
 * The two controls of each segment of a cardinal spline through `pts`: at a point the curve runs
 * along the line from the point before to the point after, scaled by `(1 - tension) / 2`, an end
 * using itself for the neighbour it lacks, and a control is a third of that from its end.
 */
function controls(pts: readonly Pt[], tension: number): [Pt, Pt][] {
  const k = (1 - tension) / 6;
  const lean = (i: number): Pt => {
    const here = pts[i] as Pt;
    const before = pts[i - 1] ?? here;
    const after = pts[i + 1] ?? here;

    return [(after[0] - before[0]) * k, (after[1] - before[1]) * k];
  };
  const out: [Pt, Pt][] = [];

  for (let i = 0; i + 1 < pts.length; i += 1) {
    const a = pts[i] as Pt;
    const b = pts[i + 1] as Pt;
    const la = lean(i);
    const lb = lean(i + 1);

    out.push([
      [a[0] + la[0], a[1] + la[1]],
      [b[0] - lb[0], b[1] - lb[1]],
    ]);
  }

  return out;
}

/** The bezier part of a spline through at least two points, to two decimals. */
export function splinePart(pts: readonly Pt[], tension: number): Bezier {
  const at = pts.map((p): Pt => [round2(p[0]), round2(p[1])]);
  const start = at[0] as Pt;

  return {
    shape: 'bezier',
    start,
    segs: controls(at, tension).map(([c1, c2], i) => [
      [round2(c1[0]), round2(c1[1])],
      [round2(c2[0]), round2(c2[1])],
      at[i + 1] as Pt,
    ]),
  };
}

/**
 * The points and tension of a bezier part that is a spline: open, and with every control where
 * one tension (of two decimals, from 0 to 1) puts it. Any other bezier is null.
 */
export function splineOf(part: Part): { pts: Pt[]; tension: number } | null {
  if (part.shape !== 'bezier' || part.closed || part.segs.length === 0) return null;
  if (part.segs.length + 1 > SPLINE_MAX_POINTS) return null;

  const pts: Pt[] = [part.start, ...part.segs.map((seg) => seg[2])];
  // With no tension every control is a known offset from its end; the stored offsets are those
  // times (1 - tension). The best fit of that one number over all controls:
  const loose = controls(pts, 0);
  let dot = 0;
  let size = 0;

  for (const [i, seg] of part.segs.entries()) {
    const a = pts[i] as Pt;
    const b = pts[i + 1] as Pt;
    const [l1, l2] = loose[i] as [Pt, Pt];

    for (const [stored, end, free] of [
      [seg[0], a, l1],
      [seg[1], b, l2],
    ] as const) {
      const want: Pt = [free[0] - end[0], free[1] - end[1]];

      dot += (stored[0] - end[0]) * want[0] + (stored[1] - end[1]) * want[1];
      size += want[0] * want[0] + want[1] * want[1];
    }
  }

  // Points that all coincide say nothing of the tension.
  const tension = size === 0 ? 0.5 : round2(1 - dot / size);

  if (!(tension >= 0 && tension <= 1)) return null;

  const again = splinePart(pts, tension);
  const near = (p: Pt, q: Pt) => Math.abs(p[0] - q[0]) <= NEAR && Math.abs(p[1] - q[1]) <= NEAR;
  const same = part.segs.every((seg, i) => {
    const own = again.segs[i];

    return own !== undefined && near(seg[0], own[0]) && near(seg[1], own[1]);
  });

  return same ? { pts: pts.map((p): Pt => [p[0], p[1]]), tension } : null;
}

/** Points along the curve for an overlay: each segment cut into `steps` straight pieces. */
export function splineCurve(pts: readonly Pt[], tension: number, steps = 12): Pt[] {
  if (pts.length < 2) return pts.map((p): Pt => [p[0], p[1]]);

  const out: Pt[] = [pts[0] as Pt];

  for (const [i, [c1, c2]] of controls(pts, tension).entries()) {
    const a = pts[i] as Pt;
    const b = pts[i + 1] as Pt;

    for (let s = 1; s <= steps; s += 1) {
      const t = s / steps;
      const u = 1 - t;
      const w = [u * u * u, 3 * u * u * t, 3 * u * t * t, t * t * t] as const;

      out.push([
        w[0] * a[0] + w[1] * c1[0] + w[2] * c2[0] + w[3] * b[0],
        w[0] * a[1] + w[1] * c1[1] + w[2] * c2[1] + w[3] * b[1],
      ]);
    }
  }

  return out;
}
