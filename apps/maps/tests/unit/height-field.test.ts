import type { Geometry } from '@lorenzo/map-renderer';
import { describe, expect, it } from 'vitest';
import {
  BRUSH_COLS,
  brushField,
  DOME,
  type EntryLine,
  entryLines,
  heightsNow,
  MAX_LEVELS,
  redraw,
  redrawWords,
  stepOf,
  strokeOf,
  withStroke,
} from '../../src/lib/height-field';

type Pt = readonly [number, number];
const FORMAT = 'lorenzo.geometry/1';
const extent = [0, 0, 1000, 800] as const;
const cell = 1000 / BRUSH_COLS;

/** A ring of `n` points round a middle, closed on its first point, as a height line is drawn. */
const ring = (cx: number, cy: number, r: number, n = 48): Pt[] => {
  const pts: Pt[] = [];
  for (let k = 0; k <= n; k += 1) {
    const a = (2 * Math.PI * (k % n)) / n;
    pts.push([
      Math.round((cx + r * Math.cos(a)) * 100) / 100,
      Math.round((cy + r * Math.sin(a)) * 100) / 100,
    ]);
  }
  return pts;
};
const line = (part: number, value: number, pts: Pt[]): EntryLine => ({ part, value, pts });
const at = (field: ReturnType<typeof brushField>, values: Float64Array, [x, y]: Pt) =>
  values[
    Math.floor((y - field.y0) / field.cell) * field.cols + Math.floor((x - field.x0) / field.cell)
  ] as number;
const zero = (field: ReturnType<typeof brushField>) => new Float64Array(field.cols * field.rows);

describe('the lines of an entry', () => {
  const lines = (parts: unknown[]): Geometry => ({ format: FORMAT, parts }) as unknown as Geometry;

  it('are none for an entry not on this Map', () => {
    expect(entryLines('Hills', null)).toEqual({ ok: true, lines: [], unit: null });
  });

  it('are its height lines by part, a curve read as it is drawn, and their one unit', () => {
    const read = entryLines(
      'Hills',
      lines([
        {
          shape: 'polyline',
          pts: [
            [0, 0],
            [10, 0],
          ],
          value: 100,
          unit: 'm',
        },
        {
          shape: 'bezier',
          start: [0, 10],
          segs: [
            [
              [3, 20],
              [7, 20],
              [10, 10],
            ],
          ],
          value: 200,
          unit: 'm',
        },
      ]),
    );
    if (!read.ok) throw new Error(read.why);
    expect(read.unit).toBe('m');
    expect(read.lines.map((one) => [one.part, one.value])).toEqual([
      [0, 100],
      [1, 200],
    ]);
    expect(read.lines[1]?.pts.length).toBeGreaterThan(2);
    expect(read.lines[1]?.pts.at(-1)).toEqual([10, 10]);
  });

  it('refuses an entry drawn as something else, or in two units, by name', () => {
    expect(
      entryLines(
        'Lake',
        lines([
          {
            shape: 'polygon',
            rings: [
              [
                [0, 0],
                [10, 0],
                [10, 10],
              ],
            ],
          },
        ]),
      ),
    ).toEqual({
      ok: false,
      why: 'Lake is drawn on this Map as something else than height lines, and the brush changes height lines only.',
    });
    expect(
      entryLines(
        'Hills',
        lines([
          {
            shape: 'polyline',
            pts: [
              [0, 0],
              [10, 0],
            ],
            value: 100,
            unit: 'm',
          },
          {
            shape: 'polyline',
            pts: [
              [0, 5],
              [10, 5],
            ],
            value: 300,
            unit: 'ft',
          },
        ]),
      ),
    ).toEqual({
      ok: false,
      why: 'Hills has lines in more than one unit (m, ft), and the brush works in one.',
    });
  });

  it('have as their step the smallest gap between two heights, and none with one height', () => {
    expect(stepOf([line(0, 100, []), line(1, 300, []), line(2, 350, []), line(3, 300, [])])).toBe(
      50,
    );
    expect(stepOf([line(0, 100, []), line(1, 100, [])])).toBeNull();
    expect(stepOf([])).toBeNull();
  });
});

describe('the field of the lines', () => {
  it('holds each line at its height, and is smooth between them', () => {
    const lines = [line(0, 100, ring(500, 400, 300)), line(1, 200, ring(500, 400, 150))];
    const field = brushField(extent, lines, 0);
    const values = heightsNow(field, zero(field), 100);

    expect(at(field, values, [800, 400])).toBeCloseTo(100, 0);
    expect(at(field, values, [650, 400])).toBeCloseTo(200, 0);
    const between = at(field, values, [725, 400]);
    expect(between).toBeGreaterThan(110);
    expect(between).toBeLessThan(190);
  });

  it('rises beyond the top line of a hill, and stays flat out to the sheet edge beyond the lowest', () => {
    const lines = [line(0, 100, ring(500, 400, 300)), line(1, 200, ring(500, 400, 150))];
    const field = brushField(extent, lines, 0);
    const values = heightsNow(field, zero(field), 100);

    expect(at(field, values, [500, 400])).toBeGreaterThan(200);
    expect(at(field, values, [500, 400])).toBeLessThanOrEqual(200 + DOME * 100 + 1e-6);
    expect(at(field, values, [20, 20])).toBeCloseTo(100, 3);
  });

  it('falls beyond the bottom line of a hollow', () => {
    const lines = [line(0, 200, ring(500, 400, 300)), line(1, 100, ring(500, 400, 150))];
    const field = brushField(extent, lines, 0);
    const values = heightsNow(field, zero(field), 100);

    expect(at(field, values, [500, 400])).toBeLessThan(100);
  });

  it('rises inside a line with nothing beside it', () => {
    const field = brushField(extent, [line(0, 50, ring(500, 400, 200))], 0);
    const values = heightsNow(field, zero(field), 10);

    expect(at(field, values, [500, 400])).toBeGreaterThan(50);
    expect(at(field, values, [20, 20])).toBeCloseTo(50, 6);
  });

  it('is flat at the first height with no line', () => {
    const field = brushField(extent, [], 30);
    const values = heightsNow(field, zero(field), 10);

    expect(new Set(values)).toEqual(new Set([30]));
    expect(field.cols).toBe(BRUSH_COLS);
    expect(field.rows).toBe(Math.ceil(800 / cell));
  });
});

