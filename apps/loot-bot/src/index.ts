import { Client, Events, GatewayIntentBits } from "discord.js";
import { createAuthCallbackRoute } from "./auth-callback-route.js";
import { attachCommandHandlers } from "./commands/index.js";
import { loadConfig } from "./config.js";
import { createHttpServer, healthzRoute } from "./http-server.js";
import { logger } from "./logger.js";

async function main(): Promise<void> {
  const config = loadConfig();

  // Slash commands are registered by their own separate task
  // (mise run register-commands / scripts/register-commands.ts), not on
  // every boot - avoids hitting Discord's registration rate limits on every
  // restart and matches apps/api's own separate `alembic upgrade head` step
  // rather than auto-migrating on startup.
  const client = new Client({ intents: [GatewayIntentBits.Guilds] });
  attachCommandHandlers(client, { config, logger });

  client.once(Events.ClientReady, (readyClient) => {
    logger.info({ tag: readyClient.user.tag }, "discord client ready");
  });

  const httpServer = createHttpServer(
    new Map([
      ["/healthz", healthzRoute],
      ["/auth/callback", createAuthCallbackRoute(config, logger)],
    ]),
    { port: config.httpPort, logger },
  );
  await httpServer.listen();
  logger.info({ port: config.httpPort }, "http server listening");

  await client.login(config.discordBotToken);

  let shuttingDown = false;
  const shutdown = async (signal: string): Promise<void> => {
    if (shuttingDown) return;
    shuttingDown = true;
    logger.info({ signal }, "shutting down");
    try {
      await httpServer.close();
      client.destroy();
    } finally {
      process.exit(0);
    }
  };
  process.on("SIGTERM", () => void shutdown("SIGTERM"));
  process.on("SIGINT", () => void shutdown("SIGINT"));
}

main().catch((error: unknown) => {
  logger.error({ err: error }, "fatal startup error");
  process.exit(1);
});
