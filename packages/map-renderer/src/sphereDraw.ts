import { bboxOf, num } from './geom';
import { type Transform, toScreen } from './project';
import type { CirclePrim, PathPrim, Prim } from './scene';
import {
  densify,
  GLOBE_RADIUS,
  isSphere,
  isVisible,
  type Projection,
  projectedRuns,
  projectionOf,
  projectLonLat,
} from './sphere';
import type { Shape } from './theme';
import type { BBox, MapModel, Part, Point, System } from './types';

/** Degrees between the samples of a line of longitude or latitude drawn on the globe. */
const GRATICULE_SAMPLE = 3;
/** The steps a graticule may have, widest first, and the closest its lines are drawn on screen. */
const GRATICULE_STEPS = [90, 45, 30, 15, 10, 5, 2, 1] as const;
const MIN_LINE_GAP_PX = 40;
const MAX_GRATICULE_SAMPLES = 30000;

function pairs(points: readonly Point[]): string {
  return points.map((p) => `${p[0]} ${p[1]}`).join(' L ');
}

function boxOf(points: readonly Point[]): BBox {
  const b = bboxOf(points);

  return [num(b[0]), num(b[1]), num(b[2]), num(b[3])];
}

/**
 * One part of a placement on a sphere, on the screen, or null when none of it is in view (ADR
 * 0358). `toPx` takes a projected drawing point to a rounded screen point. A circle and a curve are
 * not drawn: a sphere does not hold them.
 */
export function buildSphereShape(
  part: Part,
  system: System,
  toPx: (p: Point) => Point,
): Shape | null {
  const projection = projectionOf(system);
  const project = (p: Point): Point => toPx(projectLonLat(projection, p[0], p[1]));

  switch (part.shape) {
    case 'point': {
      if (!isVisible(projection, part.at[0], part.at[1])) return null;

      return { kind: 'point', at: project(part.at) };
    }

    case 'polyline': {
      if (part.pts.length < 2) return null;

      const runs = projectedRuns(projection, densify(projection, part.pts, false)).map((run) =>
        run.map(toPx),
      );

      if (runs.length === 0) return null;

      return {
        kind: 'line',
        d: runs.map((run) => `M ${pairs(run)}`).join(' '),
        bbox: boxOf(runs.flat()),
      };
    }

    case 'polygon': {
      const rings = part.rings.filter((ring) => ring.length >= 3);
      const outer = part.rings[0];

      if (rings.length === 0 || !outer || outer.length < 3) return null;

      if (
        projection.kind === 'orthographic' &&
        !outer.some((p) => isVisible(projection, p[0], p[1]))
      ) {
        return null;
      }

      const drawn = rings.map((ring) => densify(projection, ring, true).map(project));

      return {
        kind: 'area',
        d: drawn.map((ring) => `M ${pairs(ring)} Z`).join(' '),
        bbox: boxOf(drawn.flat()),
      };
    }

    default:
      return null;
  }
}

/** The globe's outline and fill, under the lines and the places; none for a flat sphere. */
export function limbPrims(model: MapModel, t: Transform): Prim[] {
  if (!isSphere(model.system) || projectionOf(model.system).kind !== 'orthographic') return [];

  const [cx, cy] = toScreen(t, [0, 0]);
  const r = num(GLOBE_RADIUS * t.scale, 'a radius');
  const prim: CirclePrim = {
    id: 'limb',
    kind: 'circle',
    cls: 'm-limb',
    cx: num(cx),
    cy: num(cy),
    r,
    bbox: [num(cx - r), num(cy - r), num(cx + r), num(cy + r)],
  };

  return [prim];
}

/** Degrees of longitude or latitude one screen pixel is worth, as the lines are spaced by it. */
function pixelsPerDegree(projection: Projection, t: Transform): number {
  return projection.kind === 'orthographic' ? (t.scale * GLOBE_RADIUS * Math.PI) / 180 : t.scale;
}

function graticuleStep(projection: Projection, t: Transform): number {
  const gap = pixelsPerDegree(projection, t);
  const globe = projection.kind === 'orthographic';

  // The finest step whose lines are at least MIN_LINE_GAP_PX apart.
  for (const step of [...GRATICULE_STEPS].reverse()) {
    if (step * gap < MIN_LINE_GAP_PX) continue;

    // The globe's lines are sampled, so the count of samples bounds how fine they may be.
    const lines = 360 / step + 180 / step;

    if (globe && lines * (180 / GRATICULE_SAMPLE) > MAX_GRATICULE_SAMPLES) continue;

    return step;
  }

  return GRATICULE_STEPS[0];
}

function meridianValues(step: number): number[] {
  const out: number[] = [];

  for (let lon = -180; lon <= 180; lon += step) out.push(lon);

  return out;
}

function parallelValues(step: number, limit: number): number[] {
  const out: number[] = [];

  for (let lat = -90; lat <= 90; lat += step) {
    if (Math.abs(lat) <= limit) out.push(lat);
  }

  return out;
}

/** Lines of longitude and latitude, the sphere's grid (ADR 0358): one path of class `m-grid`. */
export function graticulePrims(model: MapModel, t: Transform): Prim[] {
  const projection = projectionOf(model.system);
  const step = graticuleStep(projection, t);
  const at = (p: Point): string => {
    const s = toScreen(t, p);

    return `${num(s[0])} ${num(s[1])}`;
  };
  const parts: string[] = [];
  const all: Point[] = [];

  if (projection.kind === 'orthographic') {
    const sample = (from: number, to: number, line: (v: number) => Point): Point[] => {
      const out: Point[] = [];

      for (let v = from; v <= to; v += GRATICULE_SAMPLE) out.push(line(v));

      return out;
    };
    const lines: Point[][] = [
      ...meridianValues(step).map((lon) => sample(-90, 90, (lat) => [lon, lat])),
      ...parallelValues(step, 89).map((lat) => sample(-180, 180, (lon) => [lon, lat])),
    ];

    for (const samples of lines) {
      for (const run of projectedRuns(projection, samples)) {
        parts.push(`M ${run.map(at).join(' L ')}`);
        all.push(...run.map((p) => toScreen(t, p)));
      }
    }
  } else {
    // The sheet's top and bottom edges: latitude 90 and -90, held to Mercator's limit when it has one.
    const top = projectLonLat(projection, 0, 90)[1];
    const bottom = -top;

    for (const lon of meridianValues(step)) {
      parts.push(`M ${at([lon, top])} L ${at([lon, bottom])}`);
      all.push(toScreen(t, [lon, top]), toScreen(t, [lon, bottom]));
    }

    for (const lat of parallelValues(step, 90)) {
      const y = projectLonLat(projection, 0, lat)[1];

      parts.push(`M ${at([-180, y])} L ${at([180, y])}`);
      all.push(toScreen(t, [-180, y]), toScreen(t, [180, y]));
    }
  }

  if (parts.length === 0) return [];

  const prim: PathPrim = {
    id: 'grid',
    kind: 'path',
    cls: 'm-grid',
    d: parts.join(' '),
    strokeWidth: 1,
    bbox: boxOf(all),
  };

  return [prim];
}
