import { etagOf } from '@lorenzo/api-client';
import { client, pictureUpload, unwrap } from './api';
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
  TenantOut,
  TenantSummaryOut,
} from './types';

// No pager UI yet (matches notifications.ts's own precedent) - a client
// with over 50 tenants/campaigns is a later slice's problem.
const PAGE_SIZE = 50;

export async function listMyTenants(): Promise<Page<TenantSummaryOut>> {
  return unwrap(await client.GET('/tenants', { params: { query: { page: 1, size: PAGE_SIZE } } }));
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
  await unwrap(
    await client.PUT('/tenants/{tenant_id}/picture', {
      params: { path: { tenant_id: tenantId } },
      ...pictureUpload(file),
    }),
  );
}

export async function deleteTenantPicture(tenantId: string): Promise<void> {
  await unwrap(
    await client.DELETE('/tenants/{tenant_id}/picture', {
      params: { path: { tenant_id: tenantId } },
    }),
  );
}

export async function listTenantCampaigns(tenantId: string): Promise<Page<CampaignSummaryOut>> {
  return unwrap(
    await client.GET('/tenants/{tenant_id}/campaigns', {
      params: { path: { tenant_id: tenantId }, query: { page: 1, size: PAGE_SIZE } },
    }),
  );
}

export async function getCampaign(tenantId: string, campaignId: string): Promise<CampaignOut> {
  return unwrap(
    await client.GET('/tenants/{tenant_id}/campaigns/{campaign_id}', {
      params: { path: { tenant_id: tenantId, campaign_id: campaignId } },
    }),
  );
}

export async function createCampaign(tenantId: string, body: CampaignCreate): Promise<CampaignOut> {
  return unwrap(
    await client.POST('/tenants/{tenant_id}/campaigns', {
      params: { path: { tenant_id: tenantId } },
      body: body,
    }),
  );
}

export async function updateCampaign(
  tenantId: string,
  campaignId: string,
  body: CampaignUpdate,
): Promise<CampaignOut> {
  return unwrap(
    await client.PATCH('/tenants/{tenant_id}/campaigns/{campaign_id}', {
      params: { path: { tenant_id: tenantId, campaign_id: campaignId } },
      body: body,
    }),
  );
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
  await unwrap(
    await client.PUT('/tenants/{tenant_id}/campaigns/{campaign_id}/picture', {
      params: { path: { tenant_id: tenantId, campaign_id: campaignId } },
      ...pictureUpload(file),
    }),
  );
}

export async function deleteCampaignPicture(tenantId: string, campaignId: string): Promise<void> {
  await unwrap(
    await client.DELETE('/tenants/{tenant_id}/campaigns/{campaign_id}/picture', {
      params: { path: { tenant_id: tenantId, campaign_id: campaignId } },
    }),
  );
}

// Unpaginated - GmOut's own docstring calls this "inherently small and
// bounded by construction," matching OwnedByResponse's precedent.
export async function listCampaignGms(tenantId: string, campaignId: string): Promise<GmOut[]> {
  return unwrap(
    await client.GET('/tenants/{tenant_id}/campaigns/{campaign_id}/gms', {
      params: { path: { tenant_id: tenantId, campaign_id: campaignId } },
    }),
  );
}

export async function grantCampaignGm(
  tenantId: string,
  campaignId: string,
  userId: string,
): Promise<void> {
  await unwrap(
    await client.PUT('/tenants/{tenant_id}/campaigns/{campaign_id}/gms/{user_id}', {
      params: { path: { tenant_id: tenantId, campaign_id: campaignId, user_id: userId } },
    }),
  );
}

export async function revokeCampaignGm(
  tenantId: string,
  campaignId: string,
  userId: string,
): Promise<void> {
  await unwrap(
    await client.DELETE('/tenants/{tenant_id}/campaigns/{campaign_id}/gms/{user_id}', {
      params: { path: { tenant_id: tenantId, campaign_id: campaignId, user_id: userId } },
    }),
  );
}

// Returns the created player (201, PlayerSummaryOut) - RFC 0014's
// being-handoff flow needs the new player's id immediately to link a
// character to it, not just a success signal.
export async function invitePlayer(
  tenantId: string,
  campaignId: string,
  body: PlayerCreate,
): Promise<PlayerSummaryOut> {
  return unwrap(
    await client.POST('/tenants/{tenant_id}/campaigns/{campaign_id}/players', {
      params: { path: { tenant_id: tenantId, campaign_id: campaignId } },
      body: body,
    }),
  );
}

