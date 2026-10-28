import type { BBox, Point } from './types';

/**
 * Grids (ADR 0354, 0355): the cell of a square, rectangular or hex map and where a point falls. The
 * convention is written once, in `packages/map-engine/src/lorenzo_map/grid.py`, and
 * `packages/map-engine/golden/cells.json` holds both implementations to it.
 *
 * A hex cell has the `size` `w` of the distance between two opposite sides and a circumradius
 * `R = w / sqrt(3)`; a cell is `[col, row]` counted from 0 with cell `[0, 0]` at the sheet's near
 * corner; `pointy` is "odd-r" (rows) and `flat` is "odd-q" (columns). A point belongs to the nearest
 * centre, ties going to the lower row and then the lower column; on a square or rectangular grid a
 * shared edge belongs to the cell on its higher side.
 */

export type GridKind = 'square' | 'rect' | 'hex';
export type Orientation = 'flat' | 'pointy';

export type GridSpec = {
  kind: GridKind;
  cell: { size?: number; width?: number; height?: number };
  /** Hex only; a hex grid has one. */
  orientation?: Orientation;
  /** A square or rect divided `cols` by `rows`, or a hex of an `aperture` of 3, 4 or 7. */
  sub?: { cols?: number; rows?: number; aperture?: number };
};

export type Cell = readonly [number, number];

/** Two distances this close are a tie. */
export const TIE = 1e-9;
const SQRT3 = Math.sqrt(3);

export const isGridKind = (kind: unknown): kind is GridKind =>
  kind === 'square' || kind === 'rect' || kind === 'hex';

const odd = (n: number): boolean => n % 2 !== 0;

function sizes(grid: GridSpec): [number, number] {
  if (grid.kind === 'rect') return [grid.cell.width ?? 1, grid.cell.height ?? 1];

  return [grid.cell.size ?? 1, grid.cell.size ?? 1];
}

const flatToFlat = (grid: GridSpec): number => grid.cell.size ?? 1;
const radiusOf = (grid: GridSpec): number => flatToFlat(grid) / SQRT3;
const isPointy = (grid: GridSpec): boolean => grid.orientation === 'pointy';

function axialToOffset(grid: GridSpec, q: number, r: number): Cell {
  if (isPointy(grid)) return [q + (r - (odd(r) ? 1 : 0)) / 2, r];

  return [q, r + (q - (odd(q) ? 1 : 0)) / 2];
}

/** The centre of a cell. */
export function cellCentre(grid: GridSpec, extent: BBox, cell: Cell): Point {
  const [x0, y0] = extent;
  const [col, row] = cell;

  if (grid.kind !== 'hex') {
    const [w, h] = sizes(grid);

    return [x0 + (col + 0.5) * w, y0 + (row + 0.5) * h];
  }

  const w = flatToFlat(grid);
  const radius = radiusOf(grid);

  if (isPointy(grid)) {
    return [x0 + w / 2 + col * w + (odd(row) ? w / 2 : 0), y0 + radius + row * 1.5 * radius];
  }

  return [x0 + radius + col * 1.5 * radius, y0 + w / 2 + row * w + (odd(col) ? w / 2 : 0)];
}

/** The corners of a cell: clockwise on the sheet, from the near corner or the lowest angle. */
export function cellPolygon(grid: GridSpec, extent: BBox, cell: Cell): Point[] {
  const [cx, cy] = cellCentre(grid, extent, cell);

  if (grid.kind !== 'hex') {
    const [w, h] = sizes(grid);
    const x = cx - w / 2;
    const y = cy - h / 2;

    return [
      [x, y],
      [x + w, y],
      [x + w, y + h],
      [x, y + h],
    ];
  }

  return hexCorners(cx, cy, radiusOf(grid), isPointy(grid) ? -90 : 0, 0);
}

