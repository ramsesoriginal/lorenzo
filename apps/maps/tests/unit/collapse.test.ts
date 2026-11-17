import { type BBox, type Cell, cellCentre, type GridSpec } from '@lorenzo/map-renderer';
import { describe, expect, it } from 'vitest';
import { directionsOf, neighbour, opposite } from '../../src/lib/cell-neighbours';
import { collapse, learn, NOTHING, obeys, TRIES } from '../../src/lib/collapse';

const extent: BBox = [0, 0, 1000, 800];
const square: GridSpec = { kind: 'square', cell: { size: 50 } };
const rect: GridSpec = { kind: 'rect', cell: { width: 60, height: 40 } };
const pointy: GridSpec = { kind: 'hex', orientation: 'pointy', cell: { size: 58 } };
const flat: GridSpec = { kind: 'hex', orientation: 'flat', cell: { size: 58 } };
const grids: [string, GridSpec][] = [
  ['squares', square],
  ['rectangles', rect],
  ['pointed-top hexes', pointy],
  ['flat-topped hexes', flat],
];

const block = (c0: number, r0: number, c1: number, r1: number): Cell[] => {
  const cells: Cell[] = [];

  for (let row = r0; row <= r1; row += 1) {
    for (let col = c0; col <= c1; col += 1) cells.push([col, row]);
  }

  return cells;
};

describe('the cells beside a cell (ADR 0354, ADR 0478)', () => {
  for (const [name, grid] of grids) {
    it(`on ${name}: each a cell away, all different, and each way matched by its opposite`, () => {
      const directions = directionsOf(grid);

      expect(directions).toBe(grid.kind === 'hex' ? 6 : 4);

      // Cells of even and odd rows and columns: the stagger of a hex grid shows in both.
      for (const cell of block(3, 3, 6, 6)) {
        const here = cellCentre(grid, extent, cell);
        const beside = Array.from({ length: directions }, (_, d) => neighbour(grid, cell, d));
        const away = beside.map((other) => {
          const there = cellCentre(grid, extent, other);

          return Math.hypot(there[0] - here[0], there[1] - here[1]);
        });

        expect(new Set(beside.map((c) => c.join(','))).size).toBe(directions);

        if (grid.kind === 'hex') {
          // Adjacent centres are the cell's size apart (ADR 0354).
          for (const d of away) expect(d).toBeCloseTo(58, 6);
        } else if (grid.kind === 'square') {
          for (const d of away) expect(d).toBeCloseTo(50, 9);
        } else {
          expect(away.map((d) => Math.round(d))).toEqual([60, 60, 40, 40]);
        }

        for (let d = 0; d < directions; d += 1) {
          expect(neighbour(grid, neighbour(grid, cell, d), opposite(d))).toEqual(cell);
        }
      }
    });

    it(`on ${name}: a direction points the same way from every cell`, () => {
      for (let d = 0; d < directionsOf(grid); d += 1) {
        const ways = block(2, 2, 5, 5).map((cell) => {
          const here = cellCentre(grid, extent, cell);
          const there = cellCentre(grid, extent, neighbour(grid, cell, d));

          return [Math.round(there[0] - here[0]), Math.round(there[1] - here[1])].join(',');
        });

        expect(new Set(ways).size).toBe(1);
      }
    });
  }
});

describe('learning the rules from an example (ADR 0478)', () => {
  it('counts each tile, nothing included, inside the box around the example', () => {
    // A row of wall over a row of floor, three wide, with one cell of the floor's row left empty.
    const wall = block(0, 0, 2, 0);
    const floor: Cell[] = [
      [0, 1],
      [1, 1],
    ];
    const rules = learn(square, [wall, floor]);

    expect(rules.tiles).toBe(3);
    expect(rules.seen).toEqual([1, 3, 2]);
    // Directions on squares: 0 east, 1 west, 2 south, 3 north.
    const beside = (d: number, a: number, b: number) =>
      (rules.beside[d] as Uint8Array)[a * rules.tiles + b];

    expect(beside(0, 1, 1)).toBe(1);
    expect(beside(2, 1, 2)).toBe(1);
    expect(beside(3, 2, 1)).toBe(1);
    expect(beside(2, 1, NOTHING)).toBe(1);
    expect(beside(0, 2, NOTHING)).toBe(1);
    expect(beside(1, NOTHING, 2)).toBe(1);
    // Never seen: floor over wall, or wall beside nothing in its own row.
    expect(beside(2, 2, 1)).toBe(0);
    expect(beside(0, 1, NOTHING)).toBe(0);
    expect(beside(0, 2, 1)).toBe(0);
  });

  it('gives a cell two tiles hold to the later one, and learns nothing from no example', () => {
    const under = block(0, 0, 1, 0);
    const over: Cell[] = [[1, 0]];
    const rules = learn(square, [under, over]);

    expect(rules.seen).toEqual([0, 1, 1]);
    expect(learn(square, []).seen).toEqual([0]);
    expect(learn(square, [[]]).seen).toEqual([0, 0]);
  });
});

