import type { MessagePayload } from "./commands/types.js";

const DISCORD_API_BASE = "https://discord.com/api/v10";

// Discord message flags (bitfield) - only the one this bot ever sets.
const EPHEMERAL_FLAG = 1 << 6;

export function ephemeralFlags(ephemeral: boolean | undefined): number | undefined {
  return ephemeral ? EPHEMERAL_FLAG : undefined;
}

/** discord.js builder instances (EmbedBuilder, ActionRowBuilder, ...) are
 * passed straight through by every `format-*.ts` module (ADR 0053) - this
 * is the one place they get flattened to plain JSON before hitting the
 * network, via their own `.toJSON()`, same as discord.js itself would do
 * internally. */
function toPlain(value: unknown): unknown {
  if (
    typeof value === "object" &&
    value !== null &&
    "toJSON" in value &&
    typeof (value as { toJSON: unknown }).toJSON === "function"
  ) {
    return (value as { toJSON(): unknown }).toJSON();
  }
  return value;
}

export function serializeMessagePayload(
  payload: MessagePayload,
  extraFlags?: number,
): Record<string, unknown> {
  const base = typeof payload === "string" ? { content: payload } : payload;
  return {
    ...(base.content !== undefined ? { content: base.content } : {}),
    ...("embeds" in base && base.embeds !== undefined ? { embeds: base.embeds.map(toPlain) } : {}),
    ...("components" in base && base.components !== undefined
      ? { components: base.components.map(toPlain) }
      : {}),
    ...(extraFlags !== undefined ? { flags: extraFlags } : {}),
  };
}

async function discordFetch(url: string, init: RequestInit): Promise<Response> {
  const res = await fetch(url, init);
  if (!res.ok) {
    throw new Error(`Discord API call failed: ${res.status} ${await res.text()}`);
  }
  return res;
}

/** discord.js's `editReply` - edits the message the first response
 * created. Returns the edited message (its `id` is the only field any
 * command actually reads, e.g. `drop.ts`'s own message-id bookkeeping). */
export async function editOriginalInteractionResponse(
  applicationId: string,
  interactionToken: string,
  body: Record<string, unknown>,
): Promise<{ id: string }> {
  const res = await discordFetch(
    `${DISCORD_API_BASE}/webhooks/${applicationId}/${interactionToken}/messages/@original`,
    {
      method: "PATCH",
      headers: { "content-type": "application/json" },
      body: JSON.stringify(body),
    },
  );
  return (await res.json()) as { id: string };
}

/** discord.js's `followUp` - a new message tied to this same interaction's
 * webhook token (valid for 15 minutes after the interaction was created). */
export async function sendInteractionFollowUp(
  applicationId: string,
  interactionToken: string,
  body: Record<string, unknown>,
): Promise<{ id: string }> {
  const res = await discordFetch(
    `${DISCORD_API_BASE}/webhooks/${applicationId}/${interactionToken}`,
    {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify(body),
    },
  );
  return (await res.json()) as { id: string };
}

type RawMessage = Readonly<{ author: Readonly<{ id: string; bot?: boolean }> }>;

/**
 * `/add-channel-to-group`'s own "who's been active here" source (ADR
 * 0068) - the first bot-token-authenticated call in this file (every
 * other function here is interaction-token-authenticated, tied to one
 * specific triggering interaction's own reply chain). This bot has no
 * persistent Gateway connection to observe channel activity live (ADR
 * 0053), but a plain REST read of recent message history needs no
 * Gateway at all - the bot just needs `DISCORD_BOT_TOKEN` and the
 * `Read Message History` permission in that channel.
 *
 * Bot authors are excluded (a loot-bot command posting to the channel
 * shouldn't count as "someone was here"). Deduplicated, but not resolved
 * to Lorenzo identities here - that's the caller's own job, since it
 * needs each author's own linked-account token, not this one.
 */
export async function getRecentChannelAuthorIds(
  botToken: string,
  channelId: string,
  limit = 100,
): Promise<readonly string[]> {
  const res = await discordFetch(
    `${DISCORD_API_BASE}/channels/${channelId}/messages?limit=${limit}`,
    { headers: { authorization: `Bot ${botToken}` } },
  );
  const messages = (await res.json()) as readonly RawMessage[];
  const authorIds = new Set(
    messages.filter((message) => !message.author.bot).map((message) => message.author.id),
  );
  return [...authorIds];
}

/** A Discord API failure that isn't one of the outcomes a caller handles
 * specially - carries Discord's own numeric error `code` when the body had
 * one, so a caller can tell a permanent refusal from a retryable blip. */
export class DiscordApiError extends Error {
  constructor(
    readonly status: number,
    readonly code: number | undefined,
    body: string,
  ) {
    super(
      `Discord API call failed: ${status}${code !== undefined ? ` (code ${code})` : ""} ${body}`,
    );
    this.name = "DiscordApiError";
  }
}

/** Discord's "Cannot send messages to this user" - the user has DMs from
 * server members turned off (or has blocked the bot). */
const CANNOT_MESSAGE_USER = 50007;

export type DirectMessageResult = Readonly<{ kind: "sent" } | { kind: "closed" }>;

/**
 * DMs one Discord user as the bot (ADR 0095) - the second bot-token call in
 * this file, after `getRecentChannelAuthorIds`. Two REST calls, no Gateway:
 * open (or fetch) the DM channel, then post to it.
 *
 * `{ kind: "closed" }` is the one *expected* failure: the user has DMs
 * closed (code 50007), which is a fact about them, not an error - the caller
 * turns it into the "couldn't DM you" fallback. Anything else (rate limits,
 * 5xx, an unexpected 4xx) throws {@link DiscordApiError} and is the caller's
 * to retry.
 */
export async function sendDirectMessage(
  botToken: string,
  discordUserId: string,
  body: Record<string, unknown>,
): Promise<DirectMessageResult> {
  const headers = { authorization: `Bot ${botToken}`, "content-type": "application/json" };

  const channelRes = await fetch(`${DISCORD_API_BASE}/users/@me/channels`, {
    method: "POST",
    headers,
    body: JSON.stringify({ recipient_id: discordUserId }),
  });
  if (!channelRes.ok) return closedOrThrow(channelRes);
  const channel = (await channelRes.json()) as { id: string };

  const messageRes = await fetch(`${DISCORD_API_BASE}/channels/${channel.id}/messages`, {
    method: "POST",
    headers,
    body: JSON.stringify(body),
  });
  if (!messageRes.ok) return closedOrThrow(messageRes);
  return { kind: "sent" };
}

async function closedOrThrow(res: Response): Promise<DirectMessageResult> {
  const text = await res.text();
  let code: number | undefined;
  try {
    const parsed = JSON.parse(text) as { code?: unknown };
    if (typeof parsed.code === "number") code = parsed.code;
  } catch {
    // Not JSON (a gateway error page, say) - no code to read, so it's a
    // plain failure below.
  }
  if (res.status === 403 && code === CANNOT_MESSAGE_USER) return { kind: "closed" };
  throw new DiscordApiError(res.status, code, text);
}
