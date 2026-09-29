import { client, unwrap } from './api';
import { ApiError } from './apiError';
import type { UserRefOut } from './types';

// Only an exact-match miss is an empty result; other failures remain visible.
async function lookupUser(request: () => Promise<UserRefOut>): Promise<UserRefOut | null> {
  try {
    return await request();
  } catch (error) {
    if (error instanceof ApiError && error.status === 404) return null;
    throw error;
  }
}
export function findUserByEmail(email: string): Promise<UserRefOut | null> {
  return lookupUser(async () =>
    unwrap(await client.GET('/users/by-email/{email}', { params: { path: { email } } })),
  );
}
export function findUserByNickname(nickname: string): Promise<UserRefOut | null> {
  return lookupUser(async () =>
    unwrap(await client.GET('/users/by-nickname/{nickname}', { params: { path: { nickname } } })),
  );
}
