import type { LorenzoClient } from '@lorenzo/api-client';
import { describe, expect, it, vi } from 'vitest';
import { saveSlug, slugCandidates, slugProblem, suggestSlug } from '../src/slugs';

const words = { slug: 'link name', slugTaken: (slug: string) => `Taken: ${slug}.` };

describe('slugCandidates', () => {
  it('gives an item its title first, then numbers; an instance numbers from -1', () => {
    expect(slugCandidates('Long Sword', 'item').slice(0, 3)).toEqual([
      'long-sword',
      'long-sword-2',
      'long-sword-3',
    ]);
    expect(slugCandidates('Long Sword', 'instance').slice(0, 2)).toEqual([
      'long-sword-1',
      'long-sword-2',
    ]);
  });

  it('gives none for a title with no letters or digits', () => {
    expect(slugCandidates('???', 'item')).toEqual([]);
  });
});

describe('slugProblem', () => {
  it('says what is wrong in the app’s own word', () => {
    expect(slugProblem('-bad', 'link name')).toContain('A link name starts');
    expect(slugProblem('x'.repeat(101), 'link name')).toContain('A link name has at most');
    expect(slugProblem('good-1', 'link name')).toBeNull();
    expect(slugProblem('-bad')).toContain('A slug starts');
  });
});

describe('suggestSlug', () => {
  it('gives the first candidate nothing holds', async () => {
    const client = {
      GET: vi.fn(async () => ({
        data: [{ slug: 'long-sword', entity_id: 'x', name: 'x', kinds: ['item'] }],
        response: new Response(),
      })),
    } as unknown as LorenzoClient;

    expect(await suggestSlug(client, 't', 'Long Sword', 'item')).toBe('long-sword-2');
  });
});

describe('saveSlug', () => {
  const client = (put: () => unknown) =>
    ({
      PUT: vi.fn(put),
      DELETE: vi.fn(async () => ({ data: {}, response: new Response() })),
    }) as unknown as LorenzoClient;

  it('writes nothing when it is unchanged, clears when empty', async () => {
    const api = client(async () => ({ data: {}, response: new Response() }));

    await saveSlug(api, words, 't', 'e', 'same', 'same');
    await saveSlug(api, words, 't', 'e', 'was', '  ');

    expect((api as unknown as { PUT: unknown }).PUT).not.toHaveBeenCalled();
    expect((api as unknown as { DELETE: ReturnType<typeof vi.fn> }).DELETE).toHaveBeenCalledTimes(
      1,
    );
  });

  it('refuses what cannot be one, and says in the app’s words that it is taken', async () => {
    const api = client(async () => ({
      error: { detail: 'Taken.' },
      response: new Response(null, { status: 409 }),
    }));

    await expect(saveSlug(api, words, 't', 'e', null, '-bad')).rejects.toThrow('A link name');
    await expect(saveSlug(api, words, 't', 'e', null, 'rope')).rejects.toThrow('Taken: rope.');
  });
});
