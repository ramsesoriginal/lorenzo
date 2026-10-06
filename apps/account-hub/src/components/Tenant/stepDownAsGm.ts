// Stepping down as a campaign's GM (ADR 0170). Asks first with window.confirm.

import { stepDownConfirmation } from '../../lib/exits';
import { say, sayError } from '../../lib/statusLine';
import { requiredIn } from '../../lib/template';
import { revokeCampaignGm } from '../../lib/tenants';
import type { CampaignSummaryOut, TenantSummaryOut } from '../../lib/types';

const required = requiredIn('Tenant');

// Shown wherever the caller is a GM of the campaign, administrator or not:
// DELETE .../gms/{me} lets anyone remove their own grant (ADR 0034).
//
// `root` is the step-down block of one campaign's row in <Tenant />'s template.
export function bindStepDownAsGm(
  root: HTMLElement,
  tenant: TenantSummaryOut,
  campaign: CampaignSummaryOut,
  userId: string,
  onDone: () => void,
): void {
  const button = required<HTMLButtonElement>(root, '[data-step-down]');
  const status = required<HTMLElement>(root, '[data-step-down-status]');

  button.addEventListener('click', async () => {
    if (!window.confirm(stepDownConfirmation(campaign.name))) return;

    button.disabled = true;
    say(status, 'Stepping down…');

    try {
      await revokeCampaignGm(tenant.id, campaign.id, userId);
      onDone();
    } catch (cause) {
      button.disabled = false;
      sayError(status, cause);
    }
  });
}
