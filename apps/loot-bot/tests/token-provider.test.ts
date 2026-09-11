import { http, HttpResponse } from "msw";
import { setupServer } from "msw/node";
import { afterAll, afterEach, beforeAll, beforeEach, describe, expect, it, vi } from "vitest";
import { resetAuthgearConfigurationForTests } from "../src/authgear-client.js";
import { loadConfig, resetConfigForTests } from "../src/config.js";
import { decrypt, encrypt } from "../src/crypto.js";

// Real Postgres is not needed to exercise the refresh/caching logic -
// db.ts is mocked wholesale; the token endpoint itself is mocked with MSW
// (a plain HTTP call, no PKCE/JWT mechanics to prove here - see
// tests/fake-authgear-server.ts for where that full treatment lives).
vi.mock("../src/db.js", () => ({
  getLinkedAccount: vi.fn(),
  updateAccessToken: vi.fn(),
  deleteLinkedAccount: vi.fn(),
}));

import type { LinkedAccount } from "../src/db.js";
import { deleteLinkedAccount, getLinkedAccount, updateAccessToken } from "../src/db.js";
import { getValidAccessToken } from "../src/token-provider.js";

const getLinkedAccountMock = vi.mocked(getLinkedAccount);
const updateAccessTokenMock = vi.mocked(updateAccessToken);
const deleteLinkedAccountMock = vi.mocked(deleteLinkedAccount);

const ISSUER = "http://authgear-test.local";

const validEnv = {
  DISCORD_BOT_TOKEN: "token",
  DISCORD_CLIENT_ID: "123",
  DISCORD_GUILD_ID: "456",
  LORENZO_API_BASE_URL: "http://localhost:8000",
  LORENZO_TENANT_ID: "3fa85f64-5717-4562-b3fc-2c963f66afa6",
  AUTHGEAR_ISSUER: ISSUER,
  AUTHGEAR_CLIENT_ID: "test-client",
  AUTHGEAR_CLIENT_SECRET: "test-secret",
  LOOT_BOT_DATABASE_URL: "postgres://loot_bot:loot_bot@localhost:55432/lorenzo",
  LOOT_BOT_MIGRATIONS_DATABASE_URL: "postgres://lorenzo:lorenzo@localhost:55432/lorenzo",
  LOOT_BOT_TOKEN_ENCRYPTION_KEY: Buffer.alloc(32, 9).toString("base64"),
};

const server = setupServer(
  http.get(`${ISSUER}/.well-known/openid-configuration`, () =>
    HttpResponse.json({
      issuer: ISSUER,
      authorization_endpoint: `${ISSUER}/oauth2/authorize`,
      token_endpoint: `${ISSUER}/oauth2/token`,
    }),
  ),
);

beforeAll(() => server.listen({ onUnhandledRequest: "error" }));
afterEach(() => server.resetHandlers());
afterAll(() => server.close());

beforeEach(() => {
  resetConfigForTests();
  resetAuthgearConfigurationForTests();
  loadConfig(validEnv);
  getLinkedAccountMock.mockReset();
  updateAccessTokenMock.mockReset();
  deleteLinkedAccountMock.mockReset();
});

function makeLinkedAccountRow(overrides: Partial<LinkedAccount> = {}): LinkedAccount {
  return {
    discordUserId: "user-1",
    authgearSubjectId: "subject-1",
    refreshTokenEncrypted: encrypt("stored-refresh-token"),
    accessTokenEncrypted: encrypt("stored-access-token"),
    accessTokenExpiresAt: new Date(Date.now() + 3600_000),
    keyVersion: 1,
    lastRefreshedAt: null,
    createdAt: new Date(),
    updatedAt: new Date(),
    ...overrides,
  };
}

