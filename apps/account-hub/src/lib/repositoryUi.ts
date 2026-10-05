// One repository on /tenants (ADR 0178): what an owner or orga of a repository
// can do from here, and nothing that only makes sense where people play.
//
//   - rename and edit it (name, slug, description: the editor libraries use);
//   - its people and invitations (its owners are its authors, RFC 0024);
//   - its published state, read-only: publishing, granting and subscribing stay
//     on the CLI until their own screens exist;
//   - leave it.
//
// Not here: campaigns, invite links, a player roster, characters. A repository
// holds none of them (the API refuses a campaign in one).
import { renderLeaveTenant } from './exitsUi';
import { renderMembershipAdmin } from './membershipAdminUi';
import { renderTenantEdit } from './tenantEditUi';
import { publishedLabel } from './tenantKind';
import { getTenant, listTenantRoster } from './tenants';
import type { MembershipRosterEntryOut, TenantSummaryOut } from './types';

export async function renderRepository(
  tenant: TenantSummaryOut,
  userId: string,
  onChanged: () => void,
): Promise<HTMLLIElement> {
  const item = document.createElement('li');
  const heading = document.createElement('h3');
  const nameEl = document.createElement('span');
  nameEl.textContent = tenant.name;
  const kindBadge = document.createElement('span');
  kindBadge.className = 'badge';
  kindBadge.textContent = 'Repository';
  const roleBadge = document.createElement('span');
  roleBadge.className = 'badge';
  roleBadge.textContent = tenant.role;
  heading.append(nameEl, ' ', kindBadge, ' ', roleBadge);

  // The list has no publish state; the detail read does (ADR 0118).
  const { tenant: detail } = await getTenant(tenant.id);
  const published = document.createElement('p');
  published.className = 'repository-status';
  published.textContent = publishedLabel(detail.published_at);

  item.append(
    heading,
    published,
    renderTenantEdit(tenant, (updated) => {
      nameEl.textContent = updated.name;
    }),
  );

  // A repository has members and nothing else, so only an owner or orga is
  // ever listed on it; the owner-only panel is the one the library page also
  // keeps for owners (bulk invite is owner-gated server-side, RFC 0017 (e)).
  if (tenant.role === 'owner') {
    const roster = await listTenantRoster(tenant.id);
    const memberships = roster.items.filter(
      (entry): entry is MembershipRosterEntryOut => entry.kind === 'membership',
    );
    item.append(renderMembershipAdmin(tenant, memberships, onChanged));
  }
  if (tenant.role === 'owner' || tenant.role === 'orga') {
    item.append(renderLeaveTenant(tenant, userId, onChanged));
  }
  return item;
}
