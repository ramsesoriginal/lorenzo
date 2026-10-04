import { client, unwrap } from './api';
import type { MeOut } from './types';

// GET /me is the single source of "everything I am, everywhere" (its own
// docstring) - shared by the profile page and the tenants/campaigns page,
// so it lives on its own rather than inside profile.ts.
export async function getMe(): Promise<MeOut> {
  return unwrap(await client.GET('/me'));
}

// DELETE /me (ADR 0036): removes the caller's own app_user row, and with it
// every membership, player seat, GM grant and opt-out they hold. It leaves the
// Authgear login alone.
export async function deleteMyAccount(): Promise<void> {
  await unwrap(await client.DELETE('/me'));
}
