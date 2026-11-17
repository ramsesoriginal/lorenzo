// The geometry validator, mirrored (ADR 0337, ADR 0475): what the API would refuse, said before it
// is asked. The API's validator, `packages/map-engine`, is the one that decides; this one agrees
// with it on every document of `packages/map-engine/golden/geometry.json`, and exists so that a
// generator never offers a result the API would refuse. Pure: nothing here touches the page.

/** The limits of ADR 0337, as `packages/map-engine/src/lorenzo_map/limits.py` has them. */
export const LIMITS = {
  placementBytes: 64 * 1024,
  vertices: 2000,
  parts: 256,
  coordinate: 10_000_000,
  value: 1_000_000_000_000,
  unitLength: 32,
  /** Segment-pair tests a simplicity check may spend before a polygon is called too complex. */
  simplicityBudget: 4_000_000,
  /** Operations in one batch of placement writes (ADR 0351). */
  batchOperations: 100,
} as const;

export const GEOMETRY_FORMAT = 'lorenzo.geometry/1';

/** Millionths: six decimals. */
const SCALE = 1_000_000;
/** How far a number may lie from its nearest six decimals: a few units of its last place. */
const PRECISION = 2 ** -50;
const TINY = 1e-12;

type IntPoint = readonly [number, number];
type Ring = readonly IntPoint[];

/** Why a document is refused. It names the rule, never the input. */
class Refusal extends Error {}

const refuse = (why: string): never => {
  throw new Refusal(why);
};

const isObject = (value: unknown): value is Record<string, unknown> =>
  typeof value === 'object' && value !== null && !Array.isArray(value);

/** The number in millionths, or a refusal: finite, bounded, and of at most six decimals. */
function quantise(value: unknown, bound: number, what: string): number {
  if (typeof value !== 'number') return refuse(`${what} must be a number`);
  if (!Number.isFinite(value)) return refuse(`${what} must be a finite number`);
  if (Math.abs(value) > bound) return refuse(`${what} is too large`);

  const whole = Math.round(value * SCALE);

  // As the engine does (#1255): the nearest six decimals, compared in the number's own scale.
  if (Math.abs(value - whole / SCALE) > Math.max(TINY, Math.abs(value) * PRECISION)) {
    return refuse(`${what} has more than six decimals`);
  }

  return whole;
}

/** The stored form of a quantised number: a whole number when it is one. */
const canonical = (millionths: number): number => millionths / SCALE;

function point(value: unknown): IntPoint {
  if (!Array.isArray(value) || value.length !== 2) return refuse('a point is two numbers');

  return [
    quantise(value[0], LIMITS.coordinate, 'a coordinate'),
    quantise(value[1], LIMITS.coordinate, 'a coordinate'),
  ];
}

function points(value: unknown, minimum: number): IntPoint[] {
  if (!Array.isArray(value) || value.length < minimum) {
    return refuse(`a line or ring needs at least ${minimum} points`);
  }

  return value.map(point);
}

const out = (p: IntPoint): [number, number] => [canonical(p[0]), canonical(p[1])];

// Coordinates are whole millionths up to 1e13, so a product of two differences is beyond what a
// double holds exactly: the turn of three points is worked out in whole numbers of any size.
function orient(a: IntPoint, b: IntPoint, c: IntPoint): number {
  const value =
    BigInt(b[0] - a[0]) * BigInt(c[1] - a[1]) - BigInt(b[1] - a[1]) * BigInt(c[0] - a[0]);

  return value > 0n ? 1 : value < 0n ? -1 : 0;
}

/** p, known to be on the line through a and b, is between them. */
const within = (a: IntPoint, b: IntPoint, p: IntPoint): boolean =>
  Math.min(a[0], b[0]) <= p[0] &&
  p[0] <= Math.max(a[0], b[0]) &&
  Math.min(a[1], b[1]) <= p[1] &&
  p[1] <= Math.max(a[1], b[1]);

/** The closed segments ab and cd share at least one point. */
function touch(a: IntPoint, b: IntPoint, c: IntPoint, d: IntPoint): boolean {
  const o1 = orient(a, b, c);
  const o2 = orient(a, b, d);
  const o3 = orient(c, d, a);
  const o4 = orient(c, d, b);

  if (o1 !== o2 && o3 !== o4) return true;

  return (
    (o1 === 0 && within(a, b, c)) ||
    (o2 === 0 && within(a, b, d)) ||
    (o3 === 0 && within(c, d, a)) ||
    (o4 === 0 && within(c, d, b))
  );
}

