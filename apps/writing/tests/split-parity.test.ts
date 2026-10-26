import { readFileSync } from 'node:fs';
import { parse } from '@lorenzo/lorenzoscript';
import { describe, expect, it } from 'vitest';

const cases: { name: string; marked: string; allowed: boolean }[] = JSON.parse(
  readFileSync(new URL('../../api/tests/fixtures/manuscript-splits.json', import.meta.url), 'utf8'),
);

describe('safe paragraph splits retain the canonical LorenzoScript parse', () => {
  for (const example of cases.filter((item) => item.allowed)) {
    it(example.name, () => {
      const [left, right] = example.marked.split('<SPLIT>');
      const original = parse(left + right);
      const first = parse(left);
      const second = parse(right);
      expect([...first.children, ...second.children]).toEqual(original.children);
      expect([...first.footnotes, ...second.footnotes]).toEqual(original.footnotes);
      expect([...first.abbreviations, ...second.abbreviations]).toEqual(original.abbreviations);
    });
  }
});
