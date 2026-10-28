import { describe, expect, it } from 'vitest';
import { seenFrom, wayWords } from '../../src/lib/connection-words';

const stub = (id: string, name: string) => ({ id, name, slug: null, kinds: ['location'] });
const road = { end_a: stub('a', 'Hollowmere'), end_b: stub('b', 'Dunmere'), one_way: false };
const portal = { ...road, one_way: true };

describe('what a connection says from one end', () => {
  it('says a way both ways from either end', () => {
    expect(seenFrom(road, 'a')).toMatchObject({ way: 'both', other: { name: 'Dunmere' } });
    expect(seenFrom(road, 'b')).toMatchObject({ way: 'both', other: { name: 'Hollowmere' } });
    expect(wayWords('both', 'Dunmere')).toBe('to Dunmere');
  });

  it('reverses a one-way connection between its ends', () => {
    expect(seenFrom(portal, 'a')).toMatchObject({ way: 'out', other: { name: 'Dunmere' } });
    expect(seenFrom(portal, 'b')).toMatchObject({ way: 'in', other: { name: 'Hollowmere' } });
    expect(wayWords('out', 'Dunmere')).toBe('one way to Dunmere');
    expect(wayWords('in', 'Hollowmere')).toBe('one way from Hollowmere');
  });
});
