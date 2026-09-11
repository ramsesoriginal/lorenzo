import type { ServerResponse } from "node:http";
import type { Logger } from "pino";
import { exchangeAuthorizationCode, getAuthgearConfiguration } from "./authgear-client.js";
import type { Config } from "./config.js";
import { CURRENT_KEY_VERSION, encrypt } from "./crypto.js";
import { AuthgearSubjectAlreadyLinkedError, upsertLinkedAccount } from "./db.js";
import type { RouteHandler } from "./http-server.js";
import { consumePendingLink } from "./pending-links.js";

/**
 * `/auth/callback` - the redirect target Authgear sends the user's browser
 * back to after `/link` (ADR 0029). Builds a `RouteHandler` (not a bare
 * constant like `healthzRoute`) because, unlike `/healthz`, this route
 * needs `config`/`logger` - both closed over here rather than threaded
 * through `RouteHandler`'s own fixed signature.
 */
export function createAuthCallbackRoute(config: Config, logger: Logger): RouteHandler {
  return async (_req, res, url) => {
    const state = url.searchParams.get("state");
    if (!state) {
      sendHtml(
        res,
        400,
        "Link expired",
        "This link expired or was already used. Run /link again in Discord.",
      );
      return;
    }

    const pending = consumePendingLink(state);
    if (!pending) {
      sendHtml(
        res,
        400,
        "Link expired",
        "This link expired or was already used. Run /link again in Discord.",
      );
      return;
    }

    const authError = url.searchParams.get("error");
    if (authError) {
      logger.warn(
        { authError, discordUserId: pending.discordUserId },
        "authgear authorization request failed or was cancelled",
      );
      sendHtml(
        res,
        400,
        "Linking cancelled",
        "Linking was cancelled or failed. Run /link again in Discord to retry.",
      );
      return;
    }

    const code = url.searchParams.get("code");
    if (!code) {
      logger.warn(
        { discordUserId: pending.discordUserId },
        "auth callback had neither a code nor an error parameter",
      );
      sendHtml(
        res,
        400,
        "Link expired",
        "This link expired or was already used. Run /link again in Discord.",
      );
      return;
    }

    try {
      const oidcConfig = await getAuthgearConfiguration(config);

      // Only the query string (code/state) comes from the real incoming
      // request - the origin+path must match config.authCallbackUrl exactly
      // (what was sent as `redirect_uri` to /authorize), since Authgear
      // checks the token exchange's `redirect_uri` against it. `url`'s own
      // origin is a placeholder (http-server.ts parses req.url against
      // "http://localhost"), not this bot's real public base URL.
      const callbackUrl = new URL(config.authCallbackUrl);
      callbackUrl.search = url.search;

      const tokens = await exchangeAuthorizationCode(oidcConfig, {
        callbackUrl,
        state,
        codeVerifier: pending.codeVerifier,
      });

      if (tokens.refreshToken === undefined) {
        throw new Error(
          "Authgear did not return a refresh_token despite requesting the offline_access scope",
        );
      }

      await upsertLinkedAccount({
        discordUserId: pending.discordUserId,
        authgearSubjectId: tokens.subject,
        accessTokenEncrypted: encrypt(tokens.accessToken),
        refreshTokenEncrypted: encrypt(tokens.refreshToken),
        accessTokenExpiresAt: tokens.expiresAt,
        keyVersion: CURRENT_KEY_VERSION,
      });

      sendHtml(res, 200, "Linked", "Linked - you can close this tab.");
    } catch (error) {
      if (error instanceof AuthgearSubjectAlreadyLinkedError) {
        sendHtml(
          res,
          409,
          "Already linked",
          "This Lorenzo account is already linked to a different Discord user.",
        );
        return;
      }
      logger.error(
        { err: error, discordUserId: pending.discordUserId },
        "auth callback failed to complete account linking",
      );
      sendHtml(
        res,
        500,
        "Something went wrong",
        "Something went wrong linking your account. Run /link again in Discord to retry.",
      );
    }
  };
}

function sendHtml(res: ServerResponse, status: number, title: string, message: string): void {
  const body = `<!doctype html><html><head><meta charset="utf-8"><title>${title}</title></head><body><p>${message}</p></body></html>`;
  res.writeHead(status, { "content-type": "text/html; charset=utf-8" }).end(body);
}
