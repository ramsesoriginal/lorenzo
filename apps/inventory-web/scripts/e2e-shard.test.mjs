import { readFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { describe, expect, it } from 'vitest';
import { recordedWeights, shardsOf, specFiles } from './e2e-shard.mjs';

const weights = JSON.parse(
  readFileSync(
    join(dirname(fileURLToPath(import.meta.url)), '..', 'tests', 'e2e', 'shard-weights.json'),
    'utf8',
  ),
);
const files = specFiles();

describe('the shards of the end-to-end suite', () => {
  it('give every spec file to exactly one shard, however many there are', () => {
    for (const total of [1, 2, 3, 4, 5, 6]) {
      const shards = shardsOf(files, weights, total);
      expect(shards).toHaveLength(total);
      expect(shards.flat().sort()).toEqual(files);
    }
  });

  it('are the same every time', () => {
    expect(shardsOf(files, weights, 4)).toEqual(shardsOf([...files].reverse(), weights, 4));
  });

  it('give a spec file that has no weight to a shard anyway', () => {
    const withNew = [...files, 'a-new-one.spec.ts'];
    expect(shardsOf(withNew, weights, 4).flat().sort()).toEqual(withNew.sort());
  });

  it('weigh every spec file there is, so that none is guessed', () => {
    expect(files.filter((name) => weights[name] === undefined)).toEqual([]);
    expect(Object.keys(weights).filter((name) => !files.includes(name))).toEqual([]);
  });

  it('are balanced by recorded weight: the heaviest of four is within a third of the lightest', () => {
    const loads = shardsOf(files, weights, 4).map((shard) =>
      shard.reduce((sum, name) => sum + weights[name], 0),
    );
    expect(Math.max(...loads) / Math.min(...loads)).toBeLessThan(1.34);
  });
});

describe('the weights a Playwright report records', () => {
  it('are seconds of worker time per spec file, over every nested suite', () => {
    const report = {
      suites: [
        {
          specs: [],
          suites: [
            {
              specs: [
                {
                  file: 'a.spec.ts',
                  tests: [{ results: [{ duration: 1500 }, { duration: 500 }] }],
                },
                { file: 'b.spec.ts', tests: [{ results: [{ duration: 4000 }] }] },
              ],
            },
          ],
        },
        {
          file: 'a.spec.ts',
          specs: [{ file: 'a.spec.ts', tests: [{ results: [{ duration: 1000 }] }] }],
        },
      ],
    };
    expect(recordedWeights(report)).toEqual({ 'a.spec.ts': 3, 'b.spec.ts': 4 });
  });
});
