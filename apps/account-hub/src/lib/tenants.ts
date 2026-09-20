import { apiDelete, apiFetch, apiPatch, apiPost, apiPut, apiUpload } from './api';
import { API_BASE_URL } from './config';
import type {
  AuditLogEntryOut,
  BulkMembershipResultItem,
  CampaignCreate,
  CampaignOut,
  CampaignSummaryOut,
  CampaignUpdate,
  GmOut,
  MembershipCreate,
  MembershipUpdate,
  Notification,
  NotificationCreate,
  Page,
  PlayerCreate,
  PlayerSummaryOut,
  RosterEntry,
  TenantCreate,
  TenantSummaryOut,
} from './types';

// No pager UI yet (matches notifications.ts's own precedent) - a client
// with over 50 tenants/campaigns is a later slice's problem.
const PAGE_SIZE = 50;

export async function listMyTenants(): Promise<Page<TenantSummaryOut>> {
  return apiFetch<Page<TenantSummaryOut>>(`/tenants?page=1&size=${PAGE_SIZE}`);
}

// ADR 0085 - TenantSummaryOut/TenantOut carry no picture_url field (unlike
// MeOut, ADR 0056/0060), so the client constructs the URL itself; GET
// .../picture has no fallback for a tenant with nothing uploaded (a plain
// 404, unlike a user's Gravatar redirect), which pictureUi.ts's <img
// onerror> handles.
export function tenantPictureUrl(tenantId: string): string {
  return `${API_BASE_URL}/tenants/${tenantId}/picture`;
}

export async function uploadTenantPicture(tenantId: string, file: File): Promise<void> {
  await apiUpload<void>(`/tenants/${tenantId}/picture`, 'file', file);
}

export async function deleteTenantPicture(tenantId: string): Promise<void> {
  await apiDelete<void>(`/tenants/${tenantId}/picture`);
}

export async function listTenantCampaigns(tenantId: string): Promise<Page<CampaignSummaryOut>> {
  return apiFetch<Page<CampaignSummaryOut>>(
    `/tenants/${tenantId}/campaigns?page=1&size=${PAGE_SIZE}`,
  );
}

export async function getCampaign(tenantId: string, campaignId: string): Promise<CampaignOut> {
  return apiFetch<CampaignOut>(`/tenants/${tenantId}/campaigns/${campaignId}`);
}

export async function createCampaign(tenantId: string, body: CampaignCreate): Promise<CampaignOut> {
  return apiPost<CampaignOut>(`/tenants/${tenantId}/campaigns`, body);
}

export async function updateCampaign(
  tenantId: string,
  campaignId: string,
  body: CampaignUpdate,
): Promise<CampaignOut> {
  return apiPatch<CampaignOut>(`/tenants/${tenantId}/campaigns/${campaignId}`, body);
}

// ADR 0085 - same reasoning as tenantPictureUrl above, gated by
// can_manage_campaign server-side (same as update_campaign).
export function campaignPictureUrl(tenantId: string, campaignId: string): string {
  return `${API_BASE_URL}/tenants/${tenantId}/campaigns/${campaignId}/picture`;
}

export async function uploadCampaignPicture(
  tenantId: string,
  campaignId: string,
  file: File,
): Promise<void> {
  await apiUpload<void>(`/tenants/${tenantId}/campaigns/${campaignId}/picture`, 'file', file);
}

export async function deleteCampaignPicture(tenantId: string, campaignId: string): Promise<void> {
  await apiDelete<void>(`/tenants/${tenantId}/campaigns/${campaignId}/picture`);
}

// Unpaginated - GmOut's own docstring calls this "inherently small and
// bounded by construction," matching OwnedByResponse's precedent.
export async function listCampaignGms(tenantId: string, campaignId: string): Promise<GmOut[]> {
  return apiFetch<GmOut[]>(`/tenants/${tenantId}/campaigns/${campaignId}/gms`);
}

export async function grantCampaignGm(
  tenantId: string,
  campaignId: string,
  userId: string,
): Promise<void> {
  await apiPut<void>(`/tenants/${tenantId}/campaigns/${campaignId}/gms/${userId}`, undefined);
}

