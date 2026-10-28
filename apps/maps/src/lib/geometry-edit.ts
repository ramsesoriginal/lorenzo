// The shapes the editor can draw and change (ADR 0353): a point, a circle, a line and an area
// (one ring, no holes, no curves), as plain data, with the edits a pointer or a field makes to
// them and the geometry document the API takes. Pure: nothing here touches the page.
import type { Geometry } from '@lorenzo/map-renderer';

export type Pt = readonly [number, number];

export type Editable =
  | { kind: 'point'; at: Pt }
  | { kind: 'circle'; at: Pt; r: number }
  | { kind: 'line'; pts: Pt[] }
  | { kind: 'area'; pts: Pt[] };

export type Box = [number, number, number, number];

const FORMAT = 'lorenzo.geometry/1';

/** Coordinates are kept to two decimals: enough for a drawing, well inside the API's six. */
export const round2 = (n: number): number => Math.round(n * 100) / 100;

const roundPt = (p: readonly [number, number]): Pt => [round2(p[0]), round2(p[1])];

export const MIN_VERTICES = { line: 2, area: 3 } as const;

export function toGeometry(shape: Editable): Geometry {
  switch (shape.kind) {
    case 'point':
      return { format: FORMAT, parts: [{ shape: 'point', at: roundPt(shape.at) }] };
    case 'circle':
      return {
        format: FORMAT,
        parts: [{ shape: 'circle', at: roundPt(shape.at), r: round2(shape.r) }],
      };
    case 'line':
      return { format: FORMAT, parts: [{ shape: 'polyline', pts: shape.pts.map(roundPt) }] };
    case 'area':
      return {
        format: FORMAT,
        parts: [{ shape: 'polygon', rings: [shape.pts.map(roundPt)] }],
      };
  }
}

const isPt = (p: unknown): p is Pt =>
  Array.isArray(p) && p.length === 2 && p.every((n) => typeof n === 'number');

/**
 * The shape of a stored geometry when the editor can change it: one part that is a point, a
 * circle, a polyline or a polygon of a single ring. Several parts, curves and holes are not.
 */
export function editableOf(geometry: Geometry): Editable | null {
  if (geometry.parts.length !== 1) return null;
  const part = geometry.parts[0];
  if (!part) return null;
  switch (part.shape) {
    case 'point':
      return isPt(part.at) ? { kind: 'point', at: [...part.at] as Pt } : null;
    case 'circle':
      return isPt(part.at) ? { kind: 'circle', at: [...part.at] as Pt, r: part.r } : null;
    case 'polyline':
      return part.pts.every(isPt) ? { kind: 'line', pts: part.pts.map((p) => [...p] as Pt) } : null;
    case 'polygon': {
      const ring = part.rings.length === 1 ? part.rings[0] : undefined;
      return ring?.every(isPt) ? { kind: 'area', pts: ring.map((p) => [...p] as Pt) } : null;
    }
    default:
      return null;
  }
}

/** A handle of a shape the pointer drags: an id the editor knows it by, and where it is. */
export type Handle = { id: string; at: Pt };

export function handlesOf(shape: Editable): Handle[] {
  switch (shape.kind) {
    case 'point':
      return [{ id: 'p', at: shape.at }];
    case 'circle':
      return [
        { id: 'c', at: shape.at },
        { id: 'r', at: [shape.at[0] + shape.r, shape.at[1]] },
      ];
    default:
      return shape.pts.map((at, i) => ({ id: `v${i}`, at }));
  }
}

/** The shape with a handle moved to `to`. An unknown handle changes nothing. */
export function moveHandle(shape: Editable, id: string, to: Pt): Editable {
  const at = roundPt(to);
  switch (shape.kind) {
    case 'point':
      return id === 'p' ? { kind: 'point', at } : shape;
    case 'circle':
      if (id === 'c') return { ...shape, at };
      if (id === 'r')
        return {
          ...shape,
          r: Math.max(0.01, round2(Math.hypot(at[0] - shape.at[0], at[1] - shape.at[1]))),
        };
      return shape;
    default: {
      const i = id.startsWith('v') ? Number(id.slice(1)) : -1;
      if (!Number.isInteger(i) || i < 0 || i >= shape.pts.length) return shape;
      return { ...shape, pts: shape.pts.map((p, j) => (j === i ? at : p)) };
    }
  }
}

