// Invite links for a campaign's managers (ADR 0171): make one, see them all,
// revoke one. Like userPicker.ts (ADR 0074), a lib/*.ts module that builds DOM.
// A token exists exactly once, in the response to creating a link; the panel
// shows the whole link then, in one element, and nowhere else.
import { createStatusSpan } from './dom';
import { showError } from './errorUi';
import {
  EXPIRY_PRESETS,
  type ExpiryPresetId,
  expiresAtFor,
  GM_EXPIRY_PRESETS,
  GM_LINK_SHOWN_ONCE_NOTICE,
  type GmExpiryPresetId,
  inviteStatus,
  inviteUrl,
  LINK_SHOWN_ONCE_NOTICE,
  linkKindLabel,
  parseMaxUses,
  revokeConfirmation,
  STATUS_LABELS,
  usesLabel,
} from './inviteLink';
import { createInvite, listInvites, revokeInvite } from './invites';
import type { CampaignSummaryOut, InviteOut, TenantSummaryOut } from './types';

function formatWhen(iso: string): string {
  return new Date(iso).toLocaleString();
}

async function copyText(text: string, source: HTMLInputElement): Promise<void> {
  try {
    await navigator.clipboard.writeText(text);
  } catch {
    // No async clipboard (an insecure context, a blocked permission): leave the
    // link selected, ready for the person's own copy.
    source.select();
    throw new Error("Couldn't copy it for you. The link is selected: copy it yourself.");
  }
}

// What follows creating a link: the link itself, once. Also the result screen
// of /setup (ADR 0180), which says its own `notice` and `label`.
export function renderLinkOnce(
  url: string,
  onDismiss: () => void,
  notice: string = LINK_SHOWN_ONCE_NOTICE,
  label = 'Invite link',
): HTMLElement {
  const box = document.createElement('div');
  box.className = 'invite-link-once';
  box.setAttribute('role', 'status');

  const input = document.createElement('input');
  input.type = 'text';
  input.readOnly = true;
  input.className = 'invite-link-input';
  input.value = url;
  input.setAttribute('aria-label', label);

  const copy = document.createElement('button');
  copy.type = 'button';
  copy.textContent = 'Copy';
  const done = document.createElement('button');
  done.type = 'button';
  done.textContent = 'Done';
  const status = createStatusSpan();
  copy.addEventListener('click', async () => {
    try {
      await copyText(url, input);
      status.textContent = 'Copied.';
    } catch (e) {
      showError(status, e);
    }
  });
  done.addEventListener('click', () => {
    // The only copy of the link on the page goes with the box.
    input.value = '';
    onDismiss();
  });

  const noticeEl = document.createElement('p');
  noticeEl.textContent = notice;
  box.append(input, copy, done, status, noticeEl);
  queueMicrotask(() => input.select());
  return box;
}

function renderInviteRow(
  tenant: TenantSummaryOut,
  campaign: CampaignSummaryOut,
  invite: InviteOut,
  onChanged: () => void,
): HTMLLIElement {
  const item = document.createElement('li');
  const status = inviteStatus(invite, new Date());

  const badge = document.createElement('span');
  badge.className = 'badge';
  badge.textContent = STATUS_LABELS[status];
  const meta = document.createElement('span');
  meta.className = 'campaign-meta';
  meta.textContent = `${linkKindLabel(invite.role)} · Created ${formatWhen(invite.created_at)} · Expires ${formatWhen(invite.expires_at)} · Used ${usesLabel(invite)}`;
  item.append(badge, meta);

  if (status === 'active') {
    const revoke = document.createElement('button');
    revoke.type = 'button';
    revoke.textContent = 'Revoke';
    const rowStatus = createStatusSpan();
    revoke.addEventListener('click', async () => {
      if (!window.confirm(revokeConfirmation())) return;
      revoke.disabled = true;
      rowStatus.textContent = 'Revoking…';
      try {
        await revokeInvite(tenant.id, campaign.id, invite.id);
        onChanged();
      } catch (e) {
        revoke.disabled = false;
        showError(rowStatus, e);
      }
    });
    item.append(revoke, rowStatus);
  }
  return item;
}

