import { client, unwrap } from './api';
import { cached } from './cache';
import type { ManagedScopeOut, MeOut } from './types';

// GET /me is the single source of "everything I am, everywhere" (its own
// docstring) - shared by the profile page and the tenants/campaigns page,
// so it lives on its own rather than inside profile.ts.
export async function getMe(): Promise<MeOut> {
  return cached('me', async () => unwrap(await client.GET('/me')));
}

// What the caller runs, across every library: the ones they administer with all
// their campaigns, and the ones where they only GM, with just those campaigns
// (ADR 0086). /campaigns's "Where you run" is its first client (ADR 0179).
export async function getManaged(): Promise<ManagedScopeOut> {
  return cached('managed', async () => unwrap(await client.GET('/me/managed')));
}

// DELETE /me (ADR 0036): removes the caller's own app_user row, and with it
// every membership, player seat, GM grant and opt-out they hold. It leaves the
// Authgear login alone.
export async function deleteMyAccount(): Promise<void> {
  await unwrap(await client.DELETE('/me'));
}
