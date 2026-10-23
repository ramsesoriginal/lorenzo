import type { BBox } from './types';

/** How a primitive answers `hitTest`: a line within a tolerance, or an area exactly. */
export type Hit = { mode: 'line'; tol: number } | { mode: 'area' };

type Base = {
  /** Stable: the entry id, the part index and what the primitive is for. */
  id: string;
  /** Space-separated class names; the stylesheet gives them colour. */
  cls: string;
  /** In screen pixels, `[x0, y0, x1, y1]`. For text it is an estimate. */
  bbox: BBox;
  /** The placement the primitive came from; absent for furniture such as the sheet. */
  entryId?: string;
  /** The placement's accessible name; on the first primitive of each placement. */
  label?: string;
  hit?: Hit;
};

type Stroked = {
  strokeWidth?: number;
  /** A `stroke-dasharray` value such as `6 5`. */
  dash?: string;
};

export type RectPrim = Base & { kind: 'rect'; x: number; y: number; width: number; height: number };
export type PathPrim = Base & Stroked & { kind: 'path'; d: string; fillRule?: 'evenodd' };
export type CirclePrim = Base & Stroked & { kind: 'circle'; cx: number; cy: number; r: number };
export type TextPrim = Base & {
  kind: 'text';
  x: number;
  y: number;
  text: string;
  anchor?: 'middle';
};
/** An icon of the brand's atlas (`icon-<icon>`), drawn at `x`, `y` (top left) `size` square. */
export type IconPrim = Base & { kind: 'icon'; icon: string; x: number; y: number; size: number };

export type Prim = RectPrim | PathPrim | CirclePrim | TextPrim | IconPrim;

/** Plain, JSON-serialisable data in the screen pixels of the viewport. */
export type Scene = {
  theme: string;
  width: number;
  height: number;
  selection: string | null;
  iconBase: string;
  /** In draw order, first at the bottom. Primitives of one placement are contiguous. */
  prims: Prim[];
};
