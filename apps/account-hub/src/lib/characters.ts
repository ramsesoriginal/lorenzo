import { apiFetch, apiPatch, apiPost } from './api';
import type {
  CampaignOut,
  CharacterCreate,
  CharacterOut,
  CharacterSummaryOut,
  CharacterUpdate,
  Page,
} from './types';

// No pager UI yet (matches notifications.ts/tenants.ts's own precedent).
const PAGE_SIZE = 50;

export async function getCampaign(tenantId: string, campaignId: string): Promise<CampaignOut> {
  return apiFetch<CampaignOut>(`/tenants/${tenantId}/campaigns/${campaignId}`);
}

// The tenant's whole Character roster - PCs and beings (is_pc: false)
// alike. Used by the Beings page to find existing beings, since there's no
// separate "list beings" endpoint - a being is just a Character row with
// no owner_player_id (see ADR/RFC 0001-0002: is_pc is derived, not a
// stored type split).
export async function listCharacters(tenantId: string): Promise<Page<CharacterSummaryOut>> {
  return apiFetch<Page<CharacterSummaryOut>>(
    `/tenants/${tenantId}/characters?page=1&size=${PAGE_SIZE}`,
  );
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
