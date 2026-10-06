// GM management on a campaign: who the GMs are, a Revoke for each, and a picker to assign
// another (ADR 0080).

import { resolveDisplayName } from '../../lib/format';
import { say, sayError } from '../../lib/statusLine';
import { fromTemplate, requiredIn } from '../../lib/template';
import { grantCampaignGm, revokeCampaignGm } from '../../lib/tenants';
import type { CampaignSummaryOut, RosterEntry, TenantSummaryOut } from '../../lib/types';
import { renderUserPicker } from '../UserPicker/renderer';

const required = requiredIn('GM management');

// GmOut itself has no display name (ADR 0076) - roster is the tenant's full
// GET /tenants/{id}/memberships fetch (RFC 0017 (a)), a materially better name source resolved
// by matching user_id.
//
// `root` is the <GmManagement /> block.
export function renderGmManagement(
  root: HTMLElement,
  tenant: TenantSummaryOut,
  campaign: CampaignSummaryOut,
  gms: string[],
  roster: RosterEntry[],
  onChanged: () => void,
): void {
  const list = required<HTMLElement>(root, '[data-gm-list]');
  const error = required<HTMLElement>(root, '[data-error]');

  for (const userId of gms) {
    const row = fromTemplate(root, '[data-row-template]');
    const revokeButton = required<HTMLButtonElement>(row, '[data-revoke]');
    const status = required<HTMLElement>(row, '[data-status]');

    required<HTMLElement>(row, '[data-name]').textContent = resolveDisplayName(roster, userId);
    revokeButton.addEventListener('click', async () => {
      say(status, 'Revoking…');
      try {
        await revokeCampaignGm(tenant.id, campaign.id, userId);
        onChanged();
      } catch (e) {
        sayError(status, e);
      }
    });
    list.append(row);
  }

  renderUserPicker(required<HTMLElement>(root, '[data-user-picker]'), async (user) => {
    say(error, '');
    try {
      await grantCampaignGm(tenant.id, campaign.id, user.id);
      onChanged();
    } catch (e) {
      sayError(error, e);
    }
  });
}
