// Editing on a grid (ADR 0356): the words for a cell, snapping a point to a cell's centre or corner,
// and a region of whole cells as the geometry the API takes. Pure: nothing here touches the page.
import {
  type BBox,
  type Cell,
  cellAt,
  cellCentre,
  cellPolygon,
  type Geometry,
  type GridSpec,
  inGrid,
  type Part,
  type Point,
} from '@lorenzo/map-renderer';
import { cellOutlines, cellsOfOutline } from './cell-outlines';
import { type Valued, valued } from './geometry-edit';

/**
 * The most cells the Cells tool takes into one region: a drawing's own limits (ADR 0481) decide
 * what can be written, and are checked when it is.
 */
export const MAX_CELLS_PER_PLACEMENT = 10_000;

/** What a cell is called to a person: counted from 1, where the API and the files count from 0. */
export const cellWords = (cell: Cell): string => `Column ${cell[0] + 1}, row ${cell[1] + 1}`;

const same = (a: Cell, b: Cell) => a[0] === b[0] && a[1] === b[1];

/** To two decimals, as the editor keeps points; never -0. */
const roundTo = (n: number) => Math.round(n * 100) / 100 || 0;

/** The cell a point is in, when it is a cell of the grid. */
export function cellOfPoint(grid: GridSpec, extent: BBox, p: Point): Cell | null {
  const cell = cellAt(grid, extent, p);

  return inGrid(grid, extent, cell) ? cell : null;
}

/** The centre of the cell a point is in; the point itself when it is in none. */
export function snapCentre(grid: GridSpec, extent: BBox, p: Point): Point {
  const cell = cellOfPoint(grid, extent, p);

  if (!cell) return p;

  const [x, y] = cellCentre(grid, extent, cell);

  return [roundTo(x), roundTo(y)];
}

/** The nearest corner of the cell a point is in; the point itself when it is in none. */
export function snapCorner(grid: GridSpec, extent: BBox, p: Point): Point {
  const cell = cellOfPoint(grid, extent, p);

  if (!cell) return p;

  let best = p;
  let nearest = Number.POSITIVE_INFINITY;

  for (const corner of cellPolygon(grid, extent, cell)) {
    const d = Math.hypot(corner[0] - p[0], corner[1] - p[1]);

    if (d < nearest) {
      nearest = d;
      best = [roundTo(corner[0]), roundTo(corner[1])];
    }
  }

  return best;
}

/**
 * The geometry of a region of whole cells (ADR 0481): one outline for each patch of cells that
 * share an edge, and a part of its own for each cell that carries a value and a unit. A cell that
 * `was` already drew with a value keeps it (ADR 0337), so changing a region never drops a value.
 */
export function cellsGeometry(
  grid: GridSpec,
  extent: BBox,
  cells: readonly Cell[],
  was?: Geometry,
): Geometry {
  const carried = new Map<string, Valued>();

  for (const part of was?.parts ?? []) {
    const held = valued(part);

    if (held.value === undefined) continue;

    for (const cell of partCells(part, grid, extent) ?? [])
      carried.set(`${cell[0]},${cell[1]}`, held);
  }

  const plain = cells.filter((cell) => !carried.has(`${cell[0]},${cell[1]}`));
  const withValue = cells.filter((cell) => carried.has(`${cell[0]},${cell[1]}`));

  return {
    format: 'lorenzo.geometry/1',
    parts: [
      ...cellOutlines(grid, extent, plain).map((rings): Part => ({ shape: 'polygon', rings })),
      ...withValue.map(
        (cell): Part => ({
          shape: 'polygon',
          rings: [
            cellPolygon(grid, extent, cell).map((p): Point => [roundTo(p[0]), roundTo(p[1])]),
          ],
          ...carried.get(`${cell[0]},${cell[1]}`),
        }),
      ),
    ],
  };
}

/** The cells a part is: the polygon of one cell, or the outline of a patch of them (ADR 0481). */
function partCells(part: Part, grid: GridSpec, extent: BBox): Cell[] | null {
  const one = cellOfPart(part, grid, extent);

  if (one) return [one];

  return part.shape === 'polygon' ? cellsOfOutline(grid, extent, part.rings) : null;
}

/** The cell a part is exactly the polygon of (to two decimals), or null. */
function cellOfPart(part: Part, grid: GridSpec, extent: BBox): Cell | null {
  if (part.shape !== 'polygon' || part.rings.length !== 1) return null;

  const ring = part.rings[0] as readonly Point[];
  const corners = ring.length;
  const middle: Point = [
    ring.reduce((sum, p) => sum + p[0], 0) / corners,
    ring.reduce((sum, p) => sum + p[1], 0) / corners,
  ];
  const cell = cellOfPoint(grid, extent, middle);

  if (!cell) return null;

  const polygon = cellPolygon(grid, extent, cell);

  if (
    polygon.length !== corners ||
    polygon.some((p, i) => {
      const q = ring[i] as Point;

      return Math.abs(p[0] - q[0]) > 0.011 || Math.abs(p[1] - q[1]) > 0.011;
    })
  ) {
    return null;
  }

  return cell;
}

/**
 * The cells of a geometry when every part is the polygon of a cell of the grid or the outline of a
 * patch of them (to two decimals, ADR 0481), and null when any part is something else.
 */
export function cellsOf(geometry: Geometry, grid: GridSpec, extent: BBox): Cell[] | null {
  if (geometry.parts.length === 0) return null;

  const cells: Cell[] = [];

  const seen = new Set<string>();

  for (const part of geometry.parts) {
    const these = partCells(part, grid, extent);

    if (!these) return null;

    for (const cell of these) {
      const key = `${cell[0]},${cell[1]}`;

      if (!seen.has(key)) {
        seen.add(key);
        cells.push(cell);
      }
    }
  }

  return cells;
}

/** The cells with one more, or without it when it is there; unchanged beyond the limit. */
export function toggleCell(cells: readonly Cell[], cell: Cell): Cell[] {
  if (cells.some((c) => same(c, cell))) return cells.filter((c) => !same(c, cell));

  return cells.length >= MAX_CELLS_PER_PLACEMENT ? [...cells] : [...cells, cell];
}
