// What an owner or orga of a repository can do from here (ADR 0178), and nothing that only makes
// sense where people play:
//
//   - rename and edit it (name, slug, description: the editor libraries use);
//   - its people and invitations (its owners are its authors, RFC 0024);
//   - its published state, read-only: publishing, granting and subscribing stay
//     on the CLI until their own screens exist;
//   - leave it.
//
// Not here: campaigns, invite links, a player roster, characters. A repository
// holds none of them (the API refuses a campaign in one), so those slots of <Tenant /> stay
// empty. Loading and filling are apart, as in library.ts.

import { publishedLabel } from '../../lib/tenantKind';
import { getTenant, listTenantRoster } from '../../lib/tenants';
import type { MembershipRosterEntryOut, TenantSummaryOut } from '../../lib/types';
import { renderMembershipAdmin } from '../MembershipAdmin/renderer';
import type { TenantHooks } from './hooks';
import { cloneComponent, fillSlot } from './slots';

export type RepositoryData = {
  // LorenzoScript, as written; empty when there is none.
  description: string;
  // Its published state, which the list doesn't have but the detail read does (ADR 0118).
  status: string;
  // Only an owner reads these.
  memberships: MembershipRosterEntryOut[] | null;
};

export async function loadRepository(tenant: TenantSummaryOut): Promise<RepositoryData> {
  const [{ tenant: detail }, roster] = await Promise.all([
    getTenant(tenant.id),
    // A repository has members and nothing else, so only an owner or orga is
    // ever listed on it; the owner-only panel is the one the library page also
    // keeps for owners (bulk invite is owner-gated server-side, RFC 0017 (e)).
    tenant.role === 'owner' ? listTenantRoster(tenant.id) : null,
  ]);

  return {
    description: detail.description,
    status: publishedLabel(detail.published_at),
    memberships:
      roster?.items.filter(
        (entry): entry is MembershipRosterEntryOut => entry.kind === 'membership',
      ) ?? null,
  };
}

export function fillRepository(
  root: HTMLElement,
  tenant: TenantSummaryOut,
  hooks: TenantHooks,
  data: RepositoryData,
): void {
  if (data.memberships) {
    const memberships = cloneComponent(root, '[data-membership-admin-template]');

    renderMembershipAdmin(memberships, tenant, data.memberships, hooks.onChanged);
    fillSlot(root, '[data-memberships-slot]', memberships);
  }
}
