import { z } from "zod";

const envSchema = z.object({
  DISCORD_BOT_TOKEN: z.string().min(1),
  DISCORD_CLIENT_ID: z.string().min(1),
  DISCORD_GUILD_ID: z.string().min(1),
  DISCORD_PUBLIC_KEY: z.string().min(1),

  LORENZO_API_BASE_URL: z.string().url(),
  LORENZO_TENANT_ID: z.string().uuid(),

  AUTHGEAR_ISSUER: z.string().url(),
  AUTHGEAR_CLIENT_ID: z.string().min(1),
  AUTHGEAR_CLIENT_SECRET: z.string().min(1),

  LOOT_BOT_DATABASE_URL: z.string().min(1),
  // Optional here, not required: only migrate.ts's one-shot process ever
  // reads this (the privileged bootstrap/DDL role - see its own docstring).
  // The deployed server (index.ts) must never hold it, so
  // deploy-loot-bot.yml's own env_vars for the running container
  // deliberately don't set it - loadConfig() validates one shared schema for
  // both entry points, so requiring it here would crash the server's own
  // startup on every deploy. migrate.ts asserts it's actually present
  // itself, since it's the one place that genuinely can't run without it.
  LOOT_BOT_MIGRATIONS_DATABASE_URL: z.string().min(1).optional(),
  LOOT_BOT_TOKEN_ENCRYPTION_KEY: z.string().min(1),

  LOOT_BOT_HTTP_PORT: z.coerce.number().int().positive().default(8090),
  // The very first deploy can't know its own Cloud Run URL yet (a real
  // chicken-and-egg - see docs/operations/deployment-setup.md's loot-bot
  // section) and GitHub Actions' own `${{ vars.X }}` substitutes to an
  // *empty string*, not an omitted line, when X doesn't exist yet - so this
  // arrives as LOOT_BOT_PUBLIC_BASE_URL="", not unset. zod's `.default()`
  // only fires on `undefined`, never on an empty string, so without this
  // preprocess step that first deploy would fail `.url()` validation and
  // crash before ever binding to a port - confirmed the hard way, not
  // assumed.
  LOOT_BOT_PUBLIC_BASE_URL: z.preprocess(
    (v) => (v === "" ? undefined : v),
    z.string().url().default("http://127.0.0.1:8090"),
  ),

  // The service account Cloud Scheduler's job runs as (ADR 0095) - the only
  // caller `/internal/deliver-notifications` will accept, proven by the
  // OIDC token Cloud Scheduler attaches. Optional: leaving it unset switches
  // the notification-DM bridge off entirely (the route answers 404), which
  // is the right default for local dev and for a deploy that hasn't done the
  // one-time Cloud Scheduler setup. Same empty-string-means-unset handling
  // as LOOT_BOT_PUBLIC_BASE_URL above: an unset GitHub Actions variable
  // arrives as "", not as a missing line.
  NOTIFICATION_SCHEDULER_SERVICE_ACCOUNT: z.preprocess(
    (v) => (v === "" ? undefined : v),
    z.string().email().optional(),
  ),
});

export type Config = Readonly<{
  discordBotToken: string;
  discordClientId: string;
  discordGuildId: string;
  discordPublicKey: string;
  lorenzoApiBaseUrl: string;
  lorenzoTenantId: string;
  authgearIssuer: string;
  authgearClientId: string;
  authgearClientSecret: string;
  databaseUrl: string;
  migrationsDatabaseUrl: string | undefined;
  tokenEncryptionKey: string;
  httpPort: number;
  publicBaseUrl: string;
  authCallbackUrl: string;
  /** `undefined` = the notification-DM bridge is off (ADR 0095). */
  notificationSchedulerServiceAccount: string | undefined;
  /** The exact URL Cloud Scheduler's job must POST to, and the `audience`
   * its OIDC token must carry (Cloud Scheduler defaults the audience to the
   * job's own URL) - derived from the public base URL so the two can't drift. */
  notificationDeliveryUrl: string;
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
    discordPublicKey: e.DISCORD_PUBLIC_KEY,
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
    notificationSchedulerServiceAccount: e.NOTIFICATION_SCHEDULER_SERVICE_ACCOUNT,
    notificationDeliveryUrl: new URL(
      "/internal/deliver-notifications",
      e.LOOT_BOT_PUBLIC_BASE_URL,
    ).toString(),
  };
  return cached;
}

export function resetConfigForTests(): void {
  cached = undefined;
}
