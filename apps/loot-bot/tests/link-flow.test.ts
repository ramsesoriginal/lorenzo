import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { createAuthCallbackRoute } from "../src/auth-callback-route.js";
import {
  createPkcePair,
  createState,
  resetAuthgearConfigurationForTests,
} from "../src/authgear-client.js";
import { type Config, loadConfig, resetConfigForTests } from "../src/config.js";
import { AuthgearSubjectAlreadyLinkedError, upsertLinkedAccount } from "../src/db.js";
import { type HttpServer, type RouteHandler, createHttpServer } from "../src/http-server.js";
import { logger } from "../src/logger.js";
import { clearPendingLinksForTests, storePendingLink } from "../src/pending-links.js";
import { type FakeAuthgearServer, startFakeAuthgearServer } from "./fake-authgear-server.js";

// db.ts talks to a real Postgres - none of that is needed to exercise the
// linking flow itself, so it's mocked wholesale here. AuthgearSubjectAlreadyLinkedError
// is re-declared with the same shape so `error instanceof` checks inside
// auth-callback-route.ts still work against instances built in this file.
vi.mock("../src/db.js", () => ({
  upsertLinkedAccount: vi.fn(),
  AuthgearSubjectAlreadyLinkedError: class AuthgearSubjectAlreadyLinkedError extends Error {
    constructor(public readonly authgearSubjectId: string) {
      super(`duplicate authgear_subject_id: ${authgearSubjectId}`);
      this.name = "AuthgearSubjectAlreadyLinkedError";
    }
  },
}));

const upsertLinkedAccountMock = vi.mocked(upsertLinkedAccount);

const validEnv = {
  DISCORD_BOT_TOKEN: "token",
  DISCORD_CLIENT_ID: "123",
  DISCORD_GUILD_ID: "456",
  LORENZO_API_BASE_URL: "http://localhost:8000",
  LORENZO_TENANT_ID: "3fa85f64-5717-4562-b3fc-2c963f66afa6",
  AUTHGEAR_CLIENT_ID: "loot-bot-test-client",
  AUTHGEAR_CLIENT_SECRET: "loot-bot-test-secret",
  LOOT_BOT_DATABASE_URL: "postgres://loot_bot:loot_bot@localhost:55432/lorenzo",
  LOOT_BOT_MIGRATIONS_DATABASE_URL: "postgres://lorenzo:lorenzo@localhost:55432/lorenzo",
  LOOT_BOT_TOKEN_ENCRYPTION_KEY: Buffer.alloc(32, 7).toString("base64"),
};

