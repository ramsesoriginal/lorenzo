import { distanceToSegment, flattenPath, pointInRings } from './geom';
import type { Prim, Scene } from './scene';
import type { Point } from './types';

function inBox(box: Prim['bbox'], p: Point, by: number): boolean {
  return p[0] >= box[0] - by && p[0] <= box[2] + by && p[1] >= box[1] - by && p[1] <= box[3] + by;
}

function hits(prim: Prim, p: Point): boolean {
  const hit = prim.hit;

  if (!hit) return false;

  const tol = hit.mode === 'line' ? hit.tol : 0;

  if (!inBox(prim.bbox, p, tol)) return false;

  if (prim.kind === 'circle') {
    return Math.hypot(p[0] - prim.cx, p[1] - prim.cy) <= prim.r + tol;
  }

  if (prim.kind !== 'path') return false;

  const paths = flattenPath(prim.d);

  if (hit.mode === 'area') {
    return pointInRings(
      p,
      paths.filter((path) => path.closed).map((path) => path.pts),
    );
  }

  return paths.some((path) => {
    const pts = path.pts;
    const last = path.closed ? pts.length : pts.length - 1;

    for (let i = 0; i < last; i += 1) {
      const a = pts[i];
      const b = pts[(i + 1) % pts.length];

      if (a && b && distanceToSegment(p, a, b) <= tol) return true;
    }

    return false;
  });
}

/**
 * The placement under a screen point, topmost first, or null: a line within its tolerance (8
 * pixels at least, half the stroke if wider), a disc by its radius, an area exactly.
 */
export function hitTest(scene: Scene, point: Point): string | null {
  for (let i = scene.prims.length - 1; i >= 0; i -= 1) {
    const prim = scene.prims[i];

    if (prim?.entryId !== undefined && hits(prim, point)) return prim.entryId;
  }

  return null;
}
