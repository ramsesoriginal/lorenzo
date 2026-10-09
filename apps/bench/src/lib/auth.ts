import authgear, { SessionState } from '@authgear/web';
import { AUTHGEAR_CLIENT_ID, AUTHGEAR_ENDPOINT } from './config';

// Trailing slash on purpose: Cloudflare Pages redirects an extensionless path to its slash form,
// and finishAuthentication() rebuilds the token exchange's redirect_uri from window.location, so
// the registered Authorized Redirect URI must be the slash form too (same as inventory-web).
const REDIRECT_PATH = '/auth/redirect/';

let configured: Promise<void> | null = null;

function ensureConfigured(): Promise<void> {
  if (!AUTHGEAR_ENDPOINT || !AUTHGEAR_CLIENT_ID) {
    throw new Error(
      'Authgear is not configured - set PUBLIC_AUTHGEAR_ENDPOINT and PUBLIC_AUTHGEAR_CLIENT_ID.',
    );
  }
  configured ??= authgear.configure({
    endpoint: AUTHGEAR_ENDPOINT,
    clientID: AUTHGEAR_CLIENT_ID,
    sessionType: 'refresh_token',
  });
  return configured;
}

export function isAuthConfigured(): boolean {
  return Boolean(AUTHGEAR_ENDPOINT && AUTHGEAR_CLIENT_ID);
}

export async function login(): Promise<void> {
  await ensureConfigured();
  await authgear.startAuthentication({ redirectURI: `${window.location.origin}${REDIRECT_PATH}` });
}

/** From the redirect page, once Authgear has sent the browser back with a code. */
export async function completeLogin(): Promise<void> {
  await ensureConfigured();
  await authgear.finishAuthentication();
}

/**
 * Ends the session and goes home. What Bench keeps on the device for this person is forgotten by
 * the caller first (`onSignOut` in shell/session.ts): the next person's session starts empty.
 */
export async function logout(): Promise<void> {
  await ensureConfigured();
  await authgear.logout({ redirectURI: window.location.origin, force: true });
  window.location.assign('/');
}

export async function isAuthenticated(): Promise<boolean> {
  await ensureConfigured();
  return authgear.sessionState === SessionState.Authenticated;
}

export async function getAccessToken(): Promise<string | undefined> {
  await ensureConfigured();
  await authgear.refreshAccessTokenIfNeeded();
  return authgear.accessToken;
}
