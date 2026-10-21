import { expect, test, vi } from 'vitest';
import { createReadCache } from './read-cache';

const url = 'https://api.example/tenants/library/entities/entry';
const json = (value: unknown, status = 200) =>
  new Response(JSON.stringify(value), {
    status,
    headers: { 'Content-Type': 'application/json', ETag: 'version' },
  });

test('retains bounded staff reads as independent responses after a fresh scope check', async () => {
  const network = vi.fn<typeof fetch>().mockResolvedValue(json({ name: 'Visible' }));
  const cache = createReadCache(network);
  cache.configure('viewer', 'library', 'owner', true);
  expect(await (await cache.fetch(url)).json()).toEqual({ name: 'Visible' });
  expect((await cache.fetch(url)).headers.get('etag')).toBe('version');
  expect(network).toHaveBeenCalledTimes(1);
  cache.suspend();
  await cache.fetch(url); // No retained response while access is being revalidated.
  expect(network).toHaveBeenCalledTimes(2);
  cache.configure('viewer', 'library', 'owner', true);
  await cache.fetch(url);
  expect(network).toHaveBeenCalledTimes(2);
});

test('ordinary readers deduplicate in-flight reads but retain no private body', async () => {
  const pending = Promise.withResolvers<Response>();
  const network = vi
    .fn<typeof fetch>()
    .mockReturnValueOnce(pending.promise)
    .mockResolvedValue(json('fresh'));
  const cache = createReadCache(network);
  cache.configure('viewer', 'library', 'player', false);
  const first = cache.fetch(url),
    second = cache.fetch(url);
  pending.resolve(json('same'));
  expect(await (await first).json()).toBe('same');
  expect(await (await second).json()).toBe('same');
  expect(network).toHaveBeenCalledTimes(1);
  expect(await (await cache.fetch(url)).json()).toBe('fresh');
});

test('account, tenant, role and opt-out changes invalidate private responses', async () => {
  const network = vi.fn<typeof fetch>().mockImplementation(async () => json('value'));
  const cache = createReadCache(network);
  for (const [viewer, tenant, role, all] of [
    ['a', 'library', 'owner', true],
    ['b', 'library', 'owner', true],
    ['b', 'other', 'owner', true],
    ['b', 'library', 'orga', true],
    ['b', 'library', 'orga', false],
  ] as const) {
    cache.configure(viewer, tenant, role, all);
    await cache.fetch(url);
  }
  expect(network).toHaveBeenCalledTimes(5);
  expect(cache.canPrefetch()).toBe(false);
});

test('a write prevents an older in-flight read from repopulating memory', async () => {
  const pending = Promise.withResolvers<Response>();
  const network = vi
    .fn<typeof fetch>()
    .mockReturnValueOnce(pending.promise)
    .mockResolvedValueOnce(json('saved'))
    .mockResolvedValueOnce(json('new'));
  const cache = createReadCache(network);
  cache.configure('a', 'library', 'owner', true);
  const old = cache.fetch(url);
  const refused = expect(old).rejects.toThrow('view changed');
  await cache.fetch(url, { method: 'PATCH', body: '{}' });
  pending.resolve(json('old'));
  await refused;
  expect(await (await cache.fetch(url)).json()).toBe('new');
  expect(network).toHaveBeenCalledTimes(3);
});

test('forced refresh keeps the newest answer when reads finish out of order', async () => {
  const slow = Promise.withResolvers<Response>();
  const network = vi
    .fn<typeof fetch>()
    .mockReturnValueOnce(slow.promise)
    .mockResolvedValueOnce(json('new'));
  const cache = createReadCache(network);
  cache.configure('a', 'library', 'owner', true);
  const old = cache.fetch(url);
  await cache.fetch(url, { cache: 'reload' });
  slow.resolve(json('old'));
  await old;
  expect(await (await cache.fetch(url)).json()).toBe('new');
});

test('expired data supplies no offline fallback, and a denial clears other cached data', async () => {
  let clock = 0;
  const network = vi
    .fn<typeof fetch>()
    .mockResolvedValueOnce(json('secret'))
    .mockRejectedValueOnce(new TypeError('Network failed'))
    .mockResolvedValueOnce(json('denied', 403))
    .mockResolvedValueOnce(json('new'));
  const cache = createReadCache(network, () => clock);
  cache.configure('a', 'library', 'owner', true);
  await cache.fetch(url);
  clock = 11000;
  await expect(cache.fetch(url)).rejects.toThrow('Network failed');
  expect((await cache.fetch(`${url}-other`)).status).toBe(403);
  expect(cache.canPrefetch()).toBe(false);
  expect(await (await cache.fetch(url)).json()).toBe('new');
});

test('least-recently-used capacity and oversized responses stay bounded', async () => {
  const network = vi.fn<typeof fetch>().mockImplementation(async () => json('x'));
  const cache = createReadCache(network);
  cache.configure('a', 'library', 'owner', true);
  for (let i = 0; i < 65; i++) await cache.fetch(url + i);
  await cache.fetch(`${url}0`);
  expect(network).toHaveBeenCalledTimes(66);
  network.mockResolvedValue(json('x'.repeat(262145)));
  await cache.fetch(`${url}large`);
  await cache.fetch(`${url}large`);
  expect(network).toHaveBeenCalledTimes(68);
});