export function renderInviteLinks(
  tenant: TenantSummaryOut,
  campaign: CampaignSummaryOut,
): HTMLElement {
  const section = document.createElement('div');
  section.className = 'panel';
  const heading = document.createElement('p');
  heading.textContent = 'Invite links:';

  const form = document.createElement('form');
  form.className = 'inline-form';
  const expiry = document.createElement('select');
  for (const preset of EXPIRY_PRESETS) {
    const option = document.createElement('option');
    option.value = preset.id;
    option.textContent = preset.label;
    option.selected = preset.id === '1w';
    expiry.append(option);
  }
  const expiryLabel = document.createElement('label');
  expiryLabel.append('Expires in ', expiry);
  const limit = document.createElement('input');
  limit.type = 'text';
  limit.inputMode = 'numeric';
  limit.placeholder = 'No limit';
  const limitLabel = document.createElement('label');
  limitLabel.append('Most people who may use it (optional) ', limit);
  const create = document.createElement('button');
  create.type = 'submit';
  create.textContent = 'Create link';
  const formStatus = createStatusSpan();
  form.append(expiryLabel, limitLabel, create, formStatus);

  // A GM link (ADR 0177): one person, one use, at most a week. Next to the
  // player link, since whoever may grant GM may hand it over this way.
  const gmForm = document.createElement('form');
  gmForm.className = 'inline-form';
  const gmExpiry = document.createElement('select');
  for (const preset of GM_EXPIRY_PRESETS) {
    const option = document.createElement('option');
    option.value = preset.id;
    option.textContent = preset.label;
    option.selected = preset.id === '3d';
    gmExpiry.append(option);
  }
  const gmExpiryLabel = document.createElement('label');
  gmExpiryLabel.append('GM link expires in ', gmExpiry);
  const gmCreate = document.createElement('button');
  gmCreate.type = 'submit';
  gmCreate.textContent = 'Invite a GM';
  const gmStatus = createStatusSpan();
  gmForm.append(gmExpiryLabel, gmCreate, gmStatus);

  const created = document.createElement('div');
  const listStatus = createStatusSpan();
  const list = document.createElement('ul');
  list.className = 'list';
  section.append(heading, form, gmForm, created, listStatus, list);

  async function refresh(): Promise<void> {
    try {
      const invites = await listInvites(tenant.id, campaign.id);
      listStatus.textContent = invites.length === 0 ? 'No links yet.' : '';
      list.replaceChildren(
        ...invites.map((invite) => renderInviteRow(tenant, campaign, invite, () => void refresh())),
      );
    } catch (e) {
      showError(listStatus, e);
    }
  }

  form.addEventListener('submit', async (event) => {
    event.preventDefault();
    const parsed = parseMaxUses(limit.value);
    if (parsed === null) {
      formStatus.textContent = 'Use a whole number of 1 or more, or leave it empty for no limit.';
      return;
    }
    create.disabled = true;
    formStatus.textContent = 'Creating…';
    try {
      const invite = await createInvite(tenant.id, campaign.id, {
        expires_at: expiresAtFor(expiry.value as ExpiryPresetId, new Date()),
        // The generated type wants a role whatever the server's default (ADR 0177);
        // this panel makes the player links of ADR 0171.
        role: 'player',
        ...(parsed.maxUses === null ? {} : { max_uses: parsed.maxUses }),
      });
      formStatus.textContent = '';
      limit.value = '';
      created.replaceChildren(
        renderLinkOnce(inviteUrl(window.location.origin, invite.token), () =>
          created.replaceChildren(),
        ),
      );
      await refresh();
    } catch (e) {
      showError(formStatus, e);
    } finally {
      create.disabled = false;
    }
  });

  gmForm.addEventListener('submit', async (event) => {
    event.preventDefault();
    gmCreate.disabled = true;
    gmStatus.textContent = 'Creating…';
    try {
      const invite = await createInvite(tenant.id, campaign.id, {
        expires_at: expiresAtFor(gmExpiry.value as GmExpiryPresetId, new Date()),
        role: 'gm',
      });
      gmStatus.textContent = '';
      created.replaceChildren(
        renderLinkOnce(
          inviteUrl(window.location.origin, invite.token),
          () => created.replaceChildren(),
          GM_LINK_SHOWN_ONCE_NOTICE,
          'GM invite link',
        ),
      );
      await refresh();
    } catch (e) {
      showError(gmStatus, e);
    } finally {
      gmCreate.disabled = false;
    }
  });

  void refresh();
  return section;
}
