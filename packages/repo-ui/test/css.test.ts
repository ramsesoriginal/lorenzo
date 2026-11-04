import { readFileSync } from 'node:fs';
import { describe, expect, it } from 'vitest';
import { cssProblems } from '../../../tools/brand/css-guard.mjs';

const css = readFileSync(new URL('../src/repo-ui.css', import.meta.url), 'utf8');

describe('the stylesheet', () => {
  it('uses only brand tokens (ADR 0322)', () => {
    expect(cssProblems(css)).toEqual([]);
  });

  it('has a rule for every class the review is drawn with', () => {
    const source = readFileSync(new URL('../src/review.ts', import.meta.url), 'utf8');
    const used = new Set(source.match(/'repo-review(?:-[a-z]+)?'/g) ?? []);

    expect(used.size).toBeGreaterThan(8);

    for (const quoted of used) {
      const cls = quoted.slice(1, -1);

      expect(css, cls).toContain(`.${cls}`);
    }
  });

  it('stacks the values and enlarges what is pressed at phone width and for a coarse pointer', () => {
    expect(css).toMatch(
      /@media \(max-width: 720px\) \{\s*\.repo-review-values \{\s*grid-template-columns: minmax\(0, 1fr\)/,
    );
    expect(css).toMatch(
      /@media \(max-width: 720px\), \(pointer: coarse\) \{[^}]*min-height: var\(--target-min\)/,
    );
  });

  it('shows focus on the controls', () => {
    expect(css).toContain('.repo-review-action:focus-visible');
    expect(css).toContain('var(--focus-ring)');
  });
});
