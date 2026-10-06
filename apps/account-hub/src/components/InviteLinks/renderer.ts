// Invite links for a campaign's managers (ADR 0171): make one, see them all,
// revoke one. A token exists exactly once, in the response to creating a link;
// the panel shows the whole link then, in one element, and nowhere else.

import {
  EXPIRY_PRESETS,
  type ExpiryPresetId,
  expiresAtFor,
  GM_EXPIRY_PRESETS,
  GM_LINK_SHOWN_ONCE_NOTICE,
  type GmExpiryPresetId,
  inviteStatus,
  inviteUrl,
  linkKindLabel,
  parseMaxUses,
  revokeConfirmation,
  STATUS_LABELS,
  usesLabel,
} from '../../lib/inviteLink';
import { createInvite, listInvites, revokeInvite } from '../../lib/invites';
import { say, sayError } from '../../lib/statusLine';
import { fromTemplate, requiredIn, rootElement } from '../../lib/template';
import type { CampaignSummaryOut, InviteOut, TenantSummaryOut } from '../../lib/types';
import { renderLinkOnce } from '../LinkOnce/renderer';

const required = requiredIn('Invite links');

function formatWhen(iso: string): string {
  return new Date(iso).toLocaleString();
}

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
  campaign: CampaignSummaryOut,
  invite: InviteOut,
  onChanged: () => void,
): HTMLElement {
  const fragment = fromTemplate(root, '[data-invite-template]');
  const state = inviteStatus(invite, new Date());
  const revoke = required<HTMLButtonElement>(fragment, '[data-revoke]');
  const rowStatus = required<HTMLElement>(fragment, '[data-status]');

  required<HTMLElement>(fragment, '[data-state]').textContent = STATUS_LABELS[state];
  required<HTMLElement>(fragment, '[data-meta]').textContent =
    `${linkKindLabel(invite.role)} · Created ${formatWhen(invite.created_at)} · Expires ${formatWhen(invite.expires_at)} · Used ${usesLabel(invite)}`;

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
        await revokeInvite(tenant.id, campaign.id, invite.id);
        onChanged();
      } catch (e) {
        revoke.disabled = false;
        sayError(rowStatus, e);
      }
    });
  }

  return rootElement(fragment);
}

// `root` is the <InviteLinks /> panel.
export function renderInviteLinks(
  root: HTMLElement,
  tenant: TenantSummaryOut,
  campaign: CampaignSummaryOut,
): void {
  const form = required<HTMLFormElement>(root, '[data-player-form]');
  const expiry = required<HTMLSelectElement>(form, '[data-expiry]');
  const limit = required<HTMLInputElement>(form, '[data-limit]');
  const create = required<HTMLButtonElement>(form, '[data-create]');
  const formStatus = required<HTMLElement>(form, '[data-form-status]');

  const gmForm = required<HTMLFormElement>(root, '[data-gm-form]');
  const gmExpiry = required<HTMLSelectElement>(gmForm, '[data-gm-expiry]');
  const gmCreate = required<HTMLButtonElement>(gmForm, '[data-gm-create]');
  const gmStatus = required<HTMLElement>(gmForm, '[data-gm-status]');

  const created = required<HTMLElement>(root, '[data-created]');
  const listStatus = required<HTMLElement>(root, '[data-list-status]');
  const list = required<HTMLElement>(root, '[data-list]');

  fillPresets(expiry, EXPIRY_PRESETS, '1w');
  fillPresets(gmExpiry, GM_EXPIRY_PRESETS, '3d');

  // The link, shown in place of any earlier one; Done takes it off the page again.
  function showLink(url: string, options: { notice?: string; label?: string } = {}): void {
    const fragment = fromTemplate(root, '[data-link-once-template]');
    const linkOnce = required<HTMLElement>(fragment, '[data-link-once]');

    renderLinkOnce(linkOnce, { url, onDismiss: () => created.replaceChildren(), ...options });
    created.replaceChildren(fragment);
  }

  async function refresh(): Promise<void> {
    try {
      const invites = await listInvites(tenant.id, campaign.id);

      say(listStatus, invites.length === 0 ? 'No links yet.' : '');
      list.replaceChildren(
        ...invites.map((invite) => inviteRow(root, tenant, campaign, invite, () => void refresh())),
      );
    } catch (e) {
      sayError(listStatus, e);
    }
  }

  form.addEventListener('submit', async (event) => {
    event.preventDefault();

    const parsed = parseMaxUses(limit.value);

    if (parsed === null) {
      say(formStatus, 'Use a whole number of 1 or more, or leave it empty for no limit.');

      return;
    }

    create.disabled = true;
    say(formStatus, 'Creating…');

    try {
      const invite = await createInvite(tenant.id, campaign.id, {
        expires_at: expiresAtFor(expiry.value as ExpiryPresetId, new Date()),
        // The generated type wants a role whatever the server's default (ADR 0177);
        // this panel makes the player links of ADR 0171.
        role: 'player',
        ...(parsed.maxUses === null ? {} : { max_uses: parsed.maxUses }),
      });

      say(formStatus, '');
      limit.value = '';
      showLink(inviteUrl(window.location.origin, invite.token));
      await refresh();
    } catch (e) {
      sayError(formStatus, e);
    } finally {
      create.disabled = false;
    }
  });

  gmForm.addEventListener('submit', async (event) => {
    event.preventDefault();
    gmCreate.disabled = true;
    say(gmStatus, 'Creating…');

    try {
      const invite = await createInvite(tenant.id, campaign.id, {
        expires_at: expiresAtFor(gmExpiry.value as GmExpiryPresetId, new Date()),
        role: 'gm',
      });

      say(gmStatus, '');
      showLink(inviteUrl(window.location.origin, invite.token), {
        notice: GM_LINK_SHOWN_ONCE_NOTICE,
        label: 'GM invite link',
      });
      await refresh();
    } catch (e) {
      sayError(gmStatus, e);
    } finally {
      gmCreate.disabled = false;
    }
  });

  void refresh();
}
