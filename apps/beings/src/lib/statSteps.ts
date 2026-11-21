// The read of a being's stat history (ADR 0525); what the steps mean is lib/statHistory.ts.
import { client, unwrap } from './api';
import type { StatStep } from './statHistory';

/** The last steps of a being, newest first (at most thirty). */
export async function listStatSteps(tenantId: string, entityId: string): Promise<StatStep[]> {
  return unwrap(
    await client.GET('/tenants/{tenant_id}/entities/{entity_id}/stat-changes', {
      params: { path: { tenant_id: tenantId, entity_id: entityId } },
    }),
  );
}
