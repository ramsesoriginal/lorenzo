import { apiPost, apiPut } from './api';

// One-off data fix (a debug button, not a product feature): make these
// three entities read as containers. ADR 0047/0066: container-capability is
// a boolean stat_definition named `is_container` set on the entity, read
// back through `tags`, which apps/api only fills from a stat group named
// exactly "tags" (models/entity_view_mixin.py).
export const IS_CONTAINER_ENTITY_IDS = [
  'de365564-599b-48d2-bef6-18eb814e052f',
  '459bab1b-c8ce-4a48-85ad-ed4f200ebb95',
  '34abd460-6205-49d0-99e0-706622c81476',
];

export interface SeedApi {
  createStatGroup(tenantId: string, name: string): Promise<{ id: string }>;
  createBoolStatDefinition(
    tenantId: string,
    name: string,
    statGroupId: string,
  ): Promise<{ id: string }>;
  setBoolStat(
    tenantId: string,
    entityId: string,
    statDefinitionId: string,
    value: boolean,
  ): Promise<unknown>;
}

// apps/api has no list endpoint for stat groups/definitions and enforces
// (tenant_id, name) uniqueness on both, so a retry after a partial failure
// can't re-create them - the ids created on a previous run are remembered
// here instead and reused.
export interface SeedStore {
  get(key: string): string | null;
  set(key: string, value: string): void;
}

export interface SeedResult {
  statGroupId: string;
  statDefinitionId: string;
  succeeded: string[];
  failed: { entityId: string; message: string }[];
}

const message = (e: unknown) => (e instanceof Error ? e.message : String(e));

export async function seedIsContainer(
  tenantId: string,
  api: SeedApi,
  store: SeedStore,
  entityIds: string[] = IS_CONTAINER_ENTITY_IDS,
  onProgress: (line: string) => void = () => {},
): Promise<SeedResult> {
  const groupKey = `lorenzo:debug-seed:${tenantId}:tags-group`;
  const definitionKey = `lorenzo:debug-seed:${tenantId}:is-container-definition`;

  let statGroupId = store.get(groupKey);
  if (statGroupId) {
    onProgress(`Reusing stat group "tags" (${statGroupId}).`);
  } else {
    onProgress('Creating stat group "tags"…');
    statGroupId = (await api.createStatGroup(tenantId, 'tags')).id;
    store.set(groupKey, statGroupId);
  }

  let statDefinitionId = store.get(definitionKey);
  if (statDefinitionId) {
    onProgress(`Reusing stat definition is_container (${statDefinitionId}).`);
  } else {
    onProgress('Creating boolean stat definition is_container…');
    statDefinitionId = (await api.createBoolStatDefinition(tenantId, 'is_container', statGroupId))
      .id;
    store.set(definitionKey, statDefinitionId);
  }

  const succeeded: string[] = [];
  const failed: SeedResult['failed'] = [];
  for (const entityId of entityIds) {
    try {
      await api.setBoolStat(tenantId, entityId, statDefinitionId, true);
      succeeded.push(entityId);
      onProgress(`is_container = true on ${entityId}.`);
    } catch (e) {
      failed.push({ entityId, message: message(e) });
      onProgress(`Failed on ${entityId}: ${message(e)}`);
    }
  }
  return { statGroupId, statDefinitionId, succeeded, failed };
}

export const liveSeedApi: SeedApi = {
  createStatGroup: (tenantId, name) =>
    apiPost<{ id: string }>(`/tenants/${tenantId}/stat-groups`, { name }),
  createBoolStatDefinition: (tenantId, name, statGroupId) =>
    apiPost<{ id: string }>(`/tenants/${tenantId}/stat-definitions`, {
      name,
      stat_group_id: statGroupId,
      value_type: 'bool',
    }),
  setBoolStat: (tenantId, entityId, statDefinitionId, value) =>
    apiPut(`/tenants/${tenantId}/entities/${entityId}/stats/${statDefinitionId}`, { value }),
};

export function localStorageSeedStore(): SeedStore {
  return {
    get(key) {
      try {
        return window.localStorage.getItem(key);
      } catch {
        return null;
      }
    },
    set(key, value) {
      try {
        window.localStorage.setItem(key, value);
      } catch {
        // Only a retry convenience - losing it just means a retry re-creates.
      }
    },
  };
}
