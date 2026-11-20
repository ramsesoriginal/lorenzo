import { expect, test } from 'vitest';
import { findAll, replaceMatches } from '../src/find';

test('finds every match, whatever the case unless asked', () => {
  expect(findAll('Ash ash ASH', 'ash')).toEqual([
    [0, 3],
    [4, 7],
    [8, 11],
  ]);
  expect(findAll('Ash ash ASH', 'ash', { caseSensitive: true })).toEqual([[4, 7]]);
  expect(findAll('anything', '')).toEqual([]);
});

test('a whole word does not match inside another', () => {
  expect(findAll('ash ashes trash ash.', 'ash', { wholeWord: true })).toEqual([
    [0, 3],
    [16, 19],
  ]);
});

test('replaces the first match from a place, or all', () => {
  expect(replaceMatches('a b a b', 'a', 'X', { once: true, from: 1 })).toEqual({
    text: 'a b X b',
    count: 1,
    end: 5,
  });
  expect(replaceMatches('a b a b', 'b', 'YY')).toEqual({ text: 'a YY a YY', count: 2, end: 4 });
});
