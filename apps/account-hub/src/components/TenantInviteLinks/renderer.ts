// An Owner's invite links for a library or repository (ADR 0212): make one, see them all, revoke
// one. A token exists exactly once, in the response to creating a link; the panel shows the whole
// link then and nowhere else.

import { GM_WORDS } from '../../lib/gmTitle';
import {
  EXPIRY_PRESETS,
  type ExpiryPresetId,
  expiresAtFor,
  GM_EXPIRY_PRESETS,
  type GmExpiryPresetId,
  inviteStatus,
  inviteUrl,
  LIBRARY_LINK_NOTICE,
  LINK_ROLES,
  type LinkRole,
  libraryLinkWho,
  linkKindLabel,
  MAX_TEAM,
  parseTeamSize,
  revokeConfirmation,
  roleLinkNotice,
  STATUS_LABELS,
  usesLabel,
} from '../../lib/inviteLink';
import { formatTimestamp } from '../../lib/relativeTime';
import { say, sayError } from '../../lib/statusLine';
import { fromTemplate, requiredIn, rootElement } from '../../lib/template';
import { createTenantInvite, listTenantInvites, revokeTenantInvite } from '../../lib/tenantInvites';
import { kindNoun } from '../../lib/tenantKind';
import type { InviteOut, TenantSummaryOut } from '../../lib/types';
import { renderLinkOnce } from '../LinkOnce/renderer';

const required = requiredIn('Tenant invite links');

export type LinksMode = 'role' | 'library';

function fillPresets(
  select: HTMLSelectElement,
  presets: readonly { id: string; label: string }[],
  selectedId: string,
): void {
  select.replaceChildren(
    ...presets.map(
      (preset) => new Option(preset.label, preset.id, false, preset.id === selectedId),
    ),
  );
}

function inviteRow(
  root: HTMLElement,
  tenant: TenantSummaryOut,
  invite: InviteOut,
  onChanged: () => void,
): HTMLElement {
  const fragment = fromTemplate(root, '[data-invite-template]');
  const state = inviteStatus(invite, new Date());
  const revoke = required<HTMLButtonElement>(fragment, '[data-revoke]');
  const rowStatus = required<HTMLElement>(fragment, '[data-status]');

  required<HTMLElement>(fragment, '[data-state]').textContent = STATUS_LABELS[state];
  required<HTMLElement>(fragment, '[data-meta]').textContent =
    `${linkKindLabel(invite.role, GM_WORDS.title)} · Created ${formatTimestamp(invite.created_at)} · Expires ${formatTimestamp(invite.expires_at)} · Used ${usesLabel(invite)}`;

  // Only a link that still works can be revoked.
  if (state !== 'active') {
    revoke.remove();
    rowStatus.remove();
  } else {
    revoke.addEventListener('click', async () => {
      if (!window.confirm(revokeConfirmation())) return;

      revoke.disabled = true;
      say(rowStatus, 'Revoking…');

      try {
        await revokeTenantInvite(tenant.id, invite.id);
        onChanged();
      } catch (e) {
        revoke.disabled = false;
        sayError(rowStatus, e);
      }
    });
  }

  return rootElement(fragment);
}

