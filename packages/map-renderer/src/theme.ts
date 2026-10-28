import type { BBox, Part, Placement, Point, Role, System } from './types';

/**
 * A part of a placement placed on the screen. A theme draws these; it never sees a stored
 * coordinate. `area` is a polygon or a closed bezier (even-odd, holes cut out); `circle` is a
 * disc with a radius in screen pixels.
 */
export type Shape =
  | { kind: 'point'; at: Point }
  | { kind: 'circle'; at: Point; r: number }
  | { kind: 'line'; d: string; bbox: BBox }
  | { kind: 'area'; d: string; bbox: BBox };

export type DrawableShape = Exclude<Shape, { kind: 'point' }>;

/** What layout tells a theme about the view, and the helpers it needs to place things. */
export type ThemeContext = {
  system: System;
  /** Screen pixels per drawing unit. */
  scale: number;
  /** Screen pixels per design unit (1/1000 of the sheet's width): how wide a river band is. */
  design: number;
  /** Drawing units per design unit, for a theme that works in drawing space (hill arcs). */
  designUnit: number;
  names: boolean;
  showPlaces: boolean;
  /** A drawing point on the screen. */
  toScreen(p: Point): Point;
  /** A cubic given in drawing units, as a line on the screen. */
  cubic(p0: Point, p1: Point, p2: Point, p3: Point): DrawableShape;
};

export type MarkInput = {
  placement: Placement;
  /** `null` for no role and for one this version does not know. */
  role: Role | null;
  part: Part;
  partIndex: number;
  shape: Shape;
  ctx: ThemeContext;
};

/** A path or a disc, with the class that colours it and how it is stroked. */
export type DrawMark = {
  type: 'draw';
  /** What it is for, unique within a part: it ends the primitive's id. */
  purpose: string;
  shape: DrawableShape;
  cls: string;
  /** A stroke width in screen pixels. */
  width?: number;
  /** A `stroke-dasharray` value. */
  dash?: string;
  /** This mark is what `hitTest` finds the placement by (a line within a tolerance). */
  hit?: boolean;
};

export type TextMark = {
  type: 'text';
  purpose: string;
  cls: string;
  at: Point;
  text: string;
  anchor?: 'middle';
};

/** An icon of the brand's atlas, centred on `at`. */
export type IconMark = {
  type: 'icon';
  purpose: string;
  cls: string;
  at: Point;
  size: number;
  /** The atlas id without its `icon-` prefix, such as `kind-location`. */
  icon: string;
};

export type Mark = DrawMark | TextMark | IconMark;

/**
 * A theme is a code module: how each role's geometry is drawn, and the furniture around the
 * drawing. It names classes and the stylesheet names tokens, so it never carries a colour. A
 * theme cannot add a role, a field or a request (ADR 0339).
 */
export interface Theme {
  readonly name: string;
  /** The class of the sheet's fill, which spans the viewport. */
  readonly sheetClass: string;
  /**
   * Which layer of the drawing a placement is on (0 at the bottom): areas and water, then other
   * lines, then pins, then people. Within a layer placements are ordered by `z` and entry id.
   */
  layer(placement: Placement, role: Role | null): number;
  /** The marks of one part of a placement, bottom first. */
  marks(input: MarkInput): Mark[];
}
