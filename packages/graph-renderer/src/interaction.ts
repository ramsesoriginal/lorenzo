// The pure part of interaction: reducers over the view, and moving along edges by key. They emit
// new values and never fetch or write (ADR 0407).

import type { GraphModel, GraphView, Point, Scene } from './types';

export const ZOOM = { min: 0.25, max: 6 } as const;

export function clampZoom(zoom: number): number {
  return Math.min(ZOOM.max, Math.max(ZOOM.min, zoom));
}

/** Pans by a number of pixels. */
export function panBy(view: GraphView, dx: number, dy: number): GraphView {
  return { ...view, pan: { x: view.pan.x + dx, y: view.pan.y + dy } };
}

/** Zooms by a factor, keeping what is under the screen point `at` where it is. */
export function zoomAt(view: GraphView, factor: number, at: Point): GraphView {
  const zoom = clampZoom(view.zoom * factor);
  const applied = zoom / view.zoom;
  const cx = view.width / 2;
  const cy = view.height / 2;
  return {
    ...view,
    zoom,
    pan: {
      x: at.x - cx - (at.x - cx - view.pan.x) * applied,
      y: at.y - cy - (at.y - cy - view.pan.y) * applied,
    },
  };
}

/** The pan that brings a node to the middle of the viewport. */
export function centreOn(scene: Scene, view: GraphView, nodeId: string): GraphView {
  for (const p of scene.primitives) {
    if (p.kind === 'circle' && p.source.id === nodeId) {
      return panBy(view, view.width / 2 - p.cx, view.height / 2 - p.cy);
    }
  }
  return view;
}

/** What a pointer position is in the units a layout uses, to place a node by hand. */
export function toWorld(scene: Scene, at: Point): Point {
  return {
    x: (at.x - scene.frame.ox) / scene.frame.scale,
    y: (at.y - scene.frame.oy) / scene.frame.scale,
  };
}

export function neighbours(model: GraphModel, id: string): string[] {
  const out = new Set<string>();
  for (const e of model.edges) {
    if (e.a === id) out.add(e.b);
    else if (e.b === id) out.add(e.a);
  }
  return [...out].sort();
}

export type ArrowKey = 'ArrowUp' | 'ArrowDown' | 'ArrowLeft' | 'ArrowRight';

const DIRECTIONS: Record<ArrowKey, Point> = {
  ArrowUp: { x: 0, y: -1 },
  ArrowDown: { x: 0, y: 1 },
  ArrowLeft: { x: -1, y: 0 },
  ArrowRight: { x: 1, y: 0 },
};

/** The node an arrow key leads to along an edge from `from`: among its neighbours, the one that
 * lies most nearly that way (and at all that way), or none. */
export function moveAlongEdges(
  scene: Scene,
  model: GraphModel,
  from: string,
  key: ArrowKey,
): string | null {
  const at = new Map<string, Point>();
  for (const p of scene.primitives)
    if (p.kind === 'circle') at.set(p.source.id, { x: p.cx, y: p.cy });
  const origin = at.get(from);
  if (!origin) return null;
  const want = DIRECTIONS[key];
  let best: { id: string; score: number } | null = null;
  for (const other of neighbours(model, from)) {
    const there = at.get(other);
    if (!there) continue;
    const dx = there.x - origin.x;
    const dy = there.y - origin.y;
    const length = Math.sqrt(dx * dx + dy * dy) || 1;
    const score = (dx * want.x + dy * want.y) / length;
    if (score > 0.3 && (best === null || score > best.score)) best = { id: other, score };
  }
  return best?.id ?? null;
}
