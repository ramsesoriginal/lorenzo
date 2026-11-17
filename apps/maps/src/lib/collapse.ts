// Fill by wave function collapse (ADR 0478): the rules of which tile may lie beside which are
// learned from cells already drawn, and a region of cells is filled by them from a seed. A pure
// function of the example, the region and the seed (ADR 0475): no `Math.random`, no clock.
import { type Cell, type GridSpec, seeded } from '@lorenzo/map-renderer';
import { directionsOf, neighbour, opposite } from './cell-neighbours';

/** Tile 0 is nothing: a cell with no entry. The others are the entries of the example, in order. */
export const NOTHING = 0;

export type Rules = {
  /** How many tiles there are, nothing included. */
  tiles: number;
  /** How often each tile was seen in the example. */
  seen: number[];
  /** `beside[direction][a * tiles + b]` is 1 when `b` was seen beside `a` in that direction. */
  beside: Uint8Array[];
};

const key = (cell: Cell): string => `${cell[0]},${cell[1]}`;

/**
 * The rules of an example: the cells each tile holds (tile 1 the first list, and so on). A cell
 * given to several tiles is the last one's, which the caller orders so that the one drawn on top
 * is last. Nothing is tile 0, at every cell of the box around the example that no tile holds.
 */
export function learn(grid: GridSpec, example: readonly (readonly Cell[])[]): Rules {
  const tiles = example.length + 1;
  const held = new Map<string, number>();
  let low: [number, number] | null = null;
  let high: [number, number] | null = null;

  example.forEach((cells, index) => {
    for (const cell of cells) {
      held.set(key(cell), index + 1);
      low = low ? [Math.min(low[0], cell[0]), Math.min(low[1], cell[1])] : [cell[0], cell[1]];
      high = high ? [Math.max(high[0], cell[0]), Math.max(high[1], cell[1])] : [cell[0], cell[1]];
    }
  });

  const directions = directionsOf(grid);
  const rules: Rules = {
    tiles,
    seen: new Array<number>(tiles).fill(0),
    beside: Array.from({ length: directions }, () => new Uint8Array(tiles * tiles)),
  };

  if (!low || !high) return rules;

  const [c0, r0] = low as [number, number];
  const [c1, r1] = high as [number, number];
  const inBox = (cell: Cell) => cell[0] >= c0 && cell[0] <= c1 && cell[1] >= r0 && cell[1] <= r1;
  const tileAt = (cell: Cell): number => held.get(key(cell)) ?? NOTHING;

  for (let row = r0; row <= r1; row += 1) {
    for (let col = c0; col <= c1; col += 1) {
      const here = tileAt([col, row]);

      rules.seen[here] = (rules.seen[here] as number) + 1;

      for (let direction = 0; direction < directions; direction += 1) {
        const beside = neighbour(grid, [col, row], direction);

        if (inBox(beside)) {
          (rules.beside[direction] as Uint8Array)[here * tiles + tileAt(beside)] = 1;
        }
      }
    }
  }

  return rules;
}

/** How many times the whole is begun again when a cell is left with no tile. */
export const TRIES = 10;

/**
 * A tile for every cell of a region, obeying the rules between the cells of the region; null when
 * ten draws all left some cell with no tile. Cells outside the region are not looked at.
 */
