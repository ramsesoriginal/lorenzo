import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { autosaveText } from '../src/autosave';
import { backoffMs, retryRead } from '../src/retry';
import { changesText } from '../src/save-bar';

beforeEach(() => vi.useFakeTimers());
afterEach(() => vi.useRealTimers());

describe('backoff', () => {
  it('doubles from a second up to eight', () => {
    expect([1, 2, 3, 4, 5].map((n) => backoffMs(n))).toEqual([1000, 2000, 4000, 8000, 8000]);
  });
});

describe('retryRead', () => {
  it('returns at once when the read works', async () => {
    const read = vi.fn().mockResolvedValue('rows');

    await expect(retryRead(read)).resolves.toBe('rows');
    expect(read).toHaveBeenCalledTimes(1);
  });

  it('tries again after a wait, says so, and returns when a later try works', async () => {
    const read = vi
      .fn()
      .mockRejectedValueOnce(new Error('503'))
      .mockRejectedValueOnce(new Error('503'))
      .mockResolvedValue('rows');
    const onRetry = vi.fn();
    const result = retryRead(read, { onRetry });

    await vi.advanceTimersByTimeAsync(0);
    expect(onRetry).toHaveBeenCalledWith(
      expect.objectContaining({ attempt: 1, tries: 4, waitMs: 1000 }),
    );
    await vi.advanceTimersByTimeAsync(1000);
    expect(onRetry).toHaveBeenLastCalledWith(expect.objectContaining({ attempt: 2, waitMs: 2000 }));
    await vi.advanceTimersByTimeAsync(2000);
    await expect(result).resolves.toBe('rows');
    expect(read).toHaveBeenCalledTimes(3);
  });

  it('gives up after the last try with the last error', async () => {
    const read = vi.fn().mockRejectedValue(new Error('503'));
    const result = retryRead(read, { tries: 3 });
    const caught = result.catch((e: Error) => e.message);

    await vi.advanceTimersByTimeAsync(10_000);
    await expect(caught).resolves.toBe('503');
    expect(read).toHaveBeenCalledTimes(3);
  });

  it('stops at once when told to', async () => {
    const controller = new AbortController();
    const read = vi.fn().mockRejectedValue(new Error('gone'));
    const caught = retryRead(read, { signal: controller.signal }).catch((e: Error) => e.message);

    await vi.advanceTimersByTimeAsync(0);
    controller.abort();
    await vi.advanceTimersByTimeAsync(5_000);
    await expect(caught).resolves.toBe('gone');
    expect(read).toHaveBeenCalledTimes(1);
  });
});

describe('words', () => {
  it('counts changes', () => {
    expect(changesText(1)).toBe('1 change not saved');
    expect(changesText(3)).toBe('3 changes not saved');
  });

  it('says honestly when a change is only on the device', () => {
    expect(autosaveText('saved')).toBe('Saved');
    expect(autosaveText('device')).toContain('Saved on this device');
    expect(autosaveText('error')).toContain('still here');
  });
});
