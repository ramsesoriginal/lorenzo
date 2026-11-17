// A region of cells as outlines (ADR 0481): the cells of a patch, cells that share an edge, as one
// polygon of an outline and its holes, and an outline read back as the cells it holds. Nothing is
// stored to say a polygon is cells; it is worked out from the grid. Pure.
import {
  type BBox,
  type Cell,
  cellAt,
  cellCentre,
  cellPolygon,
  type GridSpec,
  inGrid,
  type Point,
} from '@lorenzo/map-renderer';

type Ring = Point[];

/** The rings of one polygon part: its outline first, then its holes. */
export type Outline = Ring[];

/** To two decimals, as the editor keeps points; never -0. */
const roundTo = (n: number) => Math.round(n * 100) / 100 || 0;

/** The smallest side of a cell: corners of different cells are at least about this far apart. */
function cellSide(grid: GridSpec): number {
  if (grid.kind === 'rect') return Math.min(grid.cell.width ?? 1, grid.cell.height ?? 1);

  return grid.cell.size ?? 1;
}

/**
 * The corners of the cells as numbered points: a corner that several cells share is one point,
 * though each cell works it out for itself and the last digits may differ.
 */
function cornerIndex(grid: GridSpec) {
  const tolerance = cellSide(grid) * 1e-6;
  const bucket = tolerance * 10;
  const buckets = new Map<string, number[]>();
  const points: Point[] = [];

  return {
    points,
    of(p: Point): number {
      const bx = Math.round(p[0] / bucket);
      const by = Math.round(p[1] / bucket);

      for (let dx = -1; dx <= 1; dx += 1) {
        for (let dy = -1; dy <= 1; dy += 1) {
          for (const index of buckets.get(`${bx + dx},${by + dy}`) ?? []) {
            const q = points[index] as Point;

            if (Math.abs(q[0] - p[0]) <= tolerance && Math.abs(q[1] - p[1]) <= tolerance) {
              return index;
            }
          }
        }
      }

      const index = points.length;
      points.push(p);
      const key = `${bx},${by}`;
      buckets.set(key, [...(buckets.get(key) ?? []), index]);

      return index;
    },
  };
}

/** The signed area of a ring. */
function areaOf(ring: readonly Point[]): number {
  let sum = 0;

  for (let i = 0; i < ring.length; i += 1) {
    const a = ring[i] as Point;
    const b = ring[(i + 1) % ring.length] as Point;
    sum += a[0] * b[1] - b[0] * a[1];
  }

  return sum / 2;
}

/** A ring without the points in the middle of a straight run, rounded as the editor keeps points. */
function straightened(ring: readonly Point[]): Ring {
  const rounded = ring.map((p): Point => [roundTo(p[0]), roundTo(p[1])]);
  const out: Ring = [];

  for (let i = 0; i < rounded.length; i += 1) {
    const before = rounded[(i - 1 + rounded.length) % rounded.length] as Point;
    const here = rounded[i] as Point;
    const after = rounded[(i + 1) % rounded.length] as Point;
    const cross =
      (here[0] - before[0]) * (after[1] - here[1]) - (here[1] - before[1]) * (after[0] - here[0]);
    const scale =
      Math.hypot(here[0] - before[0], here[1] - before[1]) *
      Math.hypot(after[0] - here[0], after[1] - here[1]);

    if (Math.abs(cross) > 1e-9 * Math.max(1, scale)) out.push(here);
  }

  return out;
}

/**
 * The outline of cells that share edges: its rings, the outline first, or null when it meets itself
 * at a point, which squares and rectangles allow where two cells meet only at a corner.
 */
function patchOutline(grid: GridSpec, extent: BBox, cells: readonly Cell[]): Outline | null {
  const corners = cornerIndex(grid);
  // Each cell's edges, all in one turning sense: an edge two cells share runs both ways and goes.
  const edges = new Map<string, [number, number]>();

  for (const cell of cells) {
    const ring = cellPolygon(grid, extent, cell).map((p) => corners.of(p));
    const turn = areaOf(cellPolygon(grid, extent, cell)) > 0 ? 1 : -1;

    for (let i = 0; i < ring.length; i += 1) {
      const a = ring[turn > 0 ? i : (i + 1) % ring.length] as number;
      const b = ring[turn > 0 ? (i + 1) % ring.length : i] as number;
      const back = `${b}>${a}`;

      if (edges.has(back)) edges.delete(back);
      else edges.set(`${a}>${b}`, [a, b]);
    }
  }

  const from = new Map<number, number[]>();

  for (const [a, b] of edges.values()) from.set(a, [...(from.get(a) ?? []), b]);

  if ([...from.values()].some((next) => next.length !== 1)) return null;

  const rings: Ring[] = [];
  const used = new Set<number>();

  for (const start of from.keys()) {
    if (used.has(start)) continue;

    const ring: Ring = [];
    let at = start;

    while (!used.has(at)) {
      used.add(at);
      ring.push(corners.points[at] as Point);
      at = (from.get(at) as number[])[0] as number;
    }

    rings.push(straightened(ring));
  }

  // The outline is the ring of the largest area; the others are its holes.
  rings.sort((a, b) => Math.abs(areaOf(b)) - Math.abs(areaOf(a)));

  return rings;
}

