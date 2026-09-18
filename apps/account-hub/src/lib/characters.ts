import { apiFetch, apiPatch, apiPost } from './api';
import type { CampaignOut, CharacterCreate, CharacterOut, CharacterUpdate } from './types';

export async function getCampaign(tenantId: string, campaignId: string): Promise<CampaignOut> {
  return apiFetch<CampaignOut>(`/tenants/${tenantId}/campaigns/${campaignId}`);
}

export async function createCharacter(
  tenantId: string,
  body: CharacterCreate,
): Promise<CharacterOut> {
  return apiPost<CharacterOut>(`/tenants/${tenantId}/characters`, body);
}

export async function updateCharacter(
  tenantId: string,
  characterId: string,
  body: CharacterUpdate,
): Promise<CharacterOut> {
  return apiPatch<CharacterOut>(`/tenants/${tenantId}/characters/${characterId}`, body);
}
