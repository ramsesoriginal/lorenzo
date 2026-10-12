import { beforeEach, describe, expect, it, vi } from 'vitest';
import { clearAppLinksCache, fill, getAppLinks } from '../src/appLinks';

const doc = {
  apps: {
    account_hub: { url: 'https://hub' },
    inventory_web: { url: 'https://inv' },
    beings: { url: 'https://beings' },
    bench: { url: 'https://bench' },
  },
  links: { item: 'https://inv/item/?tenant={tenant}&id={id}' },
};

const ok = () => Promise.resolve(new Response(JSON.stringify(doc), { status: 200 }));

describe('getAppLinks', () => {
  beforeEach(() => clearAppLinksCache());

  it('fetches /app-links once and keeps it in memory', async () => {
    const fetchImpl = vi.fn<typeof fetch>(ok);
    expect(await getAppLinks('https://api.test/', fetchImpl)).toEqual(doc);
    expect(await getAppLinks('https://api.test', fetchImpl)).toEqual(doc);
    expect(fetchImpl).toHaveBeenCalledTimes(1);
    expect(fetchImpl.mock.calls[0]?.[0]).toBe('https://api.test/app-links');
  });

  it('does not remember a failure', async () => {
    const fetchImpl = vi
      .fn<typeof fetch>()
      .mockResolvedValueOnce(new Response('no', { status: 503 }))
      .mockImplementationOnce(ok);
    await expect(getAppLinks('https://api.test', fetchImpl)).rejects.toThrow('503');
    expect(await getAppLinks('https://api.test', fetchImpl)).toEqual(doc);
  });

  it('does not remember a network error either', async () => {
    const fetchImpl = vi
      .fn<typeof fetch>()
      .mockRejectedValueOnce(new TypeError('Failed to fetch'))
      .mockImplementationOnce(ok);
    await expect(getAppLinks('https://api.test', fetchImpl)).rejects.toThrow('Failed to fetch');
    expect(await getAppLinks('https://api.test', fetchImpl)).toEqual(doc);
  });
});

describe('fill', () => {
  it('encodes values', () => {
    expect(fill(doc.links.item, { tenant: 'a b', id: 'x&y=1' })).toBe(
      'https://inv/item/?tenant=a%20b&id=x%26y%3D1',
    );
  });

  it('leaves a placeholder without a value, and fills repeats', () => {
    expect(fill('/{id}/{slug}/{id}', { id: 7 })).toBe('/7/{slug}/7');
  });
});
