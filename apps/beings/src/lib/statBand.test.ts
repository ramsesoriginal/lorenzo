import type { StatDefinition } from '@lorenzo/stat-values';
import { describe, expect, it } from 'vitest';
import { bandOf, captionOf, shownValue, signed, tagsOf, valueText, vitalsOf } from './statBand';

const definition = (name: string, value_type: string, extra: Record<string, unknown> = {}) =>
  ({ id: `id-${name}`, name, value_type, unit: null, ...extra }) as unknown as StatDefinition;

const stat = (name: string, value: number | string | boolean, extra = {}) => ({
  name,
  value,
  own: true,
  from_entity: null,
  computed: false,
  ...extra,
});

const entry = (def: StatDefinition, group: string) => ({ definition: def, group, groupId: group });
const defined = [
  entry(definition('strength', 'int'), 'Abilities'),
  entry(definition('speed', 'int', { unit: 'ft' }), 'Vitals'),
  entry(definition('mood', 'enum'), 'Vitals'),
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
    const plain = { numeric: true, signed: false };

    expect(valueText({ ...plain, value: 30, unit: 'ft' })).toBe('30 ft');
    expect(valueText({ ...plain, value: 30, unit: null })).toBe('30');
  });
});

describe('hints, signs and pins', () => {
  const library = [
    entry(
      definition('stress', 'int', { max_hint_id: 'id-stress_max', min_hint_id: 'id-zero' }),
      'Vitals',
    ),
    entry(definition('stress_max', 'int'), 'Vitals'),
    entry(definition('zero', 'int'), 'Vitals'),
    entry(
      definition('strength', 'int', { resolved_hint_id: 'id-strength_mod', pin: true }),
      'Abilities',
    ),
    entry(definition('strength_mod', 'int', { signed: true }), 'Abilities'),
  ];
  const have = [
    stat('stress', 3),
    stat('stress_max', 9),
    stat('zero', 0),
    stat('strength', 16),
    stat('strength_mod', 3),
  ];
  const groups = bandOf(library, { stats: have } as never);
  const tile = (name: string) =>
    groups.flatMap((group) => group.tiles).find((candidate) => candidate.name === name);

  it('says "of 9" from the maximum hint and takes the minimum hint as a floor', () => {
    expect(tile('stress')).toMatchObject({ of: 9, floor: 0 });
    expect(captionOf(tile('stress') as never)).toBe('of 9');
  });

  it('shows the resolved hint beside the number, signed when its definition says so', () => {
    expect(captionOf(tile('strength') as never)).toBe('+3');
    expect(shownValue(tile('strength_mod') as never)).toBe('+3');
  });

  it('has no floor and no caption when the hinted stat has no value on the being', () => {
    const [group] = bandOf(library, { stats: [stat('stress', 3)] } as never);

    expect(group?.tiles[0]).toMatchObject({ of: null, floor: null });
  });

  it('keeps the pinned numbers in the sticky bar, in the library’s order', () => {
    expect(vitalsOf(groups).map((candidate) => candidate.name)).toEqual(['strength']);
  });

  it('draws signs with a real minus', () => {
    expect(signed(4)).toBe('+4');
    expect(signed(-1)).toBe('−1');
    expect(signed(0)).toBe('±0');
  });
});

describe('tagsOf', () => {
  const library = [
    entry(definition('is_undead', 'bool', { adjustable_in_play: false }), 'tags'),
    entry(definition('prone', 'bool', { adjustable_in_play: true }), 'tags'),
    entry(definition('is_flag', 'bool'), 'other'),
  ];

  it('lists the tags of the tags group with what each is on the being', () => {
    const tags = tagsOf(library, {
      stats: [
        stat('is_undead', true, { own: false, from_entity: { id: 'x', name: 'Skeleton' } }),
        stat('prone', false),
      ],
    } as never);

    expect(tags.map((tag) => [tag.name, tag.state, tag.from, tag.adjustable])).toEqual([
      ['is_undead', 'inherited', 'Skeleton', false],
      ['prone', 'off', null, true],
    ]);
  });
});
