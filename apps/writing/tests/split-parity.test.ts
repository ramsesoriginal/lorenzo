import { readFileSync } from 'node:fs';
import { parse } from '@lorenzo/lorenzoscript';
import { describe, expect, it } from 'vitest';

// Python checks the entire offered set against these offsets. Check every offered
// boundary here, including safe alternatives in otherwise rejected examples.
const cases: { name: string; marked: string; points: number[] }[] = JSON.parse(
  readFileSync(new URL('../../api/tests/fixtures/manuscript-splits.json', import.meta.url), 'utf8'),
);

describe('safe section splits retain the canonical LorenzoScript parse', () => {
  for (const example of cases) {
    for (const offset of example.points) {
      it(`${example.name} at ${offset}`, () => {
        const source = example.marked.replace('<SPLIT>', '');
        const characters = Array.from(source);
        const left = characters.slice(0, offset).join('');
        const right = characters.slice(offset).join('');
        expect(left + right).toBe(source);
        const original = parse(source);
        const first = parse(left);
        const second = parse(right);
        expect([...first.children, ...second.children]).toEqual(original.children);
        expect([...first.footnotes, ...second.footnotes]).toEqual(original.footnotes);
        expect([...first.abbreviations, ...second.abbreviations]).toEqual(original.abbreviations);
      });
    }
  }
});
