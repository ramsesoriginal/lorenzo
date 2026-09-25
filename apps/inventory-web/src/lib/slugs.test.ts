import { beforeEach, describe, expect, it, vi } from 'vitest';

// An API whose tenant already holds some slugs, recording every slug write.
const api = vi.hoisted(() => ({
  held: new Set<string>(),
  GET: vi.fn(),
  PUT: vi.fn(),
  DELETE: vi.fn(),
}));
vi.mock('./auth', () => ({ getAccessToken: vi.fn() }));
vi.mock('./api', async (importOriginal) => ({
  ...(await importOriginal<typeof import('./api')>()),
  client: { GET: api.GET, PUT: api.PUT, DELETE: api.DELETE },
}));

import { saveSlug, slugCandidates, slugProblem, suggestSlug } from './slugs';

const ok = { data: {}, response: new Response() };
beforeEach(() => {
  api.held = new Set();
  api.GET.mockReset().mockImplementation(async (_path, options) => ({
    data: (options.params.query.slug as string[])
      .filter((slug) => api.held.has(slug))
      .map((slug) => ({ slug, entity_id: slug, name: slug, kinds: ['item'] })),
    response: new Response(),
  }));
  api.PUT.mockReset().mockImplementation(async (_path, options) =>
    api.held.has(options.body.slug)
      ? { error: { detail: 'Taken.' }, response: new Response(null, { status: 409 }) }
      : ok,
  );
  api.DELETE.mockReset().mockResolvedValue(ok);
});

describe('slugCandidates', () => {
  it('gives a catalog item its title, then numbers', () => {
    expect(slugCandidates('Belt Pouch', 'item').slice(0, 3)).toEqual([
      'belt-pouch',
      'belt-pouch-2',
      'belt-pouch-3',
    ]);
  });

  it('numbers an instance from 1, leaving the bare title to its item', () => {
    expect(slugCandidates('Belt Pouch', 'instance').slice(0, 2)).toEqual([
      'belt-pouch-1',
      'belt-pouch-2',
    ]);
  });

  it('keeps every candidate within 100 characters, without a dash before its number', () => {
    const long = `${'a'.repeat(97)} bcd`;
    const candidates = slugCandidates(long, 'instance');
    expect(candidates.every((candidate) => candidate.length <= 100)).toBe(true);
    expect(candidates[0]).toBe(`${'a'.repeat(97)}-1`);
    expect(candidates.every((candidate) => slugProblem(candidate) === null)).toBe(true);
  });

  it('has none for a title with no letters or digits', () => {
    expect(slugCandidates('???', 'item')).toEqual([]);
  });
});

describe('suggestSlug', () => {
  it('suggests the first candidate nothing holds, asking once', async () => {
    api.held = new Set(['lantern', 'lantern-2']);
    expect(await suggestSlug('t', 'Lantern', 'item')).toBe('lantern-3');
    expect(api.GET).toHaveBeenCalledTimes(1);
  });

  it("doesn't ask when there's nothing to suggest", async () => {
    expect(await suggestSlug('t', '—', 'item')).toBe('');
    expect(api.GET).not.toHaveBeenCalled();
  });
});

describe('slugProblem', () => {
  it('accepts what a link can name, and says what else is wrong', () => {
    expect(slugProblem('Ashfangs_Blade-2')).toBeNull();
    expect(slugProblem('no spaces')).toMatch(/only letters, digits/);
    expect(slugProblem('-leading')).toMatch(/starts with a letter or digit/);
    expect(slugProblem('a'.repeat(101))).toMatch(/at most 100/);
  });
});

describe('saveSlug', () => {
  it('sends nothing when the slug is unchanged', async () => {
    await saveSlug('t', 'e', 'lantern', ' lantern ');
    await saveSlug('t', 'e', null, '');
    expect(api.PUT).not.toHaveBeenCalled();
    expect(api.DELETE).not.toHaveBeenCalled();
  });

  it('clears a slug that was emptied, and sets a changed one', async () => {
    await saveSlug('t', 'e', 'lantern', '');
    expect(api.DELETE).toHaveBeenCalledTimes(1);
    await saveSlug('t', 'e', null, 'lantern');
    expect(api.PUT).toHaveBeenCalledWith(expect.any(String), {
      params: { path: { tenant_id: 't', entity_id: 'e' } },
      body: { slug: 'lantern' },
    });
  });

  it("refuses a slug that can't be one, before asking", async () => {
    await expect(saveSlug('t', 'e', null, 'no spaces')).rejects.toThrow(/only letters/);
    expect(api.PUT).not.toHaveBeenCalled();
  });

  it('says so when another entity holds it', async () => {
    api.held = new Set(['lantern']);
    await expect(saveSlug('t', 'e', null, 'lantern')).rejects.toThrow(
      'Another entity already uses “lantern”.',
    );
  });
});
