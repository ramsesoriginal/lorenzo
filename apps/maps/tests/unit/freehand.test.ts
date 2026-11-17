import { describe, expect, it } from 'vitest';
import { MAX_VERTICES, simplify, strokeLine, unitsPerPixel } from '../../src/lib/freehand';

type Pt = readonly [number, number];

/** A wavy stroke: `count` samples along x, `height` up and down. */
const wave = (count: number, height: number): Pt[] =>
  Array.from({ length: count }, (_, i): Pt => [i, i % 2 === 0 ? 0 : height]);

describe('a freehand stroke (ADR 0472)', () => {
  it('drops the samples of a straight run and keeps its ends', () => {
    const run: Pt[] = Array.from({ length: 50 }, (_, i): Pt => [i * 2, 10 + (i % 3) * 0.1]);

    expect(simplify(run, 1)).toEqual([run[0], run[49]]);
    expect(simplify([run[0] as Pt, run[1] as Pt], 1)).toHaveLength(2);
    expect(simplify([], 1)).toEqual([]);
  });

  it('keeps a corner, and more of a bend as the tolerance falls', () => {
    const corner: Pt[] = [
      ...Array.from({ length: 20 }, (_, i): Pt => [i * 5, 0]),
      ...Array.from({ length: 20 }, (_, i): Pt => [100, i * 5]),
    ];

    expect(simplify(corner, 1)).toEqual([
      [0, 0],
      [100, 0],
      [100, 95],
    ]);

    const arc: Pt[] = Array.from({ length: 91 }, (_, i): Pt => {
      const a = (i * Math.PI) / 180;

      return [100 * Math.cos(a), 100 * Math.sin(a)];
    });
    const coarse = simplify(arc, 5);
    const fine = simplify(arc, 0.5);

    expect(coarse.length).toBeGreaterThanOrEqual(3);
    expect(fine.length).toBeGreaterThan(coarse.length);
    expect(fine.length).toBeLessThan(arc.length);
    expect(simplify(arc, 0)).toHaveLength(arc.length);
  });

  it('keeps the far point of a stroke that comes back to where it began', () => {
    const loop: Pt[] = [
      [0, 0],
      [50, 1],
      [100, 0],
      [50, -1],
      [0, 0],
    ];

    expect(simplify(loop, 5)).toEqual([
      [0, 0],
      [100, 0],
      [0, 0],
    ]);
  });

  it('is kept to two decimals, without a point equal to the one before it', () => {
    const line = strokeLine(
      [
        [0.001, 0.004],
        [0.004, 0.001],
        [10.006, 0],
        [10.006, 20.499],
      ],
      0.5,
    );

    expect(line).toEqual({
      pts: [
        [0, 0],
        [10.01, 0],
        [10.01, 20.5],
      ],
      coarser: false,
    });
  });

  it('makes nothing of a stroke that went nowhere', () => {
    expect(strokeLine([], 1).pts).toEqual([]);
    expect(strokeLine([[5, 5]], 1).pts).toEqual([]);
    expect(
      strokeLine(
        [
          [5, 5],
          [5.001, 5.002],
        ],
        1,
      ).pts,
    ).toEqual([]);
  });

  it('always fits a placement: the tolerance is raised until it does, and it says so', () => {
    // A stroke whose every sample is a corner, far more of them than a placement holds.
    const long = wave(MAX_VERTICES * 3, 4);
    const kept = strokeLine(long, 0.5);

    expect(strokeLine(wave(100, 4), 0.5)).toMatchObject({ coarser: false });
    expect(kept.coarser).toBe(true);
    expect(kept.pts.length).toBeLessThanOrEqual(MAX_VERTICES);
    expect(kept.pts.length).toBeGreaterThanOrEqual(2);
    expect(kept.pts[0]).toEqual(long[0]);
    expect(kept.pts[kept.pts.length - 1]).toEqual(long[long.length - 1]);
    // The same from no tolerance at all, and to a limit of the caller's own.
    expect(strokeLine(long, 0).pts.length).toBeLessThanOrEqual(MAX_VERTICES);
    expect(strokeLine(wave(100, 4), 0.5, 10).pts.length).toBeLessThanOrEqual(10);
  });

  it('turns a tolerance in pixels into drawing units by the zoom', () => {
    // A sheet of 1000 by 800 in a view of 500 by 400: half a pixel a unit when it fits.
    const extent = [0, 0, 1000, 800] as const;
    const viewport = { width: 500, height: 400 };

    expect(unitsPerPixel(extent, viewport, 1)).toBe(2);
    expect(unitsPerPixel(extent, viewport, 4)).toBe(0.5);
    // The narrower side decides, as it does for the view.
    expect(unitsPerPixel(extent, { width: 500, height: 200 }, 1)).toBe(4);
    expect(unitsPerPixel(extent, { width: 0, height: 0 }, 1)).toBe(1);
  });
});
