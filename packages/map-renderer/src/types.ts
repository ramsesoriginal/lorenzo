/**
 * The contract the app maps API JSON onto (ADR 0336, 0337, 0338, 0339). Positions are drawing
 * units on a flat sheet; y grows downward, as in SVG.
 */

export type Point = readonly [number, number];

/** A box as `[x0, y0, x1, y1]`. */
export type BBox = readonly [number, number, number, number];

export type System = {
  kind: string;
  extent: BBox;
  scale?: { per_unit: number; unit: string };
};

export type Part =
  | { shape: 'point'; at: Point; value?: number; unit?: string }
  | { shape: 'circle'; at: Point; r: number; value?: number; unit?: string }
  | { shape: 'polyline'; pts: readonly Point[]; value?: number; unit?: string }
  | {
      shape: 'bezier';
      start: Point;
      /** Cubic segments: `[control1, control2, end]`. */
      segs: readonly (readonly [Point, Point, Point])[];
      closed?: boolean;
      value?: number;
      unit?: string;
    }
  | {
      shape: 'polygon';
      /** The outer ring, then holes. A ring is not closed by repeating its first point. */
      rings: readonly (readonly Point[])[];
      value?: number;
      unit?: string;
    };

export type Geometry = { format: string; parts: readonly Part[] };

export type StrokeStyle = 'solid' | 'dashed' | 'dotted' | 'double' | 'none';
export type Weight = 'hairline' | 'thin' | 'regular' | 'thick' | 'heavy';
export type Style = { stroke?: StrokeStyle; weight?: Weight };

export type Placement = {
  entry: { id: string; name: string; slug?: string | null; kinds: readonly string[] };
  geometry: Geometry;
  role?: string | null;
  style?: Style | null;
  z: number;
};

export type MapModel = { system: System; placements: readonly Placement[] };

/** The closed list of roles (ADR 0337). It grows only by ADR. */
export const ROLES = [
  'water',
  'ground',
  'relief',
  'vegetation',
  'diffuse',
  'celestial',
  'built-up',
  'structure',
  'interior',
  'barrier',
  'passage',
  'route',
  'conduit',
  'territory',
  'boundary',
  'hazard',
  'presence',
  'object',
  'isoline',
  'marker',
  'site',
] as const;

export type Role = (typeof ROLES)[number];

const ROLE_SET: ReadonlySet<string> = new Set(ROLES);

/** The role a placement names, or `null` for none or for one this version does not know. */
export function normaliseRole(role: string | null | undefined): Role | null {
  return typeof role === 'string' && ROLE_SET.has(role) ? (role as Role) : null;
}

/** A role said in words, for an accessible name. */
export const ROLE_WORDS: Readonly<Record<Role, string>> = {
  water: 'water',
  ground: 'ground',
  relief: 'relief',
  vegetation: 'vegetation',
  diffuse: 'diffuse area',
  celestial: 'celestial',
  'built-up': 'built-up area',
  structure: 'structure',
  interior: 'interior',
  barrier: 'barrier',
  passage: 'passage',
  route: 'route',
  conduit: 'conduit',
  territory: 'territory',
  boundary: 'boundary',
  hazard: 'hazard',
  presence: 'presence',
  object: 'object',
  isoline: 'isoline',
  marker: 'marker',
  site: 'site',
};

/** Which switches of the view a placement belongs to. */
export type Groups = {
  /** Every placement that is not `presence` or `route`, including one with no role. */
  places: boolean;
  /** Role `presence`. */
  people: boolean;
  /** Role `route`. */
  roads: boolean;
  /** Text labels. */
  names: boolean;
  /** Draw a hairline outline for hit-only placements (`style.stroke` of `none`). */
  showPlaces: boolean;
};

export type GroupName = 'places' | 'people' | 'roads';

export function groupOf(role: Role | null): GroupName {
  if (role === 'presence') return 'people';
  if (role === 'route') return 'roads';
  return 'places';
}

export const DEFAULT_GROUPS: Groups = {
  places: true,
  people: true,
  roads: true,
  names: true,
  showPlaces: true,
};

import type { Overlay } from './edit';

export type View = {
  /** The drawing's size in screen pixels. */
  viewport: { width: number; height: number };
  /** 1 fits the whole sheet in the viewport; 2 is twice that. */
  zoom: number;
  /** The drawing point at the viewport's centre. */
  centre: Point;
  groups: Groups;
  /** The selected placement's entry id. */
  selection: string | null;
  /** The hovered or focused placement's entry id. */
  hover?: string | null;
  /** Where the brand's `icons.svg` is served from; empty means an inline sprite in the page. */
  iconBase?: string;
  /** What an editor draws over the marks (ADR 0353); none when nothing is being edited. */
  overlay?: Overlay;
};
