// The parts of a placement (ADR 0474): which of them there are and what each is called, one of them
// as the shape the editor changes, and the geometry with a part changed, moved or removed. An
// area's holes are rings of their own. Pure: nothing here touches the page.
import type { Geometry, Part } from '@lorenzo/map-renderer';
import { type Editable, editableOf, type Pt, round2, toGeometry, valued } from './geometry-edit';
import { splineCurve, splineOf } from './spline';

/** A part of a geometry, and for an area which ring of it: 0 the outline, 1 and on its holes. */
export type PartRef = { part: number; ring: number };

export type PartName = {
  ref: PartRef;
  /** What it is called: "Area 3", "Height line 2, 250 m", "Hole 1 of Area 3". */
  name: string;
  /** Whether the editor can change its points; a curve that is no spline is only kept. */
  editable: boolean;
};

const FORMAT = 'lorenzo.geometry/1';

const sameRef = (a: PartRef, b: PartRef) => a.part === b.part && a.ring === b.ring;

/**
 * Whether a placement is edited part by part: it has several parts, or one area with holes. A
 * placement of one simple part is edited as it always was (ADR 0353).
 */
export function hasParts(geometry: Geometry): boolean {
  const only = geometry.parts[0];

  return geometry.parts.length > 1 || (only?.shape === 'polygon' && only.rings.length > 1);
}

/** What a part is, in a word, and whether it carries a height. */
function kindOf(part: Part): { word: string; height: string } {
  const height =
    typeof part.value === 'number' && typeof part.unit === 'string'
      ? `${part.value} ${part.unit}`
      : '';
  const line = part.shape === 'polyline' || (part.shape === 'bezier' && !part.closed);

  if (line && height) return { word: 'Height line', height };

  switch (part.shape) {
    case 'point':
      return { word: 'Point', height };
    case 'circle':
      return { word: 'Circle', height };
    case 'polyline':
      return { word: 'Line', height };
    case 'bezier':
      return { word: part.closed ? 'Curved area' : 'Curve', height };
    default:
      return { word: 'Area', height };
  }
}

/** Every part and hole in order, each numbered among its own kind. */
export function partNames(geometry: Geometry): PartName[] {
  const counts = new Map<string, number>();
  const out: PartName[] = [];

  geometry.parts.forEach((part, index) => {
    const { word, height } = kindOf(part);
    const n = (counts.get(word) ?? 0) + 1;

    counts.set(word, n);

    const name = `${word} ${n}`;
    const ref = { part: index, ring: 0 };

    out.push({
      ref,
      name: height ? `${name}, ${height}` : name,
      editable: partShape(geometry, ref) !== null,
    });

    if (part.shape === 'polygon') {
      for (let ring = 1; ring < part.rings.length; ring += 1) {
        out.push({ ref: { part: index, ring }, name: `Hole ${ring} of ${name}`, editable: true });
      }
    }
  });

  return out;
}

/**
 * One part as the shape the editor changes: a point, a circle, a line, a spline, or one ring of
 * an area as an outline. Null for a curve that is no spline and for a part that is not there.
 */
export function partShape(geometry: Geometry, ref: PartRef): Editable | null {
  const part = geometry.parts[ref.part];

  if (!part) return null;

  if (part.shape === 'polygon') {
    const ring = part.rings[ref.ring];

    if (!ring) return null;

    // A hole carries nothing of its own: the value is the area's, kept with its outline.
    return {
      kind: 'area',
      pts: ring.map((p): Pt => [p[0], p[1]]),
      ...(ref.ring === 0 ? valued(part) : {}),
    };
  }

  return ref.ring === 0 ? editableOf({ format: FORMAT, parts: [part] }) : null;
}

/** The geometry with one part, or one ring of an area, replaced by a changed shape. */
export function withPart(geometry: Geometry, ref: PartRef, shape: Editable): Geometry {
  const parts = geometry.parts.map((part, index): Part => {
    if (index !== ref.part) return part;

    if (part.shape === 'polygon' && shape.kind === 'area') {
      const rings = part.rings.map((ring, r) =>
        r === ref.ring ? shape.pts.map((p): Pt => [round2(p[0]), round2(p[1])]) : ring,
      );

      return { ...part, rings, ...(ref.ring === 0 ? valuedOrNone(shape) : {}) };
    }

    return toGeometry(shape).parts[0] as Part;
  });

  return { format: geometry.format, parts };
}

/** A shape's value and unit, or both explicitly gone, so a spread takes them away. */
function valuedOrNone(shape: Editable): { value?: number; unit?: string } {
  const carried = valued(shape);

  return 'value' in carried ? carried : { value: undefined, unit: undefined };
}