export function collapse(
  grid: GridSpec,
  region: readonly Cell[],
  rules: Rules,
  seed: number,
): number[] | null {
  const { tiles } = rules;
  const directions = directionsOf(grid);
  const count = region.length;
  const index = new Map<string, number>();

  for (const [i, cell] of region.entries()) index.set(key(cell), i);

  // The cell beside each cell in each direction, or -1 when it is not of the region.
  const next = new Int32Array(count * directions).fill(-1);

  region.forEach((cell, i) => {
    for (let direction = 0; direction < directions; direction += 1) {
      next[i * directions + direction] = index.get(key(neighbour(grid, cell, direction))) ?? -1;
    }
  });

  const usable = rules.seen.map((times) => times > 0);

  if (count === 0 || !usable.some(Boolean)) return count === 0 ? [] : null;

  for (let attempt = 0; attempt < TRIES; attempt += 1) {
    const draw = seeded(`collapse:${seed}:${attempt}`);
    // may[cell * tiles + tile] is 1 while the cell may still be that tile.
    const may = new Uint8Array(count * tiles);
    const left = new Int32Array(count);

    for (let i = 0; i < count; i += 1) {
      for (let tile = 0; tile < tiles; tile += 1) {
        if (usable[tile]) {
          may[i * tiles + tile] = 1;
          left[i] = (left[i] as number) + 1;
        }
      }
    }

    const narrow = (from: number): boolean => {
      const queue = [from];

      for (let at = 0; at < queue.length; at += 1) {
        const cell = queue[at] as number;

        for (let direction = 0; direction < directions; direction += 1) {
          const other = next[cell * directions + direction] as number;

          if (other < 0) continue;

          const allowed = rules.beside[direction] as Uint8Array;
          let changed = false;

          for (let b = 0; b < tiles; b += 1) {
            if (!may[other * tiles + b]) continue;

            let held = false;

            for (let a = 0; a < tiles && !held; a += 1) {
              held = may[cell * tiles + a] === 1 && allowed[a * tiles + b] === 1;
            }

            if (!held) {
              may[other * tiles + b] = 0;
              left[other] = (left[other] as number) - 1;
              changed = true;
            }
          }

          if (left[other] === 0) return false;
          if (changed) queue.push(other);
        }
      }

      return true;
    };

    let fits = true;

    while (fits) {
      // The cell with the fewest tiles left, the first in order among equals.
      let pick = -1;

      for (let i = 0; i < count; i += 1) {
        const options = left[i] as number;

        if (options > 1 && (pick < 0 || options < (left[pick] as number))) pick = i;
      }

      if (pick < 0) break;

      // One of its tiles, in proportion to how often each was seen.
      let total = 0;

      for (let tile = 0; tile < tiles; tile += 1) {
        if (may[pick * tiles + tile]) total += rules.seen[tile] as number;
      }

      let at = draw() * total;
      let chosen = -1;

      for (let tile = 0; tile < tiles; tile += 1) {
        if (!may[pick * tiles + tile]) continue;

        chosen = tile;
        at -= rules.seen[tile] as number;

        if (at < 0) break;
      }

      for (let tile = 0; tile < tiles; tile += 1)
        may[pick * tiles + tile] = tile === chosen ? 1 : 0;

      left[pick] = 1;
      fits = narrow(pick);
    }

    if (!fits) continue;

    const result: number[] = [];

    for (let i = 0; i < count; i += 1) {
      for (let tile = 0; tile < tiles; tile += 1) {
        if (may[i * tiles + tile]) {
          result.push(tile);
          break;
        }
      }
    }

    return result;
  }

  return null;
}

/** Whether a result obeys the rules between every two cells of the region that lie side by side. */
export function obeys(
  grid: GridSpec,
  region: readonly Cell[],
  rules: Rules,
  result: readonly number[],
): boolean {
  const index = new Map<string, number>();

  for (const [i, cell] of region.entries()) index.set(key(cell), i);

  return region.every((cell, i) => {
    for (let direction = 0; direction < directionsOf(grid); direction += 1) {
      const other = index.get(key(neighbour(grid, cell, direction)));

      if (other === undefined) continue;

      const a = result[i] as number;
      const b = result[other] as number;

      if (!(rules.beside[direction] as Uint8Array)[a * rules.tiles + b]) return false;
      // Seen one way, it was seen the other: the opposite direction holds the mirror.
      if (!(rules.beside[opposite(direction)] as Uint8Array)[b * rules.tiles + a]) return false;
    }

    return true;
  });
}
