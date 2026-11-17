import { readFileSync } from 'node:fs';
import { describe, expect, it } from 'vitest';
import { checkGeometry, GEOMETRY_FORMAT, LIMITS } from '../../src/lib/validate';

type Case = { name: string; document: unknown; reason?: string };

const golden = JSON.parse(
  readFileSync(
    new URL('../../../../packages/map-engine/golden/geometry.json', import.meta.url),
    'utf8',
  ),
) as { accepted: Case[]; refused: Case[] };

const limitsPy = readFileSync(
  new URL('../../../../packages/map-engine/src/lorenzo_map/limits.py', import.meta.url),
  'utf8',
);

/** A limit as the engine's own file states it: `NAME = 64 * 1024` or `NAME = 2_000`. */
function engineLimit(name: string): number {
  const found = new RegExp(`^${name} = ([0-9_ *]+)$`, 'm').exec(limitsPy);

  if (!found) throw new Error(`the engine has no limit ${name}`);

  return (found[1] as string)
    .split('*')
    .reduce((product, factor) => product * Number(factor.replaceAll('_', '').trim()), 1);
}

const doc = (parts: unknown[]) => ({ format: GEOMETRY_FORMAT, parts });

describe('the geometry validator, mirrored (ADR 0337, ADR 0475)', () => {
  it('has a corpus to agree on', () => {
    expect(golden.accepted.length).toBeGreaterThanOrEqual(12);
    expect(golden.refused.length).toBeGreaterThanOrEqual(33);
  });

  for (const item of golden.accepted) {
    it(`accepts what the engine accepts: ${item.name}`, () => {
      expect(checkGeometry(item.document)).toMatchObject({ ok: true });
    });
  }

  for (const item of golden.refused) {
    it(`refuses what the engine refuses: ${item.name}`, () => {
      const checked = checkGeometry(item.document);

      expect(checked.ok).toBe(false);
      // A refusal names a rule and never repeats the input.
      if (!checked.ok) expect(checked.why).not.toMatch(/\[|\{|"/);
    });
  }

  it('has the limits the engine has', () => {
    expect(LIMITS.placementBytes).toBe(engineLimit('MAX_PLACEMENT_BYTES'));
    expect(LIMITS.vertices).toBe(engineLimit('MAX_VERTICES'));
    expect(LIMITS.parts).toBe(engineLimit('MAX_PARTS'));
    expect(LIMITS.coordinate).toBe(engineLimit('MAX_COORDINATE'));
    expect(LIMITS.value).toBe(engineLimit('MAX_VALUE'));
    expect(LIMITS.unitLength).toBe(engineLimit('MAX_UNIT_LENGTH'));
    expect(LIMITS.simplicityBudget).toBe(engineLimit('SIMPLICITY_BUDGET'));
    expect(LIMITS.batchOperations).toBe(engineLimit('MAX_BATCH_OPERATIONS'));
  });

  it('counts vertices, parts and bytes, and refuses one over each limit', () => {
    const line = (count: number) => ({
      shape: 'polyline',
      pts: Array.from({ length: count }, (_, i) => [i, i % 2]),
    });

    expect(checkGeometry(doc([line(LIMITS.vertices)]))).toMatchObject({
      ok: true,
      vertices: LIMITS.vertices,
      parts: 1,
    });
    expect(checkGeometry(doc([line(LIMITS.vertices), { shape: 'point', at: [0, 0] }]))).toEqual({
      ok: false,
      why: 'a placement has at most 8000 vertices',
    });
    // A bezier counts its start and three for every segment; a circle and a point one each.
    expect(
      checkGeometry(
        doc([
          {
            shape: 'bezier',
            start: [0, 0],
            segs: [
              [
                [1, 1],
                [2, 1],
                [3, 0],
              ],
            ],
          },
          { shape: 'circle', at: [0, 0], r: 1 },
        ]),
      ),
    ).toMatchObject({ ok: true, vertices: 5, parts: 2 });

    const pins = (count: number) =>
      Array.from({ length: count }, (_, i) => ({ shape: 'point', at: [i, 0] }));

    expect(checkGeometry(doc(pins(LIMITS.parts)))).toMatchObject({ ok: true, parts: LIMITS.parts });
    expect(checkGeometry(doc(pins(LIMITS.parts + 1))).ok).toBe(false);

    // Long coordinates: within the vertices, beyond the bytes.
    const wide = {
      shape: 'polyline',
      pts: Array.from({ length: 7990 }, (_, i) => [-9999999.123456 + i, -9999999.654321 + i]),
    };
    const big = checkGeometry(doc([wide]));

    expect(big).toEqual({ ok: false, why: "a placement's geometry is too large" });
  });

  it('checks a polygon with exact arithmetic at the largest coordinates', () => {
    const far = 9_999_999.999999;
    // A sliver whose corner is a millionth off the long edge: simple, and nearly not.
    const sliver = [
      [-far, -far],
      [far, far],
      [far, far - 0.000001],
    ];

    expect(checkGeometry(doc([{ shape: 'polygon', rings: [sliver] }])).ok).toBe(true);
    // The same with a fourth point on the long edge beyond its end's neighbour: it doubles back.
    expect(
      checkGeometry(
        doc([
          {
            shape: 'polygon',
            rings: [
              [
                [0, 0],
                [far, far],
                [far / 2, far / 2],
                [far, 0],
              ],
            ],
          },
        ]),
      ).ok,
    ).toBe(false);
  });

  it('says which rule refused, for the ones a generator can meet', () => {
    const square = [
      [0, 0],
      [10, 0],
      [10, 10],
      [0, 10],
    ];
    const why = (rings: number[][][]) => {
      const checked = checkGeometry(doc([{ shape: 'polygon', rings }]));

      return checked.ok ? null : checked.why;
    };

    expect(why([square])).toBeNull();
    expect(
      why([
        [
          [0, 0],
          [10, 10],
          [10, 0],
          [0, 10],
        ],
      ]),
    ).toBe('a polygon touches or crosses itself');
    expect(
      why([
        square,
        [
          [20, 20],
          [30, 20],
          [30, 30],
        ],
      ]),
    ).toBe('a hole must lie inside the outer ring');
    expect(
      why([
        square,
        [
          [0, 0],
          [5, 1],
          [1, 5],
        ],
      ]),
    ).toBe('a polygon touches or crosses itself');
    expect(why([[...square, [0, 10]]])).toBe('a polygon has an edge of no length');
  });
});
