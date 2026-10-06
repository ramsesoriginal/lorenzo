// Deleting your account (ADR 0170), which /profile builds in code; leaving a library and stepping
// down as a campaign GM are the LeaveTenant and StepDownAsGm components. Asks first with
// window.confirm, the pattern characters.astro uses for "Leave this campaign".

import { logout } from './auth';
import { createStatusSpan } from './dom';
import { showError } from './errorUi';
import { deleteAccountConfirmation, type Exit, soleOwnerMessage } from './exits';
import { deleteMyAccount } from './me';
import { listMyTenants } from './tenants';

function exitButton(label: string, danger = false): HTMLButtonElement {
  const button = document.createElement('button');
  button.type = 'button';
  button.textContent = label;
  if (danger) button.className = 'btn-danger';
  return button;
}

// The one place a failed exit becomes words: "you're the only owner" when it is
// that, whatever describeError makes of it otherwise.
function showExitError(
  status: HTMLElement,
  error: unknown,
  libraryNames: ReadonlyMap<string, string>,
  exit: Exit,
): void {
  const soleOwner = soleOwnerMessage(error, libraryNames, exit);
  if (soleOwner === null) showError(status, error);
  else status.textContent = soleOwner;
}

// For /profile, in a section of its own. On success the person is logged out
// through Authgear: their Lorenzo account is gone, and the Authgear login is
// not (deleteAccountConfirmation says so).
export function renderDeleteAccount(): HTMLElement {
  const container = document.createElement('div');
  const button = exitButton('Delete my account', true);
  const status = createStatusSpan();
  container.append(button, status);
  button.addEventListener('click', async () => {
    if (!window.confirm(deleteAccountConfirmation())) return;
    button.disabled = true;
    status.textContent = 'Deleting…';
    try {
      await deleteMyAccount();
    } catch (e) {
      button.disabled = false;
      // The 409 names a library by id; the names come from the libraries the
      // person belongs to, fetched only now that they are needed.
      const names = new Map<string, string>();
      try {
        for (const tenant of (await listMyTenants()).items) names.set(tenant.id, tenant.name);
      } catch {
        // Without names the message still says what to do.
      }
      showExitError(status, e, names, 'delete-account');
      return;
    }
    status.textContent = 'Your account is deleted. Logging you out…';
    await logout();
  });
  return container;
}
