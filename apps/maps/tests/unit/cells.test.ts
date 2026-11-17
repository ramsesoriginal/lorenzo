import { readFileSync } from 'node:fs';
import type { BBox, Geometry, GridSpec } from '@lorenzo/map-renderer';
import { describe, expect, it } from 'vitest';
import {
  cellOfPoint,
  cellsGeometry,
  cellsOf,
  cellWords,
  MAX_CELLS_PER_PLACEMENT,
  snapCentre,
  snapCorner,
  toggleCell,
} from '../../src/lib/cells-edit';
import { checkGeometry } from '../../src/lib/validate';

const extent: BBox = [0, 0, 1000, 800];
const square: GridSpec = { kind: 'square', cell: { size: 50 } };
const rect: GridSpec = { kind: 'rect', cell: { width: 60, height: 40 } };
const pointy: GridSpec = { kind: 'hex', orientation: 'pointy', cell: { size: 58 } };
const flat: GridSpec = { kind: 'hex', orientation: 'flat', cell: { size: 58 } };

describe('cells', () => {
  it('are named from 1 for a person', () => {
    expect(cellWords([0, 0])).toBe('Column 1, row 1');
    expect(cellWords([3, 5])).toBe('Column 4, row 6');
  });

  it('are found for a point, and none outside the grid', () => {
    expect(cellOfPoint(square, extent, [125, 75])).toEqual([2, 1]);
    expect(cellOfPoint(square, extent, [-5, 10])).toBeNull();
    expect(cellOfPoint(square, extent, [1100, 10])).toBeNull();
    expect(cellOfPoint(pointy, extent, [29, 20])).toEqual([0, 0]);
  });

  it('snap a point to the centre or the nearest corner of its cell', () => {
    expect(snapCentre(square, extent, [118, 71])).toEqual([125, 75]);
    expect(snapCorner(square, extent, [118, 71])).toEqual([100, 50]);
    expect(snapCorner(square, extent, [140, 93])).toEqual([150, 100]);
    expect(snapCentre(rect, extent, [70, 50])).toEqual([90, 60]);
    // A hex corner is a circumradius from the centre.
    const centre = snapCentre(pointy, extent, [40, 40]);
    const corner = snapCorner(pointy, extent, [40, 40]);

    expect(Math.hypot(corner[0] - centre[0], corner[1] - centre[1])).toBeCloseTo(
      58 / Math.sqrt(3),
      1,
    );
    // Outside the grid nothing moves.
    expect(snapCentre(square, extent, [-20, -20])).toEqual([-20, -20]);
    expect(snapCorner(square, extent, [2000, 3000])).toEqual([2000, 3000]);
  });
});

