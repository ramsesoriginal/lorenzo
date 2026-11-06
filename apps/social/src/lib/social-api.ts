import { client, type Schema, unwrap } from './api';

export type Relationship = Schema<'RelationshipEntryOut'>;
export type RelationshipCreate = Schema<'RelationshipCreate'>;

export type EntryKind = Schema<'EntityDetailOut'>['kinds'][number];

export interface EntryChoice {
  id: string;
  name: string;
  kinds: string[];
}

/** Entries the person may see, found by name. */
export async function findEntries(
  tenant: string,
  query: string,
  kind?: EntryKind,
): Promise<EntryChoice[]> {
  const page = await unwrap(
    await client.GET('/tenants/{tenant_id}/entities', {
      params: {
        path: { tenant_id: tenant },
        query: { q: query, size: 12, ...(kind ? { kind: [kind] } : {}) },
      },
      cache: 'no-cache',
    }),
  );
  return page.items.map((entry) => ({ id: entry.id, name: entry.name, kinds: [...entry.kinds] }));
}

/** One page of the relationships the person may see. */
export async function listRelationships(
  tenant: string,
  options: { page: number; q?: string; end?: string },
) {
  return unwrap(
    await client.GET('/tenants/{tenant_id}/relationships', {
      params: {
        path: { tenant_id: tenant },
        query: {
          page: options.page,
          size: 25,
          ...(options.q ? { q: options.q } : {}),
          ...(options.end ? { end: options.end } : {}),
        },
      },
      cache: 'no-cache',
    }),
  );
}

export async function readRelationship(tenant: string, id: string) {
  const result = await client.GET('/tenants/{tenant_id}/relationships/{relationship_id}', {
    params: { path: { tenant_id: tenant, relationship_id: id } },
    cache: 'no-cache',
  });
  const relationship = await unwrap(result);
  return { relationship, version: result.response.headers.get('etag') ?? '' };
}

export async function createRelationship(tenant: string, body: RelationshipCreate) {
  return unwrap(
    await client.POST('/tenants/{tenant_id}/relationships', {
      params: { path: { tenant_id: tenant } },
      body,
    }),
  );
}

/** Replaces the ends and the direction under the version the page was read at. */
export async function replaceRelationship(
  tenant: string,
  id: string,
  version: string,
  body: { end_a: string; end_b: string; one_way: boolean },
) {
  return unwrap(
    await client.PUT('/tenants/{tenant_id}/relationships/{relationship_id}', {
      params: { path: { tenant_id: tenant, relationship_id: id } },
      headers: { 'If-Match': version },
      body,
    }),
  );
}

/** What the entry is of (its types) and what it holds (its standings), as the page may read it. */
export async function readEntry(tenant: string, id: string) {
  return unwrap(
    await client.GET('/tenants/{tenant_id}/entities/{entity_id}', {
      params: { path: { tenant_id: tenant, entity_id: id } },
      cache: 'no-cache',
    }),
  );
}

/** Opens or restricts who reads it, under the audience's own version. */
export async function setPublic(tenant: string, id: string, isPublic: boolean) {
  const current = await client.GET('/tenants/{tenant_id}/entities/{entity_id}/audience', {
    params: { path: { tenant_id: tenant, entity_id: id } },
    cache: 'no-cache',
  });
  const audience = await unwrap(current);
  return unwrap(
    await client.PUT('/tenants/{tenant_id}/entities/{entity_id}/audience', {
      params: { path: { tenant_id: tenant, entity_id: id } },
      headers: { 'If-Match': current.response.headers.get('etag') ?? '' },
      body: { ...audience, is_public: isPublic },
    }),
  );
}

export async function deleteRelationship(tenant: string, id: string, version: string) {
  const result = await client.DELETE('/tenants/{tenant_id}/relationships/{relationship_id}', {
    params: { path: { tenant_id: tenant, relationship_id: id } },
    headers: { 'If-Match': version },
  });
  if (!result.response.ok) await unwrap(result as never);
}
