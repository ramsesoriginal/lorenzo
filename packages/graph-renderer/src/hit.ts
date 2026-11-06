// Step three: hitTest(scene, point). Nodes are on top, then edges by their distance to the line.

import type { Point, Scene } from './types';

export type Hit = { kind: 'node' | 'edge' | 'group'; id: string } | null;

function distanceToSegment(p: Point, a: Point, b: Point): number {
  const dx = b.x - a.x;
  const dy = b.y - a.y;
  const length2 = dx * dx + dy * dy;
  const t =
    length2 === 0 ? 0 : Math.max(0, Math.min(1, ((p.x - a.x) * dx + (p.y - a.y) * dy) / length2));
  const x = a.x + t * dx - p.x;
  const y = a.y + t * dy - p.y;
  return Math.sqrt(x * x + y * y);
}

/** The points of a path written as `M x y L x y` or `M x y Q x y x y`, a curve sampled. */
export function samplePath(d: string, samples = 16): Point[] {
  const numbers = (d.match(/-?\d+(?:\.\d+)?/g) ?? []).map(Number);
  const point = (i: number): Point => ({ x: numbers[i] as number, y: numbers[i + 1] as number });
  if (d.includes('Q') && numbers.length >= 6) {
    const [s, c, e] = [point(0), point(2), point(4)];
    const out: Point[] = [];
    for (let k = 0; k <= samples; k += 1) {
      const t = k / samples;
      const u = 1 - t;
      out.push({
        x: u * u * s.x + 2 * u * t * c.x + t * t * e.x,
        y: u * u * s.y + 2 * u * t * c.y + t * t * e.y,
      });
    }
    return out;
  }
  const out: Point[] = [];
  for (let i = 0; i + 1 < numbers.length; i += 2) out.push(point(i));
  return out;
}

/** What is under `point`, within `slop` pixels of an edge. Nodes win over edges, and the node
 * drawn last (on top) over one beneath it. */
export function hitTest(scene: Scene, point: Point, slop = 6): Hit {
  for (let i = scene.primitives.length - 1; i >= 0; i -= 1) {
    const p = scene.primitives[i];
    if (p?.kind === 'circle') {
      const dx = point.x - p.cx;
      const dy = point.y - p.cy;
      if (dx * dx + dy * dy <= (p.r + 2) * (p.r + 2)) return p.source;
    }
  }
  let best: { id: string; distance: number } | null = null;
  for (const p of scene.primitives) {
    if (p.kind !== 'path' || p.role !== 'edge') continue;
    const points = samplePath(p.d);
    for (let i = 0; i + 1 < points.length; i += 1) {
      const distance = distanceToSegment(point, points[i] as Point, points[i + 1] as Point);
      if (distance <= slop + p.width / 2 && (best === null || distance < best.distance)) {
        best = { id: p.source.id, distance };
      }
    }
  }
  return best ? { kind: 'edge', id: best.id } : null;
}
