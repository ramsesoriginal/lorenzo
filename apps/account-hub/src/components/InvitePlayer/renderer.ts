// "Invite a player" on a campaign: pick the person, and they are invited (ADR 0080).

import { say, sayError } from '../../lib/statusLine';
import { requiredIn } from '../../lib/template';
import { invitePlayer } from '../../lib/tenants';
import type { CampaignSummaryOut, TenantSummaryOut } from '../../lib/types';
import { renderUserPicker } from '../UserPicker/renderer';

const required = requiredIn('Invite player');

// `root` is the <InvitePlayer /> block.
export function renderInvitePlayer(
  root: HTMLElement,
  tenant: TenantSummaryOut,
  campaign: CampaignSummaryOut,
): void {
  const error = required<HTMLElement>(root, '[data-error]');

  renderUserPicker(required<HTMLElement>(root, '[data-user-picker]'), async (user) => {
    say(error, '');
    try {
      await invitePlayer(tenant.id, campaign.id, { user_id: user.id });
    } catch (e) {
      sayError(error, e);
    }
  });
}
