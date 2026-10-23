import { num } from './geom';
import type { BBox, Point, System, View } from './types';

/**
 * The one place a stored position becomes a drawing position. For `plane` and `outline` it is the
 * identity, as storage and SVG are both y-down; a kind this version does not know is read as an
 * outline (ADR 0336).
 */
export function project(_system: System, point: Point): Point {
  return [point[0], point[1]];
}

/** The sheet's width: the one length that "design units" are measured against. */
export const DESIGN_SHEET = 1000;

export type Transform = {
  /** Screen pixels per drawing unit. */
  scale: number;
  width: number;
  height: number;
  centre: Point;
  /** Drawing units in one design unit: 1/1000 of the sheet's width. */
  designUnit: number;
};

export function extentOf(system: System): BBox {
  const e = system.extent;

  if (!Array.isArray(e) || e.length !== 4 || e.some((n) => !Number.isFinite(n))) {
    throw new RangeError('map-renderer: the system has no finite extent');
  }

  if (!(e[2] > e[0]) || !(e[3] > e[1])) {
    throw new RangeError('map-renderer: the extent has no area');
  }

  return [e[0], e[1], e[2], e[3]];
}

/** Screen pixels per drawing unit when the whole sheet fits the viewport. */
export function fitScale(system: System, width: number, height: number): number {
  const e = extentOf(system);

  return Math.min(width / (e[2] - e[0]), height / (e[3] - e[1]));
}

export function transformOf(system: System, view: View): Transform {
  const { width, height } = view.viewport;

  if (!(width > 0) || !(height > 0) || !Number.isFinite(width) || !Number.isFinite(height)) {
    throw new RangeError('map-renderer: the viewport has no size');
  }

  if (!(view.zoom > 0) || !Number.isFinite(view.zoom)) {
    throw new RangeError('map-renderer: the zoom is not a positive number');
  }

  const centre = project(system, view.centre);

  if (!Number.isFinite(centre[0]) || !Number.isFinite(centre[1])) {
    throw new RangeError('map-renderer: the centre is not finite');
  }

  const e = extentOf(system);

  return {
    scale: fitScale(system, width, height) * view.zoom,
    width,
    height,
    centre,
    designUnit: (e[2] - e[0]) / DESIGN_SHEET,
  };
}

/** A drawing point on the screen, unrounded. */
export function toScreen(t: Transform, p: Point): Point {
  return [
    t.width / 2 + (p[0] - t.centre[0]) * t.scale,
    t.height / 2 + (p[1] - t.centre[1]) * t.scale,
  ];
}

/** A screen point as a drawing point. */
export function toDrawing(t: Transform, p: Point): Point {
  return [
    t.centre[0] + (p[0] - t.width / 2) / t.scale,
    t.centre[1] + (p[1] - t.height / 2) / t.scale,
  ];
}

/** The screen box of a drawing box, rounded as the Scene's numbers are. */
export function boxToScreen(t: Transform, box: BBox): BBox {
  const a = toScreen(t, [box[0], box[1]]);
  const b = toScreen(t, [box[2], box[3]]);

  return [num(a[0]), num(a[1]), num(b[0]), num(b[1])];
}
