import { describe, expect, it, vi } from 'vitest';

vi.mock('./items', () => ({ getCatalogItem: vi.fn(), getItemAncestry: vi.fn() }));

import { parentsOf } from './ancestryTree';

const nodes = (entries: Record<string, string[]>) =>
  new Map(Object.entries(entries).map(([id, parentIds]) => [id, { name: id, parentIds }]));

describe('parentsOf', () => {
  it('lists the parents of an item, each with its own', () => {
    const tree = parentsOf(
      'ornate',
      nodes({ ornate: ['spellbook'], spellbook: ['book'], book: [] }),
    );

    expect(tree).toEqual([
      { id: 'spellbook', name: 'spellbook', parents: [{ id: 'book', name: 'book', parents: [] }] },
    ]);
  });

  it('shows an item twice when two of its parents share a parent', () => {
    const tree = parentsOf('d', nodes({ d: ['b', 'c'], b: ['a'], c: ['a'], a: [] }));

    expect(tree.map((parent) => parent.parents.map((p) => p.name))).toEqual([['a'], ['a']]);
  });

  it("leaves out a parent that isn't known, and stops at a cycle", () => {
    expect(parentsOf('x', nodes({ x: ['gone'] }))).toEqual([]);
    expect(parentsOf('a', nodes({ a: ['b'], b: ['a'] }))).toEqual([
      { id: 'b', name: 'b', parents: [{ id: 'a', name: 'a', parents: [] }] },
    ]);
  });
});
