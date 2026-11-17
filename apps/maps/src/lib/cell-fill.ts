// What a fill by wave function collapse does to a Map (ADR 0479): the cells of the region it works
// on, the tiles of the example, and for each tile entry the cells it has afterwards, with what
// stops the result from being applied. Pure: nothing here touches the page.
import {
  type BBox,
  type Cell,
  cellAt,
  cellCentre,
  type GridSpec,
  inGrid,
} from '@lorenzo/map-renderer';
import { cellsGeometry } from './cells-edit';
import { collapse, learn } from './collapse';
import { counted, fits, type Hints, type Region } from './generator';

/** What a tile over a drawing's limits says to change (ADR 0481). */
const TILE_HINTS: Hints = {
  vertices: 'Select a smaller area first.',
  parts: 'Select a smaller area first.',
  bytes: 'Select a smaller area first.',
  shape: 'Roll another seed.',
};
/** One batch writes at most this many placements (ADR 0351). */
export const MAX_TILES = 100;
/** A region of more cells than this is not worked out: the page would stand still for it. */
export const MAX_REGION_CELLS = 10_000;
/** How many tones the preview tells tiles apart by. */
export const TONES = 6;

/** The tone of one tile among `count`: spread over the whole range while there are tones enough,
 *  so two tiles are the faintest and the strongest, and going round again beyond that. */
export function toneOf(index: number, count: number): number {
  if (count > TONES) return index % TONES;

  return Math.round((index * (TONES - 1)) / Math.max(1, count - 1));
}

/** An entry of the example and the cells it holds there, in the order they are drawn: last on top. */
export type Tile = { id: string; name: string; cells: readonly Cell[] };

export type FilledTile = {
  id: string;
  name: string;
  /** The tone the preview draws it in, 0 to five. */
  tone: number;
  /** The cells the fill gives it in the region. */
  gained: Cell[];
  /** Every cell it has on the Map afterwards: those it had outside the region, and those gained. */
  cells: Cell[];
  /** Whether its cells are other than they were. */
  changed: boolean;
};

export type CellFill =
  | { ok: true; tiles: FilledTile[]; count: string }
  | { ok: false; why: string; tiles: FilledTile[] };

const key = (cell: Cell): string => `${cell[0]},${cell[1]}`;

/**
 * The cells of a grid whose middle lies in a region, row by row; null when there are more than
 * `most`.
 */
export function regionCells(
  grid: GridSpec,
  extent: BBox,
  region: Region,
  most = MAX_REGION_CELLS,
): Cell[] | null {
  const [x0, y0, x1, y1] = region.bounds;
  const corners = [
    cellAt(grid, extent, [x0, y0]),
    cellAt(grid, extent, [x1, y0]),
    cellAt(grid, extent, [x0, y1]),
    cellAt(grid, extent, [x1, y1]),
  ];
  // A cell beyond the corners' own may still have its middle inside: one more each way.
  const c0 = Math.max(0, Math.min(...corners.map((c) => c[0])) - 1);
  const c1 = Math.max(...corners.map((c) => c[0])) + 1;
  const r0 = Math.max(0, Math.min(...corners.map((c) => c[1])) - 1);
  const r1 = Math.max(...corners.map((c) => c[1])) + 1;
  const cells: Cell[] = [];

  for (let row = r0; row <= r1; row += 1) {
    for (let col = c0; col <= c1; col += 1) {
      const cell: Cell = [col, row];

      if (!inGrid(grid, extent, cell) || !region.contains(cellCentre(grid, extent, cell))) continue;

      cells.push(cell);

      if (cells.length > most) return null;
    }
  }

  return cells;
}

/**
 * The fill of a region from an example and a seed: what each tile entry gains, and the cells it
 * has afterwards. `held` is the cells each tile entry has on the Map being filled, by its id; with
 * this Map as its own example that is the example itself.
 */
export function cellFill(
  grid: GridSpec,
  extent: BBox,
  example: readonly Tile[],
  held: ReadonlyMap<string, readonly Cell[]>,
  region: Region,
  seed: number,
): CellFill {
  const none = (why: string): CellFill => ({ ok: false, why, tiles: [] });

  if (!example.some((tile) => tile.cells.length > 0)) {
    return none(
      'There is no example yet: draw some cells with the Cells tool first, and the fill learns from them.',
    );
  }

  if (example.length > MAX_TILES) {
    return none(
      `The example has ${example.length} entries drawn as cells, and one fill writes ${MAX_TILES}.`,
    );
  }

  const cells = regionCells(grid, extent, region);

  if (!cells) {
    return none(
      `${region.kind === 'sheet' ? 'The whole sheet' : region.words} has more than ${MAX_REGION_CELLS} cells. Select a smaller area first.`,
    );
  }

  if (cells.length === 0) return none(`No cell has its middle in ${region.words}.`);

  const result = collapse(
    grid,
    cells,
    learn(
      grid,
      example.map((tile) => tile.cells),
    ),
    seed,
  );

  if (!result) return none('No tiling fits these rules here. Roll another seed.');

  const inRegion = new Set(cells.map(key));
  const tiles = example.map((tile, index): FilledTile => {
    const gained = cells.filter((_, i) => result[i] === index + 1);
    const before = held.get(tile.id) ?? [];
    const kept = before.filter((cell) => !inRegion.has(key(cell)));
    const after = [...kept, ...gained];
    const was = new Set(before.map(key));

    return {
      id: tile.id,
      name: tile.name,
      tone: toneOf(index, example.length),
      gained,
      cells: after,
      changed: after.length !== before.length || after.some((cell) => !was.has(key(cell))),
    };
  });
  // Each tile's cells are written as outlines (ADR 0481): one that would be over a drawing's
  // limits refuses the result, by name.
  for (const tile of tiles) {
    if (!tile.changed || tile.cells.length === 0) continue;

    const fit = fits(cellsGeometry(grid, extent, tile.cells), TILE_HINTS);

    if (!fit.ok) return { ok: false, why: `${tile.name}: ${fit.why}`, tiles };
  }

  const filled = tiles.reduce((sum, tile) => sum + tile.gained.length, 0);
  const used = tiles.filter((tile) => tile.gained.length > 0).length;

  return {
    ok: true,
    tiles,
    count: `${counted(filled, 'cell', 'cells')} of ${counted(used, 'tile', 'tiles')}`,
  };
}
