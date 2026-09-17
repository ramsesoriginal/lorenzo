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