const key = (cell: Cell) => `${cell[0]},${cell[1]}`;

/** The cells that share an edge with a cell, among some cells. */
function patchesOf(grid: GridSpec, extent: BBox, cells: readonly Cell[]): Cell[][] {
  const corners = cornerIndex(grid);
  const byEdge = new Map<string, number[]>();

  cells.forEach((cell, index) => {
    const ring = cellPolygon(grid, extent, cell).map((p) => corners.of(p));

    for (let i = 0; i < ring.length; i += 1) {
      const a = ring[i] as number;
      const b = ring[(i + 1) % ring.length] as number;
      const edge = a < b ? `${a}-${b}` : `${b}-${a}`;
      byEdge.set(edge, [...(byEdge.get(edge) ?? []), index]);
    }
  });

  const parent = cells.map((_, index) => index);
  const root = (i: number): number => {
    let r = i;
    while (parent[r] !== r) r = parent[r] as number;
    parent[i] = r;
    return r;
  };

  for (const shared of byEdge.values()) {
    for (let k = 1; k < shared.length; k += 1) {
      parent[root(shared[k] as number)] = root(shared[0] as number);
    }
  }

  const groups = new Map<number, Cell[]>();

  cells.forEach((cell, index) => {
    const r = root(index);
    groups.set(r, [...(groups.get(r) ?? []), cell]);
  });

  return [...groups.values()];
}

/**
 * The outlines of a region of cells (ADR 0481): one for each patch of cells that share an edge,
 * and, for a patch whose outline would meet itself at a point, one for each of its cells.
 */
export function cellOutlines(grid: GridSpec, extent: BBox, cells: readonly Cell[]): Outline[] {
  const seen = new Set<string>();
  const unique = cells.filter((cell) => !seen.has(key(cell)) && seen.add(key(cell)));

  return patchesOf(grid, extent, unique).flatMap((patch) => {
    const outline = patch.length > 1 ? patchOutline(grid, extent, patch) : null;

    return outline
      ? [outline]
      : patch.map(
          (cell): Outline => [
            cellPolygon(grid, extent, cell).map((p): Point => [roundTo(p[0]), roundTo(p[1])]),
          ],
        );
  });
}

/** Whether a point is inside the rings of a polygon, holes and all. */
function holds(rings: readonly (readonly Point[])[], [x, y]: Point): boolean {
  let inside = false;

  for (const ring of rings) {
    for (let i = 0, j = ring.length - 1; i < ring.length; j = i, i += 1) {
      const a = ring[i] as Point;
      const b = ring[j] as Point;

      if (a[1] > y !== b[1] > y && x < ((b[0] - a[0]) * (y - a[1])) / (b[1] - a[1]) + a[0]) {
        inside = !inside;
      }
    }
  }

  return inside;
}

/** Whether two rings are the same, from any point and in either direction, to two decimals. */
function sameRing(a: readonly Point[], b: readonly Point[]): boolean {
  if (a.length !== b.length || a.length === 0) return false;

  const near = (p: Point, q: Point) =>
    Math.abs(p[0] - q[0]) <= 0.011 && Math.abs(p[1] - q[1]) <= 0.011;

  for (const backwards of [false, true]) {
    const other = backwards ? [...b].reverse() : b;

    for (let shift = 0; shift < a.length; shift += 1) {
      if (a.every((p, i) => near(p, other[(i + shift) % a.length] as Point))) return true;
    }
  }

  return false;
}

/**
 * The cells a polygon part is the outline of (ADR 0481): those whose middles lie inside it, when
 * its rings are exactly their outline; null when it is anything else.
 */
export function cellsOfOutline(
  grid: GridSpec,
  extent: BBox,
  rings: readonly (readonly Point[])[],
): Cell[] | null {
  const all = rings.flat();

  if (all.length < 3) return null;

  const xs = all.map((p) => p[0]);
  const ys = all.map((p) => p[1]);
  const corners: Point[] = [
    [Math.min(...xs), Math.min(...ys)],
    [Math.max(...xs), Math.min(...ys)],
    [Math.min(...xs), Math.max(...ys)],
    [Math.max(...xs), Math.max(...ys)],
  ];
  const near = corners.map((p) => cellAt(grid, extent, p));
  const cols = near.map((c) => c[0]);
  const rows = near.map((c) => c[1]);
  const cells: Cell[] = [];

  for (let row = Math.min(...rows) - 1; row <= Math.max(...rows) + 1; row += 1) {
    for (let col = Math.min(...cols) - 1; col <= Math.max(...cols) + 1; col += 1) {
      const cell: Cell = [col, row];

      if (inGrid(grid, extent, cell) && holds(rings, cellCentre(grid, extent, cell))) {
        cells.push(cell);
      }
    }
  }

  if (cells.length === 0) return null;

  const outlines = cellOutlines(grid, extent, cells);

  if (outlines.length !== 1) return null;

  const outline = outlines[0] as Outline;
  const mine = rings.map((ring) => straightened(ring));

  if (outline.length !== mine.length) return null;

  const left = [...outline];

  for (const ring of mine) {
    const match = left.findIndex((other) => sameRing(ring, other));

    if (match < 0) return null;

    left.splice(match, 1);
  }

  return cells;
}
