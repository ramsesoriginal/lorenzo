import { readFileSync } from 'node:fs';
import { describe, expect, it } from 'vitest';
import { cssProblems } from '../../../tools/brand/css-guard.mjs';

describe('the stylesheet', () => {
  it('uses only brand tokens (ADR 0322)', () => {
    const css = readFileSync(new URL('../src/entry-preview.css', import.meta.url), 'utf8');

    expect(cssProblems(css)).toEqual([]);
  });

  it('has a rule for every class the card is drawn with', () => {
    const css = readFileSync(new URL('../src/entry-preview.css', import.meta.url), 'utf8');
    const source = readFileSync(new URL('../src/install.ts', import.meta.url), 'utf8');
    const used = new Set(source.match(/'entry-preview(?:-[a-z]+)?'/g) ?? []);

    expect(used.size).toBeGreaterThan(4);

    for (const quoted of used) {
      const cls = quoted.slice(1, -1);

      expect(css, cls).toContain(`.${cls}`);
    }
  });
});
