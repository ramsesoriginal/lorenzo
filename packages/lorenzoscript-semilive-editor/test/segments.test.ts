import { expect, it } from 'vitest';
import { caretInSource, segmentsOf } from '../src/segments';

it('gives each top-level block its characters, blank lines left out', () => {
  const source = 'One\nline.\n\n- a\n- b\n\n[^1]: Note.';
  const segs = segmentsOf(source);
  expect(segs.map((s) => [s.type, source.slice(s.from, s.to)])).toEqual([
    ['paragraph', 'One\nline.'],
    ['list', '- a\n- b'],
    ['definition', '[^1]: Note.'],
  ]);
});

it('has no blocks for no text', () => {
  expect(segmentsOf('')).toEqual([]);
});

it('puts a click in the source near the word that was clicked', () => {
  expect(caretInSource('Hello **brave** world', 'brave', 2)).toBe(10);
  expect(caretInSource('Hello world', 'zzz', 0, 0.5)).toBe(6);
});