// `root` is the <TenantInviteLinks /> panel for `tenant`, which the caller owns. `mode` says which
// links it is about: `role` links (in People) or, for a repository, `library` links.
export function renderTenantInviteLinks(
  root: HTMLElement,
  tenant: TenantSummaryOut,
  mode: LinksMode,
): void {
  const noun = kindNoun(tenant.kind);
  const form = required<HTMLFormElement>(root, '[data-form]');
  const roleField = required<HTMLElement>(form, '[data-role-field]');
  const role = required<HTMLSelectElement>(form, '[data-role]');
  const expiry = required<HTMLSelectElement>(form, '[data-expiry]');
  const teamField = required<HTMLElement>(form, '[data-team-field]');
  const team = required<HTMLInputElement>(form, '[data-team]');
  const create = required<HTMLButtonElement>(form, '[data-create]');
  const formStatus = required<HTMLElement>(form, '[data-links-status]');
  const created = required<HTMLElement>(root, '[data-created]');
  const listStatus = required<HTMLElement>(root, '[data-list-status]');
  const list = required<HTMLElement>(root, '[data-list]');

  const isRole = mode === 'role';

  required<HTMLElement>(root, '[data-heading]').textContent = isRole
    ? 'Add people with a link:'
    : 'Or send a link:';
  required<HTMLElement>(root, '[data-help]').textContent = isRole
    ? `Someone without an account yet, or whose name you don't have, can use a link. It makes an Author or an Organizer of this ${noun}, never an Owner. Each link ends, and has a limit on how many people may use it.`
    : "A link lets whoever owns a library share this repository with it, without you knowing the library's id. It ends, and works for one library unless you say more.";
  role.replaceChildren(...LINK_ROLES.map((r) => new Option(r.label, r.role)));
  roleField.hidden = !isRole;
  fillPresets(expiry, isRole ? GM_EXPIRY_PRESETS : EXPIRY_PRESETS, isRole ? '3d' : '1w');
  required<HTMLElement>(form, '[data-team-label]').textContent = isRole
    ? `How many people may use it (1 to ${MAX_TEAM})`
    : `How many libraries may use it (1 to ${MAX_TEAM})`;

  // An Organizer link is for one person, whatever is asked.
  function syncTeam(): void {
    const single = isRole && role.value === 'orga';

    teamField.hidden = single;
    if (single) team.value = '';
  }
  role.addEventListener('change', syncTeam);
  syncTeam();

  function showLink(url: string, notice: string, label: string): void {
    const fragment = fromTemplate(root, '[data-link-once-template]');
    const linkOnce = required<HTMLElement>(fragment, '[data-link-once]');

    renderLinkOnce(linkOnce, { url, notice, label, onDismiss: () => created.replaceChildren() });
    created.replaceChildren(fragment);
  }

  async function refresh(): Promise<void> {
    try {
      const wanted = isRole ? 'tenant_role' : 'library_access';
      const invites = (await listTenantInvites(tenant.id)).filter((i) => i.kind === wanted);

      say(listStatus, invites.length === 0 ? 'No links yet.' : '');
      list.replaceChildren(
        ...invites.map((invite) => inviteRow(root, tenant, invite, () => void refresh())),
      );
    } catch (e) {
      sayError(listStatus, e);
    }
  }

  form.addEventListener('submit', async (event) => {
    event.preventDefault();

    const parsed = parseTeamSize(teamField.hidden ? '' : team.value);

    if (parsed === null) {
      say(formStatus, `Use a whole number from 1 to ${MAX_TEAM}, or leave it empty for one.`, true);

      return;
    }

    create.disabled = true;
    say(formStatus, 'Making it…');

    try {
      const picked = role.value as LinkRole;
      const invite = await createTenantInvite(
        tenant.id,
        isRole
          ? {
              kind: 'tenant_role',
              role: picked,
              max_uses: parsed.size,
              expires_at: expiresAtFor(expiry.value as GmExpiryPresetId, new Date()),
            }
          : {
              kind: 'library_access',
              max_uses: parsed.size,
              expires_at: expiresAtFor(expiry.value as ExpiryPresetId, new Date()),
            },
      );

      say(formStatus, '');
      team.value = '';
      showLink(
        inviteUrl(window.location.origin, invite.token),
        isRole
          ? roleLinkNotice(picked, noun, parsed.size)
          : `${LIBRARY_LINK_NOTICE} It works for ${libraryLinkWho(parsed.size)}.`,
        isRole
          ? `${picked === 'orga' ? 'Organizer' : 'Author'} invite link`
          : 'Library invite link',
      );
      await refresh();
    } catch (e) {
      sayError(formStatus, e);
    } finally {
      create.disabled = false;
    }
  });

  void refresh();
}
