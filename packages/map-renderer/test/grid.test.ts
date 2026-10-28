import { readFileSync } from 'node:fs';
import { describe, expect, it } from 'vitest';
import {
  type BBox,
  type Cell,
  cellAt,
  cellCentre,
  cellCount,
  cellPolygon,
  DEFAULT_GROUPS,
  type GridSpec,
  gridOf,
  gridPrims,
  inGrid,
  layout,
  MAX_DRAWN_CELLS,
  type MapModel,
  type PathPrim,
  type Point,
} from '../src';
import { transformOf } from '../src/project';
import { model, view } from './fixtures';

type Golden = {
  grids: {
    name: string;
    grid: GridSpec;
    extent: BBox;
    count: number;
    points: { point: Point; cell: Cell }[];
    cells: { cell: Cell; centre: Point; polygon: Point[] }[];
  }[];
};

const golden = JSON.parse(
  readFileSync(new URL('../../map-engine/golden/cells.json', import.meta.url), 'utf8'),
) as Golden;

const near = (a: readonly number[], b: readonly number[], eps = 1e-6) =>
  a.length === b.length && a.every((v, i) => Math.abs(v - (b[i] as number)) < eps);

describe('the cell functions agree with the golden file the engine also reads', () => {
  for (const item of golden.grids) {
    it(item.name, () => {
      expect(cellCount(item.grid, item.extent)).toBe(item.count);

      for (const { point, cell } of item.points) {
        expect(cellAt(item.grid, item.extent, point), JSON.stringify(point)).toEqual(cell);
      }

      for (const { cell, centre, polygon } of item.cells) {
        expect(near(cellCentre(item.grid, item.extent, cell), centre)).toBe(true);
        const corners = cellPolygon(item.grid, item.extent, cell);

        expect(corners).toHaveLength(polygon.length);
        expect(corners.every((p, i) => near(p, polygon[i] as Point))).toBe(true);
      }
    });

    it(`${item.name}: a cell contains its centre, and the count is the cells in the grid`, () => {
      let inside = 0;

      for (let row = -3; row < 80; row += 1) {
        for (let col = -3; col < 80; col += 1) {
          const centre = cellCentre(item.grid, item.extent, [col, row]);

          expect(cellAt(item.grid, item.extent, centre)).toEqual([col, row]);
          if (inGrid(item.grid, item.extent, [col, row])) inside += 1;
        }
      }

      if (item.count < 6000) expect(inside).toBe(item.count);
    });
  }

  it('breaks a tie to the lower row and then the lower column', () => {
    const pointy: GridSpec = { kind: 'hex', orientation: 'pointy', cell: { size: 2 } };
    const flat: GridSpec = { kind: 'hex', orientation: 'flat', cell: { size: 2 } };
    const r = 2 / Math.sqrt(3);
    const extent: BBox = [0, 0, 100, 100];

    expect(cellAt(pointy, extent, [2, r])).toEqual([0, 0]);
    expect(cellAt(flat, extent, [r, 2])).toEqual([0, 0]);
    expect(cellAt({ kind: 'square', cell: { size: 10 } }, extent, [10, 5])).toEqual([1, 0]);
  });
});

const sheet = (system: Record<string, unknown>, overlay?: GridSpec): MapModel => ({
  system: { kind: 'plane', extent: [0, 0, 1000, 800], ...system } as MapModel['system'],
  placements: [],
  ...(overlay ? { overlay } : {}),
});

const grid = (m: MapModel, groups = DEFAULT_GROUPS) =>
  layout(m, view({ groups, centre: [500, 400] })).prims.filter((p): p is PathPrim =>
    p.id.startsWith('grid'),
  );

