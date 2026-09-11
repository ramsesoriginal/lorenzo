import * as client from "openid-client";
import type { Config } from "./config.js";

type TokenEndpointResponse = client.TokenEndpointResponse & client.TokenEndpointResponseHelpers;

/**
 * Cached OIDC discovery result (server metadata + client credentials) -
 * fetched once and reused, mirroring get_dev_token.py's own single
 * `_fetch_endpoints` call and apps/api's `get_jwks_client()` `@lru_cache`
 * pattern (dependencies.py). `inFlight` collapses concurrent first callers
 * (e.g. two near-simultaneous `/link` invocations before the first
 * discovery call has resolved) onto the same request instead of firing one
 * each.
 */
let cached: client.Configuration | undefined;
let inFlight: Promise<client.Configuration> | undefined;

export async function getAuthgearConfiguration(config: Config): Promise<client.Configuration> {
  if (cached) return cached;
  if (!inFlight) {
    inFlight = discover(config).then(
      (result) => {
        cached = result;
        inFlight = undefined;
        return result;
      },
      (error: unknown) => {
        inFlight = undefined;
        throw error;
      },
    );
  }
  return inFlight;
}

async function discover(config: Config): Promise<client.Configuration> {
  const issuer = new URL(config.authgearIssuer);
  // Real Authgear issuers are always https; only a local/test issuer (see
  // tests/fake-authgear-server.ts) is plain http. Gating on the issuer's
  // own protocol - rather than e.g. NODE_ENV - means this can never
  // accidentally weaken a real deployment.
  const options: Parameters<typeof client.discovery>[4] =
    issuer.protocol === "http:" ? { execute: [client.allowInsecureRequests] } : undefined;
  return client.discovery(
    issuer,
    config.authgearClientId,
    config.authgearClientSecret,
    undefined,
    options,
  );
}

export function resetAuthgearConfigurationForTests(): void {
  cached = undefined;
  inFlight = undefined;
}

export type PkcePair = Readonly<{ verifier: string; challenge: string }>;

/** A fresh PKCE verifier/challenge pair - unique per `/link` invocation. */
export async function createPkcePair(): Promise<PkcePair> {
  const verifier = client.randomPKCECodeVerifier();
  const challenge = await client.calculatePKCECodeChallenge(verifier);
  return { verifier, challenge };
}

/** A fresh, random CSRF `state` value - unique per `/link` invocation. */
export function createState(): string {
  return client.randomState();
}

/**
 * The Authgear authorization URL to send a Discord user to for `/link`.
 * Scope includes `offline_access` so the eventual code exchange also
 * returns a refresh token (ADR 0029, confirmed against Authgear's docs).
 */
export function buildAuthorizationUrl(
  oidcConfig: client.Configuration,
  config: Config,
  params: Readonly<{ state: string; codeChallenge: string }>,
): URL {
  return client.buildAuthorizationUrl(oidcConfig, {
    redirect_uri: config.authCallbackUrl,
    scope: "openid offline_access",
    state: params.state,
    code_challenge: params.codeChallenge,
    code_challenge_method: "S256",
  });
}

export type TokenResult = Readonly<{
  accessToken: string;
  refreshToken: string | undefined;
  expiresAt: Date;
  subject: string;
}>;

/**
 * Exchanges an authorization code for tokens. `callbackUrl` must carry the
 * same origin+path as the `redirect_uri` sent to `/authorize`
 * (`config.authCallbackUrl`) - only its query string (code/state/error)
 * should come from the actual incoming request - since Authgear checks the
 * token exchange's `redirect_uri` matches exactly what was authorized.
 *
 * The returned id_token's signature is deliberately never verified (see
 * ADR 0029): it arrives over this direct, server-to-server HTTPS response
 * from Authgear's own token endpoint, not through the user's browser, so
 * there's no one positioned to forge it on this leg. openid-client itself
 * reflects that same reasoning - it only decodes and checks the id_token's
 * claims (iss/aud/exp/sub), never fetching JWKS for this call.
 */
export async function exchangeAuthorizationCode(
  oidcConfig: client.Configuration,
  params: Readonly<{ callbackUrl: URL; state: string; codeVerifier: string }>,
): Promise<TokenResult> {
  const response = await client.authorizationCodeGrant(oidcConfig, params.callbackUrl, {
    pkceCodeVerifier: params.codeVerifier,
    expectedState: params.state,
    idTokenExpected: true,
  });
  const claims = response.claims();
  if (!claims) {
    throw new Error("Authgear token response did not include an id_token");
  }
  return {
    accessToken: response.access_token,
    refreshToken: response.refresh_token,
    expiresAt: computeExpiresAt(response),
    subject: claims.sub,
  };
}

export type RefreshResult = Readonly<{
  accessToken: string;
  refreshToken: string | undefined;
  expiresAt: Date;
}>;

/**
 * Exchanges a refresh token for a fresh access token. Whether Authgear
 * rotates the refresh token on use is genuinely undocumented (ADR 0029) -
 * callers must check `refreshToken` for a new value themselves rather than
 * assume either behavior.
 */
export async function refreshAccessToken(
  oidcConfig: client.Configuration,
  refreshToken: string,
): Promise<RefreshResult> {
  const response = await client.refreshTokenGrant(oidcConfig, refreshToken);
  return {
    accessToken: response.access_token,
    refreshToken: response.refresh_token,
    expiresAt: computeExpiresAt(response),
  };
}

function computeExpiresAt(response: TokenEndpointResponse): Date {
  const expiresIn = response.expiresIn();
  if (expiresIn === undefined) {
    throw new Error("Authgear token response did not include expires_in");
  }
  return new Date(Date.now() + expiresIn * 1000);
}

/** True if `error` is Authgear rejecting a refresh token (expired/revoked/reused). */
export function isInvalidGrantError(error: unknown): boolean {
  return error instanceof client.ResponseBodyError && error.error === "invalid_grant";
}
