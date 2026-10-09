// The command layer's transport on the typed client (ADR 0122), for one repository.

import {
  fetchAllPages,
  LorenzoApiError,
  type LorenzoClient,
  MAX_PAGE_SIZE,
  unwrap,
} from '@lorenzo/api-client';
import {
  type EntrySummary,
  type ItemState,
  OfflineError,
  RefusedError,
  type Transport,
} from '../core/transport';

/** A refusal from the API as the layer understands it; a missing connection as offline. */
function translate(e: unknown): never {
  if (e instanceof LorenzoApiError) {
    throw new RefusedError(e.message, e.status === 412);
  }
  // fetch rejects with a TypeError when there is no connection (or the request was blocked).
  if (e instanceof TypeError) throw new OfflineError();
  throw e;
}

export function apiTransport(client: LorenzoClient, tenantId: string): Transport {
  const path = { tenant_id: tenantId };

  async function read(id: string): Promise<ItemState> {
    const res = await client.GET('/tenants/{tenant_id}/items/{entity_id}', {
      params: { path: { ...path, entity_id: id } },
    });
    const item = await unwrap(res);
    return {
      id,
      name: item.title,
      parentIds: item.prototype_ids,
      etag: res.response.headers.get('etag'),
    };
  }

  const guarded = async <T>(work: () => Promise<T>): Promise<T> => {
    try {
      return await work();
    } catch (e) {
      return translate(e);
    }
  };
  // A null header is left out of the request by the client.
  const ifMatch = (etag: string | null) => ({ 'if-match': etag });

  return {
    listEntries: () =>
      guarded(async (): Promise<EntrySummary[]> => {
        const rows = await fetchAllPages(async (page) =>
          unwrap(
            await client.GET('/tenants/{tenant_id}/entities', {
              params: { path, query: { page, size: MAX_PAGE_SIZE } },
            }),
          ),
        );
        return rows.map((r) => ({ id: r.id, name: r.name, kinds: [...r.kinds] }));
      }),

    getItem: (id) => guarded(() => read(id)),

    setName: (id, name, etag) =>
      guarded(async () => {
        await unwrap(
          await client.PATCH('/tenants/{tenant_id}/items/{entity_id}', {
            params: { path: { ...path, entity_id: id }, header: ifMatch(etag) },
            body: { name },
          }),
        );
        return read(id);
      }),

    setParents: (id, parentIds, etag) =>
      guarded(async () => {
        await unwrap(
          await client.PUT('/tenants/{tenant_id}/items/{entity_id}/prototypes', {
            params: { path: { ...path, entity_id: id }, header: ifMatch(etag) },
            body: { prototype_ids: parentIds },
          }),
        );
        return read(id);
      }),
  };
}