/** The six corners of a hex, the first at `start` degrees, the lattice turned by `turn` degrees. */
export function hexCorners(
  cx: number,
  cy: number,
  radius: number,
  start: number,
  turn: number,
): Point[] {
  const corners: Point[] = [];

  for (let k = 0; k < 6; k += 1) {
    const angle = ((start + 60 * k + turn) * Math.PI) / 180;

    corners.push([cx + radius * Math.cos(angle), cy + radius * Math.sin(angle)]);
  }

  return corners;
}

function cubeRound(fq: number, fr: number): [number, number] {
  const fs = -fq - fr;
  let rq = Math.round(fq);
  let rr = Math.round(fr);
  const rs = Math.round(fs);
  const dq = Math.abs(rq - fq);
  const dr = Math.abs(rr - fr);
  const ds = Math.abs(rs - fs);

  if (dq > dr && dq > ds) rq = -rr - rs;
  else if (dr > ds) rr = -rq - rs;

  return [rq, rr];
}

const NEIGHBOURS: readonly (readonly [number, number])[] = [
  [0, 0],
  [1, 0],
  [-1, 0],
  [0, 1],
  [0, -1],
  [1, -1],
  [-1, 1],
];

/** The cell a point belongs to, wherever it is; `inGrid` says whether the cell is in the grid. */
export function cellAt(grid: GridSpec, extent: BBox, point: Point): Cell {
  const [x0, y0] = extent;

  if (grid.kind !== 'hex') {
    const [w, h] = sizes(grid);

    return [Math.floor((point[0] - x0) / w), Math.floor((point[1] - y0) / h)];
  }

  const radius = radiusOf(grid);
  const [cx0, cy0] = cellCentre(grid, extent, [0, 0]);
  const dx = point[0] - cx0;
  const dy = point[1] - cy0;
  const [fq, fr] = isPointy(grid)
    ? [((SQRT3 / 3) * dx - dy / 3) / radius, ((2 / 3) * dy) / radius]
    : [((2 / 3) * dx) / radius, (-dx / 3 + (SQRT3 / 3) * dy) / radius];
  const [q, r] = cubeRound(fq, fr);
  let best: { d: number; col: number; row: number } | null = null;

  for (const [dq, dr] of NEIGHBOURS) {
    const [col, row] = axialToOffset(grid, q + dq, r + dr);
    const [ox, oy] = cellCentre(grid, extent, [col, row]);
    const d = Math.hypot(point[0] - ox, point[1] - oy);

    if (
      !best ||
      d < best.d - TIE ||
      (Math.abs(d - best.d) <= TIE && (row < best.row || (row === best.row && col < best.col)))
    ) {
      best = { d, col, row };
    }
  }

  return [best?.col ?? 0, best?.row ?? 0];
}

/** Whether a cell is in the grid: not before column or row 0, and its centre before the far edges. */
export function inGrid(grid: GridSpec, extent: BBox, cell: Cell): boolean {
  if (cell[0] < 0 || cell[1] < 0) return false;

  const [cx, cy] = cellCentre(grid, extent, cell);

  return cx < extent[2] && cy < extent[3];
}

function span(length: number, first: number, step: number): number {
  if (length <= first) return 0;

  return Math.ceil((length - first) / step - 1e-12);
}

/** How many cells are in the grid. */
export function cellCount(grid: GridSpec, extent: BBox): number {
  const width = extent[2] - extent[0];
  const height = extent[3] - extent[1];

  if (grid.kind !== 'hex') {
    const [w, h] = sizes(grid);

    return span(width, w / 2, w) * span(height, h / 2, h);
  }

  const w = flatToFlat(grid);
  const radius = radiusOf(grid);

  if (isPointy(grid)) {
    const rows = span(height, radius, 1.5 * radius);

    return (
      Math.floor((rows + 1) / 2) * span(width, w / 2, w) + Math.floor(rows / 2) * span(width, w, w)
    );
  }

  const cols = span(width, radius, 1.5 * radius);

  return (
    Math.floor((cols + 1) / 2) * span(height, w / 2, w) + Math.floor(cols / 2) * span(height, w, w)
  );
}
