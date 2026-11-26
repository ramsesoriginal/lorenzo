import type { LorenzoClient } from '@lorenzo/api-client';
import { describe, expect, it, vi } from 'vitest';
import { STATES, setTag, tagDefinitions, tagState } from '../src/tags';

const stat = (value: boolean, own: boolean) => ({
  stat_definition_id: 'd',
  group_id: 'g',
  name: 'is_magical',
  value,
  own,
  computed: false,
});

describe('tagState', () => {
  it('is the entity’s own value when it has one, and hides what it would inherit', () => {
    expect(tagState(stat(true, true))).toEqual({ state: 'on', hint: '' });
    expect(tagState(stat(false, true))).toEqual({ state: 'off', hint: '' });
  });

  it('is inherited otherwise, saying what inheriting gives now', () => {
    expect(tagState(stat(true, false))).toEqual({ state: 'inherited', hint: ' (on)' });
    expect(tagState(stat(false, false))).toEqual({ state: 'inherited', hint: ' (off)' });
    expect(tagState(undefined)).toEqual({ state: 'inherited', hint: ' (not set)' });
  });

  it('offers the three states in the order the editor draws them', () => {
    expect(STATES.map(([state]) => state)).toEqual(['inherited', 'on', 'off']);
  });
});

const page = <T>(items: T[]) => ({ items, total: items.length, page: 1, size: 100, pages: 1 });
const ok = (data: unknown) => ({ data, response: new Response() });

describe('tagDefinitions', () => {
  it('lists the bool definitions of the tags group, and nothing else', async () => {
    const client = {
      GET: vi.fn(async (path: string) =>
        ok(
          path.endsWith('/stat-groups')
            ? page([
                { id: 'tags', name: 'tags' },
                { id: 'physical', name: 'physical' },
              ])
            : page([
                { id: '1', name: 'is_magical', stat_group_id: 'tags', value_type: 'bool' },
                { id: '2', name: 'weight', stat_group_id: 'physical', value_type: 'int' },
                { id: '3', name: 'fragile', stat_group_id: 'physical', value_type: 'bool' },
              ]),
        ),
      ),
    } as unknown as LorenzoClient;

    expect((await tagDefinitions(client, 't')).map((d) => d.name)).toEqual(['is_magical']);
  });
});

describe('setTag', () => {
  const calls = () => {
    const api = {
      PUT: vi.fn(async () => ok({ stats: [] })),
      PATCH: vi.fn(async () => ok({ stats: [] })),
      DELETE: vi.fn(async () => ok({ stats: [] })),
    };

    return { api, client: api as unknown as LorenzoClient };
  };

  it('puts a tag on, patches it explicitly off and deletes it back to inherited', async () => {
    const { api, client } = calls();

    await setTag(client, 't', 'e', 'd', 'on');
    await setTag(client, 't', 'e', 'd', 'off');
    await setTag(client, 't', 'e', 'd', 'inherited');

    expect(api.PUT).toHaveBeenCalledTimes(1);
    expect(api.PATCH).toHaveBeenCalledTimes(1);
    expect(api.DELETE).toHaveBeenCalledTimes(1);
  });
});
