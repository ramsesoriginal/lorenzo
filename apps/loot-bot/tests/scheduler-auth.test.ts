import { SignJWT, createLocalJWKSet, exportJWK, generateKeyPair } from "jose";
import { beforeAll, describe, expect, it } from "vitest";
import { verifySchedulerRequest } from "../src/scheduler-auth.js";

const AUDIENCE = "https://bot.example.com/internal/deliver-notifications";
const SERVICE_ACCOUNT = "scheduler@proj.iam.gserviceaccount.com";
const GOOGLE_ISSUER = "https://accounts.google.com";

type PrivateKey = Awaited<ReturnType<typeof generateKeyPair>>["privateKey"];

let privateKey: PrivateKey;
let keys: ReturnType<typeof createLocalJWKSet>;
let otherPrivateKey: PrivateKey;

beforeAll(async () => {
  const pair = await generateKeyPair("RS256");
  privateKey = pair.privateKey;
  const jwk = { ...(await exportJWK(pair.publicKey)), kid: "key-1", alg: "RS256", use: "sig" };
  keys = createLocalJWKSet({ keys: [jwk] });
  otherPrivateKey = (await generateKeyPair("RS256")).privateKey;
});

type Overrides = Partial<{
  issuer: string;
  audience: string;
  email: string;
  emailVerified: boolean | undefined;
  expiresIn: string;
  key: PrivateKey;
}>;

/** A token shaped like the ones Cloud Scheduler's OIDC support sends, with
 * any one property overridden. */
async function token(overrides: Overrides = {}): Promise<string> {
  const emailVerified = "emailVerified" in overrides ? overrides.emailVerified : true;
  return new SignJWT({
    email: overrides.email ?? SERVICE_ACCOUNT,
    ...(emailVerified === undefined ? {} : { email_verified: emailVerified }),
  })
    .setProtectedHeader({ alg: "RS256", kid: "key-1" })
    .setIssuer(overrides.issuer ?? GOOGLE_ISSUER)
    .setAudience(overrides.audience ?? AUDIENCE)
    .setIssuedAt()
    .setExpirationTime(overrides.expiresIn ?? "1h")
    .sign(overrides.key ?? privateKey);
}

const verify = (header: string | undefined) =>
  verifySchedulerRequest(header, {
    audience: AUDIENCE,
    serviceAccountEmail: SERVICE_ACCOUNT,
    keys,
  });

describe("verifySchedulerRequest", () => {
  it("accepts a token Google signed for this route, for the expected service account", async () => {
    await expect(verify(`Bearer ${await token()}`)).resolves.toEqual({ ok: true });
  });

  it("accepts Google's other spelling of its issuer", async () => {
    await expect(
      verify(`Bearer ${await token({ issuer: "accounts.google.com" })}`),
    ).resolves.toEqual({ ok: true });
  });

  it("is case-insensitive about the 'Bearer' scheme", async () => {
    await expect(verify(`bearer ${await token()}`)).resolves.toEqual({ ok: true });
  });

  it.each([
    ["no Authorization header at all", undefined],
    ["an empty header", ""],
    ["a non-bearer scheme", "Basic dXNlcjpwYXNz"],
    ["a bearer with no token", "Bearer "],
    ["a token that isn't a JWT", "Bearer not-a-jwt"],
  ])("rejects %s", async (_label, header) => {
    const result = await verify(header);

    expect(result.ok).toBe(false);
  });

  it("rejects a token addressed to a different audience", async () => {
    const result = await verify(
      `Bearer ${await token({ audience: "https://bot.example.com/interactions" })}`,
    );

    expect(result.ok).toBe(false);
  });

  it("rejects a token not issued by Google", async () => {
    const result = await verify(`Bearer ${await token({ issuer: "https://evil.example.com" })}`);

    expect(result.ok).toBe(false);
  });

  it("rejects a token for a different service account, even one Google signed", async () => {
    // Anyone can get Google to mint an ID token with this audience for
    // *their own* account - the account check is what stops that mattering.
    const result = await verify(`Bearer ${await token({ email: "attacker@evil.example.com" })}`);

    expect(result).toEqual({ ok: false, reason: "token is for a different account" });
  });

  it.each([
    ["false", false],
    ["absent", undefined],
  ])("rejects a token whose email_verified is %s", async (_label, emailVerified) => {
    const result = await verify(`Bearer ${await token({ emailVerified })}`);

    expect(result).toEqual({ ok: false, reason: "email not verified" });
  });

  it("rejects an expired token", async () => {
    const result = await verify(`Bearer ${await token({ expiresIn: "-1m" })}`);

    expect(result.ok).toBe(false);
  });

  it("rejects a token signed with a key that isn't in the key set", async () => {
    const result = await verify(`Bearer ${await token({ key: otherPrivateKey })}`);

    expect(result.ok).toBe(false);
  });

  it("never throws - a failure is a result, with a reason for the log", async () => {
    const result = await verify("Bearer garbage.garbage.garbage");

    expect(result.ok).toBe(false);
    expect((result as { reason: string }).reason).toEqual(expect.any(String));
  });
});
