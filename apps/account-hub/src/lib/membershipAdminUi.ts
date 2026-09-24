// Tenant-level membership management + bulk invite - RFC 0017 (e).
// Distinct from campaignAdminUi.ts/gmAndPlayerUi.ts's campaign-scoped GM/
// player management: this is tenant-wide owner/orga role administration.
// Bulk invite is confirmed _require_owner-gated server-side; the
// single-item actions here are gated identically for consistency rather
// than assumed looser (showing nothing to an orga who might technically
// have single-item rights is the safe direction of a wrong guess).

import { displayNameFor } from './format';
import { bulkInviteMembers, createMembership, deleteMembership, updateMembership } from './tenants';
import type { MembershipRosterEntryOut, TenantSummaryOut, UserRefOut } from './types';
import { mountUserPicker } from './userPicker';

function renderRoleSelect(initial: 'owner' | 'orga'): HTMLSelectElement {
  const select = document.createElement('select');
  for (const role of ['owner', 'orga'] as const) {
    const option = document.createElement('option');
    option.value = role;
    option.textContent = role;
    option.selected = role === initial;
    select.append(option);
  }
  return select;
}

function renderMembershipList(
  tenant: TenantSummaryOut,
  memberships: MembershipRosterEntryOut[],
  onChanged: () => void,
): HTMLElement {
  const list = document.createElement('ul');
  list.className = 'list';
  for (const membership of memberships) {
    const item = document.createElement('li');
    const nameEl = document.createElement('span');
    nameEl.textContent = displayNameFor(membership);
    item.append(nameEl);

    const roleSelect = renderRoleSelect(membership.role as 'owner' | 'orga');
    const status = document.createElement('span');
    status.className = 'status-text';
    status.setAttribute('role', 'status');
    roleSelect.addEventListener('change', async () => {
      status.textContent = 'Saving…';
      try {
        await updateMembership(tenant.id, membership.user_id, {
          role: roleSelect.value as 'owner' | 'orga',
        });
        onChanged();
      } catch (e) {
        status.textContent = e instanceof Error ? e.message : String(e);
      }
    });
    item.append(roleSelect);

    const removeButton = document.createElement('button');
    removeButton.type = 'button';
    removeButton.textContent = 'Remove';
    removeButton.addEventListener('click', async () => {
      status.textContent = 'Removing…';
      try {
        await deleteMembership(tenant.id, membership.user_id);
        onChanged();
      } catch (e) {
        status.textContent = e instanceof Error ? e.message : String(e);
      }
    });
    item.append(removeButton, status);

    list.append(item);
  }
  return list;
}

function renderInviteForm(tenant: TenantSummaryOut, onChanged: () => void): HTMLElement {
  const container = document.createElement('div');
  const label = document.createElement('p');
  label.textContent = 'Invite a tenant admin:';
  container.append(label);

  const roleSelect = renderRoleSelect('orga');
  container.append(roleSelect);

  const status = document.createElement('span');
  status.className = 'status-text';
  status.setAttribute('role', 'status');
  container.append(status);

  mountUserPicker(container, async (user) => {
    status.textContent = 'Inviting…';
    try {
      await createMembership(tenant.id, {
        user_id: user.id,
        role: roleSelect.value as 'owner' | 'orga',
      });
      status.textContent = '';
      onChanged();
    } catch (e) {
      status.textContent = e instanceof Error ? e.message : String(e);
    }
  });

  return container;
}

function renderBulkInviteForm(tenant: TenantSummaryOut, onChanged: () => void): HTMLElement {
  const container = document.createElement('div');
  const heading = document.createElement('p');
  heading.textContent = 'Bulk invite:';
  container.append(heading);

  const rows = document.createElement('div');
  container.append(rows);

  const pending: { user: UserRefOut; roleSelect: HTMLSelectElement }[] = [];

  function addRow() {
    const row = document.createElement('div');
    row.className = 'inline-form';
    const roleSelect = renderRoleSelect('orga');
    row.append(roleSelect);
    const rowStatus = document.createElement('span');
    rowStatus.className = 'status-text';
    rowStatus.setAttribute('role', 'status');
    row.append(rowStatus);

    mountUserPicker(row, (user) => {
      pending.push({ user, roleSelect });
      rowStatus.textContent = `Resolved: ${displayNameFor({ ...user, user_id: user.id })}`;
    });

    rows.append(row);
  }
  addRow();

  const addRowButton = document.createElement('button');
  addRowButton.type = 'button';
  addRowButton.textContent = 'Add another';
  addRowButton.addEventListener('click', addRow);
  container.append(addRowButton);

  const submitButton = document.createElement('button');
  submitButton.type = 'button';
  submitButton.textContent = 'Send invites';
  const resultsEl = document.createElement('ul');
  resultsEl.className = 'list';
  submitButton.addEventListener('click', async () => {
    if (pending.length === 0) return;
    const results = await bulkInviteMembers(
      tenant.id,
      pending.map(({ user, roleSelect }) => ({
        user_id: user.id,
        role: roleSelect.value as 'owner' | 'orga',
      })),
    );
    resultsEl.replaceChildren(
      ...results.map((result) => {
        const item = document.createElement('li');
        item.textContent =
          result.status === 'ok'
            ? `${result.user_id}: invited`
            : `${result.user_id}: ${result.problem?.detail ?? result.problem?.title ?? 'failed'}`;
        return item;
      }),
    );
    onChanged();
  });
  container.append(submitButton, resultsEl);

  return container;
}

export function renderMembershipAdmin(
  tenant: TenantSummaryOut,
  memberships: MembershipRosterEntryOut[],
  onChanged: () => void,
): HTMLElement {
  const section = document.createElement('div');
  section.className = 'panel';
  const heading = document.createElement('h3');
  heading.textContent = 'Tenant admins';
  section.append(heading);
  section.append(renderMembershipList(tenant, memberships, onChanged));
  section.append(renderInviteForm(tenant, onChanged));
  section.append(renderBulkInviteForm(tenant, onChanged));
  return section;
}
