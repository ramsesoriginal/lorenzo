import pino, { type LoggerOptions } from "pino";

const isDev = process.env.NODE_ENV !== "production";

// Built conditionally, not `transport: isDev ? {...} : undefined` - under
// exactOptionalPropertyTypes (tsconfig.json), pino's own LoggerOptions type
// doesn't accept an explicit `transport: undefined`, only the key being
// absent entirely.
const options: LoggerOptions = {
  level: process.env.LOG_LEVEL ?? "info",
  ...(isDev ? { transport: { target: "pino-pretty" } } : {}),
};

/**
 * Structured JSON logging - the TS equivalent of apps/api's own structlog
 * setup (src/lorenzo_api/logging.py). Pretty-printed in dev only; plain
 * JSON otherwise, so a real deployment's log collector gets parseable lines.
 */
export const logger = pino(options);
