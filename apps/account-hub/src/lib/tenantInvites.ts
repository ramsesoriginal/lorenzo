import { fetchAllPages, MAX_PAGE_SIZE, unwrap } from '@lorenzo/api-client';
import { client } from './api';
import type { InviteCreatedOut, InviteOut, TenantInviteCreate } from './types';

// An Owner's links for a library or repository (ADR 0220): roles and library links. A campaign's
// are in invites.ts. Metadata and use counts, newest first, never a token.
export function listTenantInvites(tenantId: string): Promise<InviteOut[]> {
  return fetchAllPages(async (page) =>
    unwrap(
      await client.GET('/tenants/{tenant_id}/invites', {
        params: { path: { tenant_id: tenantId }, query: { page, size: MAX_PAGE_SIZE } },
      }),
    ),
  );
}

// The response is the only time the token exists.
export async function createTenantInvite(
  tenantId: string,
  body: TenantInviteCreate,
): Promise<InviteCreatedOut> {
  return unwrap(
    await client.POST('/tenants/{tenant_id}/invites', {
      params: { path: { tenant_id: tenantId } },
      body,
    }),
  );
}

export async function revokeTenantInvite(tenantId: string, inviteId: string): Promise<void> {
  await unwrap(
    await client.DELETE('/tenants/{tenant_id}/invites/{invite_id}', {
      params: { path: { tenant_id: tenantId, invite_id: inviteId } },
    }),
  );
}
