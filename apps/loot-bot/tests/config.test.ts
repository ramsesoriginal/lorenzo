import { beforeEach, describe, expect, it } from "vitest";
import { loadConfig, resetConfigForTests } from "../src/config.js";

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
  LOOT_BOT_TOKEN_ENCRYPTION_KEY: "a-key",
};

describe("loadConfig", () => {
  beforeEach(() => {
    resetConfigForTests();
  });

  it("parses a fully-specified environment", () => {
    const config = loadConfig(validEnv);
    expect(config.discordGuildId).toBe("456");
    expect(config.lorenzoTenantId).toBe("3fa85f64-5717-4562-b3fc-2c963f66afa6");
  });

  it("defaults the http port and public base url, and derives the callback url", () => {
    const config = loadConfig(validEnv);
    expect(config.httpPort).toBe(8090);
    expect(config.publicBaseUrl).toBe("http://127.0.0.1:8090");
    expect(config.authCallbackUrl).toBe("http://127.0.0.1:8090/auth/callback");
  });

  it("honors an explicit port and base url", () => {
    const config = loadConfig({
      ...validEnv,
      LOOT_BOT_HTTP_PORT: "9000",
      LOOT_BOT_PUBLIC_BASE_URL: "https://bot.example.com",
    });
    expect(config.httpPort).toBe(9000);
    expect(config.authCallbackUrl).toBe("https://bot.example.com/auth/callback");
  });

  it("throws with a readable message when required vars are missing", () => {
    const { DISCORD_BOT_TOKEN: _omit, ...incomplete } = validEnv;
    expect(() => loadConfig(incomplete)).toThrow(/DISCORD_BOT_TOKEN/);
  });

  it("memoizes across calls until reset", () => {
    const first = loadConfig(validEnv);
    const second = loadConfig({ ...validEnv, DISCORD_GUILD_ID: "different" });
    expect(second).toBe(first);
    expect(second.discordGuildId).toBe("456");
  });
});
