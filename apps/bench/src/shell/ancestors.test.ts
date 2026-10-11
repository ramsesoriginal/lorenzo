import { describe, expect, it } from 'vitest';
import type { EntrySummary } from '../core/transport';
import { ancestorPath, childrenOf } from './ancestors';

const e = (id: string, name: string, parentIds: string[] = []): EntrySummary => ({
  id,
  name,
  kinds: [],
  parentIds,
});
const entries = [
  e('item', 'Item'),
  e('weapon', 'Weapon', ['item']),
  e('sword', 'Sword', ['weapon']),
  e('long', 'Longsword', ['sword']),
  e('flame', 'Flaming Sword', ['sword', 'magic']),
  e('magic', 'Magic', ['item']),
  e('loop-a', 'A', ['loop-b']),
  e('loop-b', 'B', ['loop-a']),
];

describe('ancestorPath', () => {
  it('lists what an entry inherits from, farthest first', () => {
    expect(ancestorPath(entries, 'long').map((x) => x.name)).toEqual(['Item', 'Weapon', 'Sword']);
  });

  it('follows the first parent when there are several', () => {
    expect(ancestorPath(entries, 'flame').map((x) => x.name)).toEqual(['Item', 'Weapon', 'Sword']);
  });

  it('is empty for an entry with no parents, or one that is not there', () => {
    expect(ancestorPath(entries, 'item')).toEqual([]);
    expect(ancestorPath(entries, 'nothing')).toEqual([]);
  });

  it('stops at a loop', () => {
    expect(ancestorPath(entries, 'loop-a').map((x) => x.id)).toEqual(['loop-b']);
  });
});

describe('childrenOf', () => {
  it('lists the entries that name it as a parent, by name', () => {
    expect(childrenOf(entries, 'sword').map((x) => x.name)).toEqual(['Flaming Sword', 'Longsword']);
  });
});
