import { getPreference } from "./db.js";

/**
 * The seam every command that takes an optional character/container
 * parameter (loot-drop take, `/award`, `/move`) resolves it through - "use
 * whatever was explicitly given, otherwise fall back to `/set-current`'s
 * stored preference." Returns `undefined` when neither is available; the
 * caller decides what that means for its own command (usually "ask the
 * player to specify one, or run `/set-current` first").
 */
export async function resolveCurrentCharacter(
  discordUserId: string,
  explicit: string | null | undefined,
): Promise<string | undefined> {
  if (explicit) return explicit;
  const preference = await getPreference(discordUserId);
  return preference?.currentCharacterEntityId ?? undefined;
}

/** Same as {@link resolveCurrentCharacter}, for the default container. */
export async function resolveCurrentContainer(
  discordUserId: string,
  explicit: string | null | undefined,
): Promise<string | undefined> {
  if (explicit) return explicit;
  const preference = await getPreference(discordUserId);
  return preference?.currentContainerEntityId ?? undefined;
}
