import { createHash, createSign, generateKeyPairSync, randomUUID } from "node:crypto";
import http from "node:http";

/**
 * A real, local, fake Authgear server for testing the account-linking flow
 * (ADR 0029) - mirrors apps/api/tests/_fake_jwks.py's own stated principle:
 * only the issuer is fake here, not the verification mechanism. Serves a
 * real discovery document and a real `/oauth2/token` endpoint that
 * genuinely validates the PKCE `code_verifier` and mints a real RS256
 * signed JWT (a throwaway, in-process RSA keypair) as the `id_token`. The
 * `access_token`/`refresh_token` are plain opaque strings - nothing in
 * loot-bot ever cryptographically verifies those two; only Authgear and
 * apps/api do, and this fixture stands in for Authgear specifically.
 *
 * loot-bot's own code never calls `/oauth2/authorize` itself (per ADR
 * 0029, `/link` only ever hands the Discord user a URL to click - see
 * src/commands/link.ts) - there is no production code path that would hit
 * a real authorize endpoint here. `issueAuthorizationCode` simulates the
 * one fact that step leaves behind that the rest of the flow actually
 * depends on: which `code_challenge` (and `redirect_uri`) a given
 * authorization `code` was issued under - a real browser round-trip would
 * add an unexercised HTTP hop, not additional test confidence.
 */

export type FakeAuthgearServer = Readonly<{
  /** This server's own issuer identifier - feed straight into AUTHGEAR_ISSUER. */
  issuer: string;
  /**
   * Registers the one authorize-time fact the token endpoint needs to
   * check later, and returns the authorization `code` a real Authgear
   * would have redirected back with.
   */
  issueAuthorizationCode: (params: PendingAuthorization) => string;
  close: () => Promise<void>;
}>;

type PendingAuthorization = Readonly<{
  codeChallenge: string;
  redirectUri: string;
  subject: string;
}>;

export async function startFakeAuthgearServer(): Promise<FakeAuthgearServer> {
  const { privateKey } = generateKeyPairSync("rsa", { modulusLength: 2048 });
  const pendingAuthorizations = new Map<string, PendingAuthorization>();

  let issuer = "";

  const server = http.createServer((req, res) => {
    void handleRequest(req, res);
  });

  async function handleRequest(req: http.IncomingMessage, res: http.ServerResponse): Promise<void> {
    const url = new URL(req.url ?? "/", issuer);

    if (req.method === "GET" && url.pathname === "/.well-known/openid-configuration") {
      sendJson(res, 200, {
        issuer,
        authorization_endpoint: `${issuer}/oauth2/authorize`,
        token_endpoint: `${issuer}/oauth2/token`,
      });
      return;
    }

    if (req.method === "POST" && url.pathname === "/oauth2/token") {
      const body = await readBody(req);
      handleTokenRequest(new URLSearchParams(body), res);
      return;
    }

    res.writeHead(404, { "content-type": "text/plain" }).end("Not found");
  }

  function handleTokenRequest(params: URLSearchParams, res: http.ServerResponse): void {
    const grantType = params.get("grant_type");
    if (grantType !== "authorization_code") {
      sendJson(res, 400, {
        error: "unsupported_grant_type",
        error_description: `the fake authgear server only implements authorization_code, got ${grantType}`,
      });
      return;
    }

    const code = params.get("code");
    const codeVerifier = params.get("code_verifier");
    const redirectUri = params.get("redirect_uri");
    const clientId = params.get("client_id");

    if (!code || !codeVerifier || !redirectUri || !clientId) {
      sendJson(res, 400, {
        error: "invalid_grant",
        error_description: "missing one or more required token request parameters",
      });
      return;
    }

    const pending = pendingAuthorizations.get(code);
    if (!pending) {
      sendJson(res, 400, {
        error: "invalid_grant",
        error_description: "unknown, expired, or already-used authorization code",
      });
      return;
    }
    // One-shot, like a real authorization code.
    pendingAuthorizations.delete(code);

    if (redirectUri !== pending.redirectUri) {
      sendJson(res, 400, { error: "invalid_grant", error_description: "redirect_uri mismatch" });
      return;
    }

    const computedChallenge = base64url(createHash("sha256").update(codeVerifier).digest());
    if (computedChallenge !== pending.codeChallenge) {
      sendJson(res, 400, {
        error: "invalid_grant",
        error_description: "PKCE code_verifier does not match the code_challenge",
      });
      return;
    }

    const now = Math.floor(Date.now() / 1000);
    const idToken = signIdToken(privateKey, {
      iss: issuer,
      aud: clientId,
      sub: pending.subject,
      iat: now,
      exp: now + 300,
    });

    sendJson(res, 200, {
      access_token: `fake-access-${randomUUID()}`,
      refresh_token: `fake-refresh-${randomUUID()}`,
      id_token: idToken,
      token_type: "bearer",
      expires_in: 3600,
    });
  }

  await new Promise<void>((resolve) => {
    server.listen(0, "127.0.0.1", resolve);
  });
  const address = server.address();
  if (address === null || typeof address === "string") throw new Error("expected an AddressInfo");
  issuer = `http://127.0.0.1:${address.port}`;

  return {
    issuer,
    issueAuthorizationCode(params) {
      const code = `fake-code-${randomUUID()}`;
      pendingAuthorizations.set(code, params);
      return code;
    },
    close: () =>
      new Promise((resolve, reject) => {
        server.close((err) => (err ? reject(err) : resolve()));
      }),
  };
}

function base64url(input: Buffer): string {
  return input.toString("base64").replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
}

function signIdToken(privateKey: import("node:crypto").KeyObject, claims: object): string {
  const header = base64url(Buffer.from(JSON.stringify({ alg: "RS256", typ: "JWT" })));
  const payload = base64url(Buffer.from(JSON.stringify(claims)));
  const signature = createSign("RSA-SHA256").update(`${header}.${payload}`).sign(privateKey);
  return `${header}.${payload}.${base64url(signature)}`;
}

function sendJson(res: http.ServerResponse, status: number, body: unknown): void {
  res.writeHead(status, { "content-type": "application/json" }).end(JSON.stringify(body));
}

async function readBody(req: http.IncomingMessage): Promise<string> {
  const chunks: Buffer[] = [];
  for await (const chunk of req) {
    chunks.push(chunk as Buffer);
  }
  return Buffer.concat(chunks).toString("utf8");
}
