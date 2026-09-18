import { apiFetch } from './api';
import type { CampaignSummaryOut, Page, TenantSummaryOut } from './types';

// No pager UI yet (matches notifications.ts's own precedent) - a client
// with over 50 tenants/campaigns is a later slice's problem.
const PAGE_SIZE = 50;

export async function listMyTenants(): Promise<Page<TenantSummaryOut>> {
  return apiFetch<Page<TenantSummaryOut>>(`/tenants?page=1&size=${PAGE_SIZE}`);
}

export async function listTenantCampaigns(tenantId: string): Promise<Page<CampaignSummaryOut>> {
  return apiFetch<Page<CampaignSummaryOut>>(
    `/tenants/${tenantId}/campaigns?page=1&size=${PAGE_SIZE}`,
  );
}