describe("/auth/callback link flow", () => {
  let fakeAuthgear: FakeAuthgearServer;
  let callbackServer: HttpServer;
  let baseUrl: string;
  let config: Config;

  beforeEach(async () => {
    resetConfigForTests();
    resetAuthgearConfigurationForTests();
    clearPendingLinksForTests();
    upsertLinkedAccountMock.mockReset();

    fakeAuthgear = await startFakeAuthgearServer();

    // The route needs `config` (for authCallbackUrl) which in turn needs
    // this server's own assigned port - chicken-and-egg, since routes are
    // supplied to createHttpServer before .listen() assigns a port. Solved
    // by registering an indirection now and pointing it at the real route
    // once `config` is known.
    let handleCallback: RouteHandler = (_req, res) => {
      res.writeHead(500).end("route not configured yet");
    };
    callbackServer = createHttpServer(
      new Map([["/auth/callback", (req, res, url) => handleCallback(req, res, url)]]),
      { port: 0, logger },
    );
    await callbackServer.listen();
    const address = callbackServer.server.address();
    if (address === null || typeof address === "string") throw new Error("expected an AddressInfo");
    baseUrl = `http://127.0.0.1:${address.port}`;

    config = loadConfig({
      ...validEnv,
      AUTHGEAR_ISSUER: fakeAuthgear.issuer,
      LOOT_BOT_PUBLIC_BASE_URL: baseUrl,
    });

    handleCallback = createAuthCallbackRoute(config, logger);
  });

  afterEach(async () => {
    await callbackServer.close();
    await fakeAuthgear.close();
  });

  /**
   * Drives the "start a /link flow" half without a Discord interaction:
   * generates real state+PKCE, stores the pending entry exactly like
   * src/commands/link.ts would, and registers the resulting challenge with
   * the fake Authgear server under a fresh authorization code - standing in
   * for the user's browser round-trip through Authgear's real login UI,
   * which has no interesting logic of this app's own to exercise (see
   * fake-authgear-server.ts's own doc comment).
   */
  async function setUpPendingLink(discordUserId: string, subject: string): Promise<string> {
    const state = createState();
    const pkce = await createPkcePair();
    storePendingLink(state, { discordUserId, codeVerifier: pkce.verifier });
    const code = fakeAuthgear.issueAuthorizationCode({
      codeChallenge: pkce.challenge,
      redirectUri: config.authCallbackUrl,
      subject,
    });
    const url = new URL(`${baseUrl}/auth/callback`);
    url.searchParams.set("code", code);
    url.searchParams.set("state", state);
    return url.toString();
  }

  it("exchanges the code for tokens and links the account on success", async () => {
    upsertLinkedAccountMock.mockResolvedValueOnce(undefined);
    const callbackUrl = await setUpPendingLink("discord-user-1", "authgear-subject-1");

    const response = await fetch(callbackUrl);
    const body = await response.text();

    expect(response.status).toBe(200);
    expect(body).toContain("Linked");

    expect(upsertLinkedAccountMock).toHaveBeenCalledTimes(1);
    const row = upsertLinkedAccountMock.mock.calls[0]?.[0];
    expect(row?.discordUserId).toBe("discord-user-1");
    expect(row?.authgearSubjectId).toBe("authgear-subject-1");
    expect(row?.keyVersion).toBe(1);
    expect(row?.accessTokenEncrypted).toBeInstanceOf(Buffer);
    expect(row?.refreshTokenEncrypted).toBeInstanceOf(Buffer);
    expect(row?.accessTokenExpiresAt).toBeInstanceOf(Date);
    expect(row?.accessTokenExpiresAt?.getTime()).toBeGreaterThan(Date.now());
  });

  it("shows an expired-link page when state is unknown, and does not touch the db", async () => {
    const response = await fetch(`${baseUrl}/auth/callback?code=whatever&state=unknown-state`);
    const body = await response.text();

    expect(response.status).toBe(400);
    expect(body).toContain("expired");
    expect(upsertLinkedAccountMock).not.toHaveBeenCalled();
  });

  it("shows an expired-link page when state is missing entirely", async () => {
    const response = await fetch(`${baseUrl}/auth/callback?code=whatever`);
    expect(response.status).toBe(400);
    expect(await response.text()).toContain("expired");
  });

  it("shows an expired-link page when the callback has a valid state but neither code nor error", async () => {
    const state = createState();
    const pkce = await createPkcePair();
    storePendingLink(state, {
      discordUserId: "discord-user-malformed",
      codeVerifier: pkce.verifier,
    });

    const response = await fetch(`${baseUrl}/auth/callback?state=${encodeURIComponent(state)}`);

    expect(response.status).toBe(400);
    expect(await response.text()).toContain("expired");
    expect(upsertLinkedAccountMock).not.toHaveBeenCalled();
  });

  it("consumes the pending entry so the same callback URL cannot be replayed", async () => {
    upsertLinkedAccountMock.mockResolvedValueOnce(undefined);
    const callbackUrl = await setUpPendingLink("discord-user-replay", "authgear-subject-replay");

    const first = await fetch(callbackUrl);
    expect(first.status).toBe(200);

    const second = await fetch(callbackUrl);
    expect(second.status).toBe(400);
    expect(await second.text()).toContain("expired");
    expect(upsertLinkedAccountMock).toHaveBeenCalledTimes(1);
  });

  it("shows a cancelled page when Authgear reports an error, and does not touch the db", async () => {
    const state = createState();
    const pkce = await createPkcePair();
    storePendingLink(state, { discordUserId: "discord-user-2", codeVerifier: pkce.verifier });

    const url = new URL(`${baseUrl}/auth/callback`);
    url.searchParams.set("error", "access_denied");
    url.searchParams.set("state", state);

    const response = await fetch(url.toString());
    const body = await response.text();

    expect(response.status).toBe(400);
    expect(body).toContain("cancelled");
    expect(upsertLinkedAccountMock).not.toHaveBeenCalled();
  });

  it("shows an already-linked page when db.ts reports a duplicate authgear subject", async () => {
    upsertLinkedAccountMock.mockRejectedValueOnce(
      new AuthgearSubjectAlreadyLinkedError("shared-subject"),
    );
    const callbackUrl = await setUpPendingLink("discord-user-3", "shared-subject");

    const response = await fetch(callbackUrl);
    const body = await response.text();

    expect(response.status).toBe(409);
    expect(body).toContain("already linked");
  });

  it("shows a generic failure page when the code exchange itself fails (wrong PKCE verifier)", async () => {
    // Simulates a tampered/mismatched pending entry: the fake server was
    // told about a different challenge than the one actually stored, so
    // its real PKCE check fails server-side.
    const state = createState();
    const pkce = await createPkcePair();
    const otherPkce = await createPkcePair();
    storePendingLink(state, { discordUserId: "discord-user-4", codeVerifier: pkce.verifier });
    const code = fakeAuthgear.issueAuthorizationCode({
      codeChallenge: otherPkce.challenge,
      redirectUri: config.authCallbackUrl,
      subject: "authgear-subject-4",
    });

    const url = new URL(`${baseUrl}/auth/callback`);
    url.searchParams.set("code", code);
    url.searchParams.set("state", state);

    const response = await fetch(url.toString());

    expect(response.status).toBe(500);
    expect(await response.text()).toContain("Something went wrong");
    expect(upsertLinkedAccountMock).not.toHaveBeenCalled();
  });
});
