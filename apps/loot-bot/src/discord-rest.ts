import type { MessagePayload } from "./commands/types.js";

const DISCORD_API_BASE = "https://discord.com/api/v10";

// Discord message flags (bitfield) - only the one this bot ever sets.
const EPHEMERAL_FLAG = 1 << 6;

export function ephemeralFlags(ephemeral: boolean | undefined): number | undefined {
  return ephemeral ? EPHEMERAL_FLAG : undefined;
}

/** discord.js builder instances (EmbedBuilder, ActionRowBuilder, ...) are
 * passed straight through by every `format-*.ts` module (ADR 0045) - this
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