/** p is strictly inside the ring (a point on its boundary is not). */
function inside(ring: Ring, p: IntPoint): boolean {
  let isInside = false;

  for (let i = 0; i < ring.length; i += 1) {
    const a = ring[i] as IntPoint;
    const b = ring[(i + 1) % ring.length] as IntPoint;

    if (orient(a, b, p) === 0 && within(a, b, p)) return false;

    if (a[1] > p[1] !== b[1] > p[1]) {
      const cross =
        BigInt(b[0] - a[0]) * BigInt(p[1] - a[1]) - BigInt(p[0] - a[0]) * BigInt(b[1] - a[1]);

      if (cross > 0n === b[1] > a[1]) isInside = !isInside;
    }
  }

  return isInside;
}

/**
 * Refuses a polygon unless it is simple: its edges never cross or touch except where neighbours
 * meet, a hole lies inside the outline, and no hole touches or sits inside another.
 */
function checkPolygon(rings: readonly Ring[]): void {
  type Edge = { lo: number; hi: number; a: IntPoint; b: IntPoint; ring: number; index: number };
  const edges: Edge[] = [];

  rings.forEach((ring, ringIndex) => {
    for (let i = 0; i < ring.length; i += 1) {
      const a = ring[i] as IntPoint;
      const b = ring[(i + 1) % ring.length] as IntPoint;

      if (a[0] === b[0] && a[1] === b[1]) refuse('a polygon has an edge of no length');

      edges.push({
        lo: Math.min(a[0], b[0]),
        hi: Math.max(a[0], b[0]),
        a,
        b,
        ring: ringIndex,
        index: i,
      });
    }
  });

  // Neighbours within one ring meet at a vertex and must not run back over each other.
  for (const ring of rings) {
    for (let i = 0; i < ring.length; i += 1) {
      const a = ring[i] as IntPoint;
      const b = ring[(i + 1) % ring.length] as IntPoint;
      const c = ring[(i + 2) % ring.length] as IntPoint;

      if (
        orient(a, b, c) === 0 &&
        BigInt(b[0] - a[0]) * BigInt(c[0] - b[0]) + BigInt(b[1] - a[1]) * BigInt(c[1] - b[1]) < 0n
      ) {
        refuse('a polygon doubles back over itself');
      }
    }
  }

  edges.sort((one, other) => one.lo - other.lo);

  let spent = 0;

  for (let i = 0; i < edges.length; i += 1) {
    const one = edges[i] as Edge;
    const low = Math.min(one.a[1], one.b[1]);
    const high = Math.max(one.a[1], one.b[1]);

    for (let j = i + 1; j < edges.length && (edges[j] as Edge).lo <= one.hi; j += 1) {
      const other = edges[j] as Edge;

      spent += 1;

      if (spent > LIMITS.simplicityBudget) refuse('a polygon is too complex to check');

      if (Math.min(other.a[1], other.b[1]) > high || Math.max(other.a[1], other.b[1]) < low) {
        continue;
      }

      if (one.ring === other.ring) {
        const n = (rings[one.ring] as Ring).length;
        const apart = (((one.index - other.index) % n) + n) % n;

        // Neighbours: handled above.
        if (apart === 1 || apart === n - 1) continue;
      }

      if (touch(one.a, one.b, other.a, other.b)) refuse('a polygon touches or crosses itself');
    }
  }

  const [outer, ...holes] = rings;

  if (!outer) return;

  for (const hole of holes) {
    if (!inside(outer, hole[0] as IntPoint)) refuse('a hole must lie inside the outer ring');
  }

  holes.forEach((one, i) => {
    holes.forEach((other, j) => {
      if (i !== j && inside(other, one[0] as IntPoint)) {
        refuse('a hole must not lie inside another hole');
      }
    });
  });
}

const COMMON = ['shape', 'value', 'unit'];
const KEYS: Record<string, readonly string[]> = {
  point: [...COMMON, 'at'],
  circle: [...COMMON, 'at', 'r'],
  polyline: [...COMMON, 'pts'],
  bezier: [...COMMON, 'start', 'segs', 'closed'],
  polygon: [...COMMON, 'rings'],
};

/** A name the author chose (a unit): trimmed, composed, not empty, not long, no control character. */
function cleanText(value: unknown, what: string): string {
  if (typeof value !== 'string') return refuse(`${what} must be text`);

  const text = value.normalize('NFC').trim();

  if (text === '' || [...text].length > LIMITS.unitLength) {
    return refuse(`${what} must be between 1 and ${LIMITS.unitLength} characters`);
  }

  if (/\p{C}/u.test(text)) return refuse(`${what} must not contain control characters`);

  return text;
}