describe('a region of whole cells', () => {
  for (const [name, grid] of [
    ['squares', square],
    ['rectangles', rect],
    ['pointy hexes', pointy],
    ['flat hexes', flat],
  ] as const) {
    it(`is one outline for a patch of ${name}, and reads back as the same cells (ADR 0481)`, () => {
      const cells: [number, number][] = [
        [2, 3],
        [3, 3],
        [3, 4],
      ];
      const geometry = cellsGeometry(grid, extent, cells);

      expect(geometry.parts).toHaveLength(1);
      expect(geometry.parts[0]?.shape).toBe('polygon');
      expect(sorted(cellsOf(geometry, grid, extent))).toEqual(sorted(cells));
    });
  }

  it('is not read as cells when a part is something else', () => {
    const cells = cellsGeometry(square, extent, [[1, 1]]);
    const moved = JSON.parse(JSON.stringify(cells)) as Geometry;
    const part = moved.parts[0];

    if (part?.shape === 'polygon') (part.rings[0] as unknown as number[][])[1] = [101, 50];

    expect(cellsOf(moved, square, extent)).toBeNull();
    expect(
      cellsOf({ format: 'x', parts: [{ shape: 'point', at: [1, 1] }] }, square, extent),
    ).toBeNull();
    expect(cellsOf({ format: 'x', parts: [] }, square, extent)).toBeNull();
    // A square on a grid of another size is no cell.
    expect(
      cellsOf(
        cellsGeometry(square, extent, [[1, 1]]),
        { kind: 'square', cell: { size: 40 } },
        extent,
      ),
    ).toBeNull();
  });

  it('keeps each cell once, adds and takes away by toggling, and stops at the limit', () => {
    const geometry = cellsGeometry(square, extent, [
      [1, 1],
      [1, 1],
    ]);

    expect(cellsOf(geometry, square, extent)).toEqual([[1, 1]]);
    expect(toggleCell([[1, 1]], [2, 2])).toEqual([
      [1, 1],
      [2, 2],
    ]);
    expect(
      toggleCell(
        [
          [1, 1],
          [2, 2],
        ],
        [1, 1],
      ),
    ).toEqual([[2, 2]]);
    const full = Array.from({ length: MAX_CELLS_PER_PLACEMENT }, (_, i): [number, number] => [
      i,
      0,
    ]);

    expect(toggleCell(full, [0, 1])).toHaveLength(MAX_CELLS_PER_PLACEMENT);
    expect(toggleCell(full, [0, 0])).toHaveLength(MAX_CELLS_PER_PLACEMENT - 1);
  });

  it('keeps the value a cell already had when the region changes (ADR 0337)', () => {
    const drawn = cellsGeometry(square, extent, [[0, 0]]);
    const was: Geometry = {
      format: drawn.format,
      parts: [
        { ...drawn.parts[0], value: 30, unit: 'ft' } as Geometry['parts'][number],
        ...cellsGeometry(square, extent, [[1, 0]]).parts,
      ],
    };
    const next = cellsGeometry(
      square,
      extent,
      [
        [0, 0],
        [1, 0],
        [2, 0],
      ],
      was,
    );

    // The cells with no value are one outline; the cell with a value is a part of its own.
    expect(next.parts).toHaveLength(2);
    expect(next.parts[0]).not.toHaveProperty('value');
    expect(next.parts[1]).toMatchObject({ value: 30, unit: 'ft' });
    expect(cellsOf(next, square, extent)).toHaveLength(3);
  });

  it('gives a value on an outline to each of its cells, each then a part of its own', () => {
    const drawn = cellsGeometry(square, extent, [
      [0, 0],
      [1, 0],
    ]);
    const was: Geometry = {
      format: drawn.format,
      parts: [{ ...drawn.parts[0], value: 5, unit: 'm' } as Geometry['parts'][number]],
    };
    const next = cellsGeometry(
      square,
      extent,
      [
        [0, 0],
        [1, 0],
        [5, 5],
      ],
      was,
    );

    expect(next.parts.filter((p) => p.value === 5)).toHaveLength(2);
    expect(sorted(cellsOf(next, square, extent))).toEqual(
      sorted([
        [0, 0],
        [1, 0],
        [5, 5],
      ]),
    );
  });
});

const sorted = (cells: readonly (readonly [number, number])[] | null) =>
  (cells ?? []).map((c) => `${c[0]},${c[1]}`).sort();

