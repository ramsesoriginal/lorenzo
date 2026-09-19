import { apiFetch } from './api';
import { ApiError } from './apiError';
import type { UserRefOut } from './types';

// Both lookups are exact-match, 404-on-miss (ADR 0055) - callers get null
// back for "not found" specifically, not a thrown ApiError, so a picker UI
// doesn't need to catch-and-inspect an error object for the expected,
// common case of a typo or a person who isn't a Lorenzo user yet.
async function lookupUser(path: string): Promise<UserRefOut | null> {
  try {
    return await apiFetch<UserRefOut>(path);
  } catch (e) {
    if (e instanceof ApiError && e.status === 404) return null;
    throw e;
  }
}

export async function findUserByEmail(email: string): Promise<UserRefOut | null> {
  return lookupUser(`/users/by-email/${encodeURIComponent(email)}`);
}

export async function findUserByNickname(nickname: string): Promise<UserRefOut | null> {
  return lookupUser(`/users/by-nickname/${encodeURIComponent(nickname)}`);
}
