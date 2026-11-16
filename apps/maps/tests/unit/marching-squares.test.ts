import { describe, expect, it } from 'vitest';
import { nested, outlines, ringArea, ringHolds } from '../../src/lib/marching-squares';

type Pt = readonly [number, number];

/** A field from rows of digits, each a tenth: '9' is 0.9. */
const field = (rows: string[]): { values: number[]; cols: number; rows: number } => ({
  values: rows.flatMap((row) => [...row].map((digit) => Number(digit) / 10)),
  cols: (rows[0] as string).length,
  rows: rows.length,
});

const trace = (rows: string[], level = 0.5): Pt[][] => {
  const f = field(rows);

  return outlines(f.values, f.cols, f.rows, level);
};

describe('marching squares (ADR 0476)', () => {
  it('traces one ring around one number above the level, half-way to each neighbour', () => {
    const rings = trace(['000', '090', '000'], 0.45);

    expect(rings).toHaveLength(1);
    expect(rings[0]).toHaveLength(4);
    expect(new Set(rings[0]?.map((p) => p.join(',')))).toEqual(
      new Set(['1,0.5', '0.5,1', '1.5,1', '1,1.5']),
    );
  });

  it('puts a crossing along an edge by where the level falls between its two numbers', () => {
    // Between 0 and 0.8 the level 0.2 is a quarter of the way.
    const rings = trace(['000', '080', '000'], 0.2);

    expect(new Set(rings[0]?.map((p) => p.join(',')))).toEqual(
      new Set(['1,0.25', '0.25,1', '1.75,1', '1,1.75']),
    );
  });

  it('traces an outline and the hole in it as two rings', () => {
    const rings = trace(['00000', '09990', '09090', '09990', '00000'], 0.45);

    expect(rings).toHaveLength(2);

    const [big, small] = [...rings].sort((a, b) => ringArea(b) - ringArea(a)) as [Pt[], Pt[]];

    expect(ringHolds(big, small[0] as Pt)).toBe(true);
    expect(ringArea(small)).toBeCloseTo(0.5, 9);
    expect(nested(rings)).toHaveLength(1);
    expect(nested(rings)[0]).toHaveLength(2);
  });

  it('decides a square whose corners alternate by the mean of the four', () => {
    // Two numbers above the level, corner to corner. High numbers join them into one ring...
    expect(trace(['0000', '0900', '0090', '0000'], 0.4)).toHaveLength(1);
    // ...and numbers only just above it leave two.
    expect(trace(['0000', '0500', '0050', '0000'], 0.4)).toHaveLength(2);
  });

  it('gives the same rings, point for point, every time', () => {
    const rows = ['0000000', '0990990', '0900090', '0099900', '0090900', '0000000'];

    expect(trace(rows, 0.45)).toEqual(trace(rows, 0.45));
  });

  it('closes every ring, and no two rings share a point', () => {
    const rows = [
      '00000000',
      '09909090',
      '09009990',
      '00990090',
      '09099990',
      '09900900',
      '00000000',
    ];
    const rings = trace(rows, 0.45);
    const seen = new Set<string>();

    for (const ring of rings) {
      expect(ring.length).toBeGreaterThanOrEqual(3);

      for (const p of ring) {
        expect(seen.has(p.join(','))).toBe(false);
        seen.add(p.join(','));
      }
    }
  });

  it('refuses a field that is open at its edge, or of the wrong size', () => {
    expect(() => trace(['090', '000', '000'])).toThrow(/open at its edge/);
    expect(() => trace(['000', '009', '000'])).toThrow(/open at its edge/);
    expect(() => outlines([0, 0, 0], 2, 2, 0.5)).toThrow(/cols by rows/);
  });

  it('nests rings: a hole in the smallest outline that holds it, a ring in a hole on its own', () => {
    const square = (from: number, to: number): Pt[] => [
      [from, from],
      [to, from],
      [to, to],
      [from, to],
    ];
    const areas = nested([
      square(0, 100),
      square(10, 90),
      square(20, 80),
      square(30, 70),
      square(200, 300),
    ]);

    expect(areas).toHaveLength(3);
    expect(areas.map((area) => area.length)).toEqual([2, 2, 1]);
    expect(areas[0]).toEqual([square(0, 100), square(10, 90)]);
    expect(areas[1]).toEqual([square(20, 80), square(30, 70)]);
    expect(areas[2]).toEqual([square(200, 300)]);
  });
});
