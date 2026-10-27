import { readFileSync } from 'node:fs';
import { describe, expect, it } from 'vitest';
import { cssProblems } from '../../../tools/brand/css-guard.mjs';

describe('the stylesheet', () => {
  it('uses only brand tokens (ADR 0322)', () => {
    const css = readFileSync(new URL('../src/map.css', import.meta.url), 'utf8');

    expect(cssProblems(css)).toEqual([]);
  });

  it('has a rule for every class the default theme and the layout write', () => {
    const css = readFileSync(new URL('../src/map.css', import.meta.url), 'utf8');
    const source = ['themes/default.ts', 'themes/plain.ts', 'layout.ts', 'edit.ts']
      .map((file) => readFileSync(new URL(`../src/${file}`, import.meta.url), 'utf8'))
      .join('\n');
    const used = new Set(source.match(/\bm-[a-z-]+/g) ?? []);

    expect(used.size).toBeGreaterThan(20);

    for (const cls of used) expect(css, cls).toContain(`.${cls}`);
  });
});
