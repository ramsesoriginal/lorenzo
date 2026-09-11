import { randomBytes } from "node:crypto";
import { beforeEach, describe, expect, it } from "vitest";
import { loadConfig, resetConfigForTests } from "../src/config.js";
import { decrypt, encrypt } from "../src/crypto.js";

const validEnv = {
  DISCORD_BOT_TOKEN: "token",
  DISCORD_CLIENT_ID: "123",
  DISCORD_GUILD_ID: "456",
  LORENZO_API_BASE_URL: "http://localhost:8000",
  LORENZO_TENANT_ID: "3fa85f64-5717-4562-b3fc-2c963f66afa6",
  AUTHGEAR_ISSUER: "http://localhost:4000",
  AUTHGEAR_CLIENT_ID: "client",
  AUTHGEAR_CLIENT_SECRET: "secret",
  LOOT_BOT_DATABASE_URL: "postgres://loot_bot:loot_bot@localhost:55432/lorenzo",
  LOOT_BOT_MIGRATIONS_DATABASE_URL: "postgres://lorenzo:lorenzo@localhost:55432/lorenzo",
  LOOT_BOT_TOKEN_ENCRYPTION_KEY: randomBytes(32).toString("base64"),
};

describe("encrypt/decrypt", () => {
  beforeEach(() => {
    resetConfigForTests();
  });

  it("round-trips a plaintext string", () => {
    loadConfig(validEnv);

    const ciphertext = encrypt("a lorenzo access token");

    expect(ciphertext).toBeInstanceOf(Buffer);
    expect(decrypt(ciphertext)).toBe("a lorenzo access token");
  });

  it("round-trips an empty string", () => {
    loadConfig(validEnv);

    const ciphertext = encrypt("");

    expect(decrypt(ciphertext)).toBe("");
  });

  it("uses a fresh random IV per call, so the same plaintext encrypts differently", () => {
    loadConfig(validEnv);

    const a = encrypt("same plaintext");
    const b = encrypt("same plaintext");

    expect(a.equals(b)).toBe(false);
    expect(decrypt(a)).toBe("same plaintext");
    expect(decrypt(b)).toBe("same plaintext");
  });

  it("fails to decrypt under a different key (GCM auth tag check)", () => {
    loadConfig(validEnv);
    const ciphertext = encrypt("secret token");

    resetConfigForTests();
    loadConfig({ ...validEnv, LOOT_BOT_TOKEN_ENCRYPTION_KEY: randomBytes(32).toString("base64") });

    expect(() => decrypt(ciphertext)).toThrow();
  });

  it("fails loudly at construction when the configured key is not exactly 32 bytes, rather than silently padding/truncating", () => {
    loadConfig({
      ...validEnv,
      LOOT_BOT_TOKEN_ENCRYPTION_KEY: Buffer.from("too short").toString("base64"),
    });

    expect(() => encrypt("x")).toThrow(/32 bytes/);
  });

  it("fails loudly on a too-long key too", () => {
    loadConfig({
      ...validEnv,
      LOOT_BOT_TOKEN_ENCRYPTION_KEY: randomBytes(48).toString("base64"),
    });

    expect(() => encrypt("x")).toThrow(/32 bytes/);
  });

  it("rejects a ciphertext buffer too short to contain iv+authTag", () => {
    loadConfig(validEnv);

    expect(() => decrypt(Buffer.alloc(4))).toThrow(/too short/);
  });
});