export function translate(shape: Editable, dx: number, dy: number): Editable {
  const move = (p: Pt): Pt => roundPt([p[0] + dx, p[1] + dy]);
  switch (shape.kind) {
    case 'point':
    case 'circle':
      return { ...shape, at: move(shape.at) };
    default:
      return { ...shape, pts: shape.pts.map(move) };
  }
}

/** A point added after vertex `i`, halfway to the next (the first, for the last of an area). */
export function insertVertex(shape: Editable, i: number): Editable {
  if (shape.kind === 'point' || shape.kind === 'circle') return shape;
  const here = shape.pts[i];
  const next = shape.pts[(i + 1) % shape.pts.length];
  if (!here) return shape;
  // A line's last vertex has no next: the new point goes on from it, the way the line was heading.
  let to: Pt;
  if (shape.kind === 'line' && i === shape.pts.length - 1) {
    const before = shape.pts[i - 1] ?? here;
    to = [here[0] + ((here[0] - before[0]) / 2 || 10), here[1] + (here[1] - before[1]) / 2];
  } else {
    to = [(here[0] + (next?.[0] ?? here[0])) / 2, (here[1] + (next?.[1] ?? here[1])) / 2];
  }
  const pts = [...shape.pts.slice(0, i + 1), roundPt(to), ...shape.pts.slice(i + 1)];
  return { ...shape, pts };
}

/** The shape without vertex `i`, or null when it would have too few. */
export function removeVertex(shape: Editable, i: number): Editable | null {
  if (shape.kind === 'point' || shape.kind === 'circle') return null;
  if (shape.pts.length <= MIN_VERTICES[shape.kind] || i < 0 || i >= shape.pts.length) return null;
  return { ...shape, pts: shape.pts.filter((_, j) => j !== i) };
}

export function boundsOf(shape: Editable): Box {
  if (shape.kind === 'point') return [shape.at[0], shape.at[1], shape.at[0], shape.at[1]];
  if (shape.kind === 'circle') {
    return [
      shape.at[0] - shape.r,
      shape.at[1] - shape.r,
      shape.at[0] + shape.r,
      shape.at[1] + shape.r,
    ];
  }
  const xs = shape.pts.map((p) => p[0]);
  const ys = shape.pts.map((p) => p[1]);
  return [Math.min(...xs), Math.min(...ys), Math.max(...xs), Math.max(...ys)];
}

function inRing(ring: readonly Pt[], p: Pt): boolean {
  let inside = false;
  for (let i = 0, j = ring.length - 1; i < ring.length; j = i, i += 1) {
    const a = ring[i];
    const b = ring[j];
    if (!a || !b) continue;
    if (
      a[1] > p[1] !== b[1] > p[1] &&
      p[0] < ((b[0] - a[0]) * (p[1] - a[1])) / (b[1] - a[1]) + a[0]
    ) {
      inside = !inside;
    }
  }
  return inside;
}

/** Whether `p` is inside an area or a circle; a point and a line have no inside. */
export function contains(shape: Editable, p: Pt): boolean {
  if (shape.kind === 'circle') return Math.hypot(p[0] - shape.at[0], p[1] - shape.at[1]) <= shape.r;
  return shape.kind === 'area' ? inRing(shape.pts, p) : false;
}

/**
 * `count` places inside an area or a circle, in rows: the grid is made finer until enough of its
 * points are inside. Fewer come back only for a shape with no room (a sliver).
 */
export function placesInside(shape: Editable, count: number): Pt[] {
  if (count <= 0 || (shape.kind !== 'area' && shape.kind !== 'circle')) return [];
  const [x0, y0, x1, y1] = boundsOf(shape);
  for (
    let columns = Math.max(1, Math.ceil(Math.sqrt(count)));
    columns <= count * 8 + 8;
    columns += 1
  ) {
    const rows = columns;
    const found: Pt[] = [];
    for (let r = 1; r <= rows; r += 1) {
      for (let c = 1; c <= columns; c += 1) {
        const p = roundPt([
          x0 + ((x1 - x0) * c) / (columns + 1),
          y0 + ((y1 - y0) * r) / (rows + 1),
        ]);
        if (contains(shape, p)) found.push(p);
      }
    }
    if (found.length >= count) return found.slice(0, count);
  }
  return [];
}
