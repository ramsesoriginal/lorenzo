// The generators of the registry (ADR 0475), each as what the editor needs of it: what it is
// called in a history step, how it is run from its options, and what to change when a result is
// over a limit. A generator itself is a pure function in a file of its own.
import type { Geometry } from '@lorenzo/map-renderer';
import { caveSystem } from './cave';
import { fill } from './fill';
import { counted, type Hints, type Region } from './generator';
import { unitOf } from './height';
import {
  CAVE_DENSITY,
  CAVE_PASSES,
  CAVE_SIZE,
  CAVE_SMALLEST,
  FILL_FIRST,
  FILL_LEVEL,
  FILL_LINES,
  FILL_SCALE,
  FILL_SMALLEST,
  FILL_STEP,
  type NumberOption,
  type TextOption,
  UNIT,
} from './tools';

/** The options as they are set, read by a generator. A number with no value yet is null. */
export type Options = {
  number(option: NumberOption): number | null;
  text(option: TextOption): string;
};

export type GeneratorDef = {
  /** In a history step: "a cave system". */
  what: string;
  /**
   * The result for a region, a seed and the options as they are set. `needs` says what a person
   * must still give before it can be applied; the result is previewed all the same.
   */
  run(
    region: Region,
    seed: number,
    set: Options,
  ): { geometry: Geometry | null; count: string; needs?: string };
  hints: Hints;
};

export const GENERATORS: Record<string, GeneratorDef> = {
  'cave-system': {
    what: 'a cave system',
    run(region, seed, set) {
      const made = caveSystem(
        region,
        {
          size: set.number(CAVE_SIZE) ?? 0,
          density: set.number(CAVE_DENSITY) ?? 0,
          passes: set.number(CAVE_PASSES) ?? 0,
          smallest: set.number(CAVE_SMALLEST) ?? 0,
        },
        seed,
      );

      return { geometry: made.geometry, count: counted(made.caves, 'cave', 'caves') };
    },
    hints: {
      vertices: 'Lower Size, or raise Passes.',
      parts: 'Raise Smallest cave.',
      bytes: 'Lower Size.',
      shape: 'Roll another seed.',
    },
  },
  'marching-squares': {
    what: 'a fill',
    run(region, seed, set) {
      const made = fill(
        region,
        {
          scale: set.number(FILL_SCALE) ?? 0,
          level: set.number(FILL_LEVEL) ?? 0,
          smallest: set.number(FILL_SMALLEST) ?? 0,
          lines: set.number(FILL_LINES) ?? 0,
          first: set.number(FILL_FIRST),
          step: set.number(FILL_STEP),
          unit: unitOf(set.text(UNIT)),
        },
        seed,
      );
      const areas = counted(made.areas, 'area', 'areas');

      return {
        geometry: made.geometry,
        count:
          made.lines > 0
            ? `${areas} and ${counted(made.lines, 'height line', 'height lines')}`
            : areas,
        ...(made.needsHeights
          ? {
              needs:
                'Height lines need a first height, a step and a unit: give all three, or set Height lines to 0.',
            }
          : {}),
      };
    },
    hints: {
      vertices: 'Lower Height lines, or raise Scale.',
      parts: 'Raise Smallest area, or lower Height lines.',
      bytes: 'Lower Height lines.',
      shape: 'Roll another seed.',
    },
  },
};
