import { describe, expect, it, vi } from 'vitest';
import { createCardCache } from '../src/cache';
import type { EntryCard } from '../src/types';

const card = (name: string) => ({ name }) as EntryCard;
const missing = (error: unknown) => error instanceof Error && error.message === 'missing';

describe('createCardCache', () => {
  it('asks once per entry for the page', async () => {
    const fetchCard = vi.fn(async (_t: string, id: string) => card(id));
    const load = createCardCache(fetchCard);

    expect(await load('t', 'a')).toEqual(card('a'));
    await load('t', 'a');
    await load('t', 'b');
    await load('u', 'a');

    expect(fetchCard).toHaveBeenCalledTimes(3);
  });

  it('remembers a missing entry as no card', async () => {
    const fetchCard = vi.fn(async () => {
      throw new Error('missing');
    });
    const load = createCardCache(fetchCard, missing);

    expect(await load('t', 'a')).toBeNull();
    expect(await load('t', 'a')).toBeNull();
    expect(fetchCard).toHaveBeenCalledTimes(1);
  });

  it('forgets any other failure, so the next hover asks again', async () => {
    const fetchCard = vi
      .fn<(t: string, id: string) => Promise<EntryCard>>()
      .mockRejectedValueOnce(new Error('offline'))
      .mockResolvedValueOnce(card('a'));
    const load = createCardCache(fetchCard, missing);

    expect(await load('t', 'a')).toBeNull();
    expect(await load('t', 'a')).toEqual(card('a'));
    expect(fetchCard).toHaveBeenCalledTimes(2);
  });
});
