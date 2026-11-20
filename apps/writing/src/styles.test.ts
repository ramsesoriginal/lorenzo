import { readFileSync } from 'node:fs';
import { expect, test } from 'vitest';
import { cssProblems } from '../../../tools/brand/css-guard.mjs';

// ADR 0322: the app's own sheet uses the brand's tokens and nothing else.
test('the app stylesheet uses only the brand tokens', () => {
  const css = readFileSync(new URL('./styles/app.css', import.meta.url), 'utf8');

  expect(cssProblems(css)).toEqual([]);
});
