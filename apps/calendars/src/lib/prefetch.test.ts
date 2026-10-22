import { expect, test, vi } from 'vitest';

const { allowed, get } = vi.hoisted(() => ({ allowed: vi.fn(() => true), get: vi.fn() }));
vi.mock('./read-cache', () => ({ calendarReads: { scoped: allowed } }));
vi.mock('./api', () => ({ client: { GET: get }, unwrap: async (r: unknown) => r }));

import { prefetchEntry } from './prefetch';

test('prefetch deduplicates intentions, caps its queue and runs at most two requests', async () => {
  const pending: Array<ReturnType<typeof Promise.withResolvers<unknown>>> = [];
  get.mockImplementation(() => {
    const job = Promise.withResolvers<unknown>();
    pending.push(job);
    return job.promise;
  });
  for (let i = 0; i < 30; i++) {
    prefetchEntry('library', String(i));
    prefetchEntry('library', String(i));
  }
  expect(get).toHaveBeenCalledTimes(2);
  for (let i = 0; i < 10; i++) {
    pending[i]?.resolve({});
    await new Promise((resolve) => setTimeout(resolve, 0));
  }
  expect(get).toHaveBeenCalledTimes(10); // two active, eight queued; the remainder were not scheduled.
  allowed.mockReturnValue(false);
  prefetchEntry('other', 'private');
  expect(get).toHaveBeenCalledTimes(10);
});
