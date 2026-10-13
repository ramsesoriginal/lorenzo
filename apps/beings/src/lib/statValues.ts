// Stat values on a being's page (ADR 0272): the logic is packages/stat-values, shared with
// inventory-web; this binds its calls to this app's client.
import * as shared from '@lorenzo/stat-values';
import { client, unwrap } from './api';

export {
  parseStat,
  type Seen,
  StatChangedError,
  type StatRow,
  type StatValue,
  sourceIn,
  statRows,
} from '@lorenzo/stat-values';

export const statDefinitions = (tenantId: string) => shared.statDefinitions(client, tenantId);

export const setStat = (
  tenantId: string,
  entityId: string,
  definition: shared.StatDefinition,
  value: shared.StatValue,
  seen: shared.Seen,
) => shared.setStat(client, tenantId, entityId, definition, value, seen);

export const clearStat = (
  tenantId: string,
  entityId: string,
  definition: shared.StatDefinition,
  seen: shared.Seen,
) => shared.clearStat(client, tenantId, entityId, definition, seen);

/** How a stat of a being came to have its value (ADR 0276). Any participant who may read it may ask. */
export async function getExplanation(tenantId: string, entityId: string, definitionId: string) {
  return unwrap(
    await client.GET(
      '/tenants/{tenant_id}/entities/{entity_id}/stats/{stat_definition_id}/explanation',
      {
        params: {
          path: { tenant_id: tenantId, entity_id: entityId, stat_definition_id: definitionId },
        },
      },
    ),
  );
}

export const statVocabulary = (tenantId: string) => shared.statVocabulary(client, tenantId);
