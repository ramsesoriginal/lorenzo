import { z } from "zod";

const envSchema = z.object({
  DISCORD_BOT_TOKEN: z.string().min(1),
  DISCORD_CLIENT_ID: z.string().min(1),
  DISCORD_GUILD_ID: z.string().min(1),

  LORENZO_API_BASE_URL: z.string().url(),
  LORENZO_TENANT_ID: z.string().uuid(),

  AUTHGEAR_ISSUER: z.string().url(),
  AUTHGEAR_CLIENT_ID: z.string().min(1),
  AUTHGEAR_CLIENT_SECRET: z.string().min(1),

  LOOT_BOT_DATABASE_URL: z.string().min(1),
  LOOT_BOT_MIGRATIONS_DATABASE_URL: z.string().min(1),
  LOOT_BOT_TOKEN_ENCRYPTION_KEY: z.string().min(1),

  LOOT_BOT_HTTP_PORT: z.coerce.number().int().positive().default(8090),
  LOOT_BOT_PUBLIC_BASE_URL: z.string().url().default("http://127.0.0.1:8090"),
});

export type Config = Readonly<{
  discordBotToken: string;
  discordClientId: string;
  discordGuildId: string;
  lorenzoApiBaseUrl: string;
  lorenzoTenantId: string;
  authgearIssuer: string;
  authgearClientId: string;
  authgearClientSecret: string;
  databaseUrl: string;
  migrationsDatabaseUrl: string;
  tokenEncryptionKey: string;
  httpPort: number;
  publicBaseUrl: string;
  authCallbackUrl: string;
}>;

let cached: Config | undefined;

/**
 * Reads and validates process.env once, then memoizes - mirrors apps/api's
 * own `get_settings()` `@lru_cache` pattern (config.py). Call
 * `resetConfigForTests()` between tests that need a different env shape.
 */
export function loadConfig(env: NodeJS.ProcessEnv = process.env): Config {
  if (cached) return cached;

  const parsed = envSchema.safeParse(env);
  if (!parsed.success) {
    const issues = parsed.error.issues.map(
      (issue) => `  ${issue.path.join(".")}: ${issue.message}`,
    );
    throw new Error(`Invalid environment configuration:\n${issues.join("\n")}`);
  }
  const e = parsed.data;

  cached = {
    discordBotToken: e.DISCORD_BOT_TOKEN,
    discordClientId: e.DISCORD_CLIENT_ID,
    discordGuildId: e.DISCORD_GUILD_ID,
    lorenzoApiBaseUrl: e.LORENZO_API_BASE_URL,
    lorenzoTenantId: e.LORENZO_TENANT_ID,
    authgearIssuer: e.AUTHGEAR_ISSUER,
    authgearClientId: e.AUTHGEAR_CLIENT_ID,
    authgearClientSecret: e.AUTHGEAR_CLIENT_SECRET,
    databaseUrl: e.LOOT_BOT_DATABASE_URL,
    migrationsDatabaseUrl: e.LOOT_BOT_MIGRATIONS_DATABASE_URL,
    tokenEncryptionKey: e.LOOT_BOT_TOKEN_ENCRYPTION_KEY,
    httpPort: e.LOOT_BOT_HTTP_PORT,
    publicBaseUrl: e.LOOT_BOT_PUBLIC_BASE_URL,
    authCallbackUrl: new URL("/auth/callback", e.LOOT_BOT_PUBLIC_BASE_URL).toString(),
  };
  return cached;
}

export function resetConfigForTests(): void {
  cached = undefined;
}
