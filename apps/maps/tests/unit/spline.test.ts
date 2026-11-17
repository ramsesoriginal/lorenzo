import type { Geometry, Part } from '@lorenzo/map-renderer';
import { describe, expect, it } from 'vitest';
import {
  type Editable,
  editableOf,
  insertVertex,
  moveHandle,
  removeVertex,
  toGeometry,
} from '../../src/lib/geometry-edit';
import { SPLINE_MAX_POINTS, splineCurve, splineOf, splinePart } from '../../src/lib/spline';

type Pt = readonly [number, number];

const bend: Pt[] = [
  [0, 0],
  [60, 0],
  [60, 60],
];

describe('a spline (ADR 0471)', () => {
  it('is one open bezier through every point, a segment between each two', () => {
    const part = splinePart(bend, 0.5);

    expect(part.shape).toBe('bezier');
    expect(part.closed).toBeUndefined();
    expect(part.start).toEqual([0, 0]);
    expect(part.segs.map((seg) => seg[2])).toEqual([
      [60, 0],
      [60, 60],
    ]);
  });

  it('leans at a point along the line from the point before to the point after', () => {
    // Tension 0: the lean is half that line, and a control a third of the lean from its end.
    expect(splinePart(bend, 0).segs).toEqual([
      [
        [10, 0],
        [50, -10],
        [60, 0],
      ],
      [
        [70, 10],
        [60, 50],
        [60, 60],
      ],
    ]);
    // Tension 0.5 halves every lean.
    expect(splinePart(bend, 0.5).segs[0]).toEqual([
      [5, 0],
      [55, -5],
      [60, 0],
    ]);
    // Tension 1: every control lies on its end, so the curve is straight lines.
    expect(splinePart(bend, 1).segs).toEqual([
      [
        [0, 0],
        [60, 0],
        [60, 0],
      ],
      [
        [60, 0],
        [60, 60],
        [60, 60],
      ],
    ]);
  });

  it('of two points is one segment, and keeps coordinates to two decimals', () => {
    const part = splinePart(
      [
        [0.004, 0],
        [9.996, 6.0049],
      ],
      0,
    );

    expect(part.start).toEqual([0, 0]);
    expect(part.segs).toEqual([
      [
        [1.67, 1],
        [8.33, 5],
        [10, 6],
      ],
    ]);
  });

  it('is read back as its points and its tension', () => {
    const wide: Pt[] = [
      [12.5, 700.25],
      [4000, 90],
      [-350.75, 2200],
      [9000, 9000],
      [9000.5, 9001],
    ];

    for (const pts of [bend, wide]) {
      for (const tension of [0, 0.05, 0.35, 0.5, 0.95, 1]) {
        expect(splineOf(splinePart(pts, tension))).toEqual({ pts, tension });
      }
    }
  });

  it('is not read from a bezier that is closed or whose controls are its own', () => {
    const drawn = splinePart(bend, 0.5);

    expect(splineOf({ ...drawn, closed: true })).toBeNull();
    expect(splineOf({ shape: 'polyline', pts: bend })).toBeNull();

    const moved: Part = {
      ...drawn,
      segs: drawn.segs.map((seg, i) => (i === 0 ? [[5, 9], seg[1], seg[2]] : seg)),
    };

    expect(splineOf(moved)).toBeNull();
    // Controls pushed outward past the roundest spline are no spline either.
    expect(
      splineOf({
        shape: 'bezier',
        start: [0, 0],
        segs: [
          [
            [-40, 0],
            [140, 0],
            [100, 0],
          ],
        ],
      }),
    ).toBeNull();
  });

  it('gives points along the curve for an overlay, through every point', () => {
    const curve = splineCurve(bend, 0.5, 4);

    expect(curve).toHaveLength(9);
    expect(curve[0]).toEqual([0, 0]);
    expect(curve[4]).toEqual([60, 0]);
    expect(curve[8]).toEqual([60, 60]);
    expect(splineCurve([[1, 2]], 0.5)).toEqual([[1, 2]]);
  });

  it('is edited by its points: every control is derived again', () => {
    const geometry: Geometry = { format: 'lorenzo.geometry/1', parts: [splinePart(bend, 0.5)] };
    const shape = editableOf(geometry) as Editable;

    expect(shape).toEqual({ kind: 'spline', pts: bend, tension: 0.5 });
    expect(toGeometry(shape)).toEqual(geometry);

    const moved = moveHandle(shape, 'v1', [60, 30]);

    expect(toGeometry(moved).parts[0]).toEqual(
      splinePart(
        [
          [0, 0],
          [60, 30],
          [60, 60],
        ],
        0.5,
      ),
    );
    // A point added after the last goes on from it, as for a line; one removed leaves a spline.
    const longer = insertVertex(shape, 2) as Extract<Editable, { kind: 'spline' }>;

    expect(longer.pts).toHaveLength(4);
    expect(longer.pts[3]).toEqual([70, 90]);
    expect(editableOf(toGeometry(removeVertex(shape, 1) as Editable))).toMatchObject({
      kind: 'spline',
      pts: [
        [0, 0],
        [60, 60],
      ],
    });
    expect(removeVertex(removeVertex(shape, 1) as Editable, 0)).toBeNull();
  });

  it('keeps a value and a unit, and stops at the most points a placement holds', () => {
    const valued: Geometry = {
      format: 'lorenzo.geometry/1',
      parts: [{ ...splinePart(bend, 0.5), value: 250, unit: 'm' }],
    };
    const shape = editableOf(valued) as Editable;

    expect(toGeometry(moveHandle(shape, 'v0', [1, 1])).parts[0]).toMatchObject({
      value: 250,
      unit: 'm',
    });

    const most: Pt[] = Array.from({ length: SPLINE_MAX_POINTS }, (_, i): Pt => [i, i % 2]);
    const full = splinePart(most, 0.5);

    // The start and three for every segment: within the 8,000 of ADR 0481.
    expect(1 + full.segs.length * 3).toBeLessThanOrEqual(8000);
    expect(full.segs).toHaveLength(SPLINE_MAX_POINTS - 1);
    expect(1 + SPLINE_MAX_POINTS * 3).toBeGreaterThan(8000);

    const whole: Editable = { kind: 'spline', pts: most.map((p) => [...p] as Pt), tension: 0.5 };

    expect(insertVertex(whole, 3)).toBe(whole);
  });
});
