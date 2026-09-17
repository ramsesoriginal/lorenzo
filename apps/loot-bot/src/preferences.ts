import { getPreference } from "./db.js";

/**
 * The seam every command that takes an optional character/container
 * parameter (loot-drop take, `/award`, `/move`) resolves it through - "use
 * whatever was explicitly given, otherwise fall back to `/set-current`'s
 * stored preference." Returns `undefined` when neither is available; the
 * caller decides what that means for its own command (usually "ask the
 * player to specify one, or run `/set-current` first").
 *
 * Scoped per Discord channel (ADR 0068) - `getPreference` itself falls back
 * to the caller's global default when no channel-specific preference has
 * been set yet.
 */
export async function resolveCurrentCharacter(
  discordUserId: string,
  channelId: string,
  explicit: string | null | undefined,
): Promise<string | undefined> {
  if (explicit) return explicit;
  const preference = await getPreference(discordUserId, channelId);
  return preference?.currentCharacterEntityId ?? undefined;
}

/** Same as {@link resolveCurrentCharacter}, for the default container. */
export async function resolveCurrentContainer(
  discordUserId: string,
  channelId: string,
  explicit: string | null | undefined,
): Promise<string | undefined> {
  if (explicit) return explicit;
  const preference = await getPreference(discordUserId, channelId);
  return preference?.currentContainerEntityId ?? undefined;
}
