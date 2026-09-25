// Thin aliases over the generated schema (lorenzo-schema.d.ts, from
// apps/api's own OpenAPI schema - see api.ts and package.json's
// generate-client script), kept under these existing names so the rest of
// this app didn't need touching when the client itself was generated
// rather than hand-written. `Page<T>` stays hand-written: the schema
// generates one concrete `Page_<Schema>_` type per T rather than a
// reusable generic, and its own shape (items/total/page/size/pages) is
// stable, low-risk boilerplate untouched by a backend field rename.
import type { components } from './api';

export interface Page<T> {
  items: T[];
  total: number;
  page: number;
  size: number;
  pages: number;
}

export type TenantSummary = components['schemas']['TenantSummaryOut'];
export type TenantRole = TenantSummary['role'];
export type Tenant = components['schemas']['TenantOut'];
export type CharacterSummary = components['schemas']['CharacterSummaryOut'];
export type BeingSummary = components['schemas']['BeingSummaryOut'];

// Any being (RFC 0001/ADR 0025) - broader than CharacterSummary: a bare
// being with no Character row (ADR 0031) has a name only insofar as the
// caller supplied one (e.g. typed into a raw entity-id field), so this
// shape carries just what every "assign/browse a being" flow actually
// needs, structurally satisfied by both CharacterSummary and
// BeingSummary too. No generated equivalent - this is this app's own
// picker-local shape, not a response the API ever sends as such.
export interface BeingRef {
  entity_id: string;
  name: string;
}

export type TagValue = components['schemas']['TagValueOut'];
export type Description = components['schemas']['DescriptionOut'];

// ItemInstanceOut extends ItemOut directly server-side (identical fields
// plus owner_entity_id/container_entity_id/slug) - CatalogItem/ItemInstance
// below mirror that relationship over the generated types rather than
// duplicating the field list.
export type CatalogItem = components['schemas']['ItemOut'];
export type ItemInstance = components['schemas']['ItemInstanceOut'];
// The fields shared by both - the standalone item page doesn't know in
// advance whether a given id/slug resolves to a catalog item or an
// instance, and renders either through this common shape.
export type ItemBase = Omit<CatalogItem, 'in_public_catalog'>;

export type EntitySummary = components['schemas']['EntitySummary'];
export type EntityDetail = components['schemas']['EntityDetailOut'];
export type OwnedGroup = components['schemas']['OwnedGroupOut'];
export type OwnedByResponse = components['schemas']['OwnedByResponse'];
export type PrototypeAncestor = components['schemas']['PrototypeAncestorOut'];

// POST .../bulk-assign and .../bulk-move each generate their own distinct
// BulkAssignResultItem/BulkMoveResultItem schema server-side, but the two
// are structurally identical (entity_id/status/item_instance?/problem?) -
// one alias serves both call sites, the same way this app already treated
// them as one shape before codegen.
export type BulkResultItem = components['schemas']['BulkAssignResultItem'];
