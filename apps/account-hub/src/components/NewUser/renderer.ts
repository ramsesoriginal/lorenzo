// What someone who belongs nowhere yet is offered: start a table, if the account may (ADR 0175),
// or join one by an invite link or just its code, which goes on to /join as a link someone
// opened would.

import { inviteTokenFrom, inviteUrl } from '../../lib/inviteLink';
import { requiredIn } from '../../lib/template';
import { canCreateTenants } from '../../lib/tenantKind';
import type { MeOut } from '../../lib/types';

const required = requiredIn('New user');

// `root` is the <NewUser /> block; it shows itself.
export function renderNewUser(root: HTMLElement, me: MeOut): void {
  const mayCreate = canCreateTenants(me);
  const form = required<HTMLFormElement>(root, '[data-invite-form]');
  const input = required<HTMLInputElement>(root, '[data-invite-input]');
  const error = required<HTMLElement>(root, '[data-invite-error]');

  required<HTMLElement>(root, '[data-start-card]').hidden = !mayCreate;
  required<HTMLElement>(root, '[data-can-create]').hidden = !mayCreate;
  required<HTMLElement>(root, '[data-cannot-create]').hidden = mayCreate;

  form.addEventListener('submit', (event) => {
    event.preventDefault();

    const token = inviteTokenFrom(input.value);

    if (token === null) {
      error.textContent =
        "That doesn't look like an invite link or code. Check it against what your GM sent you.";
      error.hidden = false;
      input.focus();

      return;
    }

    error.hidden = true;
    input.value = '';
    window.location.assign(inviteUrl(window.location.origin, token));
  });

  root.hidden = false;
}
