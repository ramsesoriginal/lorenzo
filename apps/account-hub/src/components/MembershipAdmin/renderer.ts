// Tenant-wide membership management and bulk invite - RFC 0017 (e), with the Author role (ADR 0212).
// Distinct from the campaign-scoped GM/player management: this is tenant-wide owner/orga role
// administration. Bulk invite is confirmed _require_owner-gated server-side; the single-item
// actions here are gated identically for consistency rather than assumed looser (showing nothing
// to an orga who might technically have single-item rights is the safe direction of a wrong
// guess).

import { displayNameFor } from '../../lib/format';
import { say, sayError } from '../../lib/statusLine';
import { roleMeanings } from '../../lib/studio';
import { fromTemplate, requiredIn, rootElement } from '../../lib/template';
import { kindNoun } from '../../lib/tenantKind';
import {
  bulkInviteMembers,
  createMembership,
  deleteMembership,
  updateMembership,
} from '../../lib/tenants';
import type {
  BulkMembershipResultItem,
  MembershipRosterEntryOut,
  TenantSummaryOut,
  UserRefOut,
} from '../../lib/types';
import { renderUserPicker } from '../UserPicker/renderer';

type Role = 'owner' | 'orga' | 'author';

const required = requiredIn('Membership admin');

function roleOf(select: HTMLSelectElement): Role {
  return select.value as Role;
}

// One line per admin: the role changes on selection, and Remove takes them out.
function fillMembers(
  root: HTMLElement,
  tenant: TenantSummaryOut,
  memberships: MembershipRosterEntryOut[],
  onChanged: () => void,
): void {
  const list = required<HTMLElement>(root, '[data-members]');

  for (const membership of memberships) {
    const item = fromTemplate(root, '[data-member-template]');
    const roleSelect = required<HTMLSelectElement>(item, '[data-role]');
    const removeButton = required<HTMLButtonElement>(item, '[data-remove]');
    const status = required<HTMLElement>(item, '[data-status]');

    required<HTMLElement>(item, '[data-name]').textContent = displayNameFor(membership);
    // Who added them, where that person is in the list too.
    const adder = memberships.find((other) => other.user_id === membership.created_by);

    if (adder) {
      const addedBy = required<HTMLElement>(item, '[data-added-by]');

      addedBy.textContent = `Added by ${displayNameFor(adder)}`;
      addedBy.hidden = false;
    }
    roleSelect.value = membership.role;

    roleSelect.addEventListener('change', async () => {
      say(status, 'Saving…');
      try {
        await updateMembership(tenant.id, membership.user_id, { role: roleOf(roleSelect) });
        onChanged();
      } catch (e) {
        sayError(status, e);
      }
    });

    removeButton.addEventListener('click', async () => {
      say(status, 'Removing…');
      try {
        await deleteMembership(tenant.id, membership.user_id);
        onChanged();
      } catch (e) {
        sayError(status, e);
      }
    });

    list.append(item);
  }
}

function bindInvite(
  root: HTMLElement,
  tenant: TenantSummaryOut,
  onChanged: () => void,
  label: string,
): void {
  const invite = required<HTMLElement>(root, '[data-invite]');
  const roleSelect = required<HTMLSelectElement>(invite, '[data-invite-role]');
  const status = required<HTMLElement>(invite, '[data-status]');

  required<HTMLElement>(invite, '[data-invite-label]').textContent = label;

  // One line on what the chosen role allows, under the choice.
  const meaning = required<HTMLElement>(invite, '[data-role-meaning]');
  const showMeaning = () => {
    meaning.textContent =
      roleMeanings(tenant.kind).find((m) => m.role === roleSelect.value)?.meaning ?? '';
  };

  roleSelect.addEventListener('change', showMeaning);
  showMeaning();

  renderUserPicker(required<HTMLElement>(invite, '[data-user-picker]'), async (user) => {
    say(status, 'Inviting…');
    try {
      await createMembership(tenant.id, { user_id: user.id, role: roleOf(roleSelect) });
      say(status, '');
      onChanged();
    } catch (e) {
      sayError(status, e);
    }
  });
}

function bindBulkInvite(root: HTMLElement, tenant: TenantSummaryOut, onChanged: () => void): void {
  const bulk = required<HTMLElement>(root, '[data-bulk-invite]');
  const rows = required<HTMLElement>(bulk, '[data-bulk-rows]');
  const addRowButton = required<HTMLButtonElement>(bulk, '[data-add-row]');
  const sendButton = required<HTMLButtonElement>(bulk, '[data-send]');
  const status = required<HTMLElement>(bulk, '[data-status]');
  const results = required<HTMLElement>(bulk, '[data-results]');

  // The people looked up so far, each with the role chosen in their row.
  const pending: { user: UserRefOut; roleSelect: HTMLSelectElement }[] = [];

  function addRow() {
    const row = fromTemplate(root, '[data-bulk-row-template]');
    const roleSelect = required<HTMLSelectElement>(row, '[data-role]');
    const rowStatus = required<HTMLElement>(row, '[data-status]');

    renderUserPicker(required<HTMLElement>(row, '[data-user-picker]'), (user) => {
      pending.push({ user, roleSelect });
      say(rowStatus, `Resolved: ${displayNameFor({ ...user, user_id: user.id })}`);
    });

    rows.append(row);
  }
  addRow();

  addRowButton.addEventListener('click', addRow);

  function showResults(items: BulkMembershipResultItem[]) {
    results.replaceChildren(
      ...items.map((result) => {
        const line = rootElement(fromTemplate(root, '[data-result-template]'));
        line.textContent =
          result.status === 'ok'
            ? `${result.user_id}: invited`
            : `${result.user_id}: ${result.problem?.detail ?? result.problem?.title ?? 'failed'}`;
        return line;
      }),
    );
  }

  sendButton.addEventListener('click', async () => {
    if (pending.length === 0) return;
    say(status, 'Sending…');
    let items: BulkMembershipResultItem[];
    try {
      items = await bulkInviteMembers(
        tenant.id,
        pending.map(({ user, roleSelect }) => ({ user_id: user.id, role: roleOf(roleSelect) })),
      );
    } catch (e) {
      // The whole call failed (not one invite in it): there are no per-person
      // results to show, so say why.
      sayError(status, e);
      return;
    }
    say(status, '');
    showResults(items);
    onChanged();
  });
}

// `root` is the <MembershipAdmin /> panel. A page that has its own words for the heading and the
// invitation (Studio's People) gives them.
export function renderMembershipAdmin(
  root: HTMLElement,
  tenant: TenantSummaryOut,
  memberships: MembershipRosterEntryOut[],
  onChanged: () => void,
  words: { heading?: string; inviteLabel?: string } = {},
): void {
  required<HTMLElement>(root, '[data-heading]').textContent = words.heading ?? 'People';
  // What each role can do, in this library's or repository's words.
  required<HTMLElement>(root, '[data-roles]').replaceChildren(
    ...roleMeanings(tenant.kind).map(({ label, meaning }) => {
      const item = document.createElement('li');
      const term = document.createElement('strong');

      term.textContent = label;
      item.append(term, ` ${meaning}`);

      return item;
    }),
  );

  fillMembers(root, tenant, memberships, onChanged);
  bindInvite(
    root,
    tenant,
    onChanged,
    words.inviteLabel ?? `Add someone to this ${kindNoun(tenant.kind)}, as:`,
  );
  bindBulkInvite(root, tenant, onChanged);
}
