import { createCipheriv, createDecipheriv, randomBytes } from "node:crypto";
import { loadConfig } from "./config.js";

const ALGORITHM = "aes-256-gcm";
const KEY_LENGTH_BYTES = 32; // AES-256
const IV_LENGTH_BYTES = 12; // GCM-recommended nonce size
const AUTH_TAG_LENGTH_BYTES = 16; // node:crypto's own GCM default

/**
 * The only encryption key version this codebase currently produces or
 * accepts. `db.ts`'s `key_version` column is populated from every row's
 * creation (ADR 0029) so a future key-rotation scheme has somewhere to
 * record which key encrypted a given row, but no rotation is implemented
 * yet - there is only ever "the current key" today.
 */
export const CURRENT_KEY_VERSION = 1;

/**
 * Derives the AES-256-GCM key from LOOT_BOT_TOKEN_ENCRYPTION_KEY (ADR 0029).
 * Expected input format: exactly 32 random bytes, base64-encoded (see
 * .env.example, e.g. `openssl rand -base64 32`). The decoded length is
 * validated strictly - a too-short or too-long value throws here rather
 * than being silently truncated/padded into a key nobody could reason
 * about later.
 */
export function deriveEncryptionKey(rawKey: string): Buffer {
  const decoded = Buffer.from(rawKey, "base64");
  if (decoded.length !== KEY_LENGTH_BYTES) {
    throw new Error(
      `LOOT_BOT_TOKEN_ENCRYPTION_KEY must decode (as base64) to exactly ${KEY_LENGTH_BYTES} bytes ` +
        `for AES-256-GCM, but got ${decoded.length} bytes. Generate one with: openssl rand -base64 32`,
    );
  }
  return decoded;
}

// Deliberately not cached at module scope (unlike config.ts's own
// loadConfig()/resetConfigForTests() memoization) - re-deriving from the
// already-cached config on every call is cheap (a base64 decode of ~44
// chars) and keeps this module free of its own test-only reset hook.
function getEncryptionKey(): Buffer {
  return deriveEncryptionKey(loadConfig().tokenEncryptionKey);
}

/**
 * Encrypts `plaintext` with AES-256-GCM, packing `iv‖ciphertext‖authTag`
 * into a single Buffer - the shape db.ts's `bytea` columns expect (ADR
 * 0029). A fresh random 12-byte IV is generated per call; reusing an IV
 * under the same key would break GCM's security guarantees, so there is
 * deliberately no way to pass one in.
 */
export function encrypt(plaintext: string): Buffer {
  const key = getEncryptionKey();
  const iv = randomBytes(IV_LENGTH_BYTES);
  const cipher = createCipheriv(ALGORITHM, key, iv);
  const ciphertext = Buffer.concat([cipher.update(plaintext, "utf8"), cipher.final()]);
  const authTag = cipher.getAuthTag();
  return Buffer.concat([iv, ciphertext, authTag]);
}

/**
 * Reverses `encrypt`. Throws (node:crypto's own GCM authentication check)
 * if `buffer` was tampered with or encrypted under a different key, and
 * throws directly if it's too short to even contain an iv+authTag - either
 * way this fails loudly rather than returning garbage plaintext.
 */
export function decrypt(buffer: Buffer): string {
  if (buffer.length < IV_LENGTH_BYTES + AUTH_TAG_LENGTH_BYTES) {
    throw new Error(
      `encrypted buffer is too short to be iv‖ciphertext‖authTag (got ${buffer.length} bytes)`,
    );
  }
  const key = getEncryptionKey();
  const iv = buffer.subarray(0, IV_LENGTH_BYTES);
  const authTag = buffer.subarray(buffer.length - AUTH_TAG_LENGTH_BYTES);
  const ciphertext = buffer.subarray(IV_LENGTH_BYTES, buffer.length - AUTH_TAG_LENGTH_BYTES);

  const decipher = createDecipheriv(ALGORITHM, key, iv);
  decipher.setAuthTag(authTag);
  return Buffer.concat([decipher.update(ciphertext), decipher.final()]).toString("utf8");
}
