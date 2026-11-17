// The example of a fill of cells (ADR 0479): the entries drawn as whole cells on a Map, this one or
// another of the library with a grid of the same kind, and what this Map already holds of them.

import type { BBox, Cell, Geometry, GridSpec } from '@lorenzo/map-renderer';
import type { Tile } from './cell-fill';
import { cellsOf } from './cells-edit';

/** A placement as the example reads it: what it is, how it is drawn, and in what order. */
export type ExampleRow = {
  id: string;
  name: string;
  geometry: unknown;
  z: number;
};

/** A Map of the library that may be the example: its id and its name. */
export type ExampleMap = { id: string; name: string };

/** Two grids of the same kind: squares, rectangles, or hexes of the same orientation. */
export function sameGridKind(a: GridSpec, b: GridSpec): boolean {
  return a.kind === b.kind && (a.kind !== 'hex' || a.orientation === b.orientation);
}

/**
 * The entries drawn as whole cells on a Map, in the order they are drawn: the higher drawing order
 * last, then the later id, so the entry on top is last and wins a cell two of them hold.
 */
export function drawnCells<R extends ExampleRow>(
  rows: readonly R[],
  grid: GridSpec,
  extent: BBox,
): { row: R; cells: Cell[] }[] {
  return rows
    .flatMap((row) => {
      const cells = cellsOf(row.geometry as Geometry, grid, extent);
      return cells ? [{ row, cells }] : [];
    })
    .sort((a, b) => a.row.z - b.row.z || (a.row.id < b.row.id ? -1 : a.row.id > b.row.id ? 1 : 0));
}

/** The tiles of an example: each entry drawn as cells, with its name and its cells. */
export const tilesOf = (drawn: readonly { row: ExampleRow; cells: Cell[] }[]): Tile[] =>
  drawn.map(({ row, cells }) => ({ id: row.id, name: row.name, cells }));

/**
 * What this Map holds of the tiles of an example: each tile's cells here, none for an entry that
 * is not on this Map yet. An entry drawn here as something else than cells refuses the fill, by
 * name: a Map holds one drawing for an entry, and the fill does not take that drawing away.
 */
export function heldHere(
  tiles: readonly Tile[],
  rows: readonly ExampleRow[],
  grid: GridSpec,
  extent: BBox,
): { ok: true; held: Map<string, Cell[]> } | { ok: false; why: string } {
  const held = new Map<string, Cell[]>();
  for (const tile of tiles) {
    const row = rows.find((one) => one.id === tile.id);
    if (!row) continue;
    const cells = cellsOf(row.geometry as Geometry, grid, extent);
    if (!cells) {
      return {
        ok: false,
        why: `${row.name} is drawn on this Map as something else than cells, and a Map holds one drawing for an entry. Take it off this Map first, or choose another example.`,
      };
    }
    held.set(tile.id, cells);
  }

  return { ok: true, held };
}

/** The words that name this Map as the example on the command line. */
const THIS_MAP = ['this', 'this map', 'here'];

/**
 * The Map a name typed on the command line means among those offered: '' for this Map, the id of
 * the one whose name it is (any case), or null when none is.
 */
export function mapNamed(maps: readonly ExampleMap[], typed: string): string | null {
  const words = typed.trim().toLowerCase();
  if (THIS_MAP.includes(words)) return '';
  const found = maps.find((map) => map.name.toLowerCase() === words);

  return found ? found.id : null;
}
