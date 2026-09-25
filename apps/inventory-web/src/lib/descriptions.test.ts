import { beforeEach, describe, expect, it, vi } from 'vitest';
import type { ResolvedSlug } from './entityLinks';

// An in-memory API: the slugs below, and one picture for Ashfang.
const api = vi.hoisted(() => ({ GET: vi.fn(), failResolve: false }));
vi.mock('./auth', () => ({ getAccessToken: vi.fn() }));
vi.mock('./me', () => ({ viewerLocales: async () => ['en-GB'] }));
vi.mock('./api', async (importOriginal) => ({
  ...(await importOriginal<typeof import('./api')>()),
  client: { GET: api.GET },
}));

import { descriptionRenderer } from './descriptions';

const ENTITIES: Record<string, ResolvedSlug> = {
  ashfang: { slug: 'ashfang', entity_id: 'e1', name: 'Ashfang', kinds: ['item_instance'] },
  mira: { slug: 'mira', entity_id: 'e2', name: 'Mira', kinds: ['being', 'character'] },
};
const ok = (data: unknown) => ({ data, response: new Response() });

type Params = { params: { path: Record<string, string>; query?: { slug: string[] } } };
beforeEach(() => {
  api.failResolve = false;
  api.GET.mockReset().mockImplementation(async (path: string, { params }: Params) => {
    switch (path) {
      case '/tenants/{tenant_id}/entities/resolve':
        if (api.failResolve) return { error: {}, response: new Response(null, { status: 500 }) };
        return ok(params.query?.slug.flatMap((slug) => ENTITIES[slug] ?? []));
      case '/tenants/{tenant_id}/entities/{entity_id}': {
        const payloads = params.path.entity_id === 'e1' ? [{ kind: 'picture', id: 'p1' }] : [];
        return ok({ information: [{ type: 'main_picture', payloads }] });
      }
      case '/tenants/{tenant_id}/payloads/{payload_id}/content':
        return ok(new Blob(['a picture']));
    }
    throw new Error(`unexpected ${path}`);
  });
});

const slugRequests = () =>
  api.GET.mock.calls
    .filter(([path]) => path === '/tenants/{tenant_id}/entities/resolve')
    .map(([, { params }]) => params.query.slug);

describe('descriptionRenderer', () => {
  it('resolves every text in one request, and routes each link by its kinds', async () => {
    const render = descriptionRenderer('t1');
    const [first, second] = await render(['[[Ashfang]] and [[Nobody]]', 'Ask [Mira](mira).']);

    expect(slugRequests()).toEqual([['ashfang', 'nobody', 'mira']]);
    expect(first?.html).toContain('href="/item/?tenant=t1&amp;id=e1"');
    expect(first?.html).not.toContain('nobody');
    expect(first?.notes).toEqual([
      'No entity has the slug “nobody” yet, so readers see plain text.',
    ]);
    expect(second?.html).toContain('href="/board/?tenant=t1&amp;character=e2"');
    expect(second?.notes).toEqual([]);
  });

  it('only asks about slugs it has not seen, found or not', async () => {
    const render = descriptionRenderer('t1');
    await render(['[[Ashfang]] [[Nobody]]']);
    await render(['[[Ashfang]] [[Nobody]] [[Mira]]']);
    await render(['[[Mira]]']);

    expect(slugRequests()).toEqual([['ashfang', 'nobody'], ['mira']]);
  });

  it('asks about at most 100 slugs per request', async () => {
    const text = Array.from({ length: 150 }, (_, i) => `[[s${i}]]`).join(' ');
    await descriptionRenderer('t1')([text]);

    expect(slugRequests().map((batch) => batch.length)).toEqual([100, 50]);
  });

  it("shows an entity's main picture through a blob: URL, once per entity", async () => {
    const render = descriptionRenderer('t1');
    const [shown] = await render(['![The blade](ashfang) ![Again](ashfang) ![Mira](mira)']);
    await render(['![The blade](ashfang)']);

    expect(shown?.html).toMatch(/<img src="blob:[^"]+" alt="The blade"/);
    expect(shown?.html).toContain('Mira');
    expect(shown?.notes).toEqual(['Mira has no picture, so readers see the alt text.']);
    const pictureReads = api.GET.mock.calls.filter(([path]) => path.endsWith('/content'));
    expect(pictureReads).toHaveLength(1);
  });

  it('renders links as plain text while the lookup fails, and tries again later', async () => {
    const render = descriptionRenderer('t1');
    api.failResolve = true;
    const [failed] = await render(['[[Ashfang]]']);
    api.failResolve = false;
    const [recovered] = await render(['[[Ashfang]]']);

    expect(failed?.html).toBe('<p>Ashfang</p>\n');
    expect(failed?.notes).toEqual([]);
    expect(recovered?.html).toContain('href="/item/?tenant=t1&amp;id=e1"');
  });
});