describe('filling a region by the rules (ADR 0478)', () => {
  // Stripes: a row of one tile, then a row of the other, three rows of each, four wide.
  const stripes = [
    [...block(0, 0, 3, 0), ...block(0, 2, 3, 2), ...block(0, 4, 3, 4)],
    [...block(0, 1, 3, 1), ...block(0, 3, 3, 3), ...block(0, 5, 3, 5)],
  ];

  it('repeats what the example can only be: stripes stay stripes', () => {
    const rules = learn(square, stripes);
    const region = block(10, 10, 15, 14);
    const result = collapse(square, region, rules, 4821) as number[];

    expect(result).toHaveLength(region.length);
    expect(obeys(square, region, rules, result)).toBe(true);
    // Every row is one tile, and rows alternate.
    for (let row = 0; row < 5; row += 1) {
      const tiles = new Set(result.slice(row * 6, row * 6 + 6));

      expect(tiles.size).toBe(1);
      if (row > 0) expect(result[row * 6]).not.toBe(result[(row - 1) * 6]);
    }
    expect(result.includes(NOTHING)).toBe(false);
  });

  for (const [name, grid] of grids) {
    it(`obeys every learned rule on ${name}, across seeds`, () => {
      // Three tiles in patches and gaps: loose rules, many ways to fill.
      const example = [
        [...block(0, 0, 2, 2), ...block(6, 5, 8, 7)],
        [...block(3, 0, 5, 3), ...block(0, 5, 2, 7)],
        [...block(6, 0, 8, 2), ...block(3, 5, 5, 7)],
      ];
      const rules = learn(grid, example);
      const region = block(1, 1, 12, 10);
      let filled = 0;

      for (let seed = 0; seed < 40; seed += 1) {
        const result = collapse(grid, region, rules, seed);

        if (!result) continue;

        filled += 1;
        expect(result).toHaveLength(region.length);
        expect(obeys(grid, region, rules, result)).toBe(true);
        expect(result.every((tile) => tile >= 0 && tile < rules.tiles)).toBe(true);
      }

      expect(filled).toBeGreaterThan(30);
    });
  }

  it('is a function of its seed: the same twice, and another for another seed', () => {
    // Patches and gaps: loose rules, so the seed has a say.
    const rules = learn(square, [
      [...block(0, 0, 2, 2), ...block(6, 5, 8, 7)],
      [...block(3, 0, 5, 3), ...block(0, 5, 2, 7)],
      [...block(6, 0, 8, 2), ...block(3, 5, 5, 7)],
    ]);
    const region = block(0, 0, 9, 9);
    const once = collapse(square, region, rules, 7);

    expect(collapse(square, region, rules, 7)).toEqual(once);
    expect(collapse(square, region, rules, 8)).not.toEqual(once);
  });

  it('draws tiles as often as they were seen, more or less', () => {
    // A wide field of one tile with a small patch of another in its middle: the second stays
    // rare. (A patch at the box's own edge would never have been seen with anything beyond it.)
    const patch = block(4, 4, 5, 5);
    const field = block(0, 0, 9, 9).filter(([c, r]) => c < 4 || c > 5 || r < 4 || r > 5);
    const rules = learn(square, [field, patch]);
    let rare = 0;
    let all = 0;

    for (let seed = 0; seed < 20; seed += 1) {
      const result = collapse(square, block(0, 0, 19, 19), rules, seed) ?? [];

      rare += result.filter((tile) => tile === 2).length;
      all += result.length;
    }

    expect(all).toBeGreaterThan(0);
    expect(rare).toBeGreaterThan(0);
    expect(rare).toBeLessThan(all / 4);
  });

  it('says so when no tiling fits, after ten draws', () => {
    // One tile only ever seen with the other to its east, in a strip two wide: a region three
    // wide has no way to be filled.
    const rules = learn(square, [[[0, 0]], [[1, 0]]]);

    expect(TRIES).toBe(10);
    expect(collapse(square, block(0, 0, 1, 0), rules, 1)).toEqual([1, 2]);
    expect(collapse(square, block(0, 0, 2, 0), rules, 1)).toBeNull();
    // With no example there is no tile to give, and with no region nothing to fill.
    expect(collapse(square, block(0, 0, 2, 0), learn(square, []), 1)).toBeNull();
    expect(collapse(square, [], rules, 1)).toEqual([]);
  });

  it('looks at no cell outside the region: two cells apart are free of each other', () => {
    const rules = learn(square, [[[0, 0]], [[1, 0]]]);
    const apart: Cell[] = [
      [0, 0],
      [5, 5],
    ];

    for (let seed = 0; seed < 10; seed += 1) {
      expect(collapse(square, apart, rules, seed)).not.toBeNull();
    }
  });
});
