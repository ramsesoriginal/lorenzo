import { type JWTVerifyGetKey, createRemoteJWKSet, jwtVerify } from "jose";

/**
 * Proves a request to `/internal/deliver-notifications` really came from
 * this project's Cloud Scheduler job (ADR 0095).
 *
 * The route can't simply be private: this same Cloud Run service must stay
 * publicly reachable for Discord's interaction webhooks (ADR 0053), so
 * Cloud Run's own IAM can't be the gate. Instead Cloud Scheduler is set up
 * to send a Google-signed OIDC ID token as a bearer token (`gcloud scheduler
 * jobs create http ... --oidc-service-account-email=...`), and this checks it
 * the way Google documents for verifying such a token yourself:
 *
 * - the signature, against Google's published keys;
 * - `iss` is Google's, `aud` is exactly this route's URL (Cloud Scheduler's
 *   default audience for a job is its own target URL), and it hasn't expired;
 * - the token is for the *one* service account this deployment expects
 *   (`email` matches, and Google vouches for it via `email_verified`) -
 *   without that last check, any Google-issued token with this audience,
 *   from any account, would pass.
 *
 * No long-lived shared secret is involved (the same property Workload
 * Identity Federation gives the deploy pipeline, ADR 0011/0053): the token is
 * minted per request and expires within the hour.
 */
const GOOGLE_JWKS_URL = new URL("https://www.googleapis.com/oauth2/v3/certs");
const GOOGLE_ISSUERS = ["https://accounts.google.com", "accounts.google.com"];

// One remote key set for the process's lifetime: `jose` caches the fetched
// keys and refreshes on an unknown `kid`, so this isn't a network call per
// request.
let googleKeys: JWTVerifyGetKey | undefined;

export type SchedulerAuthOptions = Readonly<{
  /** The exact URL the Cloud Scheduler job posts to. */
  audience: string;
  /** The service account the job runs as. */
  serviceAccountEmail: string;
  /** Overridable so tests can verify against a locally generated key
   * instead of Google's. */
  keys?: JWTVerifyGetKey;
}>;

export type SchedulerAuthResult = Readonly<{ ok: true } | { ok: false; reason: string }>;

/** Never throws: a bad, missing, expired, or wrongly-addressed token is just
 * `{ ok: false }`, with a `reason` for the server log only - the route
 * answers every failure with the same bare 401, so the response tells a
 * prober nothing. */
export async function verifySchedulerRequest(
  authorizationHeader: string | undefined,
  options: SchedulerAuthOptions,
): Promise<SchedulerAuthResult> {
  const match = /^Bearer (.+)$/i.exec(authorizationHeader ?? "");
  if (!match?.[1]) return { ok: false, reason: "no bearer token" };

  try {
    googleKeys ??= createRemoteJWKSet(GOOGLE_JWKS_URL);
    const { payload } = await jwtVerify(match[1], options.keys ?? googleKeys, {
      issuer: GOOGLE_ISSUERS,
      audience: options.audience,
    });
    if (payload.email !== options.serviceAccountEmail) {
      return { ok: false, reason: "token is for a different account" };
    }
    if (payload.email_verified !== true) {
      return { ok: false, reason: "email not verified" };
    }
    return { ok: true };
  } catch (error) {
    return {
      ok: false,
      reason: error instanceof Error ? error.message : "token verification failed",
    };
  }
}
