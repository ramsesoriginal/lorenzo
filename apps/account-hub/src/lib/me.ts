import { apiFetch } from './api';
import type { MeOut } from './types';

// GET /me is the single source of "everything I am, everywhere" (its own
// docstring) - shared by the profile page and the tenants/campaigns page,
// so it lives on its own rather than inside profile.ts.
export async function getMe(): Promise<MeOut> {
  return apiFetch<MeOut>('/me');
}
