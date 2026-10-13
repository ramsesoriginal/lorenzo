import type { StatDefinition } from '@lorenzo/stat-values';
import { describe, expect, it } from 'vitest';

import type { SheetWeapon } from './sheet';
import { emptySection, weaponTable } from './weapons';

const definition = (name: string, extra: Record<string, unknown> = {}) =>
  ({ id: name, name, value_type: 'int', unit: null, signed: false, ...extra }) as StatDefinition;
const entry = (def: StatDefinition) => ({ definition: def, group: 'Weapons', groupId: 'g' });
const weapon = (name: string, stats: Record<string, number>): SheetWeapon =>
  ({
    entity_id: `id-${name}`,
    name,
    quantity: 1,
    stats: Object.entries(stats).map(([stat, value]) => ({
      name: stat,
      value,
      own: true,
      from_entity: null,
      computed: false,
    })),
  }) as SheetWeapon;

describe('weaponTable', () => {
  const vocabulary = [
    entry(definition('reach', { unit: 'ft' })),
    entry(definition('attack_bonus', { signed: true })),
    entry(definition('damage')),
  ];

  it('makes a column for each stat any weapon has, and a dash where one has none', () => {
    const table = weaponTable(
      [
        weapon('Longsword', { reach: 5, damage: 8 }),
        weapon('Dagger', { damage: 4, attack_bonus: 2 }),
      ],
      vocabulary,
    );

    expect(table.columns.map((column) => column.label)).toEqual([
      'Reach',
      'Attack bonus',
      'Damage',
    ]);
    expect(table.rows.map((row) => row.cells)).toEqual([
      ['5 ft', '—', '8'],
      ['—', '+2', '4'],
    ]);
  });

  it('is empty for no weapons', () => {
    expect(weaponTable([], vocabulary)).toEqual({ columns: [], rows: [] });
  });
});

describe('emptySection', () => {
  it('tells a missing setting from an empty section', () => {
    expect(emptySection(false, 'weapons')).toContain('has not said');
    expect(emptySection(true, 'weapons')).toBe('Nothing to show: no weapons.');
  });
});
