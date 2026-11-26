import { client, type Schema, unwrap } from './api';

export type WebDetail = Schema<'SocialWebDetail'>;
export type WebGraph = Schema<'SocialWebGraph'>;
export type WebSettings = Schema<'SocialWebSettings'>;
export type Layout = NonNullable<WebSettings['layout']>;

/** One page of the webs the person may see. */
export async function listWebs(tenant: string, page: number) {
  return unwrap(
    await client.GET('/tenants/{tenant_id}/social-webs', {
      params: { path: { tenant_id: tenant }, query: { page, size: 25 } },
      cache: 'no-cache',
    }),
  );
}

export async function createWeb(
  tenant: string,
  body: { name: string; layout: Layout; is_public: boolean },
) {
  return unwrap(
    await client.POST('/tenants/{tenant_id}/social-webs', {
      params: { path: { tenant_id: tenant } },
      body: { ...body, layout_seed: 1 },
    }),
  );
}

export async function readWeb(tenant: string, id: string) {
  const result = await client.GET('/tenants/{tenant_id}/social-webs/{web_id}', {
    params: { path: { tenant_id: tenant, web_id: id } },
    cache: 'no-cache',
  });
  const web = await unwrap(result);
  return { web, version: result.response.headers.get('etag') ?? '' };
}

/** What the person draws: the members they may see and the relationships between them. */
export async function readGraph(
  tenant: string,
  id: string,
  lens: { asOf?: string | null; asSeenBy?: string | null } = {},
) {
  return unwrap(
    await client.GET('/tenants/{tenant_id}/social-webs/{web_id}/graph', {
      params: {
        path: { tenant_id: tenant, web_id: id },
        query: {
          ...(lens.asOf ? { as_of: lens.asOf } : {}),
          ...(lens.asSeenBy ? { as_seen_by: lens.asSeenBy } : {}),
        },
      },
      cache: 'no-cache',
    }),
  );
}

export async function saveSettings(tenant: string, id: string, version: string, body: WebSettings) {
  const result = await client.PUT('/tenants/{tenant_id}/social-webs/{web_id}', {
    params: { path: { tenant_id: tenant, web_id: id } },
    headers: { 'If-Match': version },
    body,
  });
  return { web: await unwrap(result), version: result.response.headers.get('etag') ?? version };
}

export async function writeMembers(
  tenant: string,
  id: string,
  version: string,
  body: { set?: { entry_id: string; x?: number | null; y?: number | null }[]; remove?: string[] },
) {
  const result = await client.POST('/tenants/{tenant_id}/social-webs/{web_id}/members/bulk', {
    params: { path: { tenant_id: tenant, web_id: id } },
    headers: { 'If-Match': version },
    body,
  });
  return { web: await unwrap(result), version: result.response.headers.get('etag') ?? version };
}

export async function saveTypes(tenant: string, id: string, version: string, typeIds: string[]) {
  const result = await client.PUT('/tenants/{tenant_id}/social-webs/{web_id}/types', {
    params: { path: { tenant_id: tenant, web_id: id } },
    headers: { 'If-Match': version },
    body: { type_ids: typeIds },
  });
  return { web: await unwrap(result), version: result.response.headers.get('etag') ?? version };
}

/** Rename a web: it is an entry, so its name is written with the entry's own route. */
export async function renameWeb(tenant: string, id: string, name: string) {
  const path = { tenant_id: tenant, entity_id: id };
  const read = await client.GET('/tenants/{tenant_id}/entities/{entity_id}', {
    params: { path },
    cache: 'no-cache',
  });
  await unwrap(read);
  await unwrap(
    await client.PATCH('/tenants/{tenant_id}/entities/{entity_id}', {
      params: { path },
      headers: { 'If-Match': read.response.headers.get('etag') ?? '' },
      body: { name },
    }),
  );
}

/** Delete a web. It holds no entries of its own, only which ones it shows, so nothing else goes. */
export async function deleteWeb(tenant: string, id: string) {
  const path = { tenant_id: tenant, entity_id: id };
  const read = await client.GET('/tenants/{tenant_id}/entities/{entity_id}', {
    params: { path },
    cache: 'no-cache',
  });
  await unwrap(read);
  const result = await client.DELETE('/tenants/{tenant_id}/entities/{entity_id}', {
    params: { path },
    headers: { 'If-Match': read.response.headers.get('etag') ?? '' },
  });
  if (!result.response.ok) await unwrap(result as never);
}
