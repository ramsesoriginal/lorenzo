// Stat values on the item page (ADR 0263): the logic is packages/stat-values (ADR 0272), shared
// with beings; this binds its calls to this app's client, so the rest of the app imports as before.
import * as shared from '@lorenzo/stat-values';
import { client } from './api';

export {
  decimalText,
  parseStat,
  type Seen,
  StatChangedError,
  type StatDefinition,
  type StatRow,
  type StatValue,
  sourceOf,
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
