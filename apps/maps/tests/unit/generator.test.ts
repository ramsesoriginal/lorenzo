import type { Geometry } from '@lorenzo/map-renderer';
import { describe, expect, it } from 'vitest';
import { parseCommand } from '../../src/lib/command-line';
import {
  counted,
  fits,
  type Hints,
  nextSeed,
  regionOf,
  SEED_MOST,
  seedFrom,
  seedOf,
  stepName,
} from '../../src/lib/generator';
import { createOptionValues, SEED, TOOLS, type ToolDecl } from '../../src/lib/tools';

const FORMAT = 'lorenzo.geometry/1';
const sheet = [0, 0, 1000, 800] as const;
const hints: Hints = {
  vertices: 'Raise Smoothing.',
  parts: 'Raise Minimum area.',
  bytes: 'Lower Size.',
  shape: 'Try another seed.',
};

describe('what the generators share (ADR 0475)', () => {
  it('reads a seed: a whole number from 0 to 999,999', () => {
    expect(seedOf('4821')).toBe(4821);
    expect(seedOf(' 0 ')).toBe(0);
    expect(seedOf(String(SEED_MOST))).toBe(SEED_MOST);
    for (const bad of ['', '-1', '1.5', '1e3', 'seed', String(SEED_MOST + 1)]) {
      expect(seedOf(bad), bad).toBeNull();
    }
  });

  it('rolls to the next seed, and makes a first one of any 32 bits', () => {
    expect(nextSeed(4821)).toBe(4822);
    expect(nextSeed(SEED_MOST)).toBe(0);
    expect(seedFrom(0)).toBe(0);
    expect(seedFrom(4_294_967_295)).toBe(967_295);
    expect(seedFrom(-1)).toBe(967_295);
    for (const bits of [1, 999_999, 1_000_000, 123_456_789]) {
      const seed = seedFrom(bits);

      expect(Number.isInteger(seed) && seed >= 0 && seed <= SEED_MOST).toBe(true);
    }
  });

  it('takes SEED, ROLL, APPLY, DISCARD and COMPARE on the command line', () => {
    const generator: ToolDecl = {
      id: 'made-up',
      name: 'Made up',
      group: 'generate',
      icon: 'layers',
      key: 'z',
      input: 'a region and a seed',
      output: 'areas',
      state: 'ready',
      options: [SEED],
    };
    const on = { grid: false, sphere: false, tool: generator };
    const tools = [...TOOLS, generator];

    expect(parseCommand('SEED 4821', tools, on)).toEqual({
      kind: 'option',
      option: SEED,
      value: 4821,
    });
    for (const bad of ['SEED', 'SEED -1', 'SEED 1.5', 'SEED 1000000']) {
      expect(parseCommand(bad, tools, on)).toEqual({
        kind: 'error',
        message: 'SEED takes a whole number from 0 to 999999.',
      });
    }
    expect(parseCommand('roll', tools, on)).toEqual({ kind: 'roll' });
    expect(parseCommand('APPLY', tools, on)).toEqual({ kind: 'apply' });
    expect(parseCommand('Discard', tools, on)).toEqual({ kind: 'discard' });
    expect(parseCommand('COMPARE ON', tools, on)).toEqual({ kind: 'compare', on: true });
    expect(parseCommand('compare off', tools, on)).toEqual({ kind: 'compare', on: false });
    expect(parseCommand('COMPARE', tools, on)).toEqual({
      kind: 'error',
      message: 'COMPARE takes ON or OFF.',
    });
    // A seed has no first value of its own: the page draws it.
    const values = createOptionValues();

    expect(values.get(generator, SEED)).toBeNull();
    values.set(generator, SEED, 7);
    expect(values.get(generator, SEED)).toBe(7);
  });

  it('works in the selected area or circle, and otherwise in the whole sheet', () => {
    const whole = regionOf(null, sheet);

    expect(whole).toMatchObject({ kind: 'sheet', bounds: sheet, words: 'the whole sheet' });
    expect(whole.contains([0, 0])).toBe(true);
    expect(whole.contains([1000, 800])).toBe(true);
    expect(whole.contains([1001, 5])).toBe(false);

    const town = regionOf(
      {
        name: 'Old Town',
        geometry: {
          format: FORMAT,
          parts: [
            {
              shape: 'polygon',
              rings: [
                [
                  [100, 100],
                  [300, 100],
                  [100, 300],
                ],
              ],
            },
          ],
        },
      },
      sheet,
    );

    expect(town).toMatchObject({ kind: 'area', bounds: [100, 100, 300, 300], words: 'Old Town' });
    expect(town.contains([150, 150])).toBe(true);
    expect(town.contains([290, 290])).toBe(false);

    const pond = regionOf(
      {
        name: 'Pond',
        geometry: { format: FORMAT, parts: [{ shape: 'circle', at: [500, 400], r: 50 }] },
      },
      sheet,
    );

    expect(pond).toMatchObject({ kind: 'circle', bounds: [450, 350, 550, 450], words: 'Pond' });
    expect(pond.contains([530, 400])).toBe(true);
    expect(pond.contains([550, 400])).toBe(false);
    expect(pond.contains([540, 440])).toBe(false);
  });

  it('falls back to the whole sheet for a line, a pin, several parts or an area with holes', () => {
    const outline = [
      [100, 100],
      [300, 100],
      [300, 300],
    ] as [number, number][];
    const others: Geometry['parts'][] = [
      [{ shape: 'point', at: [1, 1] }],
      [{ shape: 'polyline', pts: outline }],
      [
        { shape: 'polygon', rings: [outline] },
        { shape: 'polygon', rings: [outline] },
      ],
      [
        {
          shape: 'polygon',
          rings: [
            outline,
            [
              [250, 150],
              [280, 150],
              [280, 200],
            ],
          ],
        },
      ],
    ];

    for (const parts of others) {
      expect(regionOf({ name: 'It', geometry: { format: FORMAT, parts } }, sheet).kind).toBe(
        'sheet',
      );
    }
  });

  it('offers a result the API will take, and no other', () => {
    const square = (x: number): Geometry['parts'][number] => ({
      shape: 'polygon',
      rings: [
        [
          [x, 0],
          [x + 5, 0],
          [x + 5, 5],
          [x, 5],
        ],
      ],
    });

    expect(fits({ format: FORMAT, parts: [square(0), square(10)] }, hints)).toEqual({ ok: true });
    expect(fits(null, hints)).toMatchObject({ ok: false });
    expect(fits({ format: FORMAT, parts: [] }, hints)).toEqual({
      ok: false,
      why: 'There is nothing to draw with these options. Try another seed.',
    });
  });

  it('names the limit a result is over and what to change', () => {
    const many: Geometry = {
      format: FORMAT,
      parts: Array.from({ length: 300 }, (_, i) => ({
        shape: 'point' as const,
        at: [i, 0] as const,
      })),
    };

    expect(fits(many, hints)).toEqual({
      ok: false,
      why: 'This is 300 pieces, and a drawing holds 256. Raise Minimum area.',
    });

    const long: Geometry = {
      format: FORMAT,
      parts: [
        { shape: 'polyline', pts: Array.from({ length: 2001 }, (_, i) => [i, i % 2] as const) },
      ],
    };

    expect(fits(long, hints)).toEqual({
      ok: false,
      why: 'This has more than the 2000 points a drawing holds. Raise Smoothing.',
    });

    const heavy: Geometry = {
      format: FORMAT,
      parts: [
        {
          shape: 'polyline',
          pts: Array.from(
            { length: 1990 },
            (_, i) => [1234567.123456 + i, -7654321.654321 - i] as const,
          ),
        },
      ],
    };

    expect(fits(heavy, hints)).toEqual({
      ok: false,
      why: 'This is larger than a drawing may be. Lower Size.',
    });

    const bowTie: Geometry = {
      format: FORMAT,
      parts: [
        {
          shape: 'polygon',
          rings: [
            [
              [0, 0],
              [10, 10],
              [10, 0],
              [0, 10],
            ],
          ],
        },
      ],
    };

    expect(fits(bowTie, hints)).toEqual({
      ok: false,
      why: 'One of its areas is not a shape the Map can hold. Try another seed.',
    });
  });

  it('names the history step of an Apply: the tool, the seed, how much and where', () => {
    expect(
      stepName('a cave system', 4821, counted(6, 'cave', 'caves'), regionOf(null, sheet)),
    ).toBe('Drew a cave system, seed 4821: 6 caves in the whole sheet');
    expect(counted(1, 'cave', 'caves')).toBe('1 cave');
    expect(counted(0, 'cave', 'caves')).toBe('0 caves');
  });
});
