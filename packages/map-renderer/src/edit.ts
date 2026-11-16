import { num } from './geom';
import { project, type Transform, toScreen } from './project';
import type { Prim } from './scene';
import type { BBox, Point, System } from './types';

/**
 * What an editor draws over a map (ADR 0353): the part of a shape being drawn, a rubber band to the
 * pointer, and handles to drag. It is in drawing units, never stored, and the view draws it above
 * the marks. A view knows nothing of what the editor does with it.
 */
export type OverlayShape =
  | {
      id: string;
      kind: 'line';
      pts: readonly Point[];
      /** An outline that closes on its first point. */
      closed?: boolean;
      /** A rubber band, a lighter stroke than a finished part. */
      preview?: boolean;
      /** Drawn only on the preview's side of the view's divider, when it has one. */
      clipped?: boolean;
    }
  | {
      id: string;
      /** A filled area (ADR 0475): an outline and its holes, even-odd, as a generator previews one. */
      kind: 'area';
      rings: readonly (readonly Point[])[];
      clipped?: boolean;
    }
  | {
      id: string;
      kind: 'disc';
      at: Point;
      /** In drawing units. */
      r: number;
      preview?: boolean;
    }
  | {
      id: string;
      kind: 'handle';
      at: Point;
      /** The handle being dragged. */
      active?: boolean;
    };

export type Overlay = readonly OverlayShape[];

/** The radius a handle is drawn with, and the distance it is picked from, in screen pixels. */
export const HANDLE_RADIUS = 6;
export const HANDLE_PICK = 10;

/** What a tool is told of a pointer event, in drawing units. */
export type ToolEvent = {
  point: Point;
  /** The entry whose mark is under the pointer, or null. */
  hit: string | null;
  /** The overlay handle under the pointer, or null; handles are picked before marks. */
  handle: string | null;
  shift: boolean;
  /** The click count of a click; 0 for a key. */
  detail: number;
};

/**
 * While a tool is set the pointer is the tool's: a click does not select, and a press the tool
 * takes does not pan. A view with no tool behaves as before.
 */
export interface Tool {
  readonly cursor?: 'crosshair' | 'default';
  /** A press: true takes it as a drag of the tool's own (a handle, a shape being moved). */
  down?(event: ToolEvent): boolean;
  drag?(event: ToolEvent): void;
  up?(event: ToolEvent): void;
  /** A click that was not a drag: true when the tool used it, false lets the view select. */
  click?(event: ToolEvent): boolean;
  dblclick?(event: ToolEvent): boolean;
  /** The pointer moved over the sheet and no press is held. */
  move?(event: ToolEvent): void;
  /** A key: true when the tool used it. */
  key?(event: KeyboardEvent): boolean;
}

/**
 * The screen primitives of an overlay, drawn after the marks; they take no pointer events. With
 * `divide` (a fraction of the view's width from its left, ADR 0475) the shapes marked `clipped`
 * are drawn only to its right, so the Map as it is shows on its left, and a divider is drawn there.
 */
export function overlayPrims(
  overlay: Overlay,
  system: System,
  t: Transform,
  divide?: number,
): Prim[] {
  const edge =
    divide === undefined ? null : num(Math.max(0, Math.min(1, divide)) * t.width, 'a divider');
  const clip = (clipped: boolean | undefined): { clip: BBox } | Record<string, never> =>
    clipped && edge !== null ? { clip: [edge, 0, num(t.width), num(t.height)] } : {};

  const at = (p: Point): Point => {
    const s = toScreen(t, project(system, p));

    return [num(s[0]), num(s[1])];
  };
  const prims: Prim[] = [];

  for (const shape of overlay) {
    const id = `overlay:${shape.id}`;

    if (shape.kind === 'line') {
      const pts = shape.pts.map(at);

      if (pts.length === 0) continue;

      const xs = pts.map((p) => p[0]);
      const ys = pts.map((p) => p[1]);

      prims.push({
        id,
        kind: 'path',
        cls: shape.preview ? 'm-ov m-ov-line m-ov-preview' : 'm-ov m-ov-line',
        d: `M ${pts.map((p) => `${p[0]} ${p[1]}`).join(' L ')}${shape.closed ? ' Z' : ''}`,
        bbox: [Math.min(...xs), Math.min(...ys), Math.max(...xs), Math.max(...ys)],
        ...clip(shape.clipped),
      });
    } else if (shape.kind === 'area') {
      const rings = shape.rings.map((ring) => ring.map(at)).filter((ring) => ring.length > 0);
      const all = rings.flat();

      if (all.length === 0) continue;

      const xs = all.map((p) => p[0]);
      const ys = all.map((p) => p[1]);

      prims.push({
        id,
        kind: 'path',
        cls: 'm-ov m-ov-area',
        d: rings.map((ring) => `M ${ring.map((p) => `${p[0]} ${p[1]}`).join(' L ')} Z`).join(' '),
        fillRule: 'evenodd',
        bbox: [Math.min(...xs), Math.min(...ys), Math.max(...xs), Math.max(...ys)],
        ...clip(shape.clipped),
      });
    } else if (shape.kind === 'disc') {
      const c = at(shape.at);
      const r = num(shape.r * t.scale);

      prims.push({
        id,
        kind: 'circle',
        cls: shape.preview ? 'm-ov m-ov-line m-ov-preview' : 'm-ov m-ov-line',
        cx: c[0],
        cy: c[1],
        r,
        bbox: [c[0] - r, c[1] - r, c[0] + r, c[1] + r],
      });
    } else {
      const c = at(shape.at);

      prims.push({
        id,
        kind: 'circle',
        cls: shape.active ? 'm-ov m-ov-handle m-ov-active' : 'm-ov m-ov-handle',
        cx: c[0],
        cy: c[1],
        r: HANDLE_RADIUS,
        bbox: [
          c[0] - HANDLE_RADIUS,
          c[1] - HANDLE_RADIUS,
          c[0] + HANDLE_RADIUS,
          c[1] + HANDLE_RADIUS,
        ],
      });
    }
  }

  if (edge !== null && overlay.some((shape) => 'clipped' in shape && shape.clipped)) {
    prims.push({
      id: 'overlay:divider',
      kind: 'path',
      cls: 'm-ov m-ov-divider',
      d: `M ${edge} 0 L ${edge} ${num(t.height)}`,
      bbox: [edge, 0, edge, num(t.height)],
    });
  }

  return prims;
}

/** The nearest handle within reach of a screen point, or null. The last one wins a tie. */
export function handleAt(
  overlay: Overlay,
  system: System,
  t: Transform,
  screen: Point,
): string | null {
  let found: string | null = null;
  let best = HANDLE_PICK;

  for (const shape of overlay) {
    if (shape.kind !== 'handle') continue;

    const s = toScreen(t, project(system, shape.at));
    const d = Math.hypot(s[0] - screen[0], s[1] - screen[1]);

    if (d <= best) {
      best = d;
      found = shape.id;
    }
  }

  return found;
}
