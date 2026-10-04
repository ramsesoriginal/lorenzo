// The ways out of something of your own: leave a library, step down as a
// campaign's GM, delete your account (ADR 0170). Like userPicker.ts (ADR 0074),
// a lib/*.ts module that builds DOM. Each destructive action asks first with
// window.confirm, the pattern characters.astro uses for "Leave this campaign".

import { logout } from './auth';
import { createStatusSpan } from './dom';
import { showError } from './errorUi';
import {
  deleteAccountConfirmation,
  type Exit,
  leaveTenantConfirmation,
  soleOwnerMessage,
  stepDownConfirmation,
} from './exits';
import { deleteMyAccount } from './me';
import { kindNoun } from './tenantKind';
import { deleteMembership, listMyTenants, revokeCampaignGm } from './tenants';
import type { CampaignSummaryOut, TenantSummaryOut } from './types';

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

// Shown on every library or repository where the caller has a Membership (owner or orga):
// DELETE .../memberships/{me} is open to the member themselves, whatever their
// role. A person who only plays or GMs there has nothing to leave here; their
// way out is "Leave this campaign" on /characters. A repository says so in its
// own word (ADR 0178).
export function renderLeaveTenant(
  tenant: TenantSummaryOut,
  userId: string,
  onLeft: () => void,
): HTMLElement {
  const container = document.createElement('div');
  container.className = 'panel';
  const button = exitButton(`Leave this ${kindNoun(tenant.kind)}`);
  const status = createStatusSpan();
  container.append(button, status);
  button.addEventListener('click', async () => {
    if (!window.confirm(leaveTenantConfirmation(tenant.name, tenant.kind))) return;
    button.disabled = true;
    status.textContent = 'Leaving…';
    try {
      await deleteMembership(tenant.id, userId);
      onLeft();
    } catch (e) {
      button.disabled = false;
      showExitError(status, e, new Map([[tenant.id, tenant.name]]), 'leave-library');
    }
  });
  return container;
}

// Shown wherever the caller is a GM of the campaign, administrator or not:
// DELETE .../gms/{me} lets anyone remove their own grant (ADR 0034).
export function renderStepDownAsGm(
  tenant: TenantSummaryOut,
  campaign: CampaignSummaryOut,
  userId: string,
  onDone: () => void,
): HTMLElement {
  const container = document.createElement('div');
  container.className = 'panel';
  const button = exitButton('Step down as GM');
  const status = createStatusSpan();
  container.append(button, status);
  button.addEventListener('click', async () => {
    if (!window.confirm(stepDownConfirmation(campaign.name))) return;
    button.disabled = true;
    status.textContent = 'Stepping down…';
    try {
      await revokeCampaignGm(tenant.id, campaign.id, userId);
      onDone();
    } catch (e) {
      button.disabled = false;
      showError(status, e);
    }
  });
  return container;
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
