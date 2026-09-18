import authgear, { SessionState } from '@authgear/web';
import { AUTHGEAR_CLIENT_ID, AUTHGEAR_ENDPOINT } from './config';

const REDIRECT_PATH = '/auth/redirect';

let configured: Promise<void> | null = null;

// Authgear's container is a page-load-scoped singleton that restores session
// state from storage - every page using auth calls this first, memoized so
// a page importing this module more than once doesn't configure() twice.
function ensureConfigured(): Promise<void> {
  if (!AUTHGEAR_ENDPOINT || !AUTHGEAR_CLIENT_ID) {
    throw new Error(
      'Authgear is not configured - set PUBLIC_AUTHGEAR_ENDPOINT and PUBLIC_AUTHGEAR_CLIENT_ID.',
    );
  }
  if (!configured) {
    configured = authgear.configure({
      endpoint: AUTHGEAR_ENDPOINT,
      clientID: AUTHGEAR_CLIENT_ID,
      sessionType: 'refresh_token',
    });
  }
  return configured;
}

export function isAuthConfigured(): boolean {
  return Boolean(AUTHGEAR_ENDPOINT && AUTHGEAR_CLIENT_ID);
}

export async function login(): Promise<void> {
  await ensureConfigured();
  // No `prompt` - let Authgear silently continue an existing SSO session
  // rather than forcing re-authentication every time.
  await authgear.startAuthentication({
    redirectURI: `${window.location.origin}${REDIRECT_PATH}`,
  });
}

// Called from the /auth/redirect page once Authgear sends the browser back
// with an authorization code in the query string.
export async function completeLogin(): Promise<void> {
  await ensureConfigured();
  await authgear.finishAuthentication();
}

export async function logout(): Promise<void> {
  await ensureConfigured();
  await authgear.logout({ redirectURI: window.location.origin });
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

export async function getUserInfo() {
  await ensureConfigured();
  return authgear.fetchUserInfo();
}
