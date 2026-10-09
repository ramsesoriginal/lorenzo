// The command layer's transport on the typed client (ADR 0122), for one repository.

import {
  fetchAllPages,
  LorenzoApiError,
  type LorenzoClient,
  MAX_PAGE_SIZE,
  unwrap,
} from '@lorenzo/api-client';
import {
  type EntryState,
  type EntrySummary,
  type NewEntry,
  type NewText,
  OfflineError,
  RefusedError,
  type TextDoc,
  type Transport,
} from '../core/transport';

/** A refusal from the API as the layer understands it; a missing connection as offline. */
function translate(e: unknown): never {
  if (e instanceof LorenzoApiError) {
    throw new RefusedError(e.message, e.status === 412);
  }
  // fetch rejects with a TypeError when there is no connection (or the request was blocked), and
  // says so in its own words in each browser. Any other TypeError is a bug, not a lost connection.
  if (e instanceof TypeError && /fetch|network|load failed/i.test(e.message))
    throw new OfflineError();
  throw e;
}

export function apiTransport(client: LorenzoClient, tenantId: string): Transport {
  const path = { tenant_id: tenantId };

  async function read(id: string): Promise<EntryState> {
    const res = await client.GET('/tenants/{tenant_id}/entities/{entity_id}', {
      params: { path: { ...path, entity_id: id } },
    });
    const entry = await unwrap(res);
    const docs = (type: string): TextDoc[] =>
      entry.information
        .filter((info) => info.type === type)
        .flatMap((info) => {
          const text = info.payloads.find((p) => p.kind === 'description');
          if (!text || text.kind !== 'description') return [];
          return [
            {
              id: info.id,
              payloadId: text.id,
              title: info.title,
              text: text.content,
              // The payload's own `updated_at`, as a weak ETag (ADR 0108).
              version: `W/"${text.updated_at}"`,
            },
          ];
        });
    return {
      id,
      name: entry.name,
      kinds: [...entry.kinds],
      parentIds: entry.prototypes.map((p) => p.id),
      childIds: entry.children.map((c) => c.id),
      description: docs('description')[0] ?? null,
      notes: docs('note'),
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

    getEntry: (id) => guarded(() => read(id)),

    // 201 when made, 200 when the id was already this library's (ADR 0222): both are done.
    createEntry: (entry: NewEntry) =>
      guarded(async () => {
        await unwrap(
          await client.POST('/tenants/{tenant_id}/entities', {
            params: { path },
            body: {
              id: entry.id,
              name: entry.name,
              kinds: entry.kinds.filter(
                (k): k is 'item' | 'being' => k === 'item' || k === 'being',
              ),
              parents: entry.parents,
            },
          }),
        );
        return read(entry.id);
      }),

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

    // 201 when made, 200 when the id was already this entry's (ADR 0222): both are done.
    createText: (entryId, text: NewText) =>
      guarded(async () => {
        await unwrap(
          await client.POST('/tenants/{tenant_id}/entities/{entity_id}/information', {
            params: { path: { ...path, entity_id: entryId } },
            body: {
              id: text.id,
              title: text.title,
              type: text.type,
              is_public: false,
              content: text.text,
              locale: typeof navigator === 'undefined' ? 'en-US' : navigator.language || 'en-US',
            },
          }),
        );
      }),

    setText: (payloadId, text, version) =>
      guarded(async () => {
        await unwrap(
          await client.PATCH('/tenants/{tenant_id}/payloads/{payload_id}', {
            params: { path: { ...path, payload_id: payloadId }, header: ifMatch(version) },
            body: { content: text },
          }),
        );
      }),

    setParents: (id, parentIds, etag) =>
      guarded(async () => {
        await unwrap(
          await client.PUT('/tenants/{tenant_id}/entities/{entity_id}/parents', {
            params: { path: { ...path, entity_id: id }, header: ifMatch(etag) },
            body: { parent_ids: parentIds },
          }),
        );
        return read(id);
      }),
  };
}
