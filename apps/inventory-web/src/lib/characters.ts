import { apiFetch } from './api';
import type { CharacterSummary, Page } from './types';

// mine=true (ADR 0049): only characters the caller owns, not the broader
// roster they might merely co-pilot - matches this app's player-facing v1
// scope (see docs/domain/client-views.md).
export async function listMyCharacters(tenantId: string): Promise<Page<CharacterSummary>> {
  return apiFetch<Page<CharacterSummary>>(`/tenants/${tenantId}/characters?mine=true`);
}

// mine omitted (defaults to false): the full tenant roster, PCs and NPCs
// alike - what a GM's "assign to a being" picker needs, not just their own
// characters. No search param on this endpoint, so callers filter
// client-side (same accepted caveat as apps/loot-bot's own listItems).
export async function listCharacters(tenantId: string): Promise<Page<CharacterSummary>> {
  return apiFetch<Page<CharacterSummary>>(`/tenants/${tenantId}/characters?size=100`);
}