describe("getValidAccessToken", () => {
  it("reuses a cached access token when it is not near expiry, without calling the token endpoint", async () => {
    getLinkedAccountMock.mockResolvedValue(
      makeLinkedAccountRow({
        accessTokenEncrypted: encrypt("cached-access-token"),
        accessTokenExpiresAt: new Date(Date.now() + 10 * 60_000),
      }),
    );

    // No /oauth2/token handler registered - onUnhandledRequest: "error"
    // means an unexpected refresh call would fail this test.
    const token = await getValidAccessToken("user-1");

    expect(token).toBe("cached-access-token");
    expect(updateAccessTokenMock).not.toHaveBeenCalled();
  });

  it("returns null when there is no linked account", async () => {
    getLinkedAccountMock.mockResolvedValue(undefined);

    const token = await getValidAccessToken("nobody");

    expect(token).toBeNull();
  });

  it("refreshes a near-expiry access token and stores the new refresh token when one is returned", async () => {
    getLinkedAccountMock.mockResolvedValue(
      makeLinkedAccountRow({
        accessTokenExpiresAt: new Date(Date.now() + 1_000), // inside the 60s safety margin
        refreshTokenEncrypted: encrypt("old-refresh-token"),
      }),
    );

    let receivedParams: URLSearchParams | undefined;
    server.use(
      http.post(`${ISSUER}/oauth2/token`, async ({ request }) => {
        receivedParams = new URLSearchParams(await request.text());
        return HttpResponse.json({
          access_token: "new-access-token",
          refresh_token: "new-refresh-token",
          token_type: "bearer",
          expires_in: 3600,
        });
      }),
    );

    const token = await getValidAccessToken("user-2");

    expect(token).toBe("new-access-token");
    expect(receivedParams?.get("grant_type")).toBe("refresh_token");
    expect(receivedParams?.get("refresh_token")).toBe("old-refresh-token");

    expect(updateAccessTokenMock).toHaveBeenCalledTimes(1);
    const call = updateAccessTokenMock.mock.calls[0];
    expect(call?.[0]).toBe("user-2");
    expect(call?.[1].accessTokenEncrypted ? decrypt(call[1].accessTokenEncrypted) : undefined).toBe(
      "new-access-token",
    );
    expect(call?.[1].refreshTokenEncrypted).toBeDefined();
    if (call?.[1].refreshTokenEncrypted) {
      expect(decrypt(call[1].refreshTokenEncrypted)).toBe("new-refresh-token");
    }
  });

  it("leaves the stored refresh token alone when the refresh response does not include a new one", async () => {
    getLinkedAccountMock.mockResolvedValue(
      makeLinkedAccountRow({
        accessTokenExpiresAt: new Date(Date.now() - 1_000), // already expired
        refreshTokenEncrypted: encrypt("stable-refresh-token"),
      }),
    );

    server.use(
      http.post(`${ISSUER}/oauth2/token`, () =>
        HttpResponse.json({
          access_token: "new-access-token-2",
          token_type: "bearer",
          expires_in: 3600,
          // deliberately no refresh_token in this response
        }),
      ),
    );

    const token = await getValidAccessToken("user-3");

    expect(token).toBe("new-access-token-2");
    expect(updateAccessTokenMock).toHaveBeenCalledTimes(1);
    const call = updateAccessTokenMock.mock.calls[0];
    expect(call?.[1].refreshTokenEncrypted).toBeUndefined();
  });

  it("deletes the linked account and returns null on an invalid_grant refresh failure", async () => {
    getLinkedAccountMock.mockResolvedValue(
      makeLinkedAccountRow({ accessTokenExpiresAt: new Date(Date.now() - 1_000) }),
    );

    server.use(
      http.post(`${ISSUER}/oauth2/token`, () =>
        HttpResponse.json(
          { error: "invalid_grant", error_description: "refresh token expired or revoked" },
          { status: 400 },
        ),
      ),
    );

    const token = await getValidAccessToken("user-4");

    expect(token).toBeNull();
    expect(deleteLinkedAccountMock).toHaveBeenCalledWith("user-4");
    expect(updateAccessTokenMock).not.toHaveBeenCalled();
  });

  it("propagates an unexpected refresh failure instead of silently returning null", async () => {
    getLinkedAccountMock.mockResolvedValue(
      makeLinkedAccountRow({ accessTokenExpiresAt: new Date(Date.now() - 1_000) }),
    );

    server.use(
      http.post(`${ISSUER}/oauth2/token`, () =>
        HttpResponse.json({ error: "server_error" }, { status: 500 }),
      ),
    );

    await expect(getValidAccessToken("user-6")).rejects.toBeTruthy();
    expect(deleteLinkedAccountMock).not.toHaveBeenCalled();
  });

  it("de-duplicates concurrent calls for the same user into a single refresh", async () => {
    getLinkedAccountMock.mockResolvedValue(
      makeLinkedAccountRow({ accessTokenExpiresAt: new Date(Date.now() - 1_000) }),
    );

    let tokenEndpointHits = 0;
    server.use(
      http.post(`${ISSUER}/oauth2/token`, async () => {
        tokenEndpointHits += 1;
        await new Promise((resolve) => setTimeout(resolve, 20));
        return HttpResponse.json({
          access_token: "concurrent-access-token",
          refresh_token: "concurrent-refresh-token",
          token_type: "bearer",
          expires_in: 3600,
        });
      }),
    );

    const [first, second] = await Promise.all([
      getValidAccessToken("user-5"),
      getValidAccessToken("user-5"),
    ]);

    expect(tokenEndpointHits).toBe(1);
    expect(first).toBe("concurrent-access-token");
    expect(second).toBe("concurrent-access-token");
    expect(getLinkedAccountMock).toHaveBeenCalledTimes(1);
  });
});
