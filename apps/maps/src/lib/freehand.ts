// The Freehand tool's line (ADR 0472): a dragged stroke simplified into a polyline that always
// fits a placement. Pure: nothing here touches the page.

type Pt = readonly [number, number];

/** A placement holds at most this many vertices (ADR 0337). */
export const MAX_VERTICES = 2000;

const round2 = (n: number): number => Math.round(n * 100) / 100;

/** How far `p` is from the segment between `a` and `b`. */
function distance(p: Pt, a: Pt, b: Pt): number {
  const dx = b[0] - a[0];
  const dy = b[1] - a[1];
  const length = dx * dx + dy * dy;

  if (length === 0) return Math.hypot(p[0] - a[0], p[1] - a[1]);

  const t = Math.max(0, Math.min(1, ((p[0] - a[0]) * dx + (p[1] - a[1]) * dy) / length));

  return Math.hypot(p[0] - (a[0] + t * dx), p[1] - (a[1] + t * dy));
}

/**
 * For each point, the largest tolerance that still keeps it under the Ramer-Douglas-Peucker rule:
 * the rule splits a span at its farthest point while that point is farther than the tolerance, so
 * a point is kept when it and every split above it were farther. The ends are always kept. Worked
 * out once, a stroke can then be simplified at any tolerance without walking it again.
 */
function weights(pts: readonly Pt[]): number[] {
  const weight = new Array<number>(pts.length).fill(0);

  if (pts.length === 0) return weight;

  weight[0] = Number.POSITIVE_INFINITY;
  weight[pts.length - 1] = Number.POSITIVE_INFINITY;

  // A list of spans to look at, so a long stroke never runs out of stack.
  const spans: [number, number, number][] = [[0, pts.length - 1, Number.POSITIVE_INFINITY]];

  while (spans.length > 0) {
    const [from, to, above] = spans.pop() as [number, number, number];
    let far = -1;
    let most = 0;

    for (let i = from + 1; i < to; i += 1) {
      const d = distance(pts[i] as Pt, pts[from] as Pt, pts[to] as Pt);

      if (d > most) {
        most = d;
        far = i;
      }
    }

    // Nothing off the line between the two ends: every point between them weighs nothing.
    if (far < 0) continue;

    const own = Math.min(most, above);

    weight[far] = own;
    spans.push([from, far, own], [far, to, own]);
  }

  return weight;
}

/**
 * The Ramer-Douglas-Peucker rule: a point is dropped when it lies no farther than `tolerance` from
 * the line between the points kept on either side. The ends are always kept.
 */
export function simplify(pts: readonly Pt[], tolerance: number): Pt[] {
  const weight = weights(pts);

  return pts.filter((_, i) => (weight[i] as number) > tolerance);
}

/** Drawing units to a screen pixel: what a tolerance in pixels is on the sheet at this zoom. */
export function unitsPerPixel(
  extent: readonly [number, number, number, number],
  viewport: { width: number; height: number },
  zoom: number,
): number {
  const fit = Math.min(
    viewport.width / (extent[2] - extent[0]),
    viewport.height / (extent[3] - extent[1]),
  );

  return fit > 0 && zoom > 0 ? 1 / (fit * zoom) : 1;
}

export type Stroke = {
  /** The line, to two decimals; empty when the stroke went nowhere. */
  pts: Pt[];
  /** Whether the tolerance had to be raised for the line to fit. */
  coarser: boolean;
};

/**
 * The line of a stroke: its samples to two decimals, one equal to the one before it dropped,
 * simplified by `tolerance` (in drawing units), and by half as much again, over and over, until it
 * has at most `most` points.
 */
export function strokeLine(samples: readonly Pt[], tolerance: number, most = MAX_VERTICES): Stroke {
  const pts: Pt[] = [];

  for (const sample of samples) {
    const p: Pt = [round2(sample[0]), round2(sample[1])];
    const last = pts[pts.length - 1];

    if (!last || last[0] !== p[0] || last[1] !== p[1]) pts.push(p);
  }

  if (pts.length < 2) return { pts: [], coarser: false };

  const weight = weights(pts);
  const at = (by: number) => pts.filter((_, i) => (weight[i] as number) > by);
  let by = tolerance;
  let line = at(by);
  let coarser = false;

  while (line.length > most) {
    // From nothing, half as much again is still nothing: start from the smallest step kept.
    by = Math.max(by * 1.5, 0.01);
    line = at(by);
    coarser = true;
  }

  return { pts: line, coarser };
}
