import type { BBox, Point, System } from './types';

/**
 * A sphere Map is drawn through a projection (ADR 0358). A stored position is `[longitude,
 * latitude]` in degrees (ADR 0357); a projected point is in drawing units, y down, where one unit is
 * one degree along the equator. Everything here is pure arithmetic with no DOM.
 */

export type ProjectionKind = 'equirectangular' | 'mercator' | 'orthographic';

export type Projection = {
  kind: ProjectionKind;
  /** The point facing the viewer; for `orthographic` only. */
  centre?: readonly [number, number];
};

export const PROJECTION_KINDS: readonly ProjectionKind[] = [
  'equirectangular',
  'mercator',
  'orthographic',
];

/** The globe's radius in drawing units. */
export const GLOBE_RADIUS = 90;
/** Mercator's latitude limit, where its sheet is a square of side 360. */
export const MERCATOR_LIMIT = 85.0511287798;
/** The longest a segment's sample may be, in degrees of its longer span. */
export const SAMPLE_STEP = 2;
/** The most samples one segment gets, and the most one part gets in all. */
export const MAX_SEGMENT_SAMPLES = 180;
export const MAX_PART_SAMPLES = 20000;

const RAD = Math.PI / 180;
const DEG = 180 / Math.PI;

export function isSphere(system: Pick<System, 'kind'>): boolean {
  return system.kind === 'sphere';
}

/** The projection of a system: the one it names, else the flat one. */
export function projectionOf(system: Pick<System, 'projection'>): Projection {
  const p = system.projection;

  if (p && PROJECTION_KINDS.includes(p.kind)) return p;

  return { kind: 'equirectangular' };
}

function centreOf(p: Projection): [number, number] {
  return [p.centre?.[0] ?? 0, p.centre?.[1] ?? 0];
}

function clamp(value: number, low: number, high: number): number {
  return Math.min(high, Math.max(low, value));
}

function mercator(lat: number): number {
  const phi = clamp(lat, -MERCATOR_LIMIT, MERCATOR_LIMIT) * RAD;

  return Math.log(Math.tan(Math.PI / 4 + phi / 2)) * DEG;
}

/** The projected sheet of a projection, in drawing units. */
export function sphereExtent(p: Projection): BBox {
  switch (p.kind) {
    case 'mercator':
      return [-180, -180, 180, 180];
    case 'orthographic':
      return [-GLOBE_RADIUS - 10, -GLOBE_RADIUS - 10, GLOBE_RADIUS + 10, GLOBE_RADIUS + 10];
    default:
      return [-180, -90, 180, 90];
  }
}

/** Whether a position is on the side of the globe that faces the viewer; always true when flat. */
export function isVisible(p: Projection, lon: number, lat: number): boolean {
  if (p.kind !== 'orthographic') return true;

  const [l0, p0] = centreOf(p);
  const phi = lat * RAD;
  const phi0 = p0 * RAD;

  return (
    Math.sin(phi0) * Math.sin(phi) + Math.cos(phi0) * Math.cos(phi) * Math.cos((lon - l0) * RAD) >=
    0
  );
}

/**
 * A position in drawing units. On the globe a position behind the limb is moved onto it so that
 * every number stays finite; ask `isVisible` first when that matters.
 */
export function projectLonLat(p: Projection, lon: number, lat: number): Point {
  switch (p.kind) {
    case 'mercator':
      return [lon, -mercator(lat)];

    case 'orthographic': {
      const [l0, p0] = centreOf(p);
      const phi = lat * RAD;
      const phi0 = p0 * RAD;
      const dl = (lon - l0) * RAD;
      const x = GLOBE_RADIUS * Math.cos(phi) * Math.sin(dl);
      const y =
        -GLOBE_RADIUS *
        (Math.cos(phi0) * Math.sin(phi) - Math.sin(phi0) * Math.cos(phi) * Math.cos(dl));

      if (isVisible(p, lon, lat)) return [x, y];

      const rho = Math.hypot(x, y);

      return rho < 1e-9 ? [GLOBE_RADIUS, 0] : [(x / rho) * GLOBE_RADIUS, (y / rho) * GLOBE_RADIUS];
    }

    default:
      return [lon, -lat];
  }
}

function wrapLongitude(lon: number): number {
  const wrapped = ((((lon + 180) % 360) + 360) % 360) - 180;

  return wrapped === -180 && lon > 0 ? 180 : wrapped;
}

/**
 * The longitude and latitude under a drawing point, clamped into their ranges; on the globe a point
 * outside the disc is moved onto the limb. The inverse of `projectLonLat` on the visible side.
 */
