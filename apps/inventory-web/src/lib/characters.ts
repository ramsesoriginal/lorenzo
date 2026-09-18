import { apiFetch } from './api';
import type { CharacterSummary, Page } from './types';

// mine=true (ADR 0049): only characters the caller owns, not the broader
// roster they might merely co-pilot - matches this app's player-facing v1
// scope (see docs/domain/client-views.md).
export async function listMyCharacters(tenantId: string): Promise<Page<CharacterSummary>> {
  return apiFetch<Page<CharacterSummary>>(`/tenants/${tenantId}/characters?mine=true`);
}
