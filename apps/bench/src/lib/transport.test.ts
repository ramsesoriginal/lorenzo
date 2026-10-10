import { createLorenzoClient } from '@lorenzo/api-client';
import { describe, expect, it } from 'vitest';
import { OfflineError, RefusedError } from '../core/transport';
import { apiTransport } from './transport';

const T = '11111111-1111-1111-1111-111111111111';
const E = '22222222-2222-2222-2222-222222222222';
const P = '33333333-3333-3333-3333-333333333333';
const S_INT = '44444444-4444-4444-4444-444444444444';
const S_BOOL = '55555555-5555-5555-5555-555555555555';
const definition = (id: string, name: string, value_type: string) => ({
  id,
  name,
  value_type,
  enum_values: [],
  stat_group_id: P,
});
const definitions = [definition(S_INT, 'armor', 'int'), definition(S_BOOL, 'magical', 'bool')];

type Call = { method: string; url: string; ifMatch: string | null; body: unknown };

function setup(answer: (r: Request, calls: Call[]) => Response | Promise<Response>) {
  const calls: Call[] = [];
  const client = createLorenzoClient({
    baseUrl: 'http://api.test',
    getAccessToken: () => 'token',
    fetch: async (request) => {
      const text = request.method === 'GET' ? '' : await request.clone().text();
      const body = text ? JSON.parse(text) : undefined;
      calls.push({
        method: request.method,
        url: new URL(request.url).pathname + new URL(request.url).search,
        ifMatch: request.headers.get('if-match'),
        body,
      });
      if (request.url.includes('/stat-definitions')) {
        return json({ items: definitions, total: 2, page: 1, size: 100, pages: 1 });
      }
      return answer(request, calls);
    },
  });
  return { calls, transport: apiTransport(client, T) };
}

const json = (body: unknown, init: ResponseInit & { etag?: string } = {}) =>
  new Response(JSON.stringify(body), {
    status: init.status ?? 200,
    headers: { 'content-type': 'application/json', ...(init.etag ? { etag: init.etag } : {}) },
  });

const entry = {
  id: E,
  name: 'Wolf',
  kinds: ['item'],
  slug: 'wolf',
  stats: [
    { name: 'armor', value: 12, own: false },
    { name: 'magical', value: true, own: true },
  ],
  prototypes: [{ id: P, name: 'Beast' }],
  children: [{ id: T, name: 'Pup' }],
  information: [
    {
      id: 'i1',
      type: 'description',
      title: 'Description',
      payloads: [
        {
          id: 'p1',
          kind: 'description',
          content: 'Hunts in packs.',
          updated_at: '2026-10-09T10:00:00Z',
        },
      ],
    },
    {
      id: 'i2',
      type: 'note',
      title: 'Note',
      payloads: [
        {
          id: 'p2',
          kind: 'description',
          content: 'A ranger note.',
          updated_at: '2026-10-09T11:00:00Z',
        },
      ],
    },
    {
      id: 'i3',
      type: 'rumor',
      title: 'Rumor',
      payloads: [{ id: 'p3', kind: 'description', content: 'ignored', updated_at: 'x' }],
    },
  ],
};

