// The cells beside a cell (ADR 0354, ADR 0479): four on squares and rectangles, six on hexes, in a
// fixed order of directions, so that "the cell to the east" means the same from any cell. A hex
// grid's rows or columns are staggered, so which address lies in a direction depends on whether
// the cell's row (pointed-top) or column (flat-topped) is odd. Pure.
import type { Cell, GridSpec } from '@lorenzo/map-renderer';

/** How many directions a cell has a neighbour in. */
export const directionsOf = (grid: GridSpec): number => (grid.kind === 'hex' ? 6 : 4);

/** The direction that looks back along `direction`: directions come in pairs, 0 and 1, 2 and 3... */
export const opposite = (direction: number): number =>
  direction % 2 === 0 ? direction + 1 : direction - 1;

// Each pair of rows is a direction and its opposite.
const SQUARE: readonly Cell[] = [
  [1, 0],
  [-1, 0],
  [0, 1],
  [0, -1],
];

// Pointed-top hexes sit in rows ("odd-r"): an odd row is half a cell further along.
const POINTY_EVEN: readonly Cell[] = [
  [1, 0],
  [-1, 0],
  [0, 1],
  [-1, -1],
  [-1, 1],
  [0, -1],
];
const POINTY_ODD: readonly Cell[] = [
  [1, 0],
  [-1, 0],
  [1, 1],
  [0, -1],
  [0, 1],
  [1, -1],
];

// Flat-topped hexes sit in columns ("odd-q"): an odd column is half a cell further down.
const FLAT_EVEN: readonly Cell[] = [
  [0, 1],
  [0, -1],
  [1, 0],
  [-1, -1],
  [1, -1],
  [-1, 0],
];
const FLAT_ODD: readonly Cell[] = [
  [0, 1],
  [0, -1],
  [1, 1],
  [-1, 0],
  [1, 0],
  [-1, 1],
];

const odd = (n: number): boolean => ((n % 2) + 2) % 2 === 1;

/** The cell beside `cell` in a direction, whether or not the grid has such a cell. */
export function neighbour(grid: GridSpec, cell: Cell, direction: number): Cell {
  const steps =
    grid.kind !== 'hex'
      ? SQUARE
      : grid.orientation === 'flat'
        ? odd(cell[0])
          ? FLAT_ODD
          : FLAT_EVEN
        : odd(cell[1])
          ? POINTY_ODD
          : POINTY_EVEN;
  const step = steps[direction] as Cell;

  return [cell[0] + step[0], cell[1] + step[1]];
}
