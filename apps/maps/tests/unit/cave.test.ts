import { readFileSync } from 'node:fs';
import type { Geometry } from '@lorenzo/map-renderer';
import { describe, expect, it } from 'vitest';
import { type CaveOptions, caveSystem } from '../../src/lib/cave';
import { fits, type Region, regionOf } from '../../src/lib/generator';
import { GENERATORS } from '../../src/lib/generators';
import {
  CAVE_DENSITY,
  CAVE_PASSES,
  CAVE_SIZE,
  CAVE_SMALLEST,
  type NumberOption,
  toolById,
} from '../../src/lib/tools';
import { checkGeometry } from '../../src/lib/validate';

type Sheet = [number, number, number, number];
type GoldenRegion =
  | { kind: 'sheet'; sheet: Sheet }
  | { kind: 'area'; sheet: Sheet; ring: [number, number][] }
  | { kind: 'circle'; sheet: Sheet; at: [number, number]; r: number };
type Case = {
  name: string;
  region: GoldenRegion;
  options: CaveOptions;
  seed: number;
  caves: number;
  output: Geometry | null;
};

const golden = JSON.parse(
  readFileSync(
    new URL('../../../../packages/map-engine/golden/caves.json', import.meta.url),
    'utf8',
  ),
) as { cases: Case[] };

const FORMAT = 'lorenzo.geometry/1';

function regionFor(region: GoldenRegion): Region {
  if (region.kind === 'area') {
    return regionOf(
      {
        name: 'It',
        geometry: { format: FORMAT, parts: [{ shape: 'polygon', rings: [region.ring] }] },
      },
      region.sheet,
    );
  }

  if (region.kind === 'circle') {
    return regionOf(
      {
        name: 'It',
        geometry: { format: FORMAT, parts: [{ shape: 'circle', at: region.at, r: region.r }] },
      },
      region.sheet,
    );
  }

  return regionOf(null, region.sheet);
}

const sheet: Sheet = [0, 0, 1000, 800];
const whole = regionOf(null, sheet);
const first: CaveOptions = {
  size: CAVE_SIZE.first as number,
  density: CAVE_DENSITY.first as number,
  passes: CAVE_PASSES.first as number,
  smallest: CAVE_SMALLEST.first as number,
};
const points = (geometry: Geometry | null): [number, number][] =>
  (geometry?.parts ?? []).flatMap((part) =>
    part.shape === 'polygon'
      ? part.rings.flatMap((ring) => ring.map((p) => [p[0], p[1]] as [number, number]))
      : [],
  );

