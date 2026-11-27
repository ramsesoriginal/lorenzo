// The reads and writes of who sees a being (ADR 0529); the words are lib/seenBy.ts.

import { client, unwrap } from './api';
import type { Audience } from './seenBy';

/** The audience and the version it is at, or null when the reader may not see who sees it. */
export async function loadSeenBy(
  tenantId: string,
  entityId: string,
): Promise<{ audience: Audience; version: string } | null> {
  try {
    const got = await client.GET('/tenants/{tenant_id}/entities/{entity_id}/audience', {
      params: { path: { tenant_id: tenantId, entity_id: entityId } },
    });
    const audience = await unwrap(got);
    const version = got.response.headers.get('etag');

    return version ? { audience, version } : null;
  } catch {
    return null;
  }
}

/** Says who sees it, at the version read; returns the new version. */
export async function saveSeenBy(
  tenantId: string,
  entityId: string,
  audience: Audience,
  version: string,
): Promise<string> {
  const put = await client.PUT('/tenants/{tenant_id}/entities/{entity_id}/audience', {
    params: {
      path: { tenant_id: tenantId, entity_id: entityId },
      header: { 'if-match': version },
    },
    body: audience,
  });

  await unwrap(put);

  return put.response.headers.get('etag') ?? version;
}
