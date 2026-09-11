import {
  getAuthgearConfiguration,
  isInvalidGrantError,
  refreshAccessToken,
} from "./authgear-client.js";
import { loadConfig } from "./config.js";
import { CURRENT_KEY_VERSION, decrypt, encrypt } from "./crypto.js";
import { deleteLinkedAccount, getLinkedAccount, updateAccessToken } from "./db.js";

// A cached access token is reused as long as it has at least this much
// life left; otherwise it's refreshed proactively rather than risking a
// Lorenzo API call racing against the token expiring mid-flight.
const EXPIRY_SAFETY_MARGIN_MS = 60_000;

// Single-flight de-duplication (ADR 0029): two concurrent commands for the
// same Discord user (e.g. two /inventory invocations) share one in-flight
// lookup-or-refresh instead of racing separate refresh grants against the
// same stored refresh token.
const inFlight = new Map<string, Promise<string | null>>();

/**
 * Resolves a usable Lorenzo API access token for `discordUserId`, refreshing
 * it via Authgear if necessary - the seam `src/commands/inventory.ts` (a
 * separate workstream) calls into. Returns `null` when there's no linked
 * account, or the link is no longer valid (Authgear rejected the refresh
 * token) - either way, telling the user to run `/link` is the caller's job,
 * not this function's (see ADR 0029).
 */
export function getValidAccessToken(discordUserId: string): Promise<string | null> {
  const existing = inFlight.get(discordUserId);
  if (existing) return existing;

  const result = resolveAccessToken(discordUserId).finally(() => {
    inFlight.delete(discordUserId);
  });
  inFlight.set(discordUserId, result);
  return result;
}

async function resolveAccessToken(discordUserId: string): Promise<string | null> {
  const account = await getLinkedAccount(discordUserId);
  if (!account) return null;

  // Both columns are nullable in the schema (a row could in principle
  // exist with no access token cached yet) - only take the fast path when
  // there is actually a cached token with a known expiry.
  if (account.accessTokenEncrypted && account.accessTokenExpiresAt) {
    const remainingMs = account.accessTokenExpiresAt.getTime() - Date.now();
    if (remainingMs > EXPIRY_SAFETY_MARGIN_MS) {
      return decrypt(account.accessTokenEncrypted);
    }
  }

  const config = loadConfig();
  const oidcConfig = await getAuthgearConfiguration(config);
  const refreshToken = decrypt(account.refreshTokenEncrypted);

  try {
    const tokens = await refreshAccessToken(oidcConfig, refreshToken);

    // Authgear's refresh-token rotation behavior is undocumented (ADR
    // 0029) - only overwrite the stored refresh token when the response
    // actually included a new one, which is correct whether or not
    // Authgear rotates it on use.
    await updateAccessToken(discordUserId, {
      accessTokenEncrypted: encrypt(tokens.accessToken),
      accessTokenExpiresAt: tokens.expiresAt,
      keyVersion: CURRENT_KEY_VERSION,
      ...(tokens.refreshToken !== undefined
        ? { refreshTokenEncrypted: encrypt(tokens.refreshToken) }
        : {}),
    });

    return tokens.accessToken;
  } catch (error) {
    if (isInvalidGrantError(error)) {
      await deleteLinkedAccount(discordUserId);
      return null;
    }
    throw error;
  }
}