describe('apiTransport', () => {
  it('lists the entries, every page', async () => {
    const { transport, calls } = setup((r) => {
      const page = Number(new URL(r.url).searchParams.get('page'));
      return json({
        items: [{ id: `id${page}`, name: `Entry ${page}`, kinds: ['item'], parent_ids: [P] }],
        total: 2,
        page,
        size: 100,
        pages: 2,
      });
    });
    const rows = await transport.listEntries();
    expect(rows.map((r) => r.name)).toEqual(['Entry 1', 'Entry 2']);
    expect(rows.map((r) => r.parentIds)).toEqual([[P], [P]]);
    expect(calls.every((c) => c.url.startsWith(`/tenants/${T}/entities?`))).toBe(true);
  });

  it('reads an entry with its kinds, parents, children and etag', async () => {
    const { transport, calls } = setup(() => json(entry, { etag: '"abc"' }));
    expect(await transport.getEntry(E)).toEqual({
      id: E,
      name: 'Wolf',
      kinds: ['item'],
      parentIds: [P],
      childIds: [T],
      description: {
        id: 'i1',
        payloadId: 'p1',
        title: 'Description',
        text: 'Hunts in packs.',
        version: 'W/"2026-10-09T10:00:00Z"',
      },
      notes: [
        {
          id: 'i2',
          payloadId: 'p2',
          title: 'Note',
          text: 'A ranger note.',
          version: 'W/"2026-10-09T11:00:00Z"',
        },
      ],
      stats: [
        { statId: S_INT, name: 'armor', value: 12, own: false },
        { statId: S_BOOL, name: 'magical', value: true, own: true },
      ],
      slug: 'wolf',
      etag: '"abc"',
    });
    expect(calls[0].url).toBe(`/tenants/${T}/entities/${E}`);
  });

  it('creates under the id the client made, with kinds and parents, and reads it back', async () => {
    const { transport, calls } = setup((r) =>
      r.method === 'POST' ? json(entry, { status: 201 }) : json(entry, { etag: '"n"' }),
    );
    const made = await transport.createEntry({
      id: E,
      name: 'Wolf',
      kinds: ['item'],
      parents: [P],
    });
    expect(calls[0]).toMatchObject({
      method: 'POST',
      url: `/tenants/${T}/entities`,
      body: { id: E, name: 'Wolf', kinds: ['item'], parents: [P] },
    });
    expect(made.etag).toBe('"n"');
  });

  it('a replay (200) is as good as a create (201)', async () => {
    const { transport } = setup((r) =>
      r.method === 'POST' ? json(entry, { status: 200 }) : json(entry, { etag: '"n"' }),
    );
    await expect(
      transport.createEntry({ id: E, name: 'Wolf', kinds: [], parents: [] }),
    ).resolves.toMatchObject({ id: E });
  });

  it("an id that is not available is a refusal with the API's words", async () => {
    const { transport } = setup(() =>
      json({ detail: 'That id is not available.' }, { status: 409 }),
    );
    await expect(
      transport.createEntry({ id: E, name: 'x', kinds: [], parents: [] }),
    ).rejects.toMatchObject({ name: 'RefusedError', message: 'That id is not available.' });
  });

  it('renames with If-Match, then reads the item again for the new etag', async () => {
    const { transport, calls } = setup((r) =>
      r.method === 'PATCH' ? json({}) : json({ ...entry, name: 'Dire wolf' }, { etag: '"def"' }),
    );
    const after = await transport.setName(E, 'Dire wolf', '"abc"');
    expect(calls[0]).toMatchObject({
      method: 'PATCH',
      url: `/tenants/${T}/items/${E}`,
      ifMatch: '"abc"',
      body: { name: 'Dire wolf' },
    });
    expect(after).toMatchObject({ name: 'Dire wolf', etag: '"def"' });
  });

  it('sets parents as the complete new list', async () => {
    const { transport, calls } = setup((r) =>
      r.method === 'PUT' ? json({}) : json(entry, { etag: '"x"' }),
    );
    await transport.setParents(E, [P, T], null);
    expect(calls[0]).toMatchObject({
      method: 'PUT',
      url: `/tenants/${T}/entities/${E}/parents`,
      ifMatch: null,
      body: { parent_ids: [P, T] },
    });
  });

  it('makes a description or a note under the id the client made, restricted by default', async () => {
    const { transport, calls } = setup(() => json({}, { status: 201 }));
    await transport.createText(E, { id: P, type: 'note', title: 'Note', text: 'Hello' });
    expect(calls[0]).toMatchObject({
      method: 'POST',
      url: `/tenants/${T}/entities/${E}/information`,
      body: { id: P, type: 'note', title: 'Note', is_public: false, content: 'Hello' },
    });
  });

  it("writes the text of a payload with the payload's own If-Match", async () => {
    const { transport, calls } = setup(() => json({}));
    await transport.setText('p1', 'New', 'W/"2026-10-09T10:00:00Z"');
    expect(calls[0]).toMatchObject({
      method: 'PATCH',
      url: `/tenants/${T}/payloads/p1`,
      ifMatch: 'W/"2026-10-09T10:00:00Z"',
      body: { content: 'New' },
    });
  });

  it('a stale text version is a precondition failure', async () => {
    const { transport } = setup(() => json({ detail: 'Stale.' }, { status: 412 }));
    await expect(transport.setText('p1', 'x', 'W/"old"')).rejects.toMatchObject({
      precondition: true,
    });
  });

  it('a bug is not a lost connection', async () => {
    const { transport } = setup(() => json({ nonsense: true }));
    await expect(transport.getEntry(E)).rejects.toBeInstanceOf(TypeError);
  });

  it('a stale If-Match is a precondition failure; another refusal is not', async () => {
    const stale = setup(() => json({ detail: 'Stale.' }, { status: 412 }));
    await expect(stale.transport.setName(E, 'x', '"old"')).rejects.toMatchObject({
      name: 'RefusedError',
      precondition: true,
    });
    const other = setup(() => json({ detail: 'No such item.' }, { status: 404 }));
    const error = await other.transport.getEntry(E).catch((e) => e);
    expect(error).toBeInstanceOf(RefusedError);
    expect(error.precondition).toBe(false);
    expect(error.message).toBe('No such item.');
  });

  it('no connection is offline, not a refusal', async () => {
    const { transport } = setup(() => {
      throw new TypeError('Failed to fetch');
    });
    await expect(transport.getEntry(E)).rejects.toBeInstanceOf(OfflineError);
  });
  describe('link names', () => {
    const base = `/tenants/${T}/entities`;
    const made = (answer: (r: Request, n: number) => Response) => {
      let n = 0;
      const { transport, calls } = setup((r) => {
        if (r.method === 'POST') return answer(r, ++n);
        return json(entry, { etag: '"n"' });
      });
      return { transport, calls };
    };

    it('creates with the link name it is given', async () => {
      const { transport, calls } = made(() => json(entry, { status: 201 }));
      await transport.createEntry({
        id: E,
        name: 'Wolf',
        kinds: ['item'],
        parents: [],
        slug: 'wolf',
      });
      expect(calls[0]).toMatchObject({ method: 'POST', url: base, body: { id: E, slug: 'wolf' } });
    });

    it('sends none when it has none', async () => {
      const { transport, calls } = made(() => json(entry, { status: 201 }));
      await transport.createEntry({ id: E, name: '日本', kinds: [], parents: [], slug: null });
      expect(calls[0].body).not.toHaveProperty('slug');
    });

    it('makes the entry without a link name when another entry has it (409), asking once more', async () => {
      const { transport, calls } = made((_r, n) =>
        n === 1 ? json({ detail: 'Slug in use.' }, { status: 409 }) : json(entry, { status: 201 }),
      );
      await transport.createEntry({ id: E, name: 'Wolf', kinds: [], parents: [], slug: 'wolf' });
      const posts = calls.filter((c) => c.method === 'POST');
      expect(posts).toHaveLength(2);
      expect(posts[0].body).toMatchObject({ slug: 'wolf' });
      expect(posts[1].body).not.toHaveProperty('slug');
    });

    it('a 409 with no link name sent is the answer, not asked again', async () => {
      const { transport, calls } = made(() => json({ detail: 'No.' }, { status: 409 }));
      await expect(
        transport.createEntry({ id: E, name: 'Wolf', kinds: [], parents: [], slug: null }),
      ).rejects.toMatchObject({ name: 'RefusedError' });
      expect(calls.filter((c) => c.method === 'POST')).toHaveLength(1);
    });

    it('sets a link name with PUT and takes it away with DELETE, reading the entry after', async () => {
      const { transport, calls } = setup((r) =>
        r.method === 'GET' ? json(entry, { etag: '"n"' }) : json({ entity_id: E, slug: 'x' }),
      );
      await transport.setSlug(E, 'blade');
      expect(calls[0]).toMatchObject({
        method: 'PUT',
        url: `${base}/${E}/slug`,
        body: { slug: 'blade' },
      });
      await transport.setSlug(E, null);
      expect(calls.find((c) => c.method === 'DELETE')).toMatchObject({
        url: `${base}/${E}/slug`,
      });
    });

    it("a link name another entry has is a refusal with the API's words", async () => {
      const { transport } = setup(() =>
        json({ detail: "Slug 'blade' is already in use." }, { status: 409 }),
      );
      await expect(transport.setSlug(E, 'blade')).rejects.toMatchObject({
        name: 'RefusedError',
        message: expect.stringContaining('already in use'),
      });
    });
  });

  describe('kinds', () => {
    const base = `/tenants/${T}/entities/${E}`;
    const send = async (kind: 'item' | 'being', on: boolean) => {
      const { transport, calls } = setup(() => json(entry, { etag: '"n"' }));
      const state = await transport.setKind(E, kind, on, '"old"');
      return { state, call: calls[0] };
    };

    it('gives a kind with PUT, with If-Match', async () => {
      const { call, state } = await send('being', true);
      expect(call).toMatchObject({ method: 'PUT', url: `${base}/kinds/being`, ifMatch: '"old"' });
      expect(state.etag).toBe('"n"');
    });

    it('takes a kind away with DELETE', async () => {
      expect((await send('item', false)).call).toMatchObject({
        method: 'DELETE',
        url: `${base}/kinds/item`,
        ifMatch: '"old"',
      });
    });

    it("a kind the entry cannot lose is a refusal with the server's words", async () => {
      const { transport } = setup(() =>
        json({ detail: 'Inventory items inherit from it.' }, { status: 409 }),
      );
      await expect(transport.setKind(E, 'item', false, null)).rejects.toMatchObject({
        name: 'RefusedError',
        message: 'Inventory items inherit from it.',
      });
    });
  });

  describe('stats', () => {
    const base = `/tenants/${T}/entities/${E}`;
    const written = { ...entry, previous: { had_own_value: false, value: null } };
    const sent = async (
      stat: { id: string; type: 'int' | 'bool' | 'text' },
      value: string | number | boolean | null,
    ) => {
      const { transport, calls } = setup(() => json(written, { etag: '"n"' }));
      const state = await transport.setStat(E, stat, value, '"old"');
      return { state, call: calls[0] };
    };

    it('lists the definitions with their types', async () => {
      const { transport } = setup(() => json({}));
      expect(await transport.listStatDefinitions()).toEqual([
        { id: S_INT, name: 'armor', type: 'int', enumValues: [] },
        { id: S_BOOL, name: 'magical', type: 'bool', enumValues: [] },
      ]);
    });

    it('writes a number to the stat route, with If-Match, and keeps the group', async () => {
      const { call, state } = await sent({ id: S_INT, type: 'int' }, 14);
      expect(call).toMatchObject({
        method: 'PUT',
        url: `${base}/stats/${S_INT}`,
        ifMatch: '"old"',
        body: { value: 14, acquire_group: true },
      });
      expect(state.etag).toBe('"n"');
    });

    it('sets a tag on, and off, through the tag routes', async () => {
      expect((await sent({ id: S_BOOL, type: 'bool' }, true)).call).toMatchObject({
        method: 'PUT',
        url: `${base}/tags/${S_BOOL}`,
      });
      expect((await sent({ id: S_BOOL, type: 'bool' }, false)).call).toMatchObject({
        method: 'PATCH',
        url: `${base}/tags/${S_BOOL}`,
      });
    });

    it('clears an own value: a bool through its tag, the rest through the stat', async () => {
      expect((await sent({ id: S_BOOL, type: 'bool' }, null)).call).toMatchObject({
        method: 'DELETE',
        url: `${base}/tags/${S_BOOL}`,
      });
      expect((await sent({ id: S_INT, type: 'int' }, null)).call).toMatchObject({
        method: 'DELETE',
        url: `${base}/stats/${S_INT}`,
      });
    });

    it('a stale If-Match on a stat is a precondition failure', async () => {
      const { transport } = setup(() => json({ detail: 'Stale.' }, { status: 412 }));
      await expect(
        transport.setStat(E, { id: S_INT, type: 'int' }, 1, '"old"'),
      ).rejects.toMatchObject({ precondition: true });
    });
  });
});
