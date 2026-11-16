// The generators of the registry (ADR 0475), each as what the editor needs of it: what it is
// called in a history step, how it is run from its options, and what to change when a result is
// over a limit. A generator itself is a pure function in a file of its own.
import type { Geometry } from '@lorenzo/map-renderer';
import { caveSystem } from './cave';
import { counted, type Hints, type Region } from './generator';
import { CAVE_DENSITY, CAVE_PASSES, CAVE_SIZE, CAVE_SMALLEST, type NumberOption } from './tools';

export type GeneratorDef = {
  /** In a history step: "a cave system". */
  what: string;
  /** The result for a region, a seed and the options as they are set. */
  run(
    region: Region,
    seed: number,
    number: (option: NumberOption) => number,
  ): { geometry: Geometry | null; count: string };
  hints: Hints;
};

export const GENERATORS: Record<string, GeneratorDef> = {
  'cave-system': {
    what: 'a cave system',
    run(region, seed, number) {
      const made = caveSystem(
        region,
        {
          size: number(CAVE_SIZE),
          density: number(CAVE_DENSITY),
          passes: number(CAVE_PASSES),
          smallest: number(CAVE_SMALLEST),
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
};
