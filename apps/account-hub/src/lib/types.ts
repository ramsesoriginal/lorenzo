// Shapes mirror apps/api's actual response schemas (checked against its
// live openapi.json), not guessed - keep in sync as more of the API gets
// consumed.

export type TenantRole = 'owner' | 'orga' | 'participant';

export interface MembershipOut {
  tenant_id: string;
  role: TenantRole;
}

export interface PlayerContextOut {
  campaign_id: string;
  characters: { entity_id: string; name: string }[];
}

export interface CampaignSummaryOut {
  id: string;
  name: string;
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
