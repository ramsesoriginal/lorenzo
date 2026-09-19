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

// GET /tenants/{id}/beings - see ADR 0078. A superset of
// CharacterSummaryOut: every Being, not just ones with a Character row.
// is_pc is genuinely three-valued here: null means no Character row
// exists at all, distinct from false (a Character row exists, but
// owner_player_id is unset).
export interface BeingSummaryOut {
  entity_id: string;
  name: string;
  is_pc: boolean | null;
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

// GET /users/by-email/{email}, GET /users/by-nickname/{nickname} - see ADR
// 0055. Deliberately thin - just enough to resolve an identifier a caller
// already knows into the user_id the invite/GM-assign endpoints take.
export interface UserRefOut {
  id: string;
  nickname: string | null;
  display_name: string | null;
}

// POST /tenants/{id}/campaigns/{id}/players - see RFC 0014. Bare user_id;
// the endpoint validates it's a real user itself.
export interface PlayerCreate {
  user_id: string;
}

// GET/POST /tenants/{id}/campaigns/{id}/players - a campaign's roster.
// No display name (same GmOut limitation, ADR 0076) - only a raw user_id
// per player.
export interface PlayerSummaryOut {
  id: string;
  user_id: string;
  characters: CharacterSummaryOut[];
  created_by: string | null;
  updated_by: string | null;
}

// POST /tenants/{id}/campaigns - see ADR 0034/RFC 0006. No defaults except
// secret; name/game_system/slug/description are all required.
export interface CampaignCreate {
  name: string;
  game_system: string;
  slug: string;
  description: string;
  secret?: boolean;
}

// PATCH /tenants/{id}/campaigns/{id} - exclude_unset semantics, matching
// ProfileUpdate/CharacterUpdate's own established pattern. Every field
// optional; only send keys that actually changed.
export interface CampaignUpdate {
  name?: string;
  game_system?: string;
  slug?: string;
  description?: string;
  secret?: boolean;
}

// GET /tenants/{id}/campaigns/{id}/gms - see ADR 0031/RFC 0004. Bare
// user_id, no display name - tenant_id/campaign_id are already in the URL,
// no need to repeat them per row. There's no reverse user-lookup endpoint
// anywhere in this API, so this is all a client can show per GM (ADR 0076).
export interface GmOut {
  user_id: string;
}

// POST /tenants - see ADR 0033/RFC 0012. Gated server-side by a
// platform-level Authgear role invisible to this client (RFC 0017 (d)) -
// there's no field anywhere to check before showing this form.
export interface TenantCreate {
  name: string;
  slug?: string | null;
  description?: string | null;
}

// GET /tenants/{id}/memberships - see RFC 0017 (a). A discriminated union
// (kind) covering every relationship a user has in a tenant - materially
// richer than GmOut/PlayerSummaryOut's bare user_id, since every row
// carries real nickname/display_name/user_color.
export interface MembershipRosterEntryOut {
  kind: 'membership';
  user_id: string;
  nickname: string | null;
  display_name: string | null;
  user_color: string | null;
  role: string;
  created_by: string | null;
  updated_by: string | null;
}

export interface PlayerRosterEntryOut {
  kind: 'player';
  user_id: string;
  nickname: string | null;
  display_name: string | null;
  user_color: string | null;
  campaign_id: string;
  characters: CharacterSummaryOut[];
  created_by: string | null;
  updated_by: string | null;
}

export interface GmRosterEntryOut {
  kind: 'gm';
  user_id: string;
  nickname: string | null;
  display_name: string | null;
  user_color: string | null;
  campaign_id: string;
}

export type RosterEntry = MembershipRosterEntryOut | PlayerRosterEntryOut | GmRosterEntryOut;

// POST /tenants/{id}/memberships - see ADR 0036/RFC 0007. user_id must
// already be a real app_user row - no email-invite exists (ADR 0009).
export interface MembershipCreate {
  user_id: string;
  role: 'owner' | 'orga';
}

// PATCH /tenants/{id}/memberships/{user_id} - just the one field.
export interface MembershipUpdate {
  role: 'owner' | 'orga';
}

// A plain-dict mirror of fastapi_problem.error.Problem.marshal() - used
// inside a bulk operation's per-item result to embed what a real
// single-item error response would have looked like.
export interface ProblemOut {
  type: string;
  title: string;
  status: number;
  detail: string | null;
}

// POST /tenants/{id}/memberships/bulk - one output entry per input entry,
// regardless of outcome (ADR 0062: never all-or-nothing). Exactly one of
// membership/problem is set, matching status.
export interface BulkMembershipResultItem {
  user_id: string;
  status: 'ok' | 'error';
  membership: MembershipRosterEntryOut | null;
  problem: ProblemOut | null;
}

// GET /tenants/{id}/activity-log - see ADR 0063. actor_id/target_id are
// raw UUIDs with no guaranteed cross-reference (RFC 0017 (f)) - shown
// as-is, not enriched.
export interface AuditLogEntryOut {
  id: string;
  actor_id: string | null;
  action: string;
  target_type: string;
  target_id: string | null;
  detail: string | null;
  created_at: string;
}

// POST .../notifications body, shared by the tenant/campaign scope routes
// - see ADR 0058/RFC 0017 (g). An omitted recipient_user_id broadcasts to
// that scope's own roster.
export interface NotificationCreate {
  recipient_user_id?: string | null;
  type: string;
  title: string;
  body: string;
}
