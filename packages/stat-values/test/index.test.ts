import type { LorenzoClient } from '@lorenzo/api-client';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import {
  clearStat,
  decimalText,
  parseStat,
  type StatDefinition,
  setStat,
  sourceIn,
  sourceOf,
  statDefinitions,
  statRows,
  statVocabulary,
} from '../src/index';

const api = { GET: vi.fn(), PUT: vi.fn(), DELETE: vi.fn() };
const client = api as unknown as LorenzoClient;

const definition = (name: string, value_type: StatDefinition['value_type'], extra = {}) =>
  ({
    id: `id-${name}`,
    name,
    stat_group_id: 'g1',
    value_type,
    enum_values: [],
    ...extra,
  }) as unknown as StatDefinition;
const weight = definition('weight', 'int');
const reach = definition('reach', 'float');

const detail = (stats: { name: string; value: number | string | boolean; own: boolean }[]) => ({
  data: { stats },
  response: new Response(),
});

beforeEach(() => {
  api.GET.mockReset();
  api.PUT.mockReset().mockResolvedValue({ data: { stats: [] }, response: new Response() });
  api.DELETE.mockReset().mockResolvedValue({ data: { stats: [] }, response: new Response() });
});

describe('statDefinitions', () => {
  it('lists the stats that are not tags, by group and name', async () => {
    api.GET.mockImplementation(async (path: string) => ({
      data: path.endsWith('/stat-groups')
        ? { items: [{ id: 'g1', name: 'physical' }], total: 1, page: 1, size: 100, pages: 1 }
        : {
            items: [definition('weight', 'int'), definition('is_magical', 'bool'), reach],
            total: 3,
            page: 1,
            size: 100,
            pages: 1,
          },
      response: new Response(),
    }));

    const found = await statDefinitions(client, 't');

    expect(found.map((row) => row.definition.name)).toEqual(['reach', 'weight']);
    expect(found[0]?.group).toBe('physical');
  });
});

describe('statVocabulary', () => {
  it('lists every definition, tags too, by group position and then definition position', async () => {
    const at = (name: string, group: string, position: number, value_type = 'int') =>
      definition(name, value_type as StatDefinition['value_type'], {
        stat_group_id: group,
        position,
      });

    api.GET.mockImplementation(async (path: string) => ({
      data: path.endsWith('/stat-groups')
        ? {
            items: [
              { id: 'g1', name: 'vitals', position: 1 },
              { id: 'g2', name: 'abilities', position: 0 },
            ],
            total: 2,
            page: 1,
            size: 100,
            pages: 1,
          }
        : {
            items: [
              at('speed', 'g1', 1),
              at('hit_points', 'g1', 0),
              at('strength', 'g2', 0),
              at('is_undead', 'g1', 2, 'bool'),
            ],
            total: 4,
            page: 1,
            size: 100,
            pages: 1,
          },
      response: new Response(),
    }));

    const found = await statVocabulary(client, 't');

    expect(found.map((row) => row.definition.name)).toEqual([
      'strength',
      'hit_points',
      'speed',
      'is_undead',
    ]);
    expect(found.map((row) => row.group)).toEqual(['abilities', 'vitals', 'vitals', 'vitals']);
  });
});

describe('statRows and sourceOf', () => {
  const rows = statRows(
    [
      { definition: weight, group: 'physical' },
      { definition: reach, group: 'physical' },
      { definition: definition('price', 'int'), group: 'economic' },
    ],
    {
      stats: [
        { name: 'weight', value: 3, own: true, computed: false },
        { name: 'reach', value: 1.5, own: false, computed: false },
      ],
    },
  );

  it('says whether a value is the item’s own, inherited or missing', () => {
    expect(rows.map(sourceOf)).toEqual(['Set on this item', 'Inherited', 'Not set']);
    expect(rows.map((row) => row.value)).toEqual([3, 1.5, null]);
  });
});

