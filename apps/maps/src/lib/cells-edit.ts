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

/** A placement has at most 256 parts (ADR 0337), so a region of cells has at most 256 cells. */
export const MAX_CELLS_PER_PLACEMENT = 256;

/** What a cell is called to a person: counted from 1, where the API and the files count from 0. */
export const cellWords = (cell: Cell): string => `Column ${cell[0] + 1}, row ${cell[1] + 1}`;

const same = (a: Cell, b: Cell) => a[0] === b[0] && a[1] === b[1];

const roundTo = (n: number) => Math.round(n * 100) / 100;

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

/** The geometry of a region of whole cells: one polygon part for each. */
export function cellsGeometry(grid: GridSpec, extent: BBox, cells: readonly Cell[]): Geometry {
  return {
    format: 'lorenzo.geometry/1',
    parts: cells.map(
      (cell): Part => ({
        shape: 'polygon',
        rings: [cellPolygon(grid, extent, cell).map((p): Point => [roundTo(p[0]), roundTo(p[1])])],
      }),
    ),
  };
}

/**
 * The cells of a geometry when every part is exactly the polygon of a cell of the grid (to two
 * decimals), and null when any part is something else.
 */
export function cellsOf(geometry: Geometry, grid: GridSpec, extent: BBox): Cell[] | null {
  if (geometry.parts.length === 0) return null;

  const cells: Cell[] = [];

  for (const part of geometry.parts) {
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

    if (!cells.some((c) => same(c, cell))) cells.push(cell);
  }

  return cells;
}

/** The cells with one more, or without it when it is there; unchanged beyond the limit. */
export function toggleCell(cells: readonly Cell[], cell: Cell): Cell[] {
  if (cells.some((c) => same(c, cell))) return cells.filter((c) => !same(c, cell));

  return cells.length >= MAX_CELLS_PER_PLACEMENT ? [...cells] : [...cells, cell];
}
