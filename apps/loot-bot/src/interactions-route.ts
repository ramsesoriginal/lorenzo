import type { IncomingMessage, ServerResponse } from "node:http";
import { dispatchInteraction } from "./commands/index.js";
import type { CommandContext } from "./commands/types.js";
import { verifyDiscordSignature } from "./discord-signature.js";
import type { RouteHandler } from "./http-server.js";
import {
  type RawInteractionPayload,
  type ResponseBody,
  buildAdapterInteraction,
  isPing,
  pongResponse,
} from "./interaction-adapter.js";

async function readRawBody(req: IncomingMessage): Promise<string> {
  const chunks: Buffer[] = [];
  for await (const chunk of req) {
    chunks.push(chunk as Buffer);
  }
  return Buffer.concat(chunks).toString("utf8");
}

function sendJson(res: ServerResponse, status: number, body: unknown): void {
  res.writeHead(status, { "content-type": "application/json" }).end(JSON.stringify(body));
}

const GENERIC_FAILURE_RESPONSE: ResponseBody = {
  type: 4,
  data: { content: "Something went wrong handling that.", flags: 1 << 6 },
};

/**
 * `/interactions` - Discord's HTTP Interactions Endpoint (ADR 0053): every
 * slash command, autocomplete request, button/select-menu click, and modal
 * submit arrives here as a signature-verified webhook POST instead of over
 * a Gateway connection. The signature check needs the *raw* body, read here
 * directly rather than through any generic body-parsing middleware - no
 * other route on this server needs one.
 *
 * Exactly one response is ever sent back per request. The normal path is
 * whatever `buildAdapterInteraction`'s "first response gate" resolves with,
 * once `dispatchInteraction` calls a command's own first reply/deferReply/
 * deferUpdate/update/showModal/respond. `Promise.race`d against dispatch
 * finishing at all is a safety net, not the expected path: if dispatch
 * returns (an unknown command, a bug) without ever sending a first
 * response, Discord's own webhook still needs *something* within its
 * response window, so a generic failure ack wins the race instead of
 * hanging the request.
 */
export function createInteractionsRoute(ctx: CommandContext): RouteHandler {
  return async (req, res) => {
    const rawBody = await readRawBody(req);
    const valid = await verifyDiscordSignature(
      rawBody,
      req.headers["x-signature-ed25519"],
      req.headers["x-signature-timestamp"],
      ctx.config.discordPublicKey,
    );
    if (!valid) {
      res.writeHead(401, { "content-type": "text/plain" }).end("invalid request signature");
      return;
    }

    const payload = JSON.parse(rawBody) as RawInteractionPayload;

    if (isPing(payload)) {
      sendJson(res, 200, pongResponse);
      return;
    }

    if (payload.guild_id !== ctx.config.discordGuildId) {
      ctx.logger.warn(
        { guildId: payload.guild_id },
        "ignoring interaction from an unconfigured guild",
      );
      sendJson(res, 200, GENERIC_FAILURE_RESPONSE);
      return;
    }

    const built = buildAdapterInteraction(payload);
    if (!built) {
      ctx.logger.warn({ type: payload.type }, "unsupported interaction type/component");
      sendJson(res, 200, GENERIC_FAILURE_RESPONSE);
      return;
    }

    const { interaction, firstResponse } = built;
    const dispatchSettled = dispatchInteraction(interaction, ctx).catch((error: unknown) => {
      ctx.logger.error({ err: error }, "interaction dispatch failed outside the response window");
    });

    const responseBody = await Promise.race([
      firstResponse,
      dispatchSettled.then((): ResponseBody => {
        ctx.logger.error(
          { commandName: describeInteraction(interaction) },
          "dispatch finished without ever sending a response",
        );
        return GENERIC_FAILURE_RESPONSE;
      }),
    ]);
    sendJson(res, 200, responseBody);
  };
}

function describeInteraction(interaction: { customId?: string; commandName?: string }): string {
  return interaction.commandName ?? interaction.customId ?? "(unknown)";
}
