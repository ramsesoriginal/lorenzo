import type { Logger } from "pino";
import { GLOBAL_PREFERENCE_CHANNEL_ID, setPreference } from "../db.js";
import type { LorenzoApiClient } from "../lorenzo-client.js";

/**
 * "Last-used character" memory (ADR 0088): after a command acts on an item
 * one of the caller's *own* characters owns, that character becomes the
 * caller's default - the global-default preference row (ADR 0068), so it
 * applies server-wide, and `/set-current` in a channel still pins a
 * different one there, because a channel-specific value always wins over
 * this one.
 *
 * Only ever remembers a character the caller genuinely controls: the
 * "owner" of an item a GM is acting on, or an ownerless one, says nothing
 * about who the caller is playing. Purely a convenience layered on a write
 * that already succeeded, so a failure here (an API blip, a DB error) is
 * logged and swallowed - it must never turn a completed give/move/rename
 * into an error message.
 */
export async function rememberActingCharacter(
  client: LorenzoApiClient,
  tenantId: string,
  accessToken: string,
  discordUserId: string,
  ownerEntityId: string | null,
  logger: Logger,
): Promise<void> {
  if (!ownerEntityId) return;
  try {
    const mine = await client.getControlledCharacters(tenantId, accessToken);
    if (!mine.some((character) => character.entityId === ownerEntityId)) return;
    await setPreference(discordUserId, GLOBAL_PREFERENCE_CHANNEL_ID, {
      characterEntityId: ownerEntityId,
    });
  } catch (error) {
    logger.warn({ err: error, discordUserId }, "couldn't remember last-used character");
  }
}
