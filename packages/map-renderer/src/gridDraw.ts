import { num } from './geom';
import {
  type Cell,
  cellAt,
  cellCentre,
  cellPolygon,
  type GridSpec,
  hexCorners,
  inGrid,
  isGridKind,
  type Orientation,
} from './grid';
import { extentOf, type Transform, toScreen } from './project';
import type { PathPrim, Prim } from './scene';
import { isSphere } from './sphere';
import { graticulePrims } from './sphereDraw';
import type { BBox, MapModel, Point } from './types';

/** Cells whose shortest side is under this many screen pixels are not drawn (ADR 0355). */
export const MIN_CELL_PX = 6;
/** A sub-grid whose cells are under this many pixels is not drawn. */
export const MIN_SUB_PX = 8;
/** At most this many cells are drawn at once. */
export const MAX_DRAWN_CELLS = 6000;

export type GridState = 'none' | 'drawn' | 'too_fine';

const SQRT3 = Math.sqrt(3);
const APERTURE_TURN = (Math.atan(SQRT3 / 5) * 180) / Math.PI;

/** The grid of a Map: a grid system's own, or its view's visual grid; none otherwise. */
export function gridOf(model: MapModel): GridSpec | null {
  const system = model.system as unknown as GridSpec;

  if (isGridKind(system.kind)) return system;

  return model.overlay && isGridKind(model.overlay.kind) ? model.overlay : null;
}

type Bounds = { x0: number; y0: number; x1: number; y1: number };

/** The drawing units on the screen, limited to the sheet. */
function visible(t: Transform, extent: BBox): Bounds {
  const hw = t.width / 2 / t.scale;
  const hh = t.height / 2 / t.scale;

  return {
    x0: Math.max(extent[0], t.centre[0] - hw),
    y0: Math.max(extent[1], t.centre[1] - hh),
    x1: Math.min(extent[2], t.centre[0] + hw),
    y1: Math.min(extent[3], t.centre[1] + hh),
  };
}

function pathPrim(id: string, cls: string, d: string, box: Bounds, t: Transform): PathPrim {
  const a = toScreen(t, [box.x0, box.y0]);
  const b = toScreen(t, [box.x1, box.y1]);

  return {
    id,
    kind: 'path',
    cls,
    d,
    strokeWidth: 1,
    bbox: [num(a[0]), num(a[1]), num(b[0]), num(b[1])],
  };
}

const at = (t: Transform, p: Point): string => {
  const s = toScreen(t, p);

  return `${num(s[0])} ${num(s[1])}`;
};

/** Lines every `step` from `origin` across `box`, in one direction, as path data. */
function lines(
  t: Transform,
  box: Bounds,
  origin: number,
  step: number,
  vertical: boolean,
  skipEvery = 0,
): string {
  const low = vertical ? box.x0 : box.y0;
  const high = vertical ? box.x1 : box.y1;
  let d = '';

  for (let i = Math.ceil((low - origin) / step - 1e-9); origin + i * step <= high + 1e-9; i += 1) {
    if (skipEvery > 0 && i % skipEvery === 0) continue;

    const v = origin + i * step;

    d += vertical
      ? `${d ? ' ' : ''}M ${at(t, [v, box.y0])} L ${at(t, [v, box.y1])}`
      : `${d ? ' ' : ''}M ${at(t, [box.x0, v])} L ${at(t, [box.x1, v])}`;
  }

  return d;
}

function rectGrid(grid: GridSpec, extent: BBox, t: Transform, box: Bounds): [Prim[], GridState] {
  const w = grid.kind === 'rect' ? (grid.cell.width ?? 1) : (grid.cell.size ?? 1);
  const h = grid.kind === 'rect' ? (grid.cell.height ?? 1) : (grid.cell.size ?? 1);

  if (Math.min(w, h) * t.scale < MIN_CELL_PX) return [[], 'too_fine'];

  const columns = (box.x1 - box.x0) / w;
  const rows = (box.y1 - box.y0) / h;

  if (columns * rows > MAX_DRAWN_CELLS) return [[], 'too_fine'];

  const prims: Prim[] = [
    pathPrim(
      'grid',
      'm-grid',
      `${lines(t, box, extent[0], w, true)} ${lines(t, box, extent[1], h, false)}`.trim(),
      box,
      t,
    ),
  ];
  const cols = grid.sub?.cols ?? 1;
  const subRows = grid.sub?.rows ?? 1;
  const sw = w / cols;
  const sh = h / subRows;

  if ((cols > 1 || subRows > 1) && Math.min(sw, sh) * t.scale >= MIN_SUB_PX) {
    const d = [
      cols > 1 ? lines(t, box, extent[0], sw, true, cols) : '',
      subRows > 1 ? lines(t, box, extent[1], sh, false, subRows) : '',
    ]
      .filter(Boolean)
      .join(' ');

    if (d) prims.push(pathPrim('grid-sub', 'm-grid-sub', d, box, t));
  }

  return [prims, 'drawn'];
}

