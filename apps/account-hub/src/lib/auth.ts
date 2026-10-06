import authgear, { Page, SessionState } from '@authgear/web';
import { clearCache } from './cache';
import { AUTHGEAR_CLIENT_ID, AUTHGEAR_ENDPOINT } from './config';
import { browserSessionStorage, rememberReturnPath } from './returnPath';

// Trailing slash is deliberate, not cosmetic: Cloudflare Pages 308-redirects
// any extensionless path to add one (confirmed - this happens regardless of
// whether the deploy has a `foo/index.html` directory or a flat `foo.html`
// file; it's a fixed platform behavior, not derived from build output
// shape). If this app requested the no-slash form, the browser would still
// end up at the slash form before this page's JS ever runs, and
// @authgear/web's finishAuthentication() reconstructs the token exchange's
// redirect_uri from that (now slash-suffixed) window.location - which then
// no longer exact-matches a no-slash Authorized Redirect URI. Requesting
// the slash form ourselves from the start keeps every step consistent.
const REDIRECT_PATH = '/auth/redirect/';

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
  // Back to this page afterwards, not always home (ADR 0170): a person whose
  // session expired mid-task lands where they were.
  rememberReturnPath(
    browserSessionStorage(),
    `${window.location.pathname}${window.location.search}`,
  );
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
  // A new session, perhaps a different person: nothing held from before is theirs.
  clearCache();
}

// A refresh-token session is revoked and cleared, but the SDK doesn't
// redirect afterwards: it insists on a redirectURI and then ignores it. A
// page that just logged out would go on showing the signed-in view, so this
// goes home itself. `force` clears the session even if revoking it fails.
export async function logout(): Promise<void> {
  await ensureConfigured();
  clearCache();
  await authgear.logout({ redirectURI: window.location.origin, force: true });
  window.location.assign('/');
}

// Authgear's own page for the login itself - email, password, sign-in methods - which nothing in
// the Lorenzo API can change. It opens in a new tab and needs a signed-in session. Lorenzo's copy
// of the email follows the next time someone logs in (ADR 0054).
export async function openLoginSettings(): Promise<void> {
  await ensureConfigured();
  await authgear.open(Page.Settings);
}

export async function isAuthenticated(): Promise<boolean> {
  await ensureConfigured();

  const signedIn = authgear.sessionState === SessionState.Authenticated;

  // A session that has ended (expired, or ended in another tab) leaves nothing behind to show.
  if (!signedIn) clearCache();

  return signedIn;
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
