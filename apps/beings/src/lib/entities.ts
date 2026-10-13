import { client, unwrap } from './api';
import type { EntityDetail } from './types';

// GET /tenants/{t}/entities/{id} - the entry's own name and link name, its stats with whether each is
// its own (ADR 0111), its information and kinds.
export async function getEntityDetail(tenantId: string, entityId: string): Promise<EntityDetail> {
  return unwrap(
    await client.GET('/tenants/{tenant_id}/entities/{entity_id}', {
      params: { path: { tenant_id: tenantId, entity_id: entityId } },
    }),
  );
}