describe('a stroke', () => {
  const field = brushField(extent, [], 0);

  it('moves the field most at its points and not at all from the radius on', () => {
    const stroke = strokeOf(field, [[500, 400]], 100);
    const values = heightsNow(field, withStroke(zero(field), stroke, 2), 10);

    expect(at(field, values, [500, 400])).toBeCloseTo(20, 0);
    expect(at(field, values, [560, 400])).toBeGreaterThan(0);
    expect(at(field, values, [560, 400])).toBeLessThan(20);
    expect(at(field, values, [620, 400])).toBe(0);
  });

  it('moves a place once however often it passes, and again with a new stroke', () => {
    const once = strokeOf(field, [[500, 400]], 100);
    const twice = strokeOf(
      field,
      [
        [500, 400],
        [500, 400],
        [505, 400],
      ],
      100,
    );
    expect(at(field, twice, [500, 400])).toBeCloseTo(at(field, once, [500, 400]), 1);
    expect(Math.max(...twice)).toBeLessThanOrEqual(1);

    const raised = withStroke(withStroke(zero(field), once, 1), once, 1);
    expect(Math.max(...raised)).toBeCloseTo(2 * Math.max(...once), 9);
  });

  it('lowers with a negative amount', () => {
    const values = heightsNow(
      field,
      withStroke(zero(field), strokeOf(field, [[500, 400]], 100), -1),
      10,
    );
    expect(at(field, values, [500, 400])).toBeLessThan(0);
  });
});

describe('what the brush redraws', () => {
  const hill = [line(0, 100, ring(500, 400, 300)), line(1, 200, ring(500, 400, 150))];
  const other = line(2, 100, ring(120, 120, 60, 24));

  it('keeps every line without a stroke', () => {
    const field = brushField(extent, hill, 0);
    expect(redraw(field, hill, zero(field), 100, 0, extent)).toEqual({
      ok: true,
      keep: [0, 1],
      drop: [],
      add: [],
      redrawn: 0,
      fresh: 0,
      gone: 0,
    });
  });

  it('redraws the line a stroke passes and adds the next step up, keeping the rest part for part', () => {
    const lines = [...hill, other];
    const field = brushField(extent, lines, 0);
    const raised = withStroke(zero(field), strokeOf(field, [[500, 400]], 200), 1.5);
    const result = redraw(field, lines, raised, 100, 0, extent);
    if (!result.ok) throw new Error(result.why);

    // The top line is redrawn, a new line at 300 appears, the foot of the hill and the far one stay.
    expect(result.drop).toEqual([1]);
    expect(result.keep).toEqual([0, 2]);
    expect(result.add.map((one) => one.value).sort()).toEqual([200, 300]);
    expect(result.redrawn).toBe(1);
    expect(result.fresh).toBe(1);
    expect(result.gone).toBe(0);
    expect(redrawWords(result)).toBe('1 line redrawn, 1 new');
    for (const one of result.add) {
      for (const [x, y] of one.pts) {
        expect(x).toBeGreaterThanOrEqual(0);
        expect(y).toBeLessThanOrEqual(800);
      }
    }
  });

  it('drops a line whose height the land no longer reaches there', () => {
    const field = brushField(extent, hill, 0);
    const lowered = withStroke(zero(field), strokeOf(field, [[500, 400]], 230), -1);
    const result = redraw(field, hill, lowered, 100, 0, extent);
    if (!result.ok) throw new Error(result.why);

    expect(result.drop).toContain(1);
    expect(result.keep).toContain(0);
    expect(result.gone).toBe(1);
    expect(redrawWords(result)).toContain('1 gone');
  });

  it('raises a hill from flat ground at the first height, a line at each step', () => {
    const field = brushField(extent, [], 10);
    const raised = withStroke(zero(field), strokeOf(field, [[500, 400]], 200), 3);
    const result = redraw(field, [], raised, 5, 10, extent);
    if (!result.ok) throw new Error(result.why);

    // The first height too, round the foot of the hill: the ground about it is flat at that height.
    expect(result.add.map((one) => one.value).sort((a, b) => a - b)).toEqual([10, 15, 20]);
    expect(result.fresh).toBe(3);
    // Each closes round the hill.
    for (const one of result.add) expect(one.pts[0]).toEqual(one.pts.at(-1));
  });

  it('refuses more heights than a drawing holds lines', () => {
    const field = brushField(extent, [], 0);
    const raised = withStroke(zero(field), strokeOf(field, [[500, 400]], 200), 300);
    const result = redraw(field, [], raised, 1, 0, extent);
    expect(result.ok).toBe(false);
    if (result.ok) return;
    expect(result.why).toMatch(
      new RegExp(
        `^The strokes reach \\d+ heights, and a drawing holds ${MAX_LEVELS} lines\\. Use a larger Step\\.$`,
      ),
    );
  });
});
