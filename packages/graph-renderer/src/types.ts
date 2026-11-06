// The graph renderer's vocabulary (ADR 0407): what it is given, what it asks of a theme, and the
// Scene it lays out. Everything here is plain data.

import layoutNames from './layouts.json';

/** The closed list of layout names, one source shared with the API's check (see test/layouts). */
export const LAYOUT_NAMES = layoutNames as readonly LayoutName[];
export type LayoutName = 'circle' | 'radial' | 'stress' | 'forceatlas2' | 'manual' | 'layered';

/** How an edge holds: stated (solid), derived or inherited or indirect (dashed), uncertain (dotted). */
export type EdgeStatus = 'direct' | 'derived' | 'uncertain';

export interface GraphNode {
  id: string;
  name: string;
  /** A key in the brand's icon atlas, or none. */
  icon?: string;
  /** Drawn quieter (an entry outside the current lens), never hidden by this flag. */
  dim?: boolean;
}

export interface GraphEdge {
  id: string;
  a: string;
  b: string;
  /** True for a tie that goes from `a` to `b` only; the arrowhead says so. */
  directed: boolean;
  label?: string;
  status: EdgeStatus;
  /** An optional value, drawn as the line's weight against `scale` when both are given. */
  value?: number;
  scale?: readonly [number, number];
}

export interface GraphGroup {
  id: string;
  name: string;
  members: readonly string[];
}

export interface GraphModel {
  nodes: readonly GraphNode[];
  edges: readonly GraphEdge[];
  groups?: readonly GraphGroup[];
}

export interface Point {
  x: number;
  y: number;
}

export type Selection = { kind: 'node' | 'edge'; id: string } | null;

export interface GraphView {
  /** The viewport in pixels: the Scene is in these pixels and the `<svg>` needs no transform. */
  width: number;
  height: number;
  layout: LayoutName;
  /** Seeds the engines that start from noise; the same seed is the same drawing. */
  seed: number;
  /** Hand placements, in the same units the engines use; a node here is pinned. */
  positions?: Readonly<Record<string, Point>>;
  /** Where `radial` starts from; the best connected node when none. */
  focus?: string | null;
  selection?: Selection;
  zoom: number;
  pan: Point;
  labels: boolean;
  hulls: boolean;
}

export const DEFAULT_VIEW: GraphView = {
  width: 800,
  height: 600,
  layout: 'circle',
  seed: 1,
  zoom: 1,
  pan: { x: 0, y: 0 },
  labels: true,
  hulls: false,
};

/** A theme names brand tokens and sizes, never a colour (ADR 0407). */
export interface Theme {
  name: string;
  nodeRadius: number;
  iconSize: number;
  fontSize: number;
  edgeWidth: number;
  /** The widest a weighted edge may be drawn. */
  edgeWidthMax: number;
  arrowSize: number;
  /** The gap between parallel edges of one pair. */
  parallelGap: number;
  hullPadding: number;
  /** Characters of a node's name before it is cut with an ellipsis. */
  labelChars: number;
  /** Class names the stylesheet maps onto brand tokens. */
  classes: {
    node: string;
    edge: string;
    hull: string;
    label: string;
    arrow: string;
  };
}

export type Dash = string | null;

export type Source =
  | { kind: 'node'; id: string }
  | { kind: 'edge'; id: string }
  | { kind: 'group'; id: string };

export type Primitive =
  | {
      kind: 'path';
      id: string;
      role: 'hull' | 'edge' | 'arrow';
      d: string;
      dash: Dash;
      width: number;
      className: string;
      selected: boolean;
      dim: boolean;
      source: Source;
    }
  | {
      kind: 'circle';
      id: string;
      role: 'node';
      /** The full name, for the accessible name of the mark. */
      name: string;
      cx: number;
      cy: number;
      r: number;
      className: string;
      selected: boolean;
      dim: boolean;
      source: Source;
    }
  | {
      kind: 'text';
      id: string;
      role: 'node-label' | 'edge-label' | 'hull-label';
      x: number;
      y: number;
      text: string;
      className: string;
      source: Source;
    }
  | {
      kind: 'icon';
      id: string;
      role: 'node-icon';
      x: number;
      y: number;
      size: number;
      key: string;
      source: Source;
    };

export interface Scene {
  width: number;
  height: number;
  /** World to screen: `screen = origin + world * scale`, so a pointer can be taken back to a node's
   * units (to move a node by hand). */
  frame: { scale: number; ox: number; oy: number };
  /** The box of everything drawn, in the same pixels. */
  bounds: { x0: number; y0: number; x1: number; y1: number };
  primitives: Primitive[];
}

/** An engine places nodes in abstract units and knows nothing of pixels. */
export interface LayoutGraph {
  ids: readonly string[];
  /** Undirected neighbour pairs by index into `ids`, each pair once, a < b. */
  pairs: readonly (readonly [number, number])[];
  /** Nodes with a hand position keep it. */
  pins: ReadonlyMap<number, Point>;
  /** The node `radial` grows from. */
  focus: number;
}

export type Positions = Point[];
export type Engine = (graph: LayoutGraph, seed: number) => Positions;
