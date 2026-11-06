import { expect, test } from 'vitest';
import { planStarter, STANDINGS, TYPES } from '../../src/lib/starter';
import { typeTree } from '../../src/lib/types-tree';

const row = (id: string, name: string, parents: string[] = []) => ({
  id,
  name,
  parent_ids: parents,
});

test('types hang under the types they are kinds of, each family in name order', () => {
  const tree = typeTree([
    row('c', 'Child', ['p']),
    row('p', 'Parent'),
    row('o', 'Other'),
    row('g', 'Grandchild', ['c']),
  ]);
  expect(tree.map((t) => [t.row.name, t.depth])).toEqual([
    ['Parent', 0],
    ['Child', 1],
    ['Grandchild', 2],
    ['Other', 0],
  ]);
});

test('a type whose parent is not shown is a root, and a loop cannot hang the screen', () => {
  expect(typeTree([row('a', 'A', ['gone'])]).map((t) => t.depth)).toEqual([0]);
  expect(typeTree([row('a', 'A', ['b']), row('b', 'B', ['a'])])).toEqual([]);
});

test('the starter adds only what the library lacks and each type comes after its parent', () => {
  const full = planStarter({ statNames: new Set(), entryNames: new Set() });
  expect(full.types).toHaveLength(TYPES.length);
  expect(full.standings).toHaveLength(STANDINGS.length);
  const seen = new Set<string>();
  for (const type of TYPES) {
    if (type.parent) expect(seen.has(type.parent), type.name).toBe(true);
    seen.add(type.name);
  }
  const partial = planStarter({
    statNames: new Set(['Honor']),
    entryNames: new Set(['Parent of', 'Family']),
  });
  expect(partial.standings.map((s) => s.name)).not.toContain('Honor');
  expect(partial.types.map((t) => t.name)).not.toContain('Parent of');
});

test('the starter sets no audience and every verb pair is complete', () => {
  for (const type of TYPES) {
    expect(Boolean(type.readsAs), type.name).toBe(Boolean(type.readsAsBack));
  }
  for (const standing of STANDINGS) expect(standing.min).toBeLessThan(standing.max);
});
