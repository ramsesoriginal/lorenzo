// Campaign edit (ADR 0080): an Edit button that opens the campaign form in its place.

import { say, sayError } from '../../lib/statusLine';
import { fromTemplate, requiredIn, rootElement } from '../../lib/template';
import { getCampaign } from '../../lib/tenants';
import type { CampaignSummaryOut, TenantSummaryOut } from '../../lib/types';
import { renderCampaignForm } from '../CampaignForm/renderer';

const required = requiredIn('Campaign edit');

// `root` is the <CampaignEdit /> block.
export function renderCampaignEdit(
  root: HTMLElement,
  tenant: TenantSummaryOut,
  campaign: CampaignSummaryOut,
  onChanged: () => void,
): void {
  const editButton = required<HTMLButtonElement>(root, '[data-edit]');
  const status = required<HTMLElement>(root, '[data-status]');

  // The list view's CampaignSummaryOut has no description, so editing needs
  // the one extra GET .../campaigns/{id} fetch (CampaignOut) - only when
  // Edit is actually clicked, not on every page load.
  editButton.addEventListener('click', async () => {
    editButton.disabled = true;
    say(status, 'Loading…');

    try {
      const full = await getCampaign(tenant.id, campaign.id);
      const form = rootElement(fromTemplate(root, '[data-form-template]'));

      say(status, '');
      renderCampaignForm(form, { mode: 'edit', tenant, campaign: full, onDone: onChanged });
      root.replaceChildren(form);
    } catch (e) {
      editButton.disabled = false;
      sayError(status, e);
    }
  });
}
