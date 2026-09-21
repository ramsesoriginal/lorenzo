import { client, unwrap } from './api';
import type { BeingSummary, Page } from './types';

// GET /tenants/{t}/beings (ADR 0078) - every Being in the tenant: PCs,
// NPCs, and bare beings with no Character row at all, invisible to
// GET .../characters. The "pick a being" discovery step for a GM
// assigning loot to an NPC that was never promoted into a tracked
// Character. Supports search (`q`), unlike the old characters roster.
export async function listBeings(tenantId: string, query = ''): Promise<Page<BeingSummary>> {
  return unwrap(
    await client.GET('/tenants/{tenant_id}/beings', {
      params: { path: { tenant_id: tenantId }, query: { q: query || undefined } },
    }),
  );
}
