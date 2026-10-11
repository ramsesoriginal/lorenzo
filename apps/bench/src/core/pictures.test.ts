import { describe, expect, it } from 'vitest';
import { pictureSource } from './pictures';

describe('pictureSource', () => {
  const parents: Record<string, string[]> = { c: ['b'], b: ['a', 'x'], a: [], x: [] };
  const source = (urls: Record<string, string | null | undefined>, id = 'c') =>
    pictureSource(
      (e) => parents[e] ?? [],
      (e) => urls[e],
      id,
    );
  it("is the entry's own when it has one", () => {
    expect(source({ c: 'u', a: 'v' })).toEqual({ kind: 'own' });
  });
  it('is the nearest one above, first parent first', () => {
    expect(source({ c: null, b: null, a: null, x: 'u' })).toEqual({ kind: 'inherited', from: 'x' });
    expect(source({ c: null, b: 'u', a: 'v' })).toEqual({ kind: 'inherited', from: 'b' });
  });
  it('is none when all are read and none has one', () => {
    expect(source({ c: null, b: null, a: null, x: null })).toEqual({ kind: 'none' });
  });
  it('is unknown while something above is unread', () => {
    expect(source({ c: null, b: null, a: null })).toEqual({ kind: 'unknown' });
  });
});
