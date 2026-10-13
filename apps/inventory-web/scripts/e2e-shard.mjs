// Which spec files one CI shard of the end-to-end suite runs (ADR 0148).
//
// Playwright's own `--shard` splits by the number of tests, and these differ a hundredfold in what
// they take (a drag on the board against a page that only has to load), so one shard took 239
// worker-seconds and another 108. This splits by recorded duration instead: the spec files, the
// heaviest first, each to the shard that has the least so far, which is the same on every runner.
//
//   node scripts/e2e-shard.mjs 2/4              the files of shard 2 of 4, separated by spaces
//   node scripts/e2e-shard.mjs --weights r.json  the weights a Playwright JSON report (`--reporter=json`)
//                                                records, to paste into tests/e2e/shard-weights.json
//
// A spec file that has no weight yet (a new one) counts as the median of the others, so it is run
// by exactly one shard until someone records it.
import { readdirSync, readFileSync } from 'node:fs';
import { basename, dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const APP = join(dirname(fileURLToPath(import.meta.url)), '..');
const SPECS = join(APP, 'tests', 'e2e');

/** The spec files of a directory, by name. */
export function specFiles(directory = SPECS) {
  return readdirSync(directory)
    .filter((name) => name.endsWith('.spec.ts'))
    .sort();
}

/** The median of the recorded weights, for a spec file that has none. */
function fallbackWeight(weights) {
  const recorded = Object.values(weights).sort((a, b) => a - b);
  return recorded.length === 0 ? 1 : recorded[Math.floor(recorded.length / 2)];
}

/** `total` lists of spec files, balanced by weight: the same for the same files and weights. */
export function shardsOf(files, weights, total) {
  const fallback = fallbackWeight(weights);
  const weight = (name) => weights[name] ?? fallback;
  const shards = Array.from({ length: total }, () => ({ load: 0, files: [] }));
  const heaviestFirst = [...files].sort((a, b) => weight(b) - weight(a) || a.localeCompare(b));
  for (const name of heaviestFirst) {
    const lightest = shards.reduce((least, shard) => (shard.load < least.load ? shard : least));
    lightest.files.push(name);
    lightest.load += weight(name);
  }
  return shards.map((shard) => shard.files.sort());
}

/** Seconds of worker time per spec file in a Playwright JSON report. */
export function recordedWeights(report) {
  const seconds = {};
  const visit = (suite) => {
    for (const spec of suite.specs ?? []) {
      const name = basename(spec.file);
      for (const test of spec.tests ?? []) {
        for (const result of test.results ?? []) {
          seconds[name] = (seconds[name] ?? 0) + result.duration / 1000;
        }
      }
    }
    for (const child of suite.suites ?? []) visit(child);
  };
  for (const suite of report.suites ?? []) visit(suite);
  return Object.fromEntries(
    Object.entries(seconds)
      .map(([name, value]) => [name, Math.round(value)])
      .sort(([a], [b]) => a.localeCompare(b)),
  );
}

if (process.argv[1] === fileURLToPath(import.meta.url)) {
  const [first, second] = process.argv.slice(2);
  if (first === '--weights') {
    console.log(JSON.stringify(recordedWeights(JSON.parse(readFileSync(second, 'utf8'))), null, 2));
  } else {
    const [current, total] = (first ?? '').split('/').map(Number);
    if (!(current >= 1 && total >= current)) {
      console.error(
        'usage: e2e-shard.mjs <current>/<total>  or  e2e-shard.mjs --weights <report.json>',
      );
      process.exit(2);
    }
    const weights = JSON.parse(readFileSync(join(SPECS, 'shard-weights.json'), 'utf8'));
    const files = shardsOf(specFiles(), weights, total)[current - 1];
    console.log(files.map((name) => `tests/e2e/${name}`).join(' '));
  }
}
