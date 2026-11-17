import type { BBox, Geometry, GridSpec } from '@lorenzo/map-renderer';
import { describe, expect, it } from 'vitest';
import { cellsGeometry, cellsOf } from '../../src/lib/cells-edit';
import { moved, movePoint, transformed } from '../../src/lib/transform';

const FORMAT = 'lorenzo.geometry/1';
const sheet: BBox = [0, 0, 1000, 800];
const every: Geometry = {
  format: FORMAT,
  parts: [
    { shape: 'point', at: [100, 50] },
    { shape: 'circle', at: [200, 100], r: 30, value: 12, unit: 'ft' },
    {
      shape: 'polyline',
      pts: [
        [0, 0],
        [300, 200],
      ],
      value: 100,
      unit: 'm',
    },
    {
      shape: 'bezier',
      start: [10, 10],
      segs: [
        [
          [20, 30],
          [40, 30],
          [50, 10],
        ],
      ],
    },
    {
      shape: 'polygon',
      rings: [
        [
          [100, 100],
          [200, 100],
          [200, 200],
        ],
      ],
    },
  ],
};

describe('mirror and turn about the sheet (ADR 0490)', () => {
  it('moves a point left to right, top to bottom, or both', () => {
    expect(movePoint('across', sheet, [100, 50])).toEqual([900, 50]);
    expect(movePoint('down', sheet, [100, 50])).toEqual([100, 750]);
    expect(movePoint('turn', sheet, [100, 50])).toEqual([900, 750]);
    // A sheet that does not start at 0.
    expect(movePoint('turn', [-500, 100, 500, 900], [-400, 200])).toEqual([400, 800]);
  });

  it('moves every shape point by point and keeps what a part carries', () => {
    const across = transformed('across', sheet, every);

    expect(across.parts).toEqual([
      { shape: 'point', at: [900, 50] },
      { shape: 'circle', at: [800, 100], r: 30, value: 12, unit: 'ft' },
      {
        shape: 'polyline',
        pts: [
          [1000, 0],
          [700, 200],
        ],
        value: 100,
        unit: 'm',
      },
      {
        shape: 'bezier',
        start: [990, 10],
        segs: [
          [
            [980, 30],
            [960, 30],
            [950, 10],
          ],
        ],
      },
      {
        shape: 'polygon',
        rings: [
          [
            [900, 100],
            [800, 100],
            [800, 200],
          ],
        ],
      },
    ]);
  });

  it('gives back the original when done twice', () => {
    for (const how of ['across', 'down', 'turn'] as const) {
      expect(transformed(how, sheet, transformed(how, sheet, every))).toEqual(every);
    }
  });

  it('keeps two decimals two decimals, without the noise of arithmetic', () => {
    expect(movePoint('across', [0, 0, 1000.1, 800], [0.2, 0])).toEqual([999.9, 0]);
  });
});

describe('a drawing of cells, mirrored or turned (ADR 0490)', () => {
  const square: GridSpec = { kind: 'square', cell: { size: 50 } };
  const pointy: GridSpec = { kind: 'hex', orientation: 'pointy', cell: { size: 58 } };
  const cells: [number, number][] = [
    [0, 0],
    [1, 0],
    [1, 1],
    [4, 3],
  ];

  it('stays cells where it lands on whole cells, and they are the cells it lands on', () => {
    const drawing = cellsGeometry(square, sheet, cells);
    const result = moved('turn', sheet, drawing, square);
    if (!result.ok) throw new Error(result.why);
    const landed = (cellsOf(result.geometry, square, sheet) ?? []).map((c) => c.join(',')).sort();

    // 20 columns and 16 rows: column c goes to 19 - c, row r to 15 - r.
    expect(landed).toEqual(['15,12', '18,14', '18,15', '19,15']);
  });

  it('is refused where it would not land on cells, and says why', () => {
    const narrow: BBox = [0, 0, 1010, 800];
    expect(moved('across', narrow, cellsGeometry(square, narrow, cells), square)).toEqual({
      ok: false,
      why: 'Mirrored across, its cells would not land on whole cells of this grid. Nothing was changed.',
    });
    expect(moved('down', sheet, cellsGeometry(pointy, sheet, cells), pointy)).toEqual({
      ok: false,
      why: 'Mirrored down, its cells would not land on whole cells of this grid. Nothing was changed.',
    });
  });

  it('moves a drawing that is no cells on a grid as any drawing', () => {
    expect(moved('down', sheet, every, square)).toMatchObject({ ok: true });
  });
});
