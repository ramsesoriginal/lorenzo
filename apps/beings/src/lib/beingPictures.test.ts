import { describe, expect, it, vi } from 'vitest';
import { createBeingPictures } from './beingPictures';

describe('the being list picture lookups', () => {
  it('shares a lookup between the thumbnail, hover and a redrawn row', async () => {
    const fetch = vi.fn(async () => 'blob:portrait');
    const load = createBeingPictures(fetch);
    const thumbnail = load('ashfang');
    expect(load('ashfang')).toBe(thumbnail);
    expect(await thumbnail).toBe('blob:portrait');
    expect(await load('ashfang')).toBe('blob:portrait');
    expect(fetch).toHaveBeenCalledTimes(1);
  });

  it('keeps a missing picture but allows a failed lookup to be retried', async () => {
    const fetch = vi
      .fn()
      .mockResolvedValueOnce(null)
      .mockRejectedValueOnce(new Error('offline'))
      .mockResolvedValueOnce('blob:recovered');
    const load = createBeingPictures(fetch);
    expect(await load('no-picture')).toBeNull();
    expect(await load('no-picture')).toBeNull();
    expect(await load('has-picture')).toBeNull();
    expect(await load('has-picture')).toBe('blob:recovered');
    expect(fetch).toHaveBeenCalledTimes(3);
  });

  it('limits simultaneous picture requests when many rows enter the viewport', async () => {
    const finish: Array<(value: string | null) => void> = [];
    const fetch = vi.fn(
      () =>
        new Promise<string | null>((resolve) => {
          finish.push(resolve);
        }),
    );
    const load = createBeingPictures(fetch);
    const requests = ['a', 'b', 'c', 'd', 'e'].map(load);
    await vi.waitFor(() => expect(fetch).toHaveBeenCalledTimes(4));
    finish[0]('blob:a');
    await vi.waitFor(() => expect(fetch).toHaveBeenCalledTimes(5));
    for (const done of finish.slice(1)) done(null);
    await expect(Promise.all(requests)).resolves.toEqual(['blob:a', null, null, null, null]);
  });
});
