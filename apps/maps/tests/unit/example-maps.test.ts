import type { BBox, Cell, GridSpec } from '@lorenzo/map-renderer';
import { describe, expect, it } from 'vitest';
import { cellFill } from '../../src/lib/cell-fill';
import { cellsGeometry } from '../../src/lib/cells-edit';
import { drawnCells, heldHere, mapNamed, sameGridKind, tilesOf } from '../../src/lib/example-maps';
import { regionOf } from '../../src/lib/generator';

const extent: BBox = [0, 0, 1000, 800];
const square: GridSpec = { kind: 'square', cell: { size: 50 } };
const coarse: GridSpec = { kind: 'square', cell: { size: 100 } };
const rect: GridSpec = { kind: 'rect', cell: { width: 60, height: 40 } };
const pointy: GridSpec = { kind: 'hex', orientation: 'pointy', cell: { size: 58 } };
const flat: GridSpec = { kind: 'hex', orientation: 'flat', cell: { size: 58 } };

const row = (id: string, name: string, geometry: unknown, z = 0) => ({ id, name, geometry, z });
const cellsRow = (id: string, name: string, cells: Cell[], grid = square, z = 0) =>
  row(id, name, cellsGeometry(grid, extent, cells), z);
const pin = (id: string, name: string) =>
  row(id, name, { format: 'lorenzo.geometry/1', parts: [{ shape: 'point', at: [10, 10] }] });

describe('the grids an example may come from', () => {
  it('is one of the same kind, whatever the size of a cell', () => {
    expect(sameGridKind(square, coarse)).toBe(true);
    expect(sameGridKind(pointy, { ...pointy, cell: { size: 20 } })).toBe(true);
  });

  it('is not one of another kind, or hexes of the other orientation', () => {
    expect(sameGridKind(square, rect)).toBe(false);
    expect(sameGridKind(pointy, flat)).toBe(false);
    expect(sameGridKind(square, pointy)).toBe(false);
  });
});

describe('the entries an example draws as cells', () => {
  it('reads every placement of whole cells, drawn order last on top, and leaves the rest', () => {
    const rows = [
      cellsRow('b', 'Over', [[1, 1]], square, 5),
      pin('p', 'Well'),
      cellsRow('a', 'Under', [
        [0, 0],
        [1, 1],
      ]),
      cellsRow('c', 'Also over', [[2, 2]], square, 5),
    ];
    const drawn = drawnCells(rows, square, extent);

    expect(drawn.map(({ row }) => row.id)).toEqual(['a', 'b', 'c']);
    expect(tilesOf(drawn)).toEqual([
      {
        id: 'a',
        name: 'Under',
        cells: [
          [0, 0],
          [1, 1],
        ],
      },
      { id: 'b', name: 'Over', cells: [[1, 1]] },
      { id: 'c', name: 'Also over', cells: [[2, 2]] },
    ]);
  });

  it('reads cells by their address on the example Map, so a cell may be another size there', () => {
    const drawn = drawnCells([cellsRow('a', 'Wall', [[3, 2]], coarse)], coarse, extent);

    expect(tilesOf(drawn)[0]?.cells).toEqual([[3, 2]]);
  });
});

describe('what this Map holds of an example from another Map', () => {
  const tiles = [
    { id: 'a', name: 'Wall', cells: [[0, 0]] as Cell[] },
    { id: 'b', name: 'Floor', cells: [[1, 0]] as Cell[] },
  ];

  it('is the cells an entry has here, and none for an entry not on this Map yet', () => {
    const held = heldHere(tiles, [cellsRow('a', 'Wall', [[5, 5]])], square, extent);

    expect(held).toEqual({ ok: true, held: new Map([['a', [[5, 5]]]]) });
  });

  it('refuses an entry drawn here as something else than cells, naming it', () => {
    const held = heldHere(tiles, [pin('b', 'Floor')], square, extent);

    expect(held).toEqual({
      ok: false,
      why: 'Floor is drawn on this Map as something else than cells, and a Map holds one drawing for an entry. Take it off this Map first, or choose another example.',
    });
  });

  it('gives an entry new to this Map the cells of the fill, kept cells being none', () => {
    const stripe = (row: number): Cell[] => [0, 1, 2, 3].map((col): Cell => [col, row]);
    const example = [
      cellsRow('a', 'Wall', [...stripe(0), ...stripe(2)]),
      cellsRow('b', 'Floor', [...stripe(1), ...stripe(3)]),
    ];
    const yard = {
      name: 'Yard',
      geometry: {
        format: 'lorenzo.geometry/1',
        parts: [
          {
            shape: 'polygon' as const,
            rings: [
              [
                [500, 400],
                [800, 400],
                [800, 600],
                [500, 600],
              ] as [number, number][],
            ],
          },
        ],
      },
    };
    const tileSet = tilesOf(drawnCells(example, square, extent));
    const held = heldHere(tileSet, [], square, extent);
    if (!held.ok) throw new Error(held.why);
    const made = cellFill(square, extent, tileSet, held.held, regionOf(yard, extent), 4821);
    if (!made.ok) throw new Error(made.why);

    for (const tile of made.tiles) {
      expect(tile.cells).toEqual(tile.gained);
      expect(tile.changed).toBe(tile.gained.length > 0);
    }
  });
});

describe('a Map named on the command line', () => {
  const maps = [
    { id: 'm1', name: 'Old caves' },
    { id: 'm2', name: 'Coast' },
  ];

  it('is the Map of that name, in any case', () => {
    expect(mapNamed(maps, 'old CAVES')).toBe('m1');
    expect(mapNamed(maps, '  Coast ')).toBe('m2');
  });

  it('is this Map for THIS', () => {
    expect(mapNamed(maps, 'THIS')).toBe('');
    expect(mapNamed(maps, 'this map')).toBe('');
  });

  it('is none for a name no Map offered has', () => {
    expect(mapNamed(maps, 'Desert')).toBeNull();
    expect(mapNamed([], 'Coast')).toBeNull();
  });
});
