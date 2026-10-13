// Thin aliases over the generated schema (@lorenzo/api-client's schema.d.ts, from apps/api's own
// OpenAPI schema - ADR 0091, ADR 0122), under the names the rest of this app uses. `Page<T>` is the
// package's hand-written generic.
import type { components } from './api';

export type { Page } from '@lorenzo/api-client';

export type TenantSummary = components['schemas']['TenantSummaryOut'];
export type Tenant = components['schemas']['TenantOut'];
export type CampaignSummary = components['schemas']['CampaignSummaryOut'];
export type CharacterSummary = components['schemas']['CharacterSummaryOut'];
export type BeingSummary = components['schemas']['BeingSummaryOut'];
export type Character = components['schemas']['CharacterOut'];
export type CampaignPlayer = components['schemas']['PlayerOut'];

// Any being (RFC 0001/ADR 0025): a character picked from a list, or named by an id.
export interface BeingRef {
  entity_id: string;
  name: string;
}

export type Description = components['schemas']['DescriptionOut'];
export type EntitySummary = components['schemas']['EntitySummary'];
export type EntityDetail = components['schemas']['EntityDetailOut'];
export type OwnedByResponse = components['schemas']['OwnedByResponse'];
export type ItemInstance = components['schemas']['ItemInstanceOut'];
