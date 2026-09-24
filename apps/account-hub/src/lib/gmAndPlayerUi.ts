// GM management + invite-player panels, split out of tenants.astro - see
// ADR 0080. Like userPicker.ts (ADR 0074), this is a lib/*.ts module that
// builds and returns DOM, not just an API wrapper.

import { resolveDisplayName } from './format';
import { grantCampaignGm, invitePlayer, revokeCampaignGm } from './tenants';
import type { CampaignSummaryOut, RosterEntry, TenantSummaryOut } from './types';
import { mountUserPicker } from './userPicker';

// GmOut itself has no display name (ADR 0076) - roster is the tenant's
// full GET /tenants/{id}/memberships fetch (RFC 0017 (a)), a materially
// better name source resolved by matching user_id.
export function renderGmManagement(
  tenant: TenantSummaryOut,
  campaign: CampaignSummaryOut,
  gms: string[],
  roster: RosterEntry[],
  onChanged: () => void,
): HTMLElement {
  const section = document.createElement('div');
  const heading = document.createElement('p');
  heading.textContent = 'GMs:';
  section.append(heading);

  const list = document.createElement('ul');
  list.className = 'list';
  for (const userId of gms) {
    const item = document.createElement('li');
    const idEl = document.createElement('span');
    idEl.textContent = resolveDisplayName(roster, userId);
    const revokeButton = document.createElement('button');
    revokeButton.type = 'button';
    revokeButton.textContent = 'Revoke';
    const status = document.createElement('span');
    status.className = 'status-text';
    status.setAttribute('role', 'status');
    revokeButton.addEventListener('click', async () => {
      status.textContent = 'Revoking…';
      try {
        await revokeCampaignGm(tenant.id, campaign.id, userId);
        onChanged();
      } catch (e) {
        status.textContent = e instanceof Error ? e.message : String(e);
      }
    });
    item.append(idEl, revokeButton, status);
    list.append(item);
  }
  section.append(list);

  const pickerContainer = document.createElement('div');
  const pickerLabel = document.createElement('p');
  pickerLabel.textContent = 'Assign a new GM:';
  pickerContainer.append(pickerLabel);
  mountUserPicker(pickerContainer, async (user) => {
    try {
      await grantCampaignGm(tenant.id, campaign.id, user.id);
      onChanged();
    } catch (e) {
      pickerContainer.append(
        Object.assign(document.createElement('p'), {
          textContent: e instanceof Error ? e.message : String(e),
        }),
      );
    }
  });
  section.append(pickerContainer);

  return section;
}

export function renderInvitePlayer(
  tenant: TenantSummaryOut,
  campaign: CampaignSummaryOut,
): HTMLElement {
  const section = document.createElement('div');
  const label = document.createElement('p');
  label.textContent = 'Invite a player:';
  section.append(label);
  mountUserPicker(section, async (user) => {
    try {
      await invitePlayer(tenant.id, campaign.id, { user_id: user.id });
    } catch (e) {
      section.append(
        Object.assign(document.createElement('p'), {
          textContent: e instanceof Error ? e.message : String(e),
        }),
      );
    }
  });
  return section;
}
