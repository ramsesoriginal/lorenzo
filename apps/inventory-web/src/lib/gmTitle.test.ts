import { beforeEach, describe, expect, it, vi } from 'vitest';
import { privateTo } from '../components/Notes/renderer';

const api = vi.hoisted(() => ({
  campaigns: [] as { id: string; gm_title: string; gm_title_plural: string }[],
  // character id -> the campaigns its roster is in
  rosters: {} as Record<string, string[]>,
  seats: [] as { tenant_id: string; campaign_id: string; characters: { entity_id: string }[] }[],
  GET: vi.fn(),
}));
vi.mock('./auth', () => ({ getAccessToken: vi.fn() }));
vi.mock('./api', async (importOriginal) => ({
  ...(await importOriginal<typeof import('./api')>()),
  client: { GET: api.GET },
}));

const page = <T>(items: T[]) => ({ items, total: items.length, page: 1, size: 100, pages: 1 });
const campaign = (id: string, title = 'GM', plural = 'GMs') => ({
  id,
  gm_title: title,
  gm_title_plural: plural,
});

beforeEach(() => {
  vi.resetModules();
  api.campaigns = [];
  api.rosters = {};
  api.seats = [];
  api.GET.mockReset().mockImplementation(async (path: string, options) => {
    if (path === '/me') return { data: { players: api.seats }, response: new Response() };
    if (path.endsWith('/campaigns')) return { data: page(api.campaigns), response: new Response() };

    const id = options?.params?.path?.character_id;
    const roster = api.rosters[id];

    if (!roster)
      return {
        error: { status: 404, title: 'Not found' },
        response: new Response(null, { status: 404 }),
      };

    return {
      data: { entity_id: id, players: roster.map((campaign_id) => ({ campaign_id })) },
      response: new Response(),
    };
  });
});

describe('gmWords', () => {
  it('says GM for no campaign at all', async () => {
    const { gmWords } = await import('./gmTitle');
    expect(gmWords([])).toEqual({ title: 'GM', plural: 'GMs' });
  });

  it("uses a campaign's own words", async () => {
    const { gmWords } = await import('./gmTitle');
    expect(gmWords([campaign('a', 'Storyteller', 'Storytellers')])).toEqual({
      title: 'Storyteller',
      plural: 'Storytellers',
    });
  });

  it('uses them when every campaign involved has the same ones', async () => {
    const { gmWords } = await import('./gmTitle');
    expect(
      gmWords([
        campaign('a', 'Storyteller', 'Storytellers'),
        campaign('b', 'Storyteller', 'Storytellers'),
      ]),
    ).toEqual({ title: 'Storyteller', plural: 'Storytellers' });
  });

  it('says GM when the campaigns disagree, on either word', async () => {
    const { gmWords } = await import('./gmTitle');
    expect(gmWords([campaign('a', 'Storyteller', 'Storytellers'), campaign('b')])).toEqual({
      title: 'GM',
      plural: 'GMs',
    });
    expect(
      gmWords([campaign('a', 'Master', 'Masters'), campaign('b', 'Master', 'Maestri')]),
    ).toEqual({
      title: 'GM',
      plural: 'GMs',
    });
  });

  it('keeps the words as written', async () => {
    const { gmWords } = await import('./gmTitle');
    expect(gmWords([campaign('a', 'dungeon Master', 'dungeon Masters')]).title).toBe(
      'dungeon Master',
    );
  });
});

describe('gmWordsOfBeing', () => {
  it('says GM for no being', async () => {
    const { gmWordsOfBeing } = await import('./gmTitle');
    expect(await gmWordsOfBeing('t', null)).toEqual({ title: 'GM', plural: 'GMs' });
    expect(api.GET).not.toHaveBeenCalled();
  });

  it("reads the words of the campaigns on the being's roster", async () => {
    const { gmWordsOfBeing } = await import('./gmTitle');
    api.campaigns = [campaign('a', 'Narrator', 'Narrators'), campaign('b')];
    api.rosters = { ashfang: ['a'] };
    expect(await gmWordsOfBeing('t', 'ashfang')).toEqual({
      title: 'Narrator',
      plural: 'Narrators',
    });
  });

  it('says GM for a being in two campaigns that name theirs differently', async () => {
    const { gmWordsOfBeing } = await import('./gmTitle');
    api.campaigns = [campaign('a', 'Narrator', 'Narrators'), campaign('b')];
    api.rosters = { ashfang: ['a', 'b'] };
    expect(await gmWordsOfBeing('t', 'ashfang')).toEqual({ title: 'GM', plural: 'GMs' });
  });

  it('says GM for a bare being, which has no roster to read', async () => {
    const { gmWordsOfBeing } = await import('./gmTitle');
    api.campaigns = [campaign('a', 'Narrator', 'Narrators')];
    expect(await gmWordsOfBeing('t', 'a-bare-being')).toEqual({ title: 'GM', plural: 'GMs' });
  });

  it("falls back to the viewer's own seats when the roster can't be read", async () => {
    const { gmWordsOfBeing } = await import('./gmTitle');
    api.campaigns = [campaign('a', 'Narrator', 'Narrators')];
    api.seats = [{ tenant_id: 't', campaign_id: 'a', characters: [{ entity_id: 'ashfang' }] }];
    expect(await gmWordsOfBeing('t', 'ashfang')).toEqual({
      title: 'Narrator',
      plural: 'Narrators',
    });
  });
});

describe('what a private note says', () => {
  const storytellers = { title: 'Storyteller', plural: 'Storytellers' };
  const gms = { title: 'GM', plural: 'GMs' };

  it("names the campaign's game masters by the campaign's words", () => {
    expect(privateTo(null, storytellers)).toBe("Otherwise only the campaign's Storytellers can.");
    expect(privateTo({ entity_id: 'x', name: 'Ashfang' }, storytellers)).toBe(
      "Otherwise only Ashfang's players and the campaign's Storytellers can.",
    );
  });

  it('still says GMs by default', () => {
    expect(privateTo(null, gms)).toBe("Otherwise only the campaign's GMs can.");
  });
});