/** The geometry with a whole part moved: an area with its holes. */
export function movedPart(geometry: Geometry, part: number, dx: number, dy: number): Geometry {
  const move = (p: readonly [number, number]): Pt => [round2(p[0] + dx), round2(p[1] + dy)];
  const parts = geometry.parts.map((old, index): Part => {
    if (index !== part) return old;

    switch (old.shape) {
      case 'point':
      case 'circle':
        return { ...old, at: move(old.at) };
      case 'polyline':
        return { ...old, pts: old.pts.map(move) };
      case 'polygon':
        return { ...old, rings: old.rings.map((ring) => ring.map(move)) };
      default:
        return {
          ...old,
          start: move(old.start),
          segs: old.segs.map((seg) => [move(seg[0]), move(seg[1]), move(seg[2])] as const),
        };
    }
  });

  return { format: geometry.format, parts };
}

/**
 * The geometry without a part, or without one hole of an area. Removing an area's outline removes
 * the area. Null when it is the last part: that is taking the drawing off the Map.
 */
export function withoutPart(geometry: Geometry, ref: PartRef): Geometry | null {
  const part = geometry.parts[ref.part];

  if (!part) return geometry;

  if (ref.ring > 0 && part.shape === 'polygon') {
    return {
      format: geometry.format,
      parts: geometry.parts.map((old, index) =>
        index === ref.part && old.shape === 'polygon'
          ? { ...old, rings: old.rings.filter((_, r) => r !== ref.ring) }
          : old,
      ),
    };
  }

  if (geometry.parts.length <= 1) return null;

  return { format: geometry.format, parts: geometry.parts.filter((_, i) => i !== ref.part) };
}

/** What is chosen after a part or a hole is removed: nothing that is no longer there. */
export function refAfterRemoval(chosen: PartRef | null, removed: PartRef): PartRef | null {
  if (!chosen) return null;
  if (chosen.part !== removed.part) {
    return removed.ring === 0 && chosen.part > removed.part
      ? { part: chosen.part - 1, ring: chosen.ring }
      : chosen;
  }
  if (removed.ring === 0 || sameRef(chosen, removed)) return null;

  return chosen.ring > removed.ring ? { part: chosen.part, ring: chosen.ring - 1 } : chosen;
}

function distanceToPath(p: Pt, pts: readonly (readonly [number, number])[]): number {
  let best = Number.POSITIVE_INFINITY;

  for (let i = 1; i < pts.length; i += 1) {
    const a = pts[i - 1] as Pt;
    const b = pts[i] as Pt;
    const dx = b[0] - a[0];
    const dy = b[1] - a[1];
    const length = dx * dx + dy * dy;
    const t =
      length === 0
        ? 0
        : Math.max(0, Math.min(1, ((p[0] - a[0]) * dx + (p[1] - a[1]) * dy) / length));

    best = Math.min(best, Math.hypot(p[0] - (a[0] + t * dx), p[1] - (a[1] + t * dy)));
  }

  return best;
}

function inRing(ring: readonly (readonly [number, number])[], p: Pt): boolean {
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

/**
 * The part under a point of the drawing, `reach` drawing units from a pin or a line: pins and
 * lines before circles and areas, since they lie on top of them, and the first in order of each.
 * A point in a hole is in no area.
 */
export function partAt(geometry: Geometry, p: Pt, reach: number): PartRef | null {
  let under: PartRef | null = null;

  for (const [index, part] of geometry.parts.entries()) {
    const ref = { part: index, ring: 0 };

    if (part.shape === 'point') {
      if (Math.hypot(p[0] - part.at[0], p[1] - part.at[1]) <= reach) return ref;
    } else if (part.shape === 'polyline') {
      if (distanceToPath(p, part.pts) <= reach) return ref;
    } else if (part.shape === 'bezier' && !part.closed) {
      const spline = splineOf(part);
      const path = spline
        ? splineCurve(spline.pts, spline.tension)
        : [part.start, ...part.segs.map((seg) => seg[2])];

      if (distanceToPath(p, path) <= reach) return ref;
    } else if (!under) {
      if (part.shape === 'circle') {
        if (Math.hypot(p[0] - part.at[0], p[1] - part.at[1]) <= part.r) under = ref;
      } else if (part.shape === 'polygon') {
        const [outline, ...holes] = part.rings;

        if (outline && inRing(outline, p) && !holes.some((hole) => inRing(hole, p))) under = ref;
      } else if (inRing([part.start, ...part.segs.map((seg) => seg[2])], p)) {
        under = ref;
      }
    }
  }

  return under;
}

/** Whether every part is a line or a curve that carries a height: a set of height lines (ADR 0473). */
export function isHeightLines(geometry: Geometry): boolean {
  return (
    geometry.parts.length > 0 &&
    geometry.parts.every(
      (part) =>
        (part.shape === 'polyline' || (part.shape === 'bezier' && !part.closed)) &&
        typeof part.value === 'number' &&
        typeof part.unit === 'string',
    )
  );
}

/** A placement holds at most this many parts (ADR 0337). */
export const MAX_PARTS = 256;

/** The geometry with the parts of another added after its own. */
export function withParts(geometry: Geometry, more: Geometry): Geometry {
  return { format: geometry.format, parts: [...geometry.parts, ...more.parts] };
}
