// Shapes mirror apps/api's actual response schemas (checked against its
// live openapi.json), not guessed - keep in sync as more of the API gets
// consumed.

export type TenantRole = 'owner' | 'orga' | 'participant';

export interface MembershipOut {
  tenant_id: string;
  role: TenantRole;
}

export interface CharacterSummaryOut {
  entity_id: string;
  name: string;
  is_pc: boolean;
}

export interface PlayerContextOut {
  id: string;
  tenant_id: string;
  campaign_id: string;
  characters: CharacterSummaryOut[];
}

export interface CampaignSummaryOut {
  id: string;
  slug: string;
  name: string;
  game_system: string;
  secret: boolean;
}

export interface TenantSummaryOut {
  id: string;
  slug: string;
  name: string;
  role: TenantRole;
}

export interface MeOut {
  id: string;
  authgear_subject_id: string;
  email: string | null;
  nickname: string | null;
  display_name: string | null;
  pronouns: string | null;
  bio: string | null;
  locales: string[];
  user_color: string | null;
  picture_url: string;
  memberships: MembershipOut[];
  players: PlayerContextOut[];
  campaign_gm_grants: CampaignSummaryOut[];
}

// PATCH /me body - exclude_unset semantics server-side: a key that's absent
// (undefined here, dropped by JSON.stringify) leaves that field untouched;
// an explicit `null` clears it. Never send a key the user didn't actually
// change.
export interface ProfileUpdate {
  nickname?: string | null;
  display_name?: string | null;
  pronouns?: string | null;
  bio?: string | null;
  locales?: string[] | null;
  user_color?: string | null;
}

export interface Page<T> {
  items: T[];
  total: number;
  page: number;
  size: number;
  pages: number;
}

export interface Notification {
  id: string;
  batch_id: string;
  user_id: string;
  scope: string;
  type: string;
  tenant_id: string | null;
  source_id: string | null;
  title: string;
  body: string;
  read_at: string | null;
  created_at: string;
}

export interface CampaignOut {
  id: string;
  tenant_id: string;
  slug: string;
  name: string;
  description: string;
  game_system: string;
  secret: boolean;
  created_by: string | null;
  updated_by: string | null;
  created_at: string;
  updated_at: string;
}

// POST /tenants/{id}/characters - owner_player_id is a caller's own
// PlayerContextOut.id (a Player row, itself already campaign-scoped) -
// there's no separate campaign_id on a character at all, it's implied by
// whichever player row owns/pilots it.
export interface CharacterCreate {
  name: string;
  owner_player_id?: string | null;
  player_ids?: string[];
}

export interface CharacterUpdate {
  name?: string | null;
  owner_player_id?: string | null;
}

export interface CharacterOut {
  entity_id: string;
  name: string;
  is_pc: boolean;
  owner_player_id: string | null;
  players: PlayerContextOut[];
  created_by: string | null;
  updated_by: string | null;
}
