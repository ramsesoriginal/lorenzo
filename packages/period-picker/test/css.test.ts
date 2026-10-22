import { readFileSync } from 'node:fs';
import { describe, expect, it } from 'vitest';
import { cssProblems } from '../../../tools/brand/css-guard.mjs';

describe('the stylesheet', () => {
  it('uses only brand tokens (ADR 0322)', () => {
    const css = readFileSync(new URL('../src/period-picker.css', import.meta.url), 'utf8');

    expect(cssProblems(css)).toEqual([]);
  });
});