export async function listCampaignPlayers(
  tenantId: string,
  campaignId: string,
): Promise<Page<PlayerSummaryOut>> {
  return unwrap(
    await client.GET('/tenants/{tenant_id}/campaigns/{campaign_id}/players', {
      params: {
        path: { tenant_id: tenantId, campaign_id: campaignId },
        query: { page: 1, size: PAGE_SIZE },
      },
    }),
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
  await unwrap(
    await client.DELETE('/tenants/{tenant_id}/campaigns/{campaign_id}/players/{player_id}', {
      params: { path: { tenant_id: tenantId, campaign_id: campaignId, player_id: playerId } },
    }),
  );
}

// RFC 0017 (d) - gated server-side by a platform-level Authgear role with
// no client-visible signal; always shown, 403 surfaced like any other
// authorization failure.
export async function createTenant(body: TenantCreate): Promise<TenantOut> {
  return unwrap(await client.POST('/tenants', { body: body }));
}

// RFC 0017 (a)/(e)/(f) - the tenant's full roster, one row per
// relationship (a user who is ORGA, GMs one campaign, and plays in
// another appears three times). Unpaginated here to match how this app
// already treats GmOut/PlayerSummaryOut - bounded by how many people are
// involved in one world, not by total traffic.
export async function listTenantRoster(tenantId: string): Promise<Page<RosterEntry>> {
  return unwrap(
    await client.GET('/tenants/{tenant_id}/memberships', {
      params: { path: { tenant_id: tenantId }, query: { page: 1, size: PAGE_SIZE } },
    }),
  );
}

// RFC 0017 (e) - tenant-wide owner/orga role grants, distinct from
// campaign-level GM/player management above.
export async function createMembership(
  tenantId: string,
  body: MembershipCreate,
): Promise<RosterEntry> {
  return unwrap(
    await client.POST('/tenants/{tenant_id}/memberships', {
      params: { path: { tenant_id: tenantId } },
      body: body,
    }),
  );
}

export async function updateMembership(
  tenantId: string,
  userId: string,
  body: MembershipUpdate,
): Promise<RosterEntry> {
  return unwrap(
    await client.PATCH('/tenants/{tenant_id}/memberships/{user_id}', {
      params: { path: { tenant_id: tenantId, user_id: userId } },
      body: body,
    }),
  );
}

export async function deleteMembership(tenantId: string, userId: string): Promise<void> {
  await unwrap(
    await client.DELETE('/tenants/{tenant_id}/memberships/{user_id}', {
      params: { path: { tenant_id: tenantId, user_id: userId } },
    }),
  );
}

// Never all-or-nothing (ADR 0062) - one result per input, regardless of
// outcome.
export async function bulkInviteMembers(
  tenantId: string,
  members: MembershipCreate[],
): Promise<BulkMembershipResultItem[]> {
  return unwrap(
    await client.POST('/tenants/{tenant_id}/memberships/bulk', {
      params: { path: { tenant_id: tenantId } },
      body: members,
    }),
  );
}

export async function listActivityLog(tenantId: string): Promise<Page<AuditLogEntryOut>> {
  return unwrap(
    await client.GET('/tenants/{tenant_id}/activity-log', {
      params: { path: { tenant_id: tenantId }, query: { page: 1, size: PAGE_SIZE } },
    }),
  );
}

// RFC 0017 (g) - an omitted recipient_user_id broadcasts to the scope's
// whole roster, so this can return more than one row.
export async function createTenantNotification(
  tenantId: string,
  body: NotificationCreate,
): Promise<Notification[]> {
  return unwrap(
    await client.POST('/tenants/{tenant_id}/notifications', {
      params: { path: { tenant_id: tenantId } },
      body: body,
    }),
  );
}

export async function createCampaignNotification(
  tenantId: string,
  campaignId: string,
  body: NotificationCreate,
): Promise<Notification[]> {
  return unwrap(
    await client.POST('/tenants/{tenant_id}/campaigns/{campaign_id}/notifications', {
      params: { path: { tenant_id: tenantId, campaign_id: campaignId } },
      body: body,
    }),
  );
}

export async function getTenant(tenantId: string): Promise<{ tenant: TenantOut; etag: string }> {
  const result = await client.GET('/tenants/{tenant_id}', {
    params: { path: { tenant_id: tenantId } },
  });
  const tenant = await unwrap(result);
  const etag = etagOf(result.response);
  if (!etag) throw new Error('Tenant editing is temporarily unavailable. Try again later.');
  return { tenant, etag };
}

export async function updateTenantSlug(
  tenantId: string,
  slug: string,
  etag: string,
): Promise<TenantOut> {
  return unwrap(
    await client.PATCH('/tenants/{tenant_id}', {
      params: { path: { tenant_id: tenantId }, header: { 'if-match': etag } },
      body: { slug },
    }),
  );
}
