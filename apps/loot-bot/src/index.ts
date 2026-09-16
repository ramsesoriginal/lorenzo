import { createAuthCallbackRoute } from "./auth-callback-route.js";
import { loadConfig } from "./config.js";
import { createHttpServer, healthzRoute } from "./http-server.js";
import { createInteractionsRoute } from "./interactions-route.js";
import { logger } from "./logger.js";

async function main(): Promise<void> {
  const config = loadConfig();

  // Slash commands are registered by their own separate task
  // (mise run register-commands / scripts/register-commands.ts), not on
  // every boot - avoids hitting Discord's registration rate limits on every
  // restart and matches apps/api's own separate `alembic upgrade head` step
  // rather than auto-migrating on startup.
  const httpServer = createHttpServer(
    new Map([
      ["/healthz", healthzRoute],
      ["/auth/callback", createAuthCallbackRoute(config, logger)],
      // Discord's HTTP Interactions Endpoint (ADR 0045) - replaces the
      // Gateway `Client`/`.login()` this process used to run: every slash
      // command, autocomplete, button/select-menu, and modal submit now
      // arrives as a signature-verified webhook POST here instead.
      ["/interactions", createInteractionsRoute({ config, logger })],
    ]),
    { port: config.httpPort, logger },
  );
  await httpServer.listen();
  logger.info({ port: config.httpPort }, "http server listening");

  let shuttingDown = false;
  const shutdown = async (signal: string): Promise<void> => {
    if (shuttingDown) return;
    shuttingDown = true;
    logger.info({ signal }, "shutting down");
    try {
      await httpServer.close();
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