describe('cells as outlines (ADR 0481)', () => {
  const block = (c0: number, r0: number, c1: number, r1: number) => {
    const cells: [number, number][] = [];
    for (let r = r0; r <= r1; r += 1) for (let c = c0; c <= c1; c += 1) cells.push([c, r]);
    return cells;
  };

  it('writes a block of squares as four corners, straight runs joined', () => {
    const geometry = cellsGeometry(square, extent, block(2, 2, 11, 7));
    const part = geometry.parts[0];

    expect(geometry.parts).toHaveLength(1);
    expect(part?.shape === 'polygon' && part.rings).toEqual([
      expect.arrayContaining([
        [100, 100],
        [600, 100],
        [600, 400],
        [100, 400],
      ]),
    ]);
    expect(part?.shape === 'polygon' && part.rings[0]).toHaveLength(4);
  });

  it('writes a ring of cells as an outline with a hole, and reads it back', () => {
    const cells = block(0, 0, 4, 4).filter(([c, r]) => !(c >= 1 && c <= 3 && r >= 1 && r <= 3));

    for (const grid of [square, rect]) {
      const geometry = cellsGeometry(grid, extent, cells);
      const part = geometry.parts[0];

      expect(geometry.parts).toHaveLength(1);
      expect(part?.shape === 'polygon' && part.rings).toHaveLength(2);
      expect(sorted(cellsOf(geometry, grid, extent))).toEqual(sorted(cells));
    }
  });

  it('writes patches that share no edge as outlines of their own', () => {
    const cells: [number, number][] = [...block(0, 0, 1, 1), ...block(5, 5, 6, 6), [9, 0]];
    const geometry = cellsGeometry(square, extent, cells);

    expect(geometry.parts).toHaveLength(3);
    expect(sorted(cellsOf(geometry, square, extent))).toEqual(sorted(cells));
  });

  it('writes a patch whose outline would meet itself at a corner as its cells', () => {
    // Two cells in a corner of a ring: the hole touches the outline where two cells meet only at a corner.
    const cells: [number, number][] = [
      [0, 0],
      [1, 0],
      [2, 0],
      [0, 1],
      [2, 1],
      [0, 2],
      [1, 2],
      [3, 2],
      [3, 3],
    ];
    const geometry = cellsGeometry(square, extent, cells);

    expect(sorted(cellsOf(geometry, square, extent))).toEqual(sorted(cells));
  });

  it('reads a drawing written one part a cell, as before, as its cells', () => {
    const oldStyle: Geometry = {
      format: 'lorenzo.geometry/1',
      parts: block(0, 0, 2, 0).flatMap((cell) => cellsGeometry(square, extent, [cell]).parts),
    };

    expect(oldStyle.parts).toHaveLength(3);
    expect(sorted(cellsOf(oldStyle, square, extent))).toEqual(sorted(block(0, 0, 2, 0)));
  });

  it('does not read a polygon that is not exactly an outline of cells', () => {
    const near: Geometry = {
      format: 'lorenzo.geometry/1',
      parts: [
        {
          shape: 'polygon',
          rings: [
            [
              [0, 0],
              [100, 0],
              [100, 100],
              [0, 101],
            ],
          ],
        },
      ],
    };
    const inside: Geometry = {
      format: 'lorenzo.geometry/1',
      parts: [
        {
          shape: 'polygon',
          rings: [
            [
              [10, 10],
              [140, 10],
              [140, 90],
              [10, 90],
            ],
          ],
        },
      ],
    };

    expect(cellsOf(near, square, extent)).toBeNull();
    expect(cellsOf(inside, square, extent)).toBeNull();
  });

  for (const [name, grid] of [
    ['squares', square],
    ['rectangles', rect],
    ['pointy hexes', pointy],
    ['flat hexes', flat],
  ] as const) {
    it(`round-trips random regions of ${name}`, () => {
      let seed = 7;
      const next = () => {
        seed = (seed * 1103515245 + 12345) % 2147483648;
        return seed / 2147483648;
      };

      for (let run = 0; run < 40; run += 1) {
        const cells = block(0, 0, 11, 9).filter(() => next() < 0.55);
        const geometry = cellsGeometry(grid, extent, cells);

        expect(sorted(cellsOf(geometry, grid, extent))).toEqual(sorted(cells));
        expect(geometry.parts.length).toBeLessThanOrEqual(cells.length);
        // What is written is what the API takes: no outline crosses or touches itself.
        expect(checkGeometry(geometry)).toMatchObject({ ok: true });
      }
    });
  }
});

const golden = JSON.parse(
  readFileSync(
    new URL('../../../../packages/map-engine/golden/cell-outlines.json', import.meta.url),
    'utf8',
  ),
) as {
  extent: BBox;
  cases: { name: string; grid: GridSpec; cells: [number, number][]; geometry: Geometry }[];
};

describe('the golden outlines of cells (ADR 0481)', () => {
  it('has a case for each kind of grid', () => {
    expect(golden.cases.length).toBeGreaterThanOrEqual(20);
  });

  for (const item of golden.cases) {
    it(item.name, () => {
      expect(cellsGeometry(item.grid, golden.extent, item.cells)).toEqual(item.geometry);
      expect(sorted(cellsOf(item.geometry, item.grid, golden.extent))).toEqual(sorted(item.cells));
    });
  }
});