describe('the Cave system generator (ADR 0476)', () => {
  it('has golden vectors that cover each kind of region and no cave at all', () => {
    expect(golden.cases.length).toBeGreaterThanOrEqual(8);
    expect(new Set(golden.cases.map((c) => c.region.kind))).toEqual(
      new Set(['sheet', 'area', 'circle']),
    );
    expect(golden.cases.some((c) => c.output === null)).toBe(true);
  });

  for (const item of golden.cases) {
    it(`draws the golden caves, digit for digit: ${item.name}`, () => {
      const made = caveSystem(regionFor(item.region), item.options, item.seed);

      expect(made.caves).toBe(item.caves);
      expect(made.geometry).toEqual(item.output);
      // Through JSON as the API would get it, it is the same text.
      expect(JSON.stringify(made.geometry)).toBe(JSON.stringify(item.output));
    });
  }

  it('is a function of its seed: the same twice, and another for another seed', () => {
    const once = caveSystem(whole, first, 4821);

    expect(caveSystem(whole, first, 4821)).toEqual(once);
    expect(JSON.stringify(caveSystem(whole, first, 4822).geometry)).not.toBe(
      JSON.stringify(once.geometry),
    );
  });

  it('draws only what the API will take, across seeds, options and sheets', () => {
    const sheets: Sheet[] = [sheet, [0, 0, 100, 64], [-5, -5, 5, 3], [0, 0, 4000, 1000]];
    let drawn = 0;

    for (const bounds of sheets) {
      for (const size of [16, 33, 48, 70]) {
        for (let seed = 0; seed < 25; seed += 1) {
          const made = caveSystem(
            regionOf(null, bounds),
            { size, density: 0.4 + (seed % 5) * 0.03, passes: seed % 6, smallest: 1 + (seed % 9) },
            seed,
          );

          if (!made.geometry) continue;

          drawn += 1;

          const checked = checkGeometry(made.geometry);

          // Never a shape the Map cannot hold: only a limit can refuse a result.
          if (!checked.ok) expect(checked.why).toMatch(/vertices|too large|parts/);

          expect(made.geometry.parts).toHaveLength(made.caves);
        }
      }
    }

    expect(drawn).toBeGreaterThan(300);
  });

  it('draws what the API will take on a very small sheet and on a very large or far one', () => {
    // A sheet half a unit wide needs more than two decimals to keep its points apart; one that
    // reaches past a million units is drawn in whole units, where decimals are not always taken.
    const sheets: Sheet[] = [
      [0, 0, 0.5, 0.4],
      [0, 0, 9_000_000, 7_000_000],
      [-9_999_000, -9_999_000, 9_999_000, 9_999_000],
      [1_048_576, 1_048_576, 1_049_576, 1_049_376],
    ];

    for (const bounds of sheets) {
      let drawn = 0;

      for (let seed = 0; seed < 60; seed += 1) {
        const made = caveSystem(
          regionOf(null, bounds),
          { ...first, size: 16 + (seed % 60), passes: seed % 6, smallest: 1 + (seed % 9) },
          seed,
        );

        if (!made.geometry) continue;

        drawn += 1;

        const checked = checkGeometry(made.geometry);

        if (!checked.ok) expect(`${bounds}: ${checked.why}`).toMatch(/vertices|too large|parts/);
      }

      expect(drawn).toBeGreaterThan(40);
    }

    const far = points(caveSystem(regionOf(null, [0, 0, 9_000_000, 7_000_000]), first, 3).geometry);

    expect(far.length).toBeGreaterThan(0);
    expect(far.every(([x, y]) => Number.isInteger(x) && Number.isInteger(y))).toBe(true);
  });

  it('keeps every cave inside its region', () => {
    const [x0, y0, x1, y1] = sheet;

    for (const [x, y] of points(caveSystem(whole, first, 11).geometry)) {
      expect(x > x0 && x < x1 && y > y0 && y < y1).toBe(true);
    }

    const pond = regionFor({ kind: 'circle', sheet, at: [500, 400], r: 300 });
    const inPond = points(caveSystem(pond, first, 11).geometry);

    expect(inPond.length).toBeGreaterThan(0);
    for (const [x, y] of inPond) expect(Math.hypot(x - 500, y - 400)).toBeLessThan(300);

    const yard = regionFor({
      kind: 'area',
      sheet,
      ring: [
        [100, 100],
        [900, 100],
        [900, 700],
        [100, 700],
      ],
    });
    const inYard = points(caveSystem(yard, first, 11).geometry);

    expect(inYard.length).toBeGreaterThan(0);
    for (const [x, y] of inYard) expect(x > 100 && x < 900 && y > 100 && y < 700).toBe(true);
  });

  it('takes away small caves and pillars as Smallest cave says', () => {
    const loose = { ...first, passes: 1 };
    const many = caveSystem(whole, { ...loose, smallest: 1 }, 5);
    const few = caveSystem(whole, { ...loose, smallest: 40 }, 5);
    const rings = (geometry: Geometry | null) =>
      (geometry?.parts ?? []).reduce(
        (sum, part) => sum + (part.shape === 'polygon' ? part.rings.length : 0),
        0,
      );

    expect(many.caves).toBeGreaterThan(few.caves);
    expect(rings(many.geometry)).toBeGreaterThan(rings(few.geometry));
  });

  it('is smoother with more passes: fewer points to say the same sheet', () => {
    const rough = points(caveSystem(whole, { ...first, passes: 0, smallest: 1 }, 5).geometry);
    const smooth = points(caveSystem(whole, { ...first, passes: 6, smallest: 1 }, 5).geometry);

    expect(rough.length).toBeGreaterThan(smooth.length);
  });

  it('draws nothing in a region with no room, or when all is rock', () => {
    expect(caveSystem(regionOf(null, [0, 0, 0, 10]), first, 1)).toEqual({
      geometry: null,
      caves: 0,
    });
    expect(caveSystem(regionOf(null, [0, 0, 10, 0]), first, 1)).toEqual({
      geometry: null,
      caves: 0,
    });
    expect(caveSystem(whole, { ...first, density: 1 }, 1)).toEqual({ geometry: null, caves: 0 });
  });

  it('is the generator of its tool, and says what to change when a result is over a limit', () => {
    const decl = toolById('cave-system');
    const def = GENERATORS['cave-system'];

    expect(decl).toMatchObject({ state: 'ready', generator: true, notOnSphere: true });
    expect(def?.what).toBe('a cave system');

    const number = (set: Partial<Record<string, number>>) => (option: NumberOption) =>
      set[option.id] ?? (option.first as number);
    const usual = def?.run(whole, 4821, number({}));

    expect(usual?.count).toMatch(/^\d+ caves?$/);
    expect(fits(usual?.geometry ?? null, def?.hints as never)).toEqual({ ok: true });
    // The finest field on a large square sheet has more points than a drawing holds.
    const fine = def?.run(regionOf(null, [0, 0, 5000, 5000]), 3, number({ size: 96, passes: 0 }));

    expect(fits(fine?.geometry ?? null, def?.hints as never)).toEqual({
      ok: false,
      why: 'This has more than the 2000 points a drawing holds. Lower Size, or raise Passes.',
    });
    // With no room for a cave there is nothing to apply.
    const none = def?.run(whole, 1, number({ density: 0.6, passes: 8, smallest: 60, size: 16 }));

    expect(none?.count).toBe('0 caves');
    expect(fits(none?.geometry ?? null, def?.hints as never).ok).toBe(false);
  });
});
