// A fake Authgear for the end-to-end tests (ADR 0114), run by Playwright's webServer. Only
// the issuer is fake, as in apps/api/tests/_fake_jwks.py: tokens are RS256 JWTs the real API
// verifies against this server's JWKS, and the site's unmodified @authgear/web SDK runs its
// PKCE flow against it. There's no login form: /oauth2/authorize signs in whichever subject
// the test named in the SUBJECT_COOKIE cookie.
import { createHash, generateKeyPairSync, randomBytes, sign, verify } from 'node:crypto';
import http from 'node:http';
import { AUTHGEAR_URL, SITE_URL, SUBJECT_COOKIE } from './env.ts';

type Account = { email: string; roles: string[] };

const ROLES_CLAIM = 'https://authgear.com/claims/user/roles';
const SITE_ORIGIN = new URL(SITE_URL).origin;
// A new key id per run: the API caches keys by id, so a restarted fake must not reuse one.
const KID = `e2e-${randomBytes(4).toString('hex')}`;
const { privateKey, publicKey } = generateKeyPairSync('rsa', { modulusLength: 2048 });
const jwks = {
  keys: [{ ...publicKey.export({ format: 'jwk' }), kid: KID, use: 'sig', alg: 'RS256' }],
};

const accounts = new Map<string, Account>();
const codes = new Map<string, { subject: string; challenge: string; redirectUri: string }>();
const refreshTokens = new Map<string, string>();

const opaque = () => randomBytes(24).toString('base64url');
const encode = (value: unknown) => Buffer.from(JSON.stringify(value)).toString('base64url');

function jwt(claims: Record<string, unknown>): string {
  const signed = `${encode({ alg: 'RS256', typ: 'JWT', kid: KID })}.${encode(claims)}`;
  return `${signed}.${sign('sha256', Buffer.from(signed), privateKey).toString('base64url')}`;
}

/** The claims of a token this server signed, or null. */
function claimsOf(token: string): Record<string, unknown> | null {
  const [header, body, signature] = token.split('.');
  if (!header || !body || !signature) return null;
  const valid = verify(
    'sha256',
    Buffer.from(`${header}.${body}`),
    publicKey,
    Buffer.from(signature, 'base64url'),
  );
  return valid ? JSON.parse(Buffer.from(body, 'base64url').toString()) : null;
}

function account(subject: string): Account {
  return accounts.get(subject) ?? { email: `${subject}@e2e.test`, roles: [] };
}

function accessToken(subject: string): string {
  const now = Math.floor(Date.now() / 1000);
  const { email, roles } = account(subject);
  return jwt({
    iss: AUTHGEAR_URL,
    aud: AUTHGEAR_URL,
    sub: subject,
    iat: now,
    exp: now + 3600,
    email,
    email_verified: true,
    [ROLES_CLAIM]: roles,
  });
}

function tokenResponse(subject: string, refreshToken = opaque()) {
  refreshTokens.set(refreshToken, subject);
  const now = Math.floor(Date.now() / 1000);
  return {
    token_type: 'Bearer',
    access_token: accessToken(subject),
    expires_in: 3600,
    refresh_token: refreshToken,
    id_token: jwt({
      iss: AUTHGEAR_URL,
      aud: AUTHGEAR_URL,
      sub: subject,
      iat: now,
      exp: now + 3600,
    }),
  };
}

type Reply = { status: number; body?: unknown; location?: string };

const invalidGrant: Reply = { status: 400, body: { error: 'invalid_grant' } };

function token(form: URLSearchParams): Reply {
  if (form.get('grant_type') === 'refresh_token') {
    const refreshToken = form.get('refresh_token') ?? '';
    const subject = refreshTokens.get(refreshToken);
    return subject ? { status: 200, body: tokenResponse(subject, refreshToken) } : invalidGrant;
  }
  if (form.get('grant_type') !== 'authorization_code') {
    return { status: 400, body: { error: 'unsupported_grant_type' } };
  }
  const code = form.get('code') ?? '';
  const pending = codes.get(code);
  codes.delete(code);
  const challenge = createHash('sha256')
    .update(form.get('code_verifier') ?? '')
    .digest('base64url');
  if (!pending || pending.redirectUri !== form.get('redirect_uri')) return invalidGrant;
  if (pending.challenge !== challenge) return invalidGrant;
  return { status: 200, body: tokenResponse(pending.subject) };
}

/**
 * A redirect target on the site, rebuilt from the site's own origin, or null. Like a real
 * provider with one registered client, this one sends browsers back to that client only.
 */
