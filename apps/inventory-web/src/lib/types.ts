// Shapes mirror apps/api's actual response schemas (checked against its
// live openapi.json), not guessed - keep in sync as more of the API gets
// consumed.

export interface Page<T> {
  items: T[];
  total: number;
  page: number;
  size: number;
  pages: number;
}

export type TenantRole = 'owner' | 'orga' | 'participant';

export interface TenantSummary {
  id: string;
  slug: string;
  name: string;
  role: TenantRole;
}

export interface Tenant {
  id: string;
  slug: string;
  name: string;
  description: string;
  created_by: string | null;
  updated_by: string | null;
}

export interface CharacterSummary {
  entity_id: string;
  name: string;
  is_pc: boolean;
}

// Any being (RFC 0001/ADR 0025) - broader than CharacterSummary: a bare
// being with no Character row (ADR 0031) has a name only insofar as the
// caller supplied one (e.g. typed into a raw entity-id field), so this
// shape carries just what every "assign/browse a being" flow actually
// needs, structurally satisfied by both CharacterSummary and
// BeingSummary too.
export interface BeingRef {
  entity_id: string;
  name: string;
}

// GET /tenants/{t}/beings (ADR 0078) - every Being in the tenant, PCs,
// NPCs, and bare beings alike, not just ones with a Character row.
// is_pc is genuinely three-valued here: null means no Character row
// exists at all, distinct from false (a Character row exists, just not
// player-owned).
export interface BeingSummary {
  entity_id: string;
  name: string;
  is_pc: boolean | null;
}

export interface TagValue {
  name: string;
  value: boolean | null;
}

export interface Description {
  content: string;
  locale: string;
}

// Shared fields between a catalog item (ItemOut) and an instance
// (ItemInstanceOut extends ItemOut directly, identical fields plus
// owner_entity_id/container_entity_id/slug) - one place for the field
// list instead of two copies drifting apart.
export interface ItemBase {
  entity_id: string;
  // Always a non-empty display string - falls back to the entity's own
  // name server-side when no description exists (ADR 0067).
  title: string;
  quantity: number | null;
  tags: TagValue[];
  weight: number | null;
  height: number | null;
  price: number | null;
  rarity: number | null;
  hp: number | null;
  armor: number | null;
  is_magical: boolean | null;
  is_cursed: boolean | null;
  // Computed server-side: an explicit "is_container" tag wins, else true
  // if the entity currently holds anything, else null - never inferred
  // false from mere emptiness (ADR 0066).
  is_container: boolean | null;
  descriptions: Description[];
  // An instance only ever gets one (ItemInstanceCreate.prototype_id is
  // singular), but the field itself is generically an array since it's
  // the same EntityPrototype relation catalog items' own multi-parent
  // set uses. This item's own *direct* parents - needed to seed the
  // ancestry tree at its root (getItemAncestry only returns nodes
  // strictly above it).
  prototype_ids: string[];
}

export interface ItemInstance extends ItemBase {
  container_entity_id: string | null;
  owner_entity_id: string | null;
  // Optional, unique per tenant when set (ADR 0043) - resolvable via
  // GET .../by-slug/{slug}. Set-at-creation only: ItemInstanceUpdate
  // (PATCH) doesn't include it, so it can't be changed afterward.
  slug: string | null;
}

export interface EntitySummary {
  id: string;
  name: string;
  quantity: number | null;
}

export interface OwnedGroup {
  container: EntitySummary | null;
  item_instances: ItemInstance[];
}

export interface OwnedByResponse {
  groups: OwnedGroup[];
}

// A catalog item (prototype) - GET/POST /tenants/{t}/items. Identical
// fields to ItemInstance minus its three instance-only ones (container/
// owner/slug) - see ItemBase.
export type CatalogItem = ItemBase;

export interface CampaignSummary {
  id: string;
  slug: string;
  name: string;
}

// GET /me - only the fields this app actually reads so far.
export interface MeSummary {
  campaign_gm_grants: CampaignSummary[];
}

// GET /tenants/{t}/items/{id}/prototypes/ancestry - one node. prototype_ids
// here is that ancestor's own *direct* prototypes, not the full transitive
// set - a flat node+edge list (ADR 0073), since multiple inheritance means
// the real shape is a DAG, not always a clean chain.
export interface PrototypeAncestor {
  entity_id: string;
  name: string;
  prototype_ids: string[];
}

// One output entry from POST .../bulk-assign or .../bulk-move (ADR 0044/
// 0065) - always present per input entry regardless of outcome, never
// all-or-nothing. entity_id echoes the *input* entity_id; when quantity
// was given to bulk-assign (a partial give, delegating to split-with-owner
// server-side), item_instance.entity_id is the newly created split-off
// instance's own, different id - the one that actually got the new owner.
export interface BulkResultItem {
  entity_id: string;
  status: 'ok' | 'error';
  item_instance: { entity_id: string } | null;
  problem: { title: string; detail?: string } | null;
}
