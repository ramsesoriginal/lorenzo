import { describe, expect, it } from 'vitest';
import { FormulaStore, findFormula } from './formulaStore';
import { SampleTransport } from './sample';
import type { HeldFormula } from './transport';

const f = (entryId: string, statId: string): HeldFormula => ({
  entryId,
  statId,
  version: 'v',
  formula: { kind: 'contents', source: 'weight' },
});

describe('findFormula', () => {
  const parents: Record<string, string[]> = { c: ['b'], b: ['a', 'x'], a: [], x: [] };
  const held = new Map([
    ['a', [f('a', 's')]],
    ['x', [f('x', 's')]],
  ]);
  const find = (id: string, stat = 's') =>
    findFormula(
      (e) => held.get(e),
      (e) => parents[e] ?? [],
      id,
      stat,
    );
  it('finds the nearest, first parent first', () => {
    expect(find('c')?.entryId).toBe('a');
  });
  it('prefers the entry itself', () => {
    held.set('c', [f('c', 's')]);
    expect(find('c')?.entryId).toBe('c');
  });
  it('finds nothing for a stat no one works out', () => {
    expect(find('c', 'other')).toBeNull();
  });
});

describe('FormulaStore', () => {
  const defs = [{ id: 'w', name: 'Weight', type: 'float' as const, enumValues: [] }];
  it('reads, saves and removes', async () => {
    const t = new SampleTransport([{ id: 'e', name: 'E', kinds: ['item'], parents: [] }], defs);
    let changes = 0;
    const store = new FormulaStore(t, () => changes++);
    await store.load(['e']);
    expect(store.held('e')).toEqual([]);
    const formula = { kind: 'contents', source: 'w' } as const;
    await store.save('e', 'w', formula, null);
    const held = store.held('e')?.[0];
    expect(held?.statId).toBe('w');
    await store.remove('e', 'w', held?.version ?? '');
    expect(store.held('e')).toEqual([]);
    expect(changes).toBeGreaterThan(2);
  });
});
