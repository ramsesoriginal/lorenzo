// What someone who belongs nowhere yet is offered: start a table, if the account may (ADR 0175),
// or join one by an invite link or just its code, which goes on to /join as a link someone
// opened would.

import { pastedInvite } from '../../lib/inviteLink';
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

    const result = pastedInvite(input.value, window.location.origin);

    if ('error' in result) {
      error.textContent = result.error;
      error.hidden = false;
      input.focus();

      return;
    }

    error.hidden = true;
    input.value = '';
    window.location.assign(result.href);
  });

  root.hidden = false;
}