export async function revokeCampaignGm(
  tenantId: string,
  campaignId: string,
  userId: string,
): Promise<void> {
  await apiDelete<void>(`/tenants/${tenantId}/campaigns/${campaignId}/gms/${userId}`);
}

// Returns the created player (201, PlayerSummaryOut) - RFC 0014's
// being-handoff flow needs the new player's id immediately to link a
// character to it, not just a success signal.
export async function invitePlayer(
  tenantId: string,
  campaignId: string,
  body: PlayerCreate,
): Promise<PlayerSummaryOut> {
  return apiPost<PlayerSummaryOut>(`/tenants/${tenantId}/campaigns/${campaignId}/players`, body);
}

export async function listCampaignPlayers(
  tenantId: string,
  campaignId: string,
): Promise<Page<PlayerSummaryOut>> {
  return apiFetch<Page<PlayerSummaryOut>>(
    `/tenants/${tenantId}/campaigns/${campaignId}/players?page=1&size=${PAGE_SIZE}`,
  );
}

// RFC 0017 (c) - self-service leave. Removes this specific player row
// (and every character link it grants) - other players' own roster-reuse
// links are unaffected.
export async function leaveCampaign(
  tenantId: string,
  campaignId: string,
  playerId: string,
): Promise<void> {
  await apiDelete<void>(`/tenants/${tenantId}/campaigns/${campaignId}/players/${playerId}`);
}

// RFC 0017 (d) - gated server-side by a platform-level Authgear role with
// no client-visible signal; always shown, 403 surfaced like any other
// authorization failure.
export async function createTenant(body: TenantCreate): Promise<TenantSummaryOut> {
  return apiPost<TenantSummaryOut>('/tenants', body);
}

// RFC 0017 (a)/(e)/(f) - the tenant's full roster, one row per
// relationship (a user who is ORGA, GMs one campaign, and plays in
// another appears three times). Unpaginated here to match how this app
// already treats GmOut/PlayerSummaryOut - bounded by how many people are
// involved in one world, not by total traffic.
export async function listTenantRoster(tenantId: string): Promise<Page<RosterEntry>> {
  return apiFetch<Page<RosterEntry>>(`/tenants/${tenantId}/memberships?page=1&size=${PAGE_SIZE}`);
}

// RFC 0017 (e) - tenant-wide owner/orga role grants, distinct from
// campaign-level GM/player management above.
export async function createMembership(
  tenantId: string,
  body: MembershipCreate,
): Promise<RosterEntry> {
  return apiPost<RosterEntry>(`/tenants/${tenantId}/memberships`, body);
}

export async function updateMembership(
  tenantId: string,
  userId: string,
  body: MembershipUpdate,
): Promise<RosterEntry> {
  return apiPatch<RosterEntry>(`/tenants/${tenantId}/memberships/${userId}`, body);
}

export async function deleteMembership(tenantId: string, userId: string): Promise<void> {
  await apiDelete<void>(`/tenants/${tenantId}/memberships/${userId}`);
}

// Never all-or-nothing (ADR 0062) - one result per input, regardless of
// outcome.
export async function bulkInviteMembers(
  tenantId: string,
  members: MembershipCreate[],
): Promise<BulkMembershipResultItem[]> {
  return apiPost<BulkMembershipResultItem[]>(`/tenants/${tenantId}/memberships/bulk`, members);
}

export async function listActivityLog(tenantId: string): Promise<Page<AuditLogEntryOut>> {
  return apiFetch<Page<AuditLogEntryOut>>(
    `/tenants/${tenantId}/activity-log?page=1&size=${PAGE_SIZE}`,
  );
}

// RFC 0017 (g) - an omitted recipient_user_id broadcasts to the scope's
// whole roster, so this can return more than one row.
export async function createTenantNotification(
  tenantId: string,
  body: NotificationCreate,
): Promise<Notification[]> {
  return apiPost<Notification[]>(`/tenants/${tenantId}/notifications`, body);
}

export async function createCampaignNotification(
  tenantId: string,
  campaignId: string,
  body: NotificationCreate,
): Promise<Notification[]> {
  return apiPost<Notification[]>(
    `/tenants/${tenantId}/campaigns/${campaignId}/notifications`,
    body,
  );
}
