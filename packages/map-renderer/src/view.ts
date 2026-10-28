import { extentOf, fitScale } from './project';
import type { Point, System } from './types';

/**
 * The interaction's arithmetic, kept pure so it can be tested without a DOM: what zoom and pan
 * do to the zoom and the centre. Screen points are pixels from the viewport's top left.
 */

export const MIN_ZOOM = 0.25;
export const MAX_ZOOM = 16;
/** What one press of a zoom button or key multiplies the zoom by. */
export const ZOOM_STEP = 1.25;
/** What an arrow key pans by, in screen pixels. */
export const PAN_STEP = 48;
/** How far past the sheet the centre may be panned, as a share of the sheet's size. */
export const PAN_MARGIN = 0.5;

export type ViewState = { zoom: number; centre: Point };
export type Viewport = { width: number; height: number };

export function clampZoom(zoom: number): number {
  if (!Number.isFinite(zoom)) return 1;

  return Math.min(MAX_ZOOM, Math.max(MIN_ZOOM, zoom));
}

/** The centre of the sheet. */
export function sheetCentre(system: System): Point {
  const e = extentOf(system);

  return [(e[0] + e[2]) / 2, (e[1] + e[3]) / 2];
}

/** "Whole map": the sheet fits the viewport, centred. */
export function fitView(system: System): ViewState {
  return { zoom: 1, centre: sheetCentre(system) };
}

/** The centre, kept within the sheet and a margin around it. */
export function clampCentre(system: System, centre: Point): Point {
  const e = extentOf(system);
  const mx = (e[2] - e[0]) * PAN_MARGIN;
  const my = (e[3] - e[1]) * PAN_MARGIN;

  return [
    Math.min(e[2] + mx, Math.max(e[0] - mx, centre[0])),
    Math.min(e[3] + my, Math.max(e[1] - my, centre[1])),
  ];
}

function scaleOf(system: System, viewport: Viewport, zoom: number): number {
  return fitScale(system, viewport.width, viewport.height) * zoom;
}

/** A screen point as a drawing point. */
export function screenToDrawing(
  system: System,
  viewport: Viewport,
  state: ViewState,
  point: Point,
): Point {
  const s = scaleOf(system, viewport, state.zoom);

  return [
    state.centre[0] + (point[0] - viewport.width / 2) / s,
    state.centre[1] + (point[1] - viewport.height / 2) / s,
  ];
}

/**
 * Sets the zoom (clamped). With an `anchor` (a screen point) the drawing point under it stays
 * under it, as a wheel zooms toward the pointer; without one the centre stays.
 */
export function zoomTo(
  system: System,
  viewport: Viewport,
  state: ViewState,
  zoom: number,
  anchor?: Point,
): ViewState {
  const next = clampZoom(zoom);

  if (!anchor) return { zoom: next, centre: state.centre };

  const under = screenToDrawing(system, viewport, state, anchor);
  const s = scaleOf(system, viewport, next);
  const centre: Point = [
    under[0] - (anchor[0] - viewport.width / 2) / s,
    under[1] - (anchor[1] - viewport.height / 2) / s,
  ];

  return { zoom: next, centre: clampCentre(system, centre) };
}

export function zoomBy(
  system: System,
  viewport: Viewport,
  state: ViewState,
  factor: number,
  anchor?: Point,
): ViewState {
  return zoomTo(system, viewport, state, state.zoom * factor, anchor);
}

/** Moves the drawing by `dx`, `dy` screen pixels (a drag): the centre moves the other way. */
export function panBy(
  system: System,
  viewport: Viewport,
  state: ViewState,
  dx: number,
  dy: number,
): ViewState {
  const s = scaleOf(system, viewport, state.zoom);

  return {
    zoom: state.zoom,
    centre: clampCentre(system, [state.centre[0] - dx / s, state.centre[1] - dy / s]),
  };
}

/** Puts a drawing point at the centre, at the same zoom. Not clamped: it is a choice. */
export function centreOn(state: ViewState, point: Point): ViewState {
  return { zoom: state.zoom, centre: [point[0], point[1]] };
}

export function sameView(a: ViewState, b: ViewState): boolean {
  return a.zoom === b.zoom && a.centre[0] === b.centre[0] && a.centre[1] === b.centre[1];
}

/** The zoom as a percentage, as the toolbar says it. */
export function zoomLabel(zoom: number): string {
  return `${Math.round(zoom * 100)}%`;
}
