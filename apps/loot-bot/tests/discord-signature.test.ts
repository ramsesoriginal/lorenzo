import { generateKeyPairSync, sign } from "node:crypto";
import { describe, expect, it } from "vitest";
import { verifyDiscordSignature } from "../src/discord-signature.js";

// Real Ed25519 keypair, generated once for this file - Discord's own
// signing scheme, so a signature Node's built-in crypto produces is
// verifiable by `discord-interactions`' own tweetnacl-based `verifyKey`
// without needing that library to also generate the fixture.
const { publicKey, privateKey } = generateKeyPairSync("ed25519");

function hexPublicKey(): string {
  const jwk = publicKey.export({ format: "jwk" }) as { x: string };
  return Buffer.from(jwk.x, "base64url").toString("hex");
}

function signHex(message: string): string {
  return sign(null, Buffer.from(message), privateKey).toString("hex");
}

describe("verifyDiscordSignature", () => {
  const body = JSON.stringify({ type: 1 });
  const timestamp = "1700000000";

  it("accepts a genuinely signed request", async () => {
    const signature = signHex(timestamp + body);
    await expect(verifyDiscordSignature(body, signature, timestamp, hexPublicKey())).resolves.toBe(
      true,
    );
  });

  it("rejects a tampered body", async () => {
    const signature = signHex(timestamp + body);
    await expect(
      verifyDiscordSignature('{"type":2}', signature, timestamp, hexPublicKey()),
    ).resolves.toBe(false);
  });

  it("rejects a tampered timestamp", async () => {
    const signature = signHex(timestamp + body);
    await expect(
      verifyDiscordSignature(body, signature, "1700000001", hexPublicKey()),
    ).resolves.toBe(false);
  });

  it("rejects a signature from the wrong key", async () => {
    const { privateKey: otherPrivateKey } = generateKeyPairSync("ed25519");
    const wrongSignature = sign(null, Buffer.from(timestamp + body), otherPrivateKey).toString(
      "hex",
    );
    await expect(
      verifyDiscordSignature(body, wrongSignature, timestamp, hexPublicKey()),
    ).resolves.toBe(false);
  });

  it("rejects when the signature or timestamp header is missing", async () => {
    const signature = signHex(timestamp + body);
    await expect(verifyDiscordSignature(body, undefined, timestamp, hexPublicKey())).resolves.toBe(
      false,
    );
    await expect(verifyDiscordSignature(body, signature, undefined, hexPublicKey())).resolves.toBe(
      false,
    );
  });

  it("rejects when a header arrives as an array (a malformed/duplicated header)", async () => {
    const signature = signHex(timestamp + body);
    await expect(
      verifyDiscordSignature(body, [signature, signature], timestamp, hexPublicKey()),
    ).resolves.toBe(false);
  });
});
