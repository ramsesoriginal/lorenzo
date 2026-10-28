import { describe, expect, it } from 'vitest';
import { amount, legWords, routeWords, straightWords } from '../../src/lib/distance-words';

const leg = (name: string, start: string, end: string, length: number | null) => ({
  connection: { name },
  start: { name: start },
  end: { name: end },
  length,
});

describe('what a distance says', () => {
  it('writes a number as given, with the unit the author chose', () => {
    expect(amount(40, 'miles')).toBe('40 miles');
    expect(amount(18.027756, 'feet')).toBe('18.027756 feet');
    expect(amount(1234.5, 'km')).toBe('1,234.5 km');
    expect(amount(3, null)).toBe('3');
  });

  it('says a straight line and how a grid counted its diagonals', () => {
    const answer = {
      mode: 'straight',
      state: 'known',
      value: 20,
      unit: 'feet',
      route: [],
    } as const;

    expect(straightWords(answer)).toBe('Straight line: 20 feet.');
    expect(straightWords(answer, 'alternating')).toBe(
      'Straight line: 20 feet, counting diagonals by the alternating rule.',
    );
  });

  it('says the same place is 0, as it is, and never writes an unknown as zero', () => {
    expect(
      straightWords({ mode: 'straight', state: 'known', value: 0, unit: 'miles', route: [] }),
    ).toBe('Straight line: 0 miles.');
    const unknown = straightWords({
      mode: 'straight',
      state: 'unknown',
      reason: 'the Map has no scale',
      value: null,
      route: [],
    });

    expect(unknown).toBe('Straight line: the Map has no scale.');
    expect(unknown).not.toMatch(/\b0\b/);
  });

  it('says a route over its legs', () => {
    const route = [leg('First', 'A', 'B', 10), leg('Second', 'B', 'C', 42)];

    expect(routeWords({ mode: 'route', state: 'known', value: 52, unit: 'miles', route })).toBe(
      'By the connections: 52 miles, over 2 legs.',
    );
    expect(
      routeWords({
        mode: 'route',
        state: 'known',
        value: 5,
        unit: 'miles',
        route: [leg('Only', 'A', 'B', 5)],
      }),
    ).toBe('By the connections: 5 miles, over 1 leg.');
    expect(legWords(route[0] as never, 'miles')).toBe('First, A to B: 10 miles');
  });

  it('says what a partial route lacks and marks the legs with no length', () => {
    const route = [leg('Known', 'A', 'B', 12), leg('Rough', 'B', 'C', null)];

    expect(
      routeWords({
        mode: 'route',
        state: 'partial',
        at_least: 12,
        unmeasured_legs: 1,
        unit: 'miles',
        route,
      }),
    ).toBe('By the connections: at least 12 miles; 1 of 2 legs have no length.');
    expect(legWords(route[1] as never, 'miles')).toBe('Rough, B to C: no length');
  });

  it("gives the API's own reason when there is no route or the search was cut off", () => {
    expect(
      routeWords({ mode: 'route', state: 'unknown', reason: 'no known route', route: [] }),
    ).toBe('By the connections: no known route.');
    expect(
      routeWords({
        mode: 'route',
        state: 'limit_reached',
        reason: 'too much to search',
        route: [],
      }),
    ).toBe('By the connections: too much to search.');
  });
});
