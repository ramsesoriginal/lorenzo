import { apiDelete, apiFetch, apiPost, apiPut } from './api';
import type {
  CampaignCreate,
  CampaignOut,
  CampaignSummaryOut,
  GmOut,
  Page,
  PlayerCreate,
  TenantSummaryOut,
} from './types';

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

export async function createCampaign(tenantId: string, body: CampaignCreate): Promise<CampaignOut> {
  return apiPost<CampaignOut>(`/tenants/${tenantId}/campaigns`, body);
}

// Unpaginated - GmOut's own docstring calls this "inherently small and
// bounded by construction," matching OwnedByResponse's precedent.
export async function listCampaignGms(tenantId: string, campaignId: string): Promise<GmOut[]> {
  return apiFetch<GmOut[]>(`/tenants/${tenantId}/campaigns/${campaignId}/gms`);
}

export async function grantCampaignGm(
  tenantId: string,
  campaignId: string,
  userId: string,
): Promise<void> {
  await apiPut<void>(`/tenants/${tenantId}/campaigns/${campaignId}/gms/${userId}`, undefined);
}

export async function revokeCampaignGm(
  tenantId: string,
  campaignId: string,
  userId: string,
): Promise<void> {
  await apiDelete<void>(`/tenants/${tenantId}/campaigns/${campaignId}/gms/${userId}`);
}

export async function invitePlayer(
  tenantId: string,
  campaignId: string,
  body: PlayerCreate,
): Promise<void> {
  await apiPost<void>(`/tenants/${tenantId}/campaigns/${campaignId}/players`, body);
}