export function unprojectPoint(p: Projection, x: number, y: number): Point {
  switch (p.kind) {
    case 'mercator':
      return [
        clamp(x, -180, 180),
        clamp(
          (2 * Math.atan(Math.exp(-y * RAD)) - Math.PI / 2) * DEG,
          -MERCATOR_LIMIT,
          MERCATOR_LIMIT,
        ),
      ];

    case 'orthographic': {
      const [l0, p0] = centreOf(p);
      const phi0 = p0 * RAD;
      let px = x / GLOBE_RADIUS;
      let py = -y / GLOBE_RADIUS;
      let rho = Math.hypot(px, py);

      if (rho < 1e-12) return [l0, p0];

      if (rho > 1) {
        px /= rho;
        py /= rho;
        rho = 1;
      }

      const c = Math.asin(rho);
      const sinc = Math.sin(c);
      const cosc = Math.cos(c);
      const lat = Math.asin(
        clamp(cosc * Math.sin(phi0) + (py * sinc * Math.cos(phi0)) / rho, -1, 1),
      );
      const lon =
        l0 * RAD + Math.atan2(px * sinc, rho * Math.cos(phi0) * cosc - py * Math.sin(phi0) * sinc);

      return [clamp(wrapLongitude(lon * DEG), -180, 180), clamp(lat * DEG, -90, 90)];
    }

    default:
      return [clamp(x, -180, 180), clamp(-y, -90, 90)];
  }
}

/** Whether a drawing point is on the sheet's drawn globe; every point of a flat sheet is. */
export function onGlobe(p: Projection, x: number, y: number): boolean {
  return p.kind !== 'orthographic' || Math.hypot(x, y) <= GLOBE_RADIUS;
}

/**
 * The positions of a polyline or a ring with samples between them where the projection bends a
 * straight line of longitude and latitude (ADR 0358). A flat projection needs none.
 */
export function densify(p: Projection, points: readonly Point[], closed: boolean): Point[] {
  if (p.kind === 'equirectangular' || points.length < 2) return [...points];

  const segments = closed ? points.length : points.length - 1;
  const perSegment = Math.max(
    1,
    Math.min(MAX_SEGMENT_SAMPLES, Math.floor(MAX_PART_SAMPLES / segments)),
  );
  const out: Point[] = [];

  for (let i = 0; i < segments; i += 1) {
    const a = points[i] as Point;
    const b = points[(i + 1) % points.length] as Point;
    const n = Math.max(
      1,
      Math.min(
        perSegment,
        Math.ceil(Math.max(Math.abs(b[0] - a[0]), Math.abs(b[1] - a[1])) / SAMPLE_STEP),
      ),
    );

    for (let k = 0; k < n; k += 1) {
      out.push([a[0] + ((b[0] - a[0]) * k) / n, a[1] + ((b[1] - a[1]) * k) / n]);
    }
  }

  if (!closed) out.push(points[points.length - 1] as Point);

  return out;
}

/** The projected point where the segment from a visible to a hidden position meets the limb. */
function limbPoint(p: Projection, visible: Point, hidden: Point): Point {
  let low = 0;
  let high = 1;

  for (let i = 0; i < 24; i += 1) {
    const mid = (low + high) / 2;

    if (
      isVisible(
        p,
        visible[0] + (hidden[0] - visible[0]) * mid,
        visible[1] + (hidden[1] - visible[1]) * mid,
      )
    ) {
      low = mid;
    } else {
      high = mid;
    }
  }

  return projectLonLat(
    p,
    visible[0] + (hidden[0] - visible[0]) * low,
    visible[1] + (hidden[1] - visible[1]) * low,
  );
}

/**
 * Samples as the projected runs in front: one run for a flat projection, and for the globe every
 * stretch that is not behind the limb, ending exactly on it. A run has at least two points.
 */
export function projectedRuns(p: Projection, samples: readonly Point[]): Point[][] {
  if (p.kind !== 'orthographic') {
    return samples.length >= 2 ? [samples.map((s) => projectLonLat(p, s[0], s[1]))] : [];
  }

  const runs: Point[][] = [];
  let current: Point[] = [];
  let previous: Point | null = null;
  let previousVisible = false;

  const flush = (): void => {
    if (current.length >= 2) runs.push(current);

    current = [];
  };

  for (const s of samples) {
    const visible = isVisible(p, s[0], s[1]);

    if (visible) {
      if (previous && !previousVisible) current.push(limbPoint(p, s, previous));

      current.push(projectLonLat(p, s[0], s[1]));
    } else if (previous && previousVisible) {
      current.push(limbPoint(p, previous, s));
      flush();
    }

    previous = s;
    previousVisible = visible;
  }

  flush();

  return runs;
}
