import { beforeEach, describe, expect, it, vi } from 'vitest';

// debugSeed.ts imports lib/api.ts (for its live API), which reaches
// @authgear/web via lib/auth - browser-only at import time.
vi.mock('./auth', () => ({ getAccessToken: vi.fn() }));

import {
  IS_CONTAINER_ENTITY_IDS,
  type SeedApi,
  type SeedStore,
  seedIsContainer,
} from './debugSeed';

function makeStore(
  initial: Record<string, string> = {},
): SeedStore & { data: Map<string, string> } {
  const data = new Map(Object.entries(initial));
  return {
    data,
    get: (key) => data.get(key) ?? null,
    set: (key, value) => void data.set(key, value),
  };
}

describe('seedIsContainer', () => {
  let api: { [K in keyof SeedApi]: ReturnType<typeof vi.fn> };

  beforeEach(() => {
    api = {
      createStatGroup: vi.fn().mockResolvedValue({ id: 'group-1' }),
      createBoolStatDefinition: vi.fn().mockResolvedValue({ id: 'def-1' }),
      setBoolStat: vi.fn().mockResolvedValue({}),
    };
  });

  it('creates the "tags" group, then the boolean definition inside it, then sets true on every entity', async () => {
    const result = await seedIsContainer('t1', api as unknown as SeedApi, makeStore());

    expect(api.createStatGroup).toHaveBeenCalledWith('t1', 'tags');
    expect(api.createBoolStatDefinition).toHaveBeenCalledWith('t1', 'is_container', 'group-1');
    expect(api.setBoolStat).toHaveBeenCalledTimes(3);
    for (const entityId of IS_CONTAINER_ENTITY_IDS) {
      expect(api.setBoolStat).toHaveBeenCalledWith('t1', entityId, 'def-1', true);
    }
    expect(result.succeeded).toEqual(IS_CONTAINER_ENTITY_IDS);
    expect(result.failed).toEqual([]);
  });

  it('targets exactly the three requested entity ids', () => {
    expect(IS_CONTAINER_ENTITY_IDS).toEqual([
      'de365564-599b-48d2-bef6-18eb814e052f',
      '459bab1b-c8ce-4a48-85ad-ed4f200ebb95',
      '34abd460-6205-49d0-99e0-706622c81476',
    ]);
  });

  it('remembers created ids and reuses them on a retry instead of re-creating (unique names)', async () => {
    const store = makeStore();
    await seedIsContainer('t1', api as unknown as SeedApi, store);
    await seedIsContainer('t1', api as unknown as SeedApi, store);

    expect(api.createStatGroup).toHaveBeenCalledTimes(1);
    expect(api.createBoolStatDefinition).toHaveBeenCalledTimes(1);
    expect(api.setBoolStat).toHaveBeenCalledTimes(6);
  });

  it('keeps remembered ids separate per tenant', async () => {
    const store = makeStore();
    await seedIsContainer('t1', api as unknown as SeedApi, store);
    await seedIsContainer('t2', api as unknown as SeedApi, store);
    expect(api.createStatGroup).toHaveBeenCalledTimes(2);
  });

  it('keeps going after one entity fails and reports it', async () => {
    api.setBoolStat.mockRejectedValueOnce(new Error('403 forbidden'));
    const result = await seedIsContainer('t1', api as unknown as SeedApi, makeStore());

    expect(result.failed).toEqual([
      { entityId: IS_CONTAINER_ENTITY_IDS[0], message: '403 forbidden' },
    ]);
    expect(result.succeeded).toEqual(IS_CONTAINER_ENTITY_IDS.slice(1));
  });

  it('saves the group id even if the definition step then fails, so a retry does not re-create the group', async () => {
    const store = makeStore();
    api.createBoolStatDefinition.mockRejectedValueOnce(new Error('boom'));

    await expect(seedIsContainer('t1', api as unknown as SeedApi, store)).rejects.toThrow('boom');
    await seedIsContainer('t1', api as unknown as SeedApi, store);

    expect(api.createStatGroup).toHaveBeenCalledTimes(1);
  });
});