describe('the grid in a Scene', () => {
  it('is under every placement and takes no pointer, name or entry', () => {
    const scene = layout(
      { ...model, system: { ...model.system, kind: 'square', cell: { size: 50 } } },
      view(),
    );
    const first = scene.prims.findIndex((p) => p.entryId);
    const drawn = scene.prims.filter((p) => p.id.startsWith('grid'));

    expect(drawn.map((p) => p.id)).toEqual(['grid']);
    expect(scene.prims.indexOf(drawn[0] as never)).toBeLessThan(first);
    expect(drawn.every((p) => !p.entryId && !p.hit && !p.label)).toBe(true);
    expect(drawn[0]?.cls).toBe('m-grid');
  });

  it('draws the lines of a square and a rectangular grid, and a sub-grid between them', () => {
    const square = grid(sheet({ kind: 'square', cell: { size: 100 } }));
    const verticals = (square[0]?.d.match(/M/g) ?? []).length;

    // 1000 wide and 800 high: 11 + 9 lines at the cell edges.
    expect(verticals).toBe(20);
    const sub = grid(sheet({ kind: 'square', cell: { size: 100 }, sub: { cols: 2, rows: 4 } }));

    expect(sub.map((p) => p.id)).toEqual(['grid', 'grid-sub']);
    expect(sub[1]?.cls).toBe('m-grid-sub');
    // Between the cell edges only: 10 (cols) - 10 edges... one extra line per cell column and three per row.
    expect((sub[1]?.d.match(/M/g) ?? []).length).toBe(10 + 8 * 3 - 0);
    const rect = grid(sheet({ kind: 'rect', cell: { width: 250, height: 200 } }));

    expect((rect[0]?.d.match(/M/g) ?? []).length).toBe(5 + 5);
  });

  it('draws the cells of a hex grid, one outline each, and a sub-grid for each aperture', () => {
    const hex = sheet({ kind: 'hex', orientation: 'pointy', cell: { size: 100 } });
    const prims = grid(hex);
    const cells = (prims[0]?.d.match(/Z/g) ?? []).length;

    expect(cells).toBeGreaterThan(50);
    expect(cells).toBeLessThanOrEqual(
      cellCount(hex.system as unknown as GridSpec, [0, 0, 1000, 800]),
    );
    for (const aperture of [3, 4, 7]) {
      const withSub = grid(sheet({ ...hex.system, sub: { aperture } }));

      expect(
        withSub.map((p) => p.id),
        String(aperture),
      ).toEqual(['grid', 'grid-sub']);
      expect((withSub[1]?.d.match(/Z/g) ?? []).length).toBeGreaterThan(cells);
    }
  });

  it('gives any system a view grid, and a grid system its own only', () => {
    const over: GridSpec = { kind: 'hex', orientation: 'flat', cell: { size: 80 } };

    expect(grid(sheet({}, over)).map((p) => p.id)).toEqual(['grid']);
    expect(grid(sheet({ kind: 'outline' }, over))).toHaveLength(1);
    expect(grid(sheet({}))).toEqual([]);
    expect(gridOf(sheet({ kind: 'square', cell: { size: 10 } }, over))?.kind).toBe('square');
    expect(gridOf(sheet({}, over))?.kind).toBe('hex');
    expect(gridOf(sheet({}))).toBeNull();
  });

  it('is hidden by the switch, and too fine to draw below the level of detail', () => {
    const fine = sheet({ kind: 'square', cell: { size: 100 } });

    expect(grid(fine, { ...DEFAULT_GROUPS, grid: false })).toEqual([]);
    const tiny = sheet({ kind: 'square', cell: { size: 1 } });
    const t = transformOf(tiny.system, view({ centre: [500, 400] }));

    expect(gridPrims(tiny, t).state).toBe('too_fine');
    expect(grid(tiny)).toEqual([]);
    const dense = sheet({ kind: 'hex', orientation: 'flat', cell: { size: 8 } });

    expect(
      gridPrims(dense, transformOf(dense.system, view({ zoom: 8, centre: [500, 400] }))).state,
    ).toBe('drawn');
    expect(MAX_DRAWN_CELLS).toBe(6000);
    expect(gridPrims(fine, transformOf(fine.system, view({ centre: [500, 400] }))).state).toBe(
      'drawn',
    );
    expect(
      gridPrims(sheet({}), transformOf(sheet({}).system, view({ centre: [500, 400] }))).state,
    ).toBe('none');
  });

  it('changes nothing for a Map without a grid', () => {
    const before = JSON.stringify(layout(model, view()));

    expect(before).not.toContain('m-grid');
  });
});
