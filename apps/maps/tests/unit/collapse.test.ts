import { readFileSync } from 'node:fs';
import { type BBox, type Cell, cellCentre, type GridSpec } from '@lorenzo/map-renderer';
import { describe, expect, it } from 'vitest';
import {
  cellFill,
  MAX_REGION_CELLS,
  MAX_TILE_CELLS,
  regionCells,
  type Tile,
  TONES,
} from '../../src/lib/cell-fill';
import { directionsOf, neighbour, opposite } from '../../src/lib/cell-neighbours';
import { collapse, learn, NOTHING, obeys, TRIES } from '../../src/lib/collapse';
import { regionOf } from '../../src/lib/generator';

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

describe('the cells beside a cell (ADR 0354, ADR 0479)', () => {
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

describe('learning the rules from an example (ADR 0479)', () => {
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

describe('filling a region by the rules (ADR 0479)', () => {
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

describe('what a fill does to a Map (ADR 0479)', () => {
  const FORMAT = 'lorenzo.geometry/1';
  const whole = regionOf(null, [0, 0, 1000, 800]);
  const yard = regionOf(
    {
      name: 'The yard',
      geometry: {
        format: FORMAT,
        parts: [
          {
            shape: 'polygon',
            rings: [
              [
                [500, 400],
                [800, 400],
                [800, 600],
                [500, 600],
              ],
            ],
          },
        ],
      },
    },
    [0, 0, 1000, 800],
  );
  // Two entries in patches, on a grid of 20 by 16 squares.
  const wall: Tile = {
    id: 'wall',
    name: 'Wall',
    cells: [...block(0, 0, 3, 1), ...block(0, 4, 3, 5)],
  };
  const floor: Tile = { id: 'floor', name: 'Floor', cells: block(0, 2, 3, 3) };
  const held = new Map([
    ['wall', wall.cells],
    ['floor', floor.cells],
  ]);

  it('takes the cells whose middle lies in the region, row by row', () => {
    expect(regionCells(square, extent, whole)).toHaveLength(20 * 16);
    expect(regionCells(square, extent, whole)?.slice(0, 3)).toEqual([
      [0, 0],
      [1, 0],
      [2, 0],
    ]);
    // 300 by 200 units of 50-unit cells: six by four, from column 10 and row 8.
    const inYard = regionCells(square, extent, yard) as Cell[];

    expect(inYard).toHaveLength(24);
    expect(inYard[0]).toEqual([10, 8]);
    expect(inYard[23]).toEqual([15, 11]);
    // Hexes too: every cell found has its middle in the region.
    for (const cell of regionCells(pointy, extent, yard) as Cell[]) {
      expect(yard.contains(cellCentre(pointy, extent, cell))).toBe(true);
    }
    expect(regionCells(square, extent, whole, 100)).toBeNull();
    expect(MAX_REGION_CELLS).toBe(10_000);
  });

  it('gives each tile the cells it gains, and keeps what it had outside the region', () => {
    const fill = cellFill(square, extent, [wall, floor], held, yard, 4821);

    if (!fill.ok) throw new Error(fill.why);

    const [walls, floors] = fill.tiles as [
      (typeof fill.tiles)[number],
      (typeof fill.tiles)[number],
    ];

    expect(fill.count).toMatch(/^\d+ cells of [12] tiles?$/);
    expect(walls.gained.length + floors.gained.length).toBeLessThanOrEqual(24);
    // What lay outside the region is all still there, before what was gained.
    expect(walls.cells.slice(0, wall.cells.length)).toEqual(wall.cells);
    expect(walls.cells).toHaveLength(wall.cells.length + walls.gained.length);
    expect(floors.cells).toHaveLength(floor.cells.length + floors.gained.length);
    expect(walls.tone).toBe(0);
    expect(floors.tone).toBe(TONES - 1);
    expect(walls.changed).toBe(walls.gained.length > 0);
    for (const cell of [...walls.gained, ...floors.gained]) {
      expect(cell[0] >= 10 && cell[0] <= 15 && cell[1] >= 8 && cell[1] <= 11).toBe(true);
    }
  });

  it('replaces what a tile had inside the region: over its own example, the example goes', () => {
    // The region is the whole sheet, so every cell of the example is inside it.
    const small = regionOf(null, [0, 0, 200, 300]);
    const fill = cellFill(square, extent, [wall, floor], held, small, 7);

    if (!fill.ok) throw new Error(fill.why);

    for (const tile of fill.tiles) {
      // Nothing is kept from before: only what the fill gave.
      expect(tile.cells).toEqual(tile.gained);
    }
    expect(fill.tiles.reduce((sum, tile) => sum + tile.gained.length, 0)).toBeLessThanOrEqual(24);
  });

  it('refuses a tile that would hold more than a drawing does, naming it', () => {
    // One tile and nothing else in the example: the whole sheet of 320 cells would all be it.
    const all: Tile = { id: 'sea', name: 'The sea', cells: block(0, 0, 3, 3) };
    const fill = cellFill(square, extent, [all], new Map([['sea', all.cells]]), whole, 1);

    expect(fill.ok).toBe(false);
    if (fill.ok) return;
    expect(fill.why).toBe(
      'The sea would hold 320 cells, and a drawing holds 256. Select a smaller area first.',
    );
    expect(fill.tiles[0]?.gained).toHaveLength(320);
    expect(MAX_TILE_CELLS).toBe(256);
  });

  it('says what is missing: no example, a region too large, or no tiling', () => {
    expect(cellFill(square, extent, [], new Map(), whole, 1)).toMatchObject({
      ok: false,
      why: 'There is no example yet: draw some cells with the Cells tool first, and the fill learns from them.',
    });

    const fine: GridSpec = { kind: 'square', cell: { size: 5 } };

    expect(cellFill(fine, extent, [wall], held, whole, 1)).toMatchObject({
      ok: false,
      why: 'The whole sheet has more than 10000 cells. Select a smaller area first.',
    });
    // One tile only ever seen with the other to its east, in a strip two wide.
    const strip: Tile[] = [
      { id: 'a', name: 'A', cells: [[0, 0]] },
      { id: 'b', name: 'B', cells: [[1, 0]] },
    ];

    expect(cellFill(square, extent, strip, new Map(), whole, 1)).toMatchObject({
      ok: false,
      why: 'No tiling fits these rules here. Roll another seed.',
    });
  });
});

interface GoldenCase {
  name: string;
  grid: GridSpec;
  example: Tile[];
  region:
    | { kind: 'sheet' }
    | { kind: 'area'; ring: [number, number][] }
    | { kind: 'circle'; at: [number, number]; r: number };
  seed: number;
  ok: boolean;
  count?: string;
  why?: string;
  tiles: { id: string; tone: number; gained: Cell[]; cells: Cell[]; changed: boolean }[];
}

const golden = JSON.parse(
  readFileSync(
    new URL('../../../../packages/map-engine/golden/collapse.json', import.meta.url),
    'utf8',
  ),
) as { extent: BBox; cases: GoldenCase[] };

describe('the golden vectors', () => {
  it.each(golden.cases.map((item) => [item.name, item] as const))('%s', (_name, item) => {
    const FORMAT = 'lorenzo.geometry/1';
    const selected =
      item.region.kind === 'area'
        ? {
            name: 'It',
            geometry: {
              format: FORMAT,
              parts: [{ shape: 'polygon' as const, rings: [item.region.ring] }],
            },
          }
        : item.region.kind === 'circle'
          ? {
              name: 'It',
              geometry: {
                format: FORMAT,
                parts: [{ shape: 'circle' as const, at: item.region.at, r: item.region.r }],
              },
            }
          : null;
    const made = cellFill(
      item.grid,
      golden.extent,
      item.example,
      new Map(item.example.map((tile) => [tile.id, tile.cells])),
      regionOf(selected, golden.extent),
      item.seed,
    );

    expect(made.ok).toBe(item.ok);
    if (made.ok) expect(made.count).toBe(item.count);
    else expect(made.why).toBe(item.why);
    expect(
      made.tiles.map((tile) => ({
        id: tile.id,
        tone: tile.tone,
        gained: tile.gained,
        cells: tile.cells,
        changed: tile.changed,
      })),
    ).toEqual(item.tiles);
  });
});
