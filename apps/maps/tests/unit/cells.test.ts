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
    it(`is a polygon part for each of ${name}, and reads back as the same cells`, () => {
      const cells: [number, number][] = [
        [2, 3],
        [3, 3],
        [3, 4],
      ];
      const geometry = cellsGeometry(grid, extent, cells);

      expect(geometry.parts).toHaveLength(3);
      expect(geometry.parts.every((p) => p.shape === 'polygon')).toBe(true);
      expect(cellsOf(geometry, grid, extent)).toEqual(cells);
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
});
