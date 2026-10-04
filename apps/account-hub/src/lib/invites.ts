import { createLorenzoClient, fetchAllPages, MAX_PAGE_SIZE, unwrap } from '@lorenzo/api-client';
import { client } from './api';
import { API_BASE_URL } from './config';
import type {
  InviteCreate,
  InviteCreatedOut,
  InviteOut,
  InvitePreviewOut,
  InviteRedeemOut,
} from './types';

// GET /invites/{token} is unauthenticated: a visitor with a link has no login
// yet. The shared client refuses to send any request without an access token,
// so the preview goes through a client built without a token source.
const publicClient = createLorenzoClient({ baseUrl: API_BASE_URL });

// Metadata and use counts, newest first, never a token. Every page: a campaign
// whose GM has made over a page of links still shows them all.
export function listInvites(tenantId: string, campaignId: string): Promise<InviteOut[]> {
  return fetchAllPages(async (page) =>
    unwrap(
      await client.GET('/tenants/{tenant_id}/campaigns/{campaign_id}/invites', {
        params: {
          path: { tenant_id: tenantId, campaign_id: campaignId },
          query: { page, size: MAX_PAGE_SIZE },
        },
      }),
    ),
  );
}

// The response is the only time the token exists (ADR 0092).
export async function createInvite(
  tenantId: string,
  campaignId: string,
  body: InviteCreate,
): Promise<InviteCreatedOut> {
  return unwrap(
    await client.POST('/tenants/{tenant_id}/campaigns/{campaign_id}/invites', {
      params: { path: { tenant_id: tenantId, campaign_id: campaignId } },
      body,
    }),
  );
}

export async function revokeInvite(
  tenantId: string,
  campaignId: string,
  inviteId: string,
): Promise<void> {
  await unwrap(
    await client.DELETE('/tenants/{tenant_id}/campaigns/{campaign_id}/invites/{invite_id}', {
      params: { path: { tenant_id: tenantId, campaign_id: campaignId, invite_id: inviteId } },
    }),
  );
}

export async function previewInvite(token: string): Promise<InvitePreviewOut> {
  return unwrap(await publicClient.GET('/invites/{token}', { params: { path: { token } } }));
}

// Needs a login, not a tenant: any verified user. Idempotent for someone who is
// already a player there (already_joined).
export async function redeemInvite(token: string): Promise<InviteRedeemOut> {
  return unwrap(await client.POST('/invites/{token}/redeem', { params: { path: { token } } }));
}
