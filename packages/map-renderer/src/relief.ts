import { areaRings, cubicAt, partBounds, pointInRings } from './geom';
import { seeded } from './random';
import type { Part, Point } from './types';

/** One hill arc as a cubic, in drawing units: start, two controls, end. */
export type Arc = readonly [Point, Point, Point, Point];

/** The longest arc, in design units (the Bench design's hills are 240 wide on a 1000 sheet). */
const ARC_WIDTH = 240;
/** The control points' rise as a share of an arc's width (50 over 240 in the design). */
const RISE = 50 / 240;
/** A second, nested arc behind each, offset right and down, as the design draws its hills. */
const NEST_DX = 0.125;
const NEST_DY = 1 / 6;
const NEST_WIDTH = 1.08;
const MAX_ARCS = 48;

function containment(part: Part): ((p: Point) => boolean) | null {
  if (part.shape === 'circle') {
    const { at, r } = part;

    return (p) => Math.hypot(p[0] - at[0], p[1] - at[1]) <= r;
  }

  const rings = areaRings(part);

  return rings ? (p) => pointInRings(p, rings) : null;
}

/**
 * Short arcs in rows inside an area, seeded from `seed` (the entry's id and the part's index) so
 * that the same shape always gets the same hills and nothing is stored. A function of the
 * geometry and the seed only: not of the view, so zooming never moves an arc.
 */
export function reliefArcs(part: Part, seed: string, designUnit: number): Arc[] {
  const inside = containment(part);
  const bounds = partBounds(part);

  if (!inside || !bounds) return [];

  const rand = seeded(seed);
  const width = bounds[2] - bounds[0];
  const arcW = Math.min(ARC_WIDTH * designUnit, width * 0.7);

  if (!(arcW > 0)) return [];

  const rowStep = arcW * 0.6;
  const arcs: Arc[] = [];

  const make = (x: number, y: number, w: number, k: number): Arc => {
    const rise = RISE * w * k;

    return [
      [x, y],
      [x + w / 3, y - rise],
      [x + (2 * w) / 3, y - rise],
      [x + w, y],
    ];
  };

  const fits = (arc: Arc): boolean => {
    const [a, b, c, d] = arc;

    return (
      inside(a) &&
      inside(d) &&
      inside([(a[0] + d[0]) / 2, a[1]]) &&
      [0.25, 0.5, 0.75].every((t) => inside(cubicAt(a, b, c, d, t)))
    );
  };

  for (let y = bounds[1] + arcW * 0.25 + rand() * rowStep * 0.5; y <= bounds[3]; y += rowStep) {
    let x = bounds[0] + rand() * arcW * 0.5;

    while (x + arcW <= bounds[2] && arcs.length < MAX_ARCS) {
      const w = arcW * (0.85 + rand() * 0.3);
      const k = 0.85 + rand() * 0.3;
      const arc = make(x, y, w, k);

      if (fits(arc)) arcs.push(arc);

      const nested = make(x + w * NEST_DX, y + w * NEST_DY, w * NEST_WIDTH, k);

      if (fits(nested)) arcs.push(nested);

      x += arcW * 1.2 + rand() * arcW * 0.25;
    }

    if (arcs.length >= MAX_ARCS) break;
  }

  return arcs;
}
