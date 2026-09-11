import { REST, Routes } from "discord.js";
import { commandDefinitions } from "../src/commands/index.js";
import { loadConfig } from "../src/config.js";
import { logger } from "../src/logger.js";

/**
 * Registers this bot's slash commands for DISCORD_GUILD_ID. Guild-scoped
 * (not global) commands, deliberately - this bot only ever serves one guild
 * (ADR 0029), and guild command updates propagate immediately, unlike
 * global commands' up-to-an-hour cache. Run via `mise run register-commands`
 * whenever `src/commands/index.ts`'s command list changes; not run
 * automatically on every boot (see src/index.ts).
 */
async function main(): Promise<void> {
  const config = loadConfig();
  const rest = new REST().setToken(config.discordBotToken);

  const result = await rest.put(
    Routes.applicationGuildCommands(config.discordClientId, config.discordGuildId),
    { body: commandDefinitions },
  );

  const count = Array.isArray(result) ? result.length : 0;
  logger.info({ count, guildId: config.discordGuildId }, "registered slash commands");
}

main().catch((error: unknown) => {
  logger.error({ err: error }, "failed to register commands");
  process.exit(1);
});
