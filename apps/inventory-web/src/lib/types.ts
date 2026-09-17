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

export interface TagValue {
  name: string;
  value: boolean | null;
}

export interface Description {
  content: string;
  locale: string;
}

export interface ItemInstance {
  entity_id: string;
  // Always a non-empty display string - falls back to the entity's own
  // name server-side when no description exists (ADR 0067).
  title: string;
  quantity: number | null;
  container_entity_id: string | null;
  owner_entity_id: string | null;
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
