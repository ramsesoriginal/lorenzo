import { apiFetch } from './api';
import type { OwnedByResponse } from './types';

// Grouped by *direct* container only (ADR 0020's task brief) - a null
// group for items with no container, one group per occupied container.
// Not recursive: a container that's itself empty produces no group of its
// own, but still appears as a card inside whichever group holds it.
export async function getOwnedItemInstances(
  tenantId: string,
  ownerEntityId: string,
): Promise<OwnedByResponse> {
  return apiFetch<OwnedByResponse>(`/tenants/${tenantId}/item-instances/owned-by/${ownerEntityId}`);
}
