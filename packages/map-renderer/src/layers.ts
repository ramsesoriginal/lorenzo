import { num } from './geom';
import { extentOf, type Transform } from './project';
import type { ImagePrim, Prim } from './scene';
import { isSphere } from './sphere';
import type { BBox, MapModel, Point } from './types';

/**
 * The pictures a Map is drawn over (ADR 0362). A layer is made by the host: `href` is a `data:`
 * image URL it built itself (anything else is not drawn) and `size` the picture's natural size in
 * pixels. The renderer fetches and decodes nothing.
 */
export type Anchor = { image: Point; at: Point };

/** `null` is *fit the sheet*; otherwise two anchors (a similarity) or three (an affine map). */
export type Calibration = { anchors: readonly Anchor[] };

export type Layer = {
  /** Stable for the layer; it is part of the primitive's id. */
  id: string;
  href: string;
  size: readonly [number, number];
  opacity?: number | null;
  calibration?: Calibration | null;
};

/** `x' = a x + c y + e`, `y' = b x + d y + f`, as an SVG `matrix(a b c d e f)`. */
export type Matrix = readonly [number, number, number, number, number, number];

const DATA_IMAGE = /^data:image\/(?:png|jpeg|gif|webp|svg\+xml)[;,]/i;

export function isDataImage(href: string): boolean {
  return DATA_IMAGE.test(href);
}

/**
 * A matrix entry to six decimals: a picture of thousands of pixels drawn on a sheet of hundreds of
 * units has entries far below what the Scene's two decimals could keep.
 */
function fine(n: number): number {
  if (!Number.isFinite(n)) throw new RangeError('map-renderer: a layer matrix is not finite');

  const v = Math.round(n * 1e6) / 1e6;

  return v === 0 ? 0 : v;
}

function valid(layer: Layer): boolean {
  const [w, h] = layer.size;

  return isDataImage(layer.href) && w > 0 && h > 0 && Number.isFinite(w) && Number.isFinite(h);
}

function fit(extent: BBox, w: number, h: number): Matrix {
  const width = extent[2] - extent[0];
  const height = extent[3] - extent[1];
  const s = Math.min(width / w, height / h);

  return [s, 0, 0, s, extent[0] + (width - s * w) / 2, extent[1] + (height - s * h) / 2];
}

/** Two pairs of points as a turn, one scale and a move, working in complex numbers. */
function similarity(p: readonly Point[], q: readonly Point[]): Matrix | null {
  const [p1, p2] = p as [Point, Point];
  const [q1, q2] = q as [Point, Point];
  const dpx = p2[0] - p1[0];
  const dpy = p2[1] - p1[1];
  const denominator = dpx * dpx + dpy * dpy;

  if (!(denominator > 0)) return null;

  const dqx = q2[0] - q1[0];
  const dqy = q2[1] - q1[1];
  const ar = (dqx * dpx + dqy * dpy) / denominator;
  const ai = (dqy * dpx - dqx * dpy) / denominator;

  return [ar, ai, -ai, ar, q1[0] - (ar * p1[0] - ai * p1[1]), q1[1] - (ai * p1[0] + ar * p1[1])];
}

/** Three pairs of points as an affine map, by Cramer's rule. */
function affine(p: readonly Point[], q: readonly Point[]): Matrix | null {
  const [p1, p2, p3] = p as [Point, Point, Point];
  const [q1, q2, q3] = q as [Point, Point, Point];
  const det = p1[0] * (p2[1] - p3[1]) + p2[0] * (p3[1] - p1[1]) + p3[0] * (p1[1] - p2[1]);

  if (!(Math.abs(det) > 1e-12)) return null;

  const solve = (v1: number, v2: number, v3: number): [number, number, number] => [
    (v1 * (p2[1] - p3[1]) + v2 * (p3[1] - p1[1]) + v3 * (p1[1] - p2[1])) / det,
    (v1 * (p3[0] - p2[0]) + v2 * (p1[0] - p3[0]) + v3 * (p2[0] - p1[0])) / det,
    (v1 * (p2[0] * p3[1] - p3[0] * p2[1]) +
      v2 * (p3[0] * p1[1] - p1[0] * p3[1]) +
      v3 * (p1[0] * p2[1] - p2[0] * p1[1])) /
      det,
  ];
  const [a, c, e] = solve(q1[0], q2[0], q3[0]);
  const [b, d, f] = solve(q1[1], q2[1], q3[1]);

  return [a, b, c, d, e, f];
}

/**
 * Where a picture of `size` pixels lies on the sheet, as a matrix from its pixels to drawing units:
 * fitted whole and centred when there is no calibration, else from its anchors. Null when the
 * calibration cannot be solved (anchors on top of one another or on a line).
 */
export function layerMatrix(extent: BBox, layer: Layer): Matrix | null {
  const [w, h] = layer.size;
  const anchors = layer.calibration?.anchors;

  if (!anchors) return fit(extent, w, h);

  const pixels = anchors.map((a): Point => [a.image[0] * w, a.image[1] * h]);
  const sheet = anchors.map((a): Point => a.at);
  const matrix =
    anchors.length === 2
      ? similarity(pixels, sheet)
      : anchors.length === 3
        ? affine(pixels, sheet)
        : null;

  return matrix && matrix.every(Number.isFinite) ? matrix : null;
}

/** The pictures of a Map as primitives, bottom first; none for a sphere (ADR 0362). */
export function layerPrims(model: MapModel, t: Transform): Prim[] {
  if (isSphere(model.system) || !model.layers?.length) return [];

  const extent = extentOf(model.system);
  const prims: Prim[] = [];

  for (const layer of model.layers) {
    if (!valid(layer)) continue;

    const m = layerMatrix(extent, layer);

    if (!m) continue;

    const [w, h] = layer.size;
    // Drawing units to the screen: scale, then move.
    const ox = t.width / 2 - t.centre[0] * t.scale;
    const oy = t.height / 2 - t.centre[1] * t.scale;
    const s = t.scale;
    const matrix: [number, number, number, number, number, number] = [
      fine(m[0] * s),
      fine(m[1] * s),
      fine(m[2] * s),
      fine(m[3] * s),
      fine(m[4] * s + ox),
      fine(m[5] * s + oy),
    ];
    const corners = [
      [0, 0],
      [w, 0],
      [w, h],
      [0, h],
    ].map(
      ([x, y]): Point => [
        (matrix[0] * (x as number) + matrix[2] * (y as number) + matrix[4]) as number,
        (matrix[1] * (x as number) + matrix[3] * (y as number) + matrix[5]) as number,
      ],
    );
    const xs = corners.map((c) => c[0]);
    const ys = corners.map((c) => c[1]);
    const prim: ImagePrim = {
      id: `layer:${layer.id}`,
      kind: 'image',
      cls: 'm-layer',
      href: layer.href,
      key: `${layer.id}:${layer.href.length}`,
      width: num(w),
      height: num(h),
      matrix,
      ...(layer.opacity === null || layer.opacity === undefined
        ? {}
        : { opacity: num(layer.opacity, 'an opacity') }),
      bbox: [
        num(Math.min(...xs)),
        num(Math.min(...ys)),
        num(Math.max(...xs)),
        num(Math.max(...ys)),
      ],
    };

    prims.push(prim);
  }

  return prims;
}
