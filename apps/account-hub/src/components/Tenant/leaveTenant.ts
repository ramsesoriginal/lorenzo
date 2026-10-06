// Leaving a library or repository (ADR 0170). Asks first with window.confirm, the pattern
// characters.astro uses for "Leave this campaign".

import { leaveTenantConfirmation, soleOwnerMessage } from '../../lib/exits';
import { say, sayError } from '../../lib/statusLine';
import { requiredIn } from '../../lib/template';
import { kindNoun } from '../../lib/tenantKind';
import { deleteMembership } from '../../lib/tenants';
import type { TenantSummaryOut } from '../../lib/types';

const required = requiredIn('Tenant');

export type BoundLeaveTenant = {
  // Shows the button for `tenant` if its caller holds a Membership there, and nothing otherwise.
  show(tenant: TenantSummaryOut): void;
};

// Shown on every library or repository where the caller has a Membership (owner or orga):
// DELETE .../memberships/{me} is open to the member themselves, whatever their role. A person
// who only plays or GMs there has nothing to leave here; their way out is "Leave this campaign"
// on /campaigns. A repository says so in its own word (ADR 0178).
//
// `root` is <Tenant />'s leave block, one for every tenant shown, so this binds once and `show`
// says which tenant it is for.
export function bindLeaveTenant(
  root: HTMLElement,
  userId: string,
  onLeft: () => void,
): BoundLeaveTenant {
  const button = required<HTMLButtonElement>(root, '[data-leave-button]');
  const noun = required<HTMLElement>(root, '[data-noun]');
  const status = required<HTMLElement>(root, '[data-leave-status]');

  let tenant: TenantSummaryOut | null = null;
  // Counts the tenants shown, so an answer that arrives for an earlier one is dropped.
  let shown = 0;

  button.addEventListener('click', async () => {
    const target = tenant;
    const turn = shown;

    if (!target) return;
    if (!window.confirm(leaveTenantConfirmation(target.name, target.kind))) return;

    button.disabled = true;
    say(status, 'Leaving…');

    try {
      await deleteMembership(target.id, userId);
      onLeft();
    } catch (cause) {
      if (turn !== shown) return;

      button.disabled = false;

      // "You're the only owner" in its own words, whatever describeError makes of it otherwise.
      const soleOwner = soleOwnerMessage(
        cause,
        new Map([[target.id, target.name]]),
        'leave-library',
      );

      if (soleOwner === null) sayError(status, cause);
      else say(status, soleOwner, true);
    }
  });

  return {
    show(next) {
      shown += 1;
      tenant = next;

      noun.textContent = kindNoun(next.kind);
      button.disabled = false;
      say(status, '');
      root.hidden = next.role !== 'owner' && next.role !== 'orga';
    },
  };
}
