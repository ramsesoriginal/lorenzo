import { expect, it } from 'vitest';
import { blockRanges, parse } from '../src';

const source = [
  '# Title', // 0
  '', // 1
  'First paragraph', // 2
  'continues here.', // 3
  '', // 4
  '- one', // 5
  '- two', // 6
  '', // 7
  '```', // 8
  'code', // 9
  '', // 10 (inside the fence)
  '```', // 11
  '',
  '> quoted', // 13
  '',
  '[^a]: A note.', // 15
  '',
  '| a | b |', // 17
  '| - | - |',
  '| 1 | 2 |', // 19
].join('\n');

it('says which lines each top-level block covers', () => {
  expect(blockRanges(source)).toEqual([
    { type: 'heading', start: 0, end: 1 },
    { type: 'paragraph', start: 2, end: 4 },
    { type: 'list', start: 5, end: 7 },
    { type: 'code', start: 8, end: 12 },
    { type: 'blockquote', start: 13, end: 14 },
    { type: 'definition', start: 15, end: 16 },
    { type: 'table', start: 17, end: 20 },
  ]);
});

it('agrees with parse about how many blocks there are', () => {
  const real = blockRanges(source).filter((r) => r.type !== 'definition');
  expect(real).toHaveLength(parse(source).children.length);
});

it('reads CRLF as LF, and has nothing for an empty source', () => {
  expect(blockRanges('a\r\n\r\nb')).toEqual([
    { type: 'paragraph', start: 0, end: 1 },
    { type: 'paragraph', start: 2, end: 3 },
  ]);
  expect(blockRanges('')).toEqual([]);
});

it('does not disturb a later parse', () => {
  const before = JSON.stringify(parse(source));
  blockRanges(source);
  expect(JSON.stringify(parse(source))).toBe(before);
});