/** A part in its stored form, and how many of a placement's vertices it is. */
function part(raw: unknown): { stored: Record<string, unknown>; vertices: number } {
  if (!isObject(raw)) return refuse('a part must be an object');

  const shape = raw.shape;
  const keys = typeof shape === 'string' ? KEYS[shape] : undefined;

  if (typeof shape !== 'string' || !keys) {
    return refuse('a part must be a point, circle, polyline, bezier or polygon');
  }

  if (Object.keys(raw).some((key) => !keys.includes(key))) {
    return refuse('a part has a key it does not know');
  }

  const stored: Record<string, unknown> = { shape };
  let vertices: number;

  if (shape === 'point') {
    stored.at = out(point(raw.at));
    vertices = 1;
  } else if (shape === 'circle') {
    const at = point(raw.at);
    const radius = quantise(raw.r, LIMITS.coordinate, 'a radius');

    if (radius <= 0) refuse('a radius must be positive');

    stored.at = out(at);
    stored.r = canonical(radius);
    vertices = 1;
  } else if (shape === 'polyline') {
    const pts = points(raw.pts, 2);

    stored.pts = pts.map(out);
    vertices = pts.length;
  } else if (shape === 'bezier') {
    const start = point(raw.start);
    const segs = raw.segs;

    if (!Array.isArray(segs) || segs.length === 0) {
      return refuse('a bezier needs at least one segment');
    }

    const storedSegs = segs.map((seg) => {
      if (!Array.isArray(seg) || seg.length !== 3) {
        return refuse('a bezier segment is two controls and an end');
      }

      return seg.map((p) => out(point(p)));
    });

    if ('closed' in raw && typeof raw.closed !== 'boolean') {
      refuse('closed must be true or false');
    }

    stored.start = out(start);
    stored.segs = storedSegs;

    if ('closed' in raw) stored.closed = raw.closed;

    vertices = 1 + 3 * storedSegs.length;
  } else {
    const ringsRaw = raw.rings;

    if (!Array.isArray(ringsRaw) || ringsRaw.length === 0) {
      return refuse('a polygon needs an outer ring');
    }

    const rings = ringsRaw.map((ring) => points(ring, 3));

    checkPolygon(rings);
    stored.rings = rings.map((ring) => ring.map(out));
    vertices = rings.reduce((sum, ring) => sum + ring.length, 0);
  }

  if ('value' in raw !== 'unit' in raw) refuse('a value and its unit go together');

  if ('value' in raw) {
    stored.value = canonical(quantise(raw.value, LIMITS.value, 'a value'));
    stored.unit = cleanText(raw.unit, 'a unit');
  }

  return { stored, vertices };
}

export type Checked =
  | { ok: true; vertices: number; parts: number; bytes: number }
  | { ok: false; why: string };

/**
 * Whether the API would take a geometry, and if not, which rule refuses it. The size in bytes is
 * that of the compact JSON of its stored form, as the API measures it; at the very edge of the
 * limit a number may be written a character longer or shorter there than here.
 */
export function checkGeometry(document: unknown): Checked {
  try {
    if (
      !isObject(document) ||
      Object.keys(document).length !== 2 ||
      !('format' in document) ||
      !('parts' in document)
    ) {
      return refuse('a geometry is a format and its parts');
    }

    if (document.format !== GEOMETRY_FORMAT) return refuse('a geometry must name its format');

    const raw = document.parts;

    if (!Array.isArray(raw) || raw.length === 0 || raw.length > LIMITS.parts) {
      return refuse(`a geometry has between 1 and ${LIMITS.parts} parts`);
    }

    const parts: Record<string, unknown>[] = [];
    let vertices = 0;

    for (const one of raw) {
      const { stored, vertices: count } = part(one);

      parts.push(stored);
      vertices += count;

      if (vertices > LIMITS.vertices) {
        return refuse(`a placement has at most ${LIMITS.vertices} vertices`);
      }
    }

    const bytes = new TextEncoder().encode(
      JSON.stringify({ format: GEOMETRY_FORMAT, parts }),
    ).length;

    if (bytes > LIMITS.placementBytes) return refuse("a placement's geometry is too large");

    return { ok: true, vertices, parts: parts.length, bytes };
  } catch (error) {
    if (error instanceof Refusal) return { ok: false, why: error.message };

    throw error;
  }
}
