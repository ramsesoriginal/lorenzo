// The tests' own way into the API (ADR 0114): typed calls as a given person, holding a token
// the fake Authgear minted for them, over the shared client package (ADR 0122).
import { createLorenzoClient, type LorenzoClient } from '@lorenzo/api-client';
import { API_URL, AUTHGEAR_URL } from './env.ts';

export type Api = LorenzoClient;

/** Registers `subject` with the fake Authgear, and returns an API client acting as them. */
export async function apiAs(subject: string, roles: string[] = []): Promise<Api> {
  const response = await fetch(`${AUTHGEAR_URL}/e2e/accounts`, {
    method: 'POST',
    body: JSON.stringify({ subject, roles }),
  });
  const { access_token } = (await response.json()) as { access_token: string };
  return createLorenzoClient({ baseUrl: API_URL, getAccessToken: () => access_token });
}

/** A call's data; a failed call throws with the API's problem, so a broken seed says why. */
export async function ok<T>(
  call: Promise<{ data?: T; error?: unknown; response: Response }>,
): Promise<T> {
  const { data, error, response } = await call;
  if (error !== undefined || !response.ok) {
    throw new Error(`${response.url} answered ${response.status}: ${JSON.stringify(error)}`);
  }
  return data as T;
}

/** A refresh token for `subject` from the fake Authgear, for a browser to start out signed in. */
export async function refreshTokenFor(subject: string): Promise<string> {
  const response = await fetch(`${AUTHGEAR_URL}/e2e/sessions`, {
    method: 'POST',
    body: JSON.stringify({ subject }),
  });
  const { refresh_token } = (await response.json()) as { refresh_token: string };
  return refresh_token;
}