function onSite(target: string | null): URL | null {
  if (!URL.canParse(target ?? '')) return null;
  const parsed = new URL(target as string);
  return parsed.origin === SITE_ORIGIN ? new URL(`${SITE_ORIGIN}${parsed.pathname}`) : null;
}

function authorize(url: URL, cookies: string): Reply {
  const subject = new URLSearchParams(cookies.replaceAll('; ', '&')).get(SUBJECT_COOKIE);
  const redirectUri = url.searchParams.get('redirect_uri');
  const back = onSite(redirectUri);
  if (!subject || !redirectUri || !back) {
    return {
      status: 400,
      body: { error: `name a subject in the ${SUBJECT_COOKIE} cookie, and return to the site` },
    };
  }
  const code = opaque();
  codes.set(code, {
    subject,
    challenge: url.searchParams.get('code_challenge') ?? '',
    redirectUri,
  });
  back.searchParams.set('code', code);
  const state = url.searchParams.get('state');
  if (state) back.searchParams.set('state', state);
  return { status: 302, location: back.href };
}

function userinfo(authorization: string): Reply {
  const claims = claimsOf(authorization.replace(/^Bearer /, ''));
  if (!claims) return { status: 401, body: { error: 'invalid_token' } };
  const subject = String(claims.sub);
  return {
    status: 200,
    body: { sub: subject, email: account(subject).email, email_verified: true },
  };
}

async function route(req: http.IncomingMessage, url: URL, body: string): Promise<Reply> {
  const path = `${req.method} ${url.pathname}`;
  switch (path) {
    case 'GET /.well-known/openid-configuration':
      return {
        status: 200,
        body: {
          issuer: AUTHGEAR_URL,
          authorization_endpoint: `${AUTHGEAR_URL}/oauth2/authorize`,
          token_endpoint: `${AUTHGEAR_URL}/oauth2/token`,
          userinfo_endpoint: `${AUTHGEAR_URL}/oauth2/userinfo`,
          revocation_endpoint: `${AUTHGEAR_URL}/oauth2/revoke`,
          end_session_endpoint: `${AUTHGEAR_URL}/oauth2/end_session`,
          jwks_uri: `${AUTHGEAR_URL}/oauth2/jwks`,
        },
      };
    case 'GET /oauth2/jwks':
      return { status: 200, body: jwks };
    case 'GET /oauth2/authorize':
      return authorize(url, req.headers.cookie ?? '');
    case 'POST /oauth2/token':
      return token(new URLSearchParams(body));
    case 'GET /oauth2/userinfo':
      return userinfo(req.headers.authorization ?? '');
    case 'POST /oauth2/revoke':
      refreshTokens.delete(new URLSearchParams(body).get('token') ?? '');
      return { status: 200, body: {} };
    case 'GET /oauth2/end_session': {
      const back = onSite(url.searchParams.get('post_logout_redirect_uri'));
      return { status: 302, location: back?.href ?? SITE_URL };
    }
    // The tests' own door: registers who a subject is and hands back a token for seeding.
    case 'POST /e2e/accounts': {
      const { subject, email, roles } = JSON.parse(body);
      accounts.set(subject, { email: email ?? `${subject}@e2e.test`, roles: roles ?? [] });
      return { status: 200, body: { access_token: accessToken(subject) } };
    }
    default:
      return { status: 404, body: { error: `no ${path} here` } };
  }
}

const server = http.createServer(async (req, res) => {
  const url = new URL(req.url ?? '/', AUTHGEAR_URL);
  const chunks: Buffer[] = [];
  for await (const chunk of req) chunks.push(chunk as Buffer);
  // The SDK calls the token and userinfo endpoints with credentials, from the site only.
  if (req.headers.origin === SITE_ORIGIN) {
    res.setHeader('access-control-allow-origin', SITE_ORIGIN);
    res.setHeader('access-control-allow-credentials', 'true');
    res.setHeader('vary', 'Origin');
  }
  if (req.method === 'OPTIONS') {
    res.setHeader('access-control-allow-methods', 'GET, POST, OPTIONS');
    res.setHeader(
      'access-control-allow-headers',
      req.headers['access-control-request-headers'] ?? '',
    );
    res.writeHead(204).end();
    return;
  }
  const reply = await route(req, url, Buffer.concat(chunks).toString());
  if (reply.location) res.setHeader('location', reply.location);
  if (reply.body === undefined) {
    res.writeHead(reply.status).end();
    return;
  }
  res.writeHead(reply.status, { 'content-type': 'application/json' });
  res.end(JSON.stringify(reply.body));
});

const { hostname, port } = new URL(AUTHGEAR_URL);
server.listen(Number(port), hostname, () => console.log(`fake Authgear on ${AUTHGEAR_URL}`));