describe('sourceOf for another kind of entry', () => {
  it('names what the stat belongs to', () => {
    expect(sourceIn('being', { value: 3, own: true })).toBe('Set on this being');
    expect(sourceOf({ value: 3, own: true })).toBe('Set on this item');
  });
});

describe('parseStat', () => {
  it('takes whole numbers for an int and refuses the rest', () => {
    expect(parseStat(weight, ' 12 ')).toEqual({ value: 12 });
    expect(parseStat(weight, '1.5')).toHaveProperty('problem');
    expect(parseStat(weight, '')).toHaveProperty('problem');
  });

  it('takes a point or a comma for a decimal, and no exponent', () => {
    expect(parseStat(reach, '2,5')).toEqual({ value: 2.5 });
    expect(parseStat(reach, '3')).toEqual({ value: 3 });
    expect(parseStat(reach, '1e3')).toHaveProperty('problem');
  });

  it('takes one of an enum’s values', () => {
    const binding = definition('binding', 'enum', { enum_values: ['on_own', 'none'] });

    expect(parseStat(binding, 'none')).toEqual({ value: 'none' });
    expect(parseStat(binding, 'other')).toHaveProperty('problem');
  });

  it('takes any text that is not empty', () => {
    const note = definition('rarity', 'text');

    expect(parseStat(note, ' rare ')).toEqual({ value: ' rare ' });
    expect(parseStat(note, '  ')).toHaveProperty('problem');
  });
});

describe('decimalText', () => {
  it('keeps the point of a whole decimal', () => {
    expect(decimalText(3)).toBe('3.0');
    expect(decimalText(2.5)).toBe('2.5');
  });
});

describe('setStat', () => {
  it('sets the value, asking for the group', async () => {
    api.GET.mockResolvedValue(detail([{ name: 'weight', value: 1, own: false }]));

    await setStat(client, 't', 'e', weight, 4, { value: 1, own: false });

    expect(api.PUT.mock.calls[0]?.[1]).toMatchObject({ body: { value: 4, acquire_group: true } });
  });

  it('writes a whole decimal with its point', async () => {
    api.GET.mockResolvedValue(detail([]));

    await setStat(client, 't', 'e', reach, 3, { value: null, own: false });

    const options = api.PUT.mock.calls[0]?.[1];
    expect(options.bodySerializer()).toBe('{"value":3.0,"acquire_group":true}');
  });

  it('refuses, and writes nothing, when the own value moved since it was read', async () => {
    api.GET.mockResolvedValue(detail([{ name: 'weight', value: 9, own: true }]));

    await expect(setStat(client, 't', 'e', weight, 4, { value: 1, own: true })).rejects.toThrow(
      /Someone changed this stat/,
    );
    expect(api.PUT).not.toHaveBeenCalled();
  });

  it('does not mind a different inherited value', async () => {
    api.GET.mockResolvedValue(detail([{ name: 'weight', value: 9, own: false }]));

    await setStat(client, 't', 'e', weight, 4, { value: 1, own: false });

    expect(api.PUT).toHaveBeenCalledOnce();
  });
});

describe('clearStat', () => {
  it('deletes the own value', async () => {
    api.GET.mockResolvedValue(detail([{ name: 'weight', value: 1, own: true }]));

    await clearStat(client, 't', 'e', weight, { value: 1, own: true });

    expect(api.DELETE.mock.calls[0]?.[1]).toMatchObject({
      params: { path: { tenant_id: 't', entity_id: 'e', stat_definition_id: 'id-weight' } },
    });
  });

  it('refuses when the value was cleared by someone else', async () => {
    api.GET.mockResolvedValue(detail([{ name: 'weight', value: 1, own: false }]));

    await expect(clearStat(client, 't', 'e', weight, { value: 1, own: true })).rejects.toThrow(
      /Someone changed/,
    );
    expect(api.DELETE).not.toHaveBeenCalled();
  });
});
