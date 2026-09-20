import { beforeEach, describe, expect, it } from "vitest";
import { loadConfig, resetConfigForTests } from "../src/config.js";

const validEnv = {
  DISCORD_BOT_TOKEN: "token",
  DISCORD_CLIENT_ID: "123",
  DISCORD_GUILD_ID: "456",
  DISCORD_PUBLIC_KEY: "public-key",
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

  it("defaults the public base url when it's an empty string, not just when it's absent", () => {
    // GitHub Actions' `${{ vars.LOOT_BOT_PUBLIC_BASE_URL }}` substitutes to
    // "" rather than omitting the line when that variable doesn't exist yet
    // (the real state on loot-bot's very first deploy, before its own Cloud
    // Run URL is known) - confirmed against a real failed deploy, not
    // assumed. zod's `.default()` alone doesn't cover this: it only fires on
    // `undefined`, and "" is a defined (if invalid) value.
    const config = loadConfig({ ...validEnv, LOOT_BOT_PUBLIC_BASE_URL: "" });
    expect(config.publicBaseUrl).toBe("http://127.0.0.1:8090");
  });

  it("loads successfully without LOOT_BOT_MIGRATIONS_DATABASE_URL - the deployed server's own real env", () => {
    // deploy-loot-bot.yml's env_vars for the running container deliberately
    // never set this (the privileged bootstrap/DDL role - only migrate.ts's
    // one-shot process needs it, per its own docstring) - loadConfig() must
    // not require it, or index.ts's every real deploy would crash on
    // startup before ever binding to a port. Confirmed against a real
    // failed deploy, not assumed.
    const { LOOT_BOT_MIGRATIONS_DATABASE_URL: _omit, ...serverEnv } = validEnv;
    const config = loadConfig(serverEnv);
    expect(config.migrationsDatabaseUrl).toBeUndefined();
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

describe("loadConfig - notification bridge (ADR 0095)", () => {
  beforeEach(() => {
    resetConfigForTests();
  });

  it("is off by default: no scheduler service account configured", () => {
    expect(loadConfig(validEnv).notificationSchedulerServiceAccount).toBeUndefined();
  });

  it("reads the scheduler's service account", () => {
    const config = loadConfig({
      ...validEnv,
      NOTIFICATION_SCHEDULER_SERVICE_ACCOUNT: "scheduler@proj.iam.gserviceaccount.com",
    });

    expect(config.notificationSchedulerServiceAccount).toBe(
      "scheduler@proj.iam.gserviceaccount.com",
    );
  });

  it('treats an empty string as unset - an unset GitHub Actions variable arrives as ""', () => {
    const config = loadConfig({ ...validEnv, NOTIFICATION_SCHEDULER_SERVICE_ACCOUNT: "" });

    expect(config.notificationSchedulerServiceAccount).toBeUndefined();
  });

  it("rejects a value that isn't an email address", () => {
    expect(() =>
      loadConfig({ ...validEnv, NOTIFICATION_SCHEDULER_SERVICE_ACCOUNT: "not-an-email" }),
    ).toThrow("NOTIFICATION_SCHEDULER_SERVICE_ACCOUNT");
  });

  it("derives the delivery URL - the job's target and its OIDC audience - from the public base URL", () => {
    const config = loadConfig({ ...validEnv, LOOT_BOT_PUBLIC_BASE_URL: "https://bot.example.com" });

    expect(config.notificationDeliveryUrl).toBe(
      "https://bot.example.com/internal/deliver-notifications",
    );
  });
});
