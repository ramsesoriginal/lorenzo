import type { StatDefinition } from '@lorenzo/stat-values';
import { describe, expect, it } from 'vitest';
import { bandOf, valueText, vitalsOf } from './statBand';

const definition = (name: string, value_type: string, unit: string | null = null) =>
  ({ name, value_type, unit }) as unknown as StatDefinition;

const stat = (name: string, value: number | string | boolean, extra = {}) => ({
  name,
  value,
  own: true,
  from_entity: null,
  computed: false,
  ...extra,
});

const defined = [
  { definition: definition('strength', 'int'), group: 'Abilities' },
  { definition: definition('speed', 'int', 'ft'), group: 'Vitals' },
  { definition: definition('mood', 'enum'), group: 'Vitals' },
];

describe('bandOf', () => {
  it('groups numbers as tiles and the rest as rows, in the order of the library', () => {
    const groups = bandOf(defined, {
      stats: [stat('mood', 'calm'), stat('speed', 30), stat('strength', 17)],
    });

    expect(groups.map((group) => group.name)).toEqual(['Abilities', 'Vitals']);
    expect(groups[1]?.tiles.map((tile) => tile.label)).toEqual(['Speed']);
    expect(groups[1]?.rows.map((row) => row.label)).toEqual(['Mood']);
  });

  it('leaves out tags and groups with nothing to show', () => {
    const groups = bandOf(defined, { stats: [stat('is_undead', true), stat('strength', 8)] });

    expect(groups.map((group) => group.name)).toEqual(['Abilities']);
  });

  it('says where a value comes from', () => {
    const [group] = bandOf(defined, {
      stats: [
        stat('strength', 17, {
          own: false,
          from_entity: { id: 'x', name: 'Dwarf' },
          computed: true,
        }),
      ],
    } as never);

    expect(group?.tiles[0]).toMatchObject({ own: false, computed: true, from: 'Dwarf' });
  });

  it('keeps a stat of a definition it cannot see, in a group of no name', () => {
    const groups = bandOf([], { stats: [stat('luck', 3)] });

    expect(groups).toHaveLength(1);
    expect(groups[0]?.name).toBe('');
    expect(groups[0]?.rows[0]?.value).toBe(3);
  });
});

describe('vitalsOf and valueText', () => {
  it('keeps the first three number tiles of the first group that has any', () => {
    const groups = bandOf(defined, { stats: [stat('speed', 30), stat('strength', 17)] });

    expect(vitalsOf(groups).map((tile) => tile.label)).toEqual(['Strength']);
  });

  it('puts the unit after the value', () => {
    expect(valueText({ value: 30, unit: 'ft' })).toBe('30 ft');
    expect(valueText({ value: 30, unit: null })).toBe('30');
  });
});
