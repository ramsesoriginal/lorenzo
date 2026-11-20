import { expect, test } from 'vitest';
import { complete, completionContext } from '../src/complete';

test('finds the words typed after the last [[ before the caret', () => {
  expect(completionContext('See [[Ash', 9)).toEqual({ start: 6, query: 'Ash' });
  expect(completionContext('See [[Ash]] and', 15)).toBeNull();
  expect(completionContext('See [[Ash\nmore', 14)).toBeNull();
  expect(completionContext('no link', 7)).toBeNull();
});

test('writes the chosen name and closes the link, once', () => {
  expect(complete('See [[As', 8, 'Ashfang')).toEqual({ text: 'See [[Ashfang]]', caret: 15 });
  expect(complete('See [[As]] x', 8, 'Ashfang')).toEqual({ text: 'See [[Ashfang]] x', caret: 15 });
});
