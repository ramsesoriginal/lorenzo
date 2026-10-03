import { describe, expect, it, vi } from 'vitest';
import { createStaleCache } from './staleCache';

function setup() {
  let time = 0;
  const fetch = vi.fn(async (key: string) => `${key}@${time}`);
  const cache = createStaleCache(fetch, () => time);

  const advance = (ms: number) => {
    time += ms;
  };

  return { cache, fetch, advance };
}

describe('createStaleCache', () => {
  it('has nothing until a fetch, then keeps the last answer', async () => {
    const { cache } = setup();

    expect(cache.peek('a')).toBeUndefined();
    expect(await cache.refresh('a')).toBe('a@0');
    expect(cache.peek('a')).toBe('a@0');
  });

  it('fetches again unless what is kept is younger than maxAge', async () => {
    const { cache, fetch, advance } = setup();

    await cache.refresh('a');
    advance(5);

    expect(await cache.refresh('a', 10)).toBe('a@0');
    expect(fetch).toHaveBeenCalledTimes(1);

    advance(10);

    expect(await cache.refresh('a', 10)).toBe('a@15');
    expect(await cache.refresh('a')).toBe('a@15');
    expect(fetch).toHaveBeenCalledTimes(3);
  });

  it('shares one request between callers asking at the same time with a maxAge', async () => {
    const { cache, fetch } = setup();

    await Promise.all([cache.refresh('a', 10), cache.refresh('a', 10), cache.refresh('b', 10)]);

    expect(fetch).toHaveBeenCalledTimes(2);
  });

  it('never joins a request that started earlier when asked without a maxAge', async () => {
    const { cache, fetch } = setup();
    let release: () => void = () => {};

    fetch.mockImplementationOnce(async () => {
      await new Promise<void>((resolve) => {
        release = resolve;
      });

      return 'before the change';
    });

    const early = cache.refresh('a', 10);
    const reload = cache.refresh('a');

    expect(await reload).toBe('a@0');

    release();

    expect(await early).toBe('before the change');
    // The older answer arriving later doesn't replace the newer one.
    expect(cache.peek('a')).toBe('a@0');
  });

  it('prefetches only what is not kept yet, and ignores a failure', async () => {
    const { cache, fetch } = setup();

    cache.prefetch('a');
    await cache.refresh('a', 10);
    cache.prefetch('a');

    expect(fetch).toHaveBeenCalledTimes(1);

    fetch.mockRejectedValueOnce(new Error('down'));
    cache.prefetch('b');
    await Promise.resolve();

    expect(cache.peek('b')).toBeUndefined();
  });

  it('keeps the old answer when a fetch fails', async () => {
    const { cache, fetch } = setup();

    await cache.refresh('a');
    fetch.mockRejectedValueOnce(new Error('down'));

    await expect(cache.refresh('a')).rejects.toThrow('down');
    expect(cache.peek('a')).toBe('a@0');
  });
});
