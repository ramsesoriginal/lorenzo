import { describe, expect, it } from 'vitest';
import type { EntrySummary } from '../core/transport';
import { buildRows, counts } from './explorerRows';

const e = (id: string, name: string, kinds: string[], parentIds: string[] = []): EntrySummary => ({
  id,
  name,
  kinds,
  parentIds,
});
const entries = [
  e('root', 'Monster', ['item']),
  e('beast', 'Beast', ['item'], ['root']),
  e('undead', 'Undead', ['item'], ['root']),
  e('ghoul', 'Ghoul', ['item'], ['undead', 'beast']),
  e('npc', 'Mara', ['being']),
  e('node', 'People', []),
];
const shape = (rows: ReturnType<typeof buildRows>) =>
  rows.map((r) => (r.type === 'header' ? `# ${r.label}` : `${'  '.repeat(r.depth)}${r.id}`));

describe('the tree', () => {
  it('shows an entry under each of its parents, children by name', () => {
    expect(shape(buildRows(entries, 'inherits'))).toEqual([
      'npc',
      'root',
      '  beast',
      '    ghoul',
      '  undead',
      '    ghoul',
      'node',
    ]);
  });

  it('says how many parents an entry with several has, and counts the places', () => {
    const rows = buildRows(entries, 'inherits');
    const ghouls = rows.filter((r) => r.type === 'entry' && r.id === 'ghoul');
    expect(ghouls.map((r) => r.type === 'entry' && r.parentCount)).toEqual([2, 2]);
    expect(new Set(ghouls.map((r) => r.key)).size).toBe(2);
    expect(counts(rows)).toEqual({ entries: 6, places: 7 });
  });

  it('hides what is under a collapsed entry', () => {
    const rows = buildRows(entries, 'inherits', new Set(['root']));
    expect(shape(rows)).toEqual(['npc', 'root', 'node']);
    const root = rows.find((r) => r.type === 'entry' && r.id === 'root');
    expect(root).toMatchObject({ hasChildren: true, open: false });
  });

  it('takes an entry whose parent is not in the list as a root', () => {
    expect(shape(buildRows([e('a', 'A', [], ['gone'])], 'inherits'))).toEqual(['a']);
  });

  it('does not loop on a cycle', () => {
    const rows = buildRows([e('a', 'A', [], ['b']), e('b', 'B', [], ['a'])], 'inherits');
    expect(shape(rows).length).toBeGreaterThan(0);
    expect(shape(rows).length).toBeLessThan(6);
  });
});

describe('the other orders', () => {
  it('is A to Z, flat', () => {
    expect(shape(buildRows(entries, 'name'))).toEqual([
      'beast',
      'ghoul',
      'npc',
      'root',
      'node',
      'undead',
    ]);
  });

  it('groups by kind, an entry in each of its kinds, bare entries last', () => {
    const both = [...entries, e('both', 'Both', ['item', 'being'])];
    expect(shape(buildRows(both, 'kind'))).toEqual([
      '# Items',
      '  beast',
      '  both',
      '  ghoul',
      '  root',
      '  undead',
      '# Beings',
      '  both',
      '  npc',
      '# Bare entries',
      '  node',
    ]);
  });
});
