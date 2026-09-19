import { apiFetch } from './api';
import type { BeingSummary, Page } from './types';

// GET /tenants/{t}/beings (ADR 0078) - every Being in the tenant: PCs,
// NPCs, and bare beings with no Character row at all, invisible to
// GET .../characters. The "pick a being" discovery step for a GM
// assigning loot to an NPC that was never promoted into a tracked
// Character. Supports search (`q`), unlike the old characters roster.
export async function listBeings(tenantId: string, query = ''): Promise<Page<BeingSummary>> {
  const qs = query ? `?q=${encodeURIComponent(query)}` : '';
  return apiFetch<Page<BeingSummary>>(`/tenants/${tenantId}/beings${qs}`);
}
