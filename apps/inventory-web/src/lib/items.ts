import { apiDelete, apiFetch, apiPut } from './api';
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

export async function setContainer(
  tenantId: string,
  entityId: string,
  containerEntityId: string,
): Promise<void> {
  await apiPut(`/tenants/${tenantId}/item-instances/${entityId}/container`, {
    container_entity_id: containerEntityId,
  });
}

export async function clearContainer(tenantId: string, entityId: string): Promise<void> {
  await apiDelete(`/tenants/${tenantId}/item-instances/${entityId}/container`);
}
