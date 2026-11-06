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
export async function readGraph(tenant: string, id: string) {
  return unwrap(
    await client.GET('/tenants/{tenant_id}/social-webs/{web_id}/graph', {
      params: { path: { tenant_id: tenant, web_id: id } },
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
