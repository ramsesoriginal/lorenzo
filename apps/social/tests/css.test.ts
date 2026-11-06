import { readFileSync } from 'node:fs';
import { expect, test } from 'vitest';
import { cssProblems } from '../../../tools/brand/css-guard.mjs';

// ADR 0322: the app's own sheet uses the brand's tokens and nothing else. An undefined var()
// silently becomes nothing (`--radius-md` once left every panel square), and a literal colour,
// font, shadow or breakpoint is a second source of truth.
test('the app stylesheet uses only the brand tokens', () => {
  const css = readFileSync(new URL('../src/styles/app.css', import.meta.url), 'utf8');

  expect(cssProblems(css)).toEqual([]);
});
