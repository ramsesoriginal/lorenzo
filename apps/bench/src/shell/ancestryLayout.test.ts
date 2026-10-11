import { describe, expect, it } from 'vitest';
import type { EntrySummary } from '../core/transport';
import { ancestryLayout } from './ancestryLayout';

const e = (id: string, name: string, parentIds: string[] = []): EntrySummary => ({
  id,
  name,
  kinds: [],
  parentIds,
});
const family = [
  e('weapon', 'Weapon'),
  e('sword', 'Sword', ['weapon']),
  e('dagger', 'Dagger', ['weapon']),
  e('long', 'Longsword', ['sword']),
  e('flame', 'Flaming Sword', ['sword']),
  e('ash', 'Ashfang', ['flame']),
];
type L = ReturnType<typeof ancestryLayout>;
const y = (l: L, id: string) => l.nodes.find((n) => n.id === id)?.y ?? Number.NaN;

describe('ancestryLayout', () => {
  it('puts what an entry inherits from above it and what inherits from it below', () => {
    const l = ancestryLayout(family, 'flame');
    expect(y(l, 'weapon')).toBeLessThan(y(l, 'sword'));
    expect(y(l, 'sword')).toBeLessThan(y(l, 'flame'));
    expect(y(l, 'flame')).toBeLessThan(y(l, 'ash'));
  });

  it('shows its line and nothing else: no siblings, no relatives', () => {
    const l = ancestryLayout(family, 'flame');
    expect(l.nodes.map((n) => n.id).sort()).toEqual(['ash', 'flame', 'sword', 'weapon'].sort());
  });

  it('marks the entry, and draws an edge from each that inherits to what it inherits from', () => {
    const l = ancestryLayout(family, 'flame');
    expect(l.nodes.filter((n) => n.selected).map((n) => n.id)).toEqual(['flame']);
    expect(l.edges).toContainEqual({ from: 'flame', to: 'sword' });
    expect(l.edges).toContainEqual({ from: 'ash', to: 'flame' });
  });

  it('sits an entry below all of its parents when they are at different heights', () => {
    const l = ancestryLayout([e('a', 'A'), e('b', 'B', ['a']), e('c', 'C', ['a', 'b'])], 'c');
    expect(y(l, 'c')).toBeGreaterThan(y(l, 'b'));
    expect(y(l, 'b')).toBeGreaterThan(y(l, 'a'));
  });

  it('keeps nodes in a row from overlapping, inside the width', () => {
    const l = ancestryLayout(family, 'flame');
    const row = ancestryLayout(
      [e('p', 'P'), e('a', 'Alpha', ['p']), e('b', 'Beta', ['p']), e('c', 'Gamma', ['p'])],
      'p',
    )
      .nodes.filter((n) => n.id !== 'p')
      .sort((a, b) => a.x - b.x);
    for (let i = 1; i < row.length; i++) {
      const before = row[i - 1];
      expect(row[i]?.x ?? 0).toBeGreaterThanOrEqual((before?.x ?? 0) + (before?.w ?? 0));
    }
    for (const n of l.nodes) expect(n.x + n.w).toBeLessThanOrEqual(l.width);
    expect(row.length).toBe(3);
  });

  it('counts the children that do not fit in a row', () => {
    const kids = Array.from({ length: 9 }, (_, i) => e(`k${i}`, `Kid ${i}`, ['p']));
    const l = ancestryLayout([e('p', 'Parent'), ...kids], 'p');
    expect(l.nodes.filter((n) => n.id.startsWith('k'))).toHaveLength(6);
    expect(l.hidden).toBe(3);
  });

  it('stops at a loop, and answers nothing for an entry that is not there', () => {
    const l = ancestryLayout([e('a', 'A', ['b']), e('b', 'B', ['a'])], 'a');
    expect(l.nodes.length).toBeGreaterThan(0);
    expect(ancestryLayout(family, 'nothing').nodes).toEqual([]);
  });
});
