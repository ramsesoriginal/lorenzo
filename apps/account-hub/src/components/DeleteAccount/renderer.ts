// Deleting your account (ADR 0170). Leaving a library and stepping down as a campaign GM are part of
// the Tenant component. Asks first with window.confirm, the pattern "Leave this campaign" uses. On
// success the person is logged out through Authgear: their Lorenzo account is gone, and the
// Authgear login is not (deleteAccountConfirmation says so).

import { logout } from '../../lib/auth';
import { deleteAccountConfirmation, soleOwnerMessage } from '../../lib/exits';
import { deleteMyAccount } from '../../lib/me';
import { say, sayError } from '../../lib/statusLine';
import { requiredIn } from '../../lib/template';
import { listMyTenants } from '../../lib/tenants';

const required = requiredIn('Delete account');

// `root` is the <DeleteAccount /> block; it shows itself.
export function renderDeleteAccount(root: HTMLElement): void {
  const button = required<HTMLButtonElement>(root, '[data-delete]');
  const status = required<HTMLElement>(root, '[data-status]');

  button.addEventListener('click', async () => {
    if (!window.confirm(deleteAccountConfirmation())) return;

    button.disabled = true;
    say(status, 'Deleting…');

    try {
      await deleteMyAccount();
    } catch (cause) {
      button.disabled = false;

      // The 409 names a library by id; the names come from the libraries the person belongs to,
      // fetched only now that they are needed.
      const names = new Map<string, string>();

      try {
        for (const tenant of (await listMyTenants()).items) names.set(tenant.id, tenant.name);
      } catch {
        // Without names the message still says what to do.
      }

      // The one place a failed delete becomes words: "you're the only owner" when it is that,
      // whatever describeError makes of it otherwise.
      const soleOwner = soleOwnerMessage(cause, names, 'delete-account');

      if (soleOwner === null) sayError(status, cause);
      else say(status, soleOwner, true);

      return;
    }

    say(status, 'Your account is deleted. Logging you out…');
    await logout();
  });

  root.hidden = false;
}
