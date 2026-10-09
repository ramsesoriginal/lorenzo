import { createLorenzoClient } from '@lorenzo/api-client';
import { describe, expect, it } from 'vitest';
import { OfflineError, RefusedError } from '../core/transport';
import { apiTransport } from './transport';

const T = '11111111-1111-1111-1111-111111111111';
const E = '22222222-2222-2222-2222-222222222222';
const P = '33333333-3333-3333-3333-333333333333';

type Call = { method: string; url: string; ifMatch: string | null; body: unknown };

function setup(answer: (r: Request, calls: Call[]) => Response | Promise<Response>) {
  const calls: Call[] = [];
  const client = createLorenzoClient({
    baseUrl: 'http://api.test',
    getAccessToken: () => 'token',
    fetch: async (request) => {
      const body = request.method === 'GET' ? undefined : await request.clone().json();
      calls.push({
        method: request.method,
        url: new URL(request.url).pathname + new URL(request.url).search,
        ifMatch: request.headers.get('if-match'),
        body,
      });
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

const item = { title: 'Wolf', prototype_ids: [P] };

describe('apiTransport', () => {
  it('lists the entries, every page', async () => {
    const { transport, calls } = setup((r) => {
      const page = Number(new URL(r.url).searchParams.get('page'));
      return json({
        items: [{ id: `id${page}`, name: `Entry ${page}`, kinds: ['item'] }],
        total: 2,
        page,
        size: 100,
        pages: 2,
      });
    });
    const rows = await transport.listEntries();
    expect(rows.map((r) => r.name)).toEqual(['Entry 1', 'Entry 2']);
    expect(calls.every((c) => c.url.startsWith(`/tenants/${T}/entities?`))).toBe(true);
  });

  it('reads an item with its parents and its etag', async () => {
    const { transport } = setup(() => json(item, { etag: '"abc"' }));
    expect(await transport.getItem(E)).toEqual({
      id: E,
      name: 'Wolf',
      parentIds: [P],
      etag: '"abc"',
    });
  });

  it('renames with If-Match, then reads the item again for the new etag', async () => {
    const { transport, calls } = setup((r) =>
      r.method === 'PATCH' ? json(item) : json({ ...item, title: 'Dire wolf' }, { etag: '"def"' }),
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
      r.method === 'PUT' ? json({}) : json(item, { etag: '"x"' }),
    );
    await transport.setParents(E, [P, T], null);
    expect(calls[0]).toMatchObject({
      method: 'PUT',
      url: `/tenants/${T}/items/${E}/prototypes`,
      ifMatch: null,
      body: { prototype_ids: [P, T] },
    });
  });

  it('a stale If-Match is a precondition failure; another refusal is not', async () => {
    const stale = setup(() => json({ detail: 'Stale.' }, { status: 412 }));
    await expect(stale.transport.setName(E, 'x', '"old"')).rejects.toMatchObject({
      name: 'RefusedError',
      precondition: true,
    });
    const other = setup(() => json({ detail: 'No such item.' }, { status: 404 }));
    const error = await other.transport.getItem(E).catch((e) => e);
    expect(error).toBeInstanceOf(RefusedError);
    expect(error.precondition).toBe(false);
    expect(error.message).toBe('No such item.');
  });

  it('no connection is offline, not a refusal', async () => {
    const { transport } = setup(() => {
      throw new TypeError('Failed to fetch');
    });
    await expect(transport.getItem(E)).rejects.toBeInstanceOf(OfflineError);
  });
});