/** The cells of a hex grid that overlap `box`, a cell of margin around it. */
function hexCellsIn(grid: GridSpec, extent: BBox, box: Bounds): Cell[] {
  const size = grid.cell.size ?? 1;
  const reach = size;
  const corners: Point[] = [
    [box.x0 - reach, box.y0 - reach],
    [box.x1 + reach, box.y0 - reach],
    [box.x0 - reach, box.y1 + reach],
    [box.x1 + reach, box.y1 + reach],
  ];
  const cells = corners.map((p) => cellAt(grid, extent, p));
  const cols = cells.map((c) => c[0]);
  const rows = cells.map((c) => c[1]);
  const found: Cell[] = [];

  for (let row = Math.min(...rows) - 1; row <= Math.max(...rows) + 1; row += 1) {
    for (let col = Math.min(...cols) - 1; col <= Math.max(...cols) + 1; col += 1) {
      if (inGrid(grid, extent, [col, row])) found.push([col, row]);
      if (found.length > MAX_DRAWN_CELLS) return found;
    }
  }

  return found;
}

const pointyToFlat = (o: GridSpec['orientation']): Orientation =>
  o === 'pointy' ? 'flat' : 'pointy';

/** The lattice a hex cell is divided into, drawn for the eye (ADR 0355). */
function apertureLattice(grid: GridSpec) {
  const size = grid.cell.size ?? 1;
  const aperture = grid.sub?.aperture;
  const orientation: Orientation = grid.orientation ?? 'flat';

  if (aperture === 3) {
    return { size: size / SQRT3, orientation: pointyToFlat(grid.orientation), turn: 0 };
  }

  if (aperture === 7) {
    return { size: size / Math.sqrt(7), orientation, turn: APERTURE_TURN };
  }

  if (aperture === 4) return { size: size / 2, orientation, turn: 0 };

  return null;
}

function hexSub(grid: GridSpec, extent: BBox, t: Transform, box: Bounds): Prim | null {
  const lattice = apertureLattice(grid);

  if (!lattice || lattice.size * t.scale < MIN_SUB_PX) return null;

  const anchor = cellCentre(grid, extent, [0, 0]);
  const w = lattice.size;
  const radius = w / SQRT3;
  const pointy = lattice.orientation === 'pointy';
  const rad = (lattice.turn * Math.PI) / 180;
  const cos = Math.cos(rad);
  const sin = Math.sin(rad);
  // The lattice's own cell (0, 0) is centred on the anchor, then turned and placed.
  const sub: GridSpec = { kind: 'hex', orientation: lattice.orientation, cell: { size: w } };
  const home: BBox = pointy ? [-w / 2, -radius, 0, 0] : [-radius, -w / 2, 0, 0];
  const toLattice = (p: Point): Point => {
    const dx = p[0] - anchor[0];
    const dy = p[1] - anchor[1];

    return [dx * cos + dy * sin, -dx * sin + dy * cos];
  };
  const toDrawing = (p: Point): Point => [
    anchor[0] + p[0] * cos - p[1] * sin,
    anchor[1] + p[0] * sin + p[1] * cos,
  ];
  const corners = [
    [box.x0, box.y0],
    [box.x1, box.y0],
    [box.x0, box.y1],
    [box.x1, box.y1],
  ].map((p) => cellAt(sub, home, toLattice([p[0] as number, p[1] as number])));
  const cols = corners.map((c) => c[0]);
  const rows = corners.map((c) => c[1]);
  let count = 0;
  let d = '';

  for (let row = Math.min(...rows) - 2; row <= Math.max(...rows) + 2; row += 1) {
    for (let col = Math.min(...cols) - 2; col <= Math.max(...cols) + 2; col += 1) {
      const centre = toDrawing(cellCentre(sub, home, [col, row]));

      if (centre[0] < extent[0] || centre[0] >= extent[2]) continue;

      if (centre[1] < extent[1] || centre[1] >= extent[3]) continue;

      count += 1;

      if (count > MAX_DRAWN_CELLS) return null;

      const ring = hexCorners(
        ...cellCentre(sub, home, [col, row]),
        radius,
        pointy ? -90 : 0,
        0,
      ).map((p) => at(t, toDrawing(p)));

      d += `${d ? ' ' : ''}M ${ring.join(' L ')} Z`;
    }
  }

  return d ? pathPrim('grid-sub', 'm-grid-sub', d, box, t) : null;
}

function hexGrid(grid: GridSpec, extent: BBox, t: Transform, box: Bounds): [Prim[], GridState] {
  if ((grid.cell.size ?? 1) * t.scale < MIN_CELL_PX) return [[], 'too_fine'];

  const cells = hexCellsIn(grid, extent, box);

  if (cells.length > MAX_DRAWN_CELLS) return [[], 'too_fine'];

  const d = cells
    .map(
      (cell) =>
        `M ${cellPolygon(grid, extent, cell)
          .map((p) => at(t, p))
          .join(' L ')} Z`,
    )
    .join(' ');
  const prims: Prim[] = d ? [pathPrim('grid', 'm-grid', d, box, t)] : [];
  const sub = hexSub(grid, extent, t, box);

  if (sub) prims.push(sub);

  return [prims, 'drawn'];
}

/** The primitives of a Map's grid for a view, and whether it could be drawn. */
export function gridPrims(model: MapModel, t: Transform): { prims: Prim[]; state: GridState } {
  // A sphere's grid is its lines of longitude and latitude (ADR 0358).
  if (isSphere(model.system)) return { prims: graticulePrims(model, t), state: 'drawn' };

  const grid = gridOf(model);

  if (!grid) return { prims: [], state: 'none' };

  const extent = extentOf(model.system);
  const box = visible(t, extent);

  if (!(box.x1 > box.x0) || !(box.y1 > box.y0)) return { prims: [], state: 'drawn' };

  const [prims, state] =
    grid.kind === 'hex' ? hexGrid(grid, extent, t, box) : rectGrid(grid, extent, t, box);

  return { prims, state };
}
