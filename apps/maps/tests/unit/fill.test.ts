import { readFileSync } from 'node:fs';
import type { Geometry } from '@lorenzo/map-renderer';
import { describe, expect, it } from 'vitest';
import { decimalsFor, fieldOver } from '../../src/lib/field';
import { FILL_COLS, type FillOptions, fill } from '../../src/lib/fill';
import { fits, type Region, regionOf } from '../../src/lib/generator';
import { GENERATORS, type Options } from '../../src/lib/generators';
import { outlines } from '../../src/lib/marching-squares';
import {
  FILL_LEVEL,
  FILL_LINES,
  FILL_SCALE,
  FILL_SMALLEST,
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
  options: FillOptions;
  seed: number;
  areas: number;
  lines: number;
  needsHeights: boolean;
  output: Geometry | null;
};

const golden = JSON.parse(
  readFileSync(
    new URL('../../../../packages/map-engine/golden/fills.json', import.meta.url),
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
const first: FillOptions = {
  scale: FILL_SCALE.first as number,
  level: FILL_LEVEL.first as number,
  smallest: FILL_SMALLEST.first as number,
  lines: FILL_LINES.first as number,
  first: null,
  step: null,
  unit: null,
};
const heights = { first: 100, step: 50, unit: 'm' };
const points = (geometry: Geometry | null): [number, number][] =>
  (geometry?.parts ?? []).flatMap((part) =>
    part.shape === 'polygon'
      ? part.rings.flatMap((ring) => ring.map((p) => [p[0], p[1]] as [number, number]))
      : part.shape === 'polyline'
        ? part.pts.map((p) => [p[0], p[1]] as [number, number])
        : [],
  );

describe('the Fill by marching squares generator (ADR 0477)', () => {
  it('has golden vectors that cover each kind of region, height lines and nothing at all', () => {
    expect(golden.cases.length).toBeGreaterThanOrEqual(10);
    expect(new Set(golden.cases.map((c) => c.region.kind))).toEqual(
      new Set(['sheet', 'area', 'circle']),
    );
    expect(golden.cases.some((c) => c.output === null)).toBe(true);
    expect(golden.cases.some((c) => c.lines > 0 && !c.needsHeights)).toBe(true);
    expect(golden.cases.some((c) => c.needsHeights)).toBe(true);
  });

  for (const item of golden.cases) {
    it(`draws the golden fill, digit for digit: ${item.name}`, () => {
      const made = fill(regionFor(item.region), item.options, item.seed);

      expect([made.areas, made.lines, made.needsHeights]).toEqual([
        item.areas,
        item.lines,
        item.needsHeights,
      ]);
      expect(JSON.stringify(made.geometry)).toBe(JSON.stringify(item.output));
    });
  }

  it('is a function of its seed: the same twice, and another for another seed', () => {
    const once = fill(whole, first, 4821);

    expect(fill(whole, first, 4821)).toEqual(once);
    expect(JSON.stringify(fill(whole, first, 4822).geometry)).not.toBe(
      JSON.stringify(once.geometry),
    );
  });

  it('draws only what the API will take, across seeds, options and sheets', () => {
    const sheets: Sheet[] = [
      sheet,
      [0, 0, 0.5, 0.4],
      [-5, -5, 5, 3],
      [0, 0, 4000, 1000],
      [0, 0, 9_000_000, 7_000_000],
      [1_048_576, 1_048_576, 1_049_576, 1_049_376],
    ];
    let drawn = 0;

    for (const bounds of sheets) {
      for (let seed = 0; seed < 60; seed += 1) {
        const made = fill(
          regionOf(null, bounds),
          {
            scale: 2 + (seed % 19),
            level: 0.3 + (seed % 9) * 0.05,
            smallest: 1 + (seed % 7),
            lines: seed % 3,
            ...heights,
          },
          seed,
        );

        if (!made.geometry) continue;

        drawn += 1;

        const checked = checkGeometry(made.geometry);

        // Never a shape the Map cannot hold: only a limit can refuse a result.
        if (!checked.ok) expect(`${bounds}: ${checked.why}`).toMatch(/vertices|too large|parts/);
      }
    }

    expect(drawn).toBeGreaterThan(300);
  });

  it('keeps areas and height lines inside the region', () => {
    const [x0, y0, x1, y1] = sheet;
    const all = points(fill(whole, { ...first, lines: 2, ...heights }, 11).geometry);

    expect(all.length).toBeGreaterThan(0);
    for (const [x, y] of all) expect(x > x0 && x < x1 && y > y0 && y < y1).toBe(true);

    const pond = regionFor({ kind: 'circle', sheet, at: [500, 400], r: 300 });
    const inPond = points(fill(pond, { ...first, level: 0.4 }, 11).geometry);

    expect(inPond.length).toBeGreaterThan(0);
    for (const [x, y] of inPond) expect(Math.hypot(x - 500, y - 400)).toBeLessThan(300);
  });

  it('draws less at a higher level, finer shapes at a larger scale, fewer with a larger smallest', () => {
    const size = (geometry: Geometry | null) => points(geometry).length;
    const low = fill(whole, { ...first, level: 0.35 }, 5);
    const high = fill(whole, { ...first, level: 0.65 }, 5);
    const coarse = fill(whole, { ...first, scale: 3 }, 5);
    const fine = fill(whole, { ...first, scale: 18 }, 5);

    expect(checkAreaShare(low.geometry)).toBeGreaterThan(checkAreaShare(high.geometry));
    expect(fine.areas).toBeGreaterThan(coarse.areas);
    expect(size(fine.geometry)).toBeGreaterThan(size(coarse.geometry));
    expect(fill(whole, { ...first, scale: 18, smallest: 1 }, 5).areas).toBeGreaterThan(
      fill(whole, { ...first, scale: 18, smallest: 40 }, 5).areas,
    );
  });

  it('writes height lines after the areas, each level a step higher', () => {
    const made = fill(whole, { ...first, scale: 3, lines: 3, ...heights }, 12);
    const parts = made.geometry?.parts ?? [];
    const lines = parts.slice(made.areas);

    expect(made.lines).toBeGreaterThan(0);
    expect(parts.slice(0, made.areas).every((part) => part.shape === 'polygon')).toBe(true);
    expect(lines).toHaveLength(made.lines);
    for (const line of lines) {
      if (line.shape !== 'polyline') throw new Error('a height line is a polyline');

      expect(line.pts.length).toBeGreaterThanOrEqual(2);
      expect(line.unit).toBe('m');
      expect([100, 150, 200]).toContain(line.value);
    }
    expect(new Set(lines.map((line) => line.value)).size).toBeGreaterThan(1);
    expect(made.needsHeights).toBe(false);
    // A step that is not whole is kept to the format's six decimals.
    const odd = fill(whole, { ...first, scale: 3, lines: 3, first: 0.1, step: 0.2, unit: 'm' }, 12);

    const oddValues = (odd.geometry?.parts ?? []).slice(odd.areas).map((line) => line.value);

    // 0.1 and 0.2 make 0.30000000000000004 unless kept to six decimals; a level the field
    // does not reach has no line.
    expect(oddValues).toContain(0.3);
    expect(oddValues.every((value) => [0.1, 0.3, 0.5].includes(value as number))).toBe(true);
  });

  it('ends a height line at the edge of its region, and never runs one along it', () => {
    // A sheet of whole cells, 64 by 48: the cells that take part begin two and a half cells in
    // from each side, and a line the edge cuts ends between there and one cell nearer the side.
    const cell = 1000 / FILL_COLS;
    const even = regionOf(null, [0, 0, 1000, 750]);
    const fromSide = ([x, y]: readonly [number, number]) => Math.min(x, y, 1000 - x, 750 - y);
    let closed = 0;
    let open = 0;

    for (let seed = 0; seed < 40; seed += 1) {
      const made = fill(even, { ...first, scale: 3, level: 0.4, lines: 3, ...heights }, seed);

      for (const line of (made.geometry?.parts ?? []).slice(made.areas)) {
        if (line.shape !== 'polyline') throw new Error('a height line is a polyline');

        const ends = [line.pts[0], line.pts[line.pts.length - 1]] as [
          readonly [number, number],
          readonly [number, number],
        ];

        const near = (p: readonly [number, number]) => fromSide(p) < 2.5 * cell - 0.01;

        // No stretch of any line runs along the side: of two points one after the other, at most
        // one is at the edge.
        for (let k = 1; k < line.pts.length; k += 1) {
          const a = line.pts[k - 1] as readonly [number, number];
          const b = line.pts[k] as readonly [number, number];

          expect(near(a) && near(b) && (a[0] !== b[0] || a[1] !== b[1])).toBe(false);
        }
        // And none comes nearer the side than the cells that take part allow.
        for (const p of line.pts) expect(fromSide(p)).toBeGreaterThan(1.5 * cell - 0.01);

        if (ends[0][0] === ends[1][0] && ends[0][1] === ends[1][1]) {
          // It goes round: inside, or touching the edge in the one point it begins and ends at.
          closed += 1;
          continue;
        }

        // The edge cut it: it ends at the edge, both ways.
        open += 1;
        for (const end of ends) expect(near(end)).toBe(true);
      }
    }

    expect(closed).toBeGreaterThan(5);
    expect(open).toBeGreaterThan(5);
  });

  it('previews height lines without their heights, and says they are needed', () => {
    for (const missing of [
      { first: null, step: 50, unit: 'm' },
      { first: 100, step: null, unit: 'm' },
      { first: 100, step: 50, unit: null },
      { first: 100, step: 50, unit: '' },
    ]) {
      const made = fill(whole, { ...first, scale: 3, lines: 2, ...missing }, 12);

      expect(made.needsHeights).toBe(true);
      expect(made.lines).toBeGreaterThan(0);
      expect(
        (made.geometry?.parts ?? []).slice(made.areas).every((line) => !('value' in line)),
      ).toBe(true);
    }

    expect(fill(whole, first, 12).needsHeights).toBe(false);
  });

  it('is the generator of its tool: counts, what is needed first, and what to change', () => {
    const decl = toolById('marching-squares');
    const def = GENERATORS['marching-squares'];

    expect(decl).toMatchObject({ state: 'ready', generator: true, notOnSphere: true });
    expect(def?.what).toBe('a fill');

    const set = (numbers: Partial<Record<string, number>>, unit = ''): Options => ({
      number: (option: NumberOption) => numbers[option.id] ?? option.first,
      text: () => unit,
    });
    const usual = def?.run(whole, 4821, set({}));

    expect(usual?.count).toMatch(/^\d+ areas?$/);
    expect(usual?.needs).toBeUndefined();
    expect(fits(usual?.geometry ?? null, def?.hints as never)).toEqual({ ok: true });

    const lined = def?.run(whole, 12, set({ scale: 3, lines: 2, first: 100, step: 50 }, 'm'));

    expect(lined?.count).toMatch(/^\d+ areas? and \d+ height lines?$/);
    expect(lined?.needs).toBeUndefined();
    expect(def?.run(whole, 12, set({ scale: 3, lines: 2 })).needs).toBe(
      'Height lines need a first height, a step and a unit: give all three, or set Height lines to 0.',
    );
    // Even the finest noise with every height line fits a drawing since ADR 0481; one over the
    // limit is still named.
    const many = def?.run(whole, 3, set({ scale: 20, lines: 8, first: 0, step: 1 }, 'm'));

    expect(fits(many?.geometry ?? null, def?.hints as never)).toEqual({ ok: true });
    expect(
      fits(
        {
          format: 'lorenzo.geometry/1',
          parts: [
            { shape: 'polyline', pts: Array.from({ length: 8001 }, (_, i) => [i, i % 2] as const) },
          ],
        } as never,
        def?.hints as never,
      ),
    ).toEqual({
      ok: false,
      why: 'This has more than the 8000 points a drawing holds. Lower Height lines, or raise Scale.',
    });
  });
});

/** How much of what a fill draws is area: the sum of its outlines less their holes. */
function checkAreaShare(geometry: Geometry | null): number {
  let total = 0;

  for (const part of geometry?.parts ?? []) {
    if (part.shape !== 'polygon') continue;

    part.rings.forEach((ring, index) => {
      let twice = 0;

      for (let i = 0, j = ring.length - 1; i < ring.length; j = i, i += 1) {
        const a = ring[j] as readonly [number, number];
        const b = ring[i] as readonly [number, number];

        twice += a[0] * b[1] - b[0] * a[1];
      }

      total += (index === 0 ? 1 : -1) * (Math.abs(twice) / 2);
    });
  }

  return total;
}

describe('a field over a region, and its decimals (ADR 0476, ADR 0477)', () => {
  it('is square cells over the box around the region, with its edge and the outside left out', () => {
    const field = fieldOver(whole, 10);

    expect(field).toMatchObject({ cols: 10, rows: 8, cell: 100, x0: 0, y0: 0 });
    // The edge cells and the cells beside them take no part.
    expect([...(field?.wall ?? [])].filter((w) => w === 0)).toHaveLength(6 * 4);
    expect(fieldOver(regionOf(null, [0, 0, 0, 10]), 10)).toBeNull();
    expect(fieldOver(regionOf(null, [0, 0, 10, 0]), 10)).toBeNull();
    expect(fieldOver(whole, 2)).toBeNull();
    // A very wide region still has four rows.
    expect(fieldOver(regionOf(null, [0, 0, 1000, 10]), 10)?.rows).toBe(4);
  });

  it('keeps two decimals, and more for a fine field, however far out it lies', () => {
    const over = (bounds: Sheet) => fieldOver(regionOf(null, bounds), FILL_COLS) as never;

    expect(decimalsFor(over(sheet))).toBe(2);
    expect(decimalsFor(over(sheet), 16)).toBe(2);
    expect(decimalsFor(over([0, 0, 10, 8]), 16)).toBe(3);
    expect(decimalsFor(over([0, 0, 0.5, 0.4]), 16)).toBe(4);
    expect(decimalsFor(over([0, 0, 0.000001, 0.000001]), 16)).toBe(6);
    // Without steps to keep apart, two decimals whatever the cell.
    expect(decimalsFor(over([0, 0, 0.5, 0.4]))).toBe(2);
    // Far out as near: the validator takes two decimals there too (#1255).
    expect(decimalsFor(over([0, 0, 9_000_000, 7_000_000]), 16)).toBe(2);
    expect(decimalsFor(over([-2_000_000, 0, -1_999_000, 800]), 16)).toBe(2);
    expect(decimalsFor(over([999_000, 0, 1_000_000, 800]), 16)).toBe(2);
  });

  it('puts a crossing on a step of its edge, and never on an end of it', () => {
    // Between 0 and 0.9 the level 0.02 falls a forty-fifth of the way: nearer the end than a step.
    const values = [0, 0, 0, 0, 0.9, 0, 0, 0, 0];
    const free = outlines(values, 3, 3, 0.02)[0] ?? [];
    const stepped = outlines(values, 3, 3, 0.02, 16)[0] ?? [];

    expect(free.some(([x]) => Math.abs(x - 1 / 45) < 1e-9)).toBe(true);
    expect(new Set(stepped.map((p) => p.join(',')))).toEqual(
      new Set(['1,0.0625', '0.0625,1', '1.9375,1', '1,1.9375']),
    );
    // In the middle a step changes nothing.
    expect(outlines(values, 3, 3, 0.45, 16)).toEqual(outlines(values, 3, 3, 0.45));
  });
});
