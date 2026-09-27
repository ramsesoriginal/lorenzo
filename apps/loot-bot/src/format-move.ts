import { ActionRowBuilder, ButtonBuilder, ButtonStyle } from "discord.js";

/**
 * `/move`'s "Move anyway" (ADR 0128) - a GM's answer to a move the API
 * refused because it wouldn't fit. Pure builders, no Discord API calls,
 * mirroring format-give.ts. The whole intent lives in the button's own
 * `customId` (ADR 0088's pattern): two entity ids fit Discord's
 * 100-character limit.
 */
export type MoveAnywayIntent = Readonly<{ itemEntityId: string; containerEntityId: string }>;

export function buildMoveAnywayCustomId(intent: MoveAnywayIntent): string {
  return `move:force:${intent.itemEntityId}:${intent.containerEntityId}`;
}

/** Inverse of {@link buildMoveAnywayCustomId}; `undefined` for anything else. */
export function parseMoveAnywayCustomId(customId: string): MoveAnywayIntent | undefined {
  const [namespace, action, itemEntityId, containerEntityId, ...rest] = customId.split(":");
  if (namespace !== "move" || action !== "force" || rest.length > 0) return undefined;
  if (!itemEntityId || !containerEntityId) return undefined;
  return { itemEntityId, containerEntityId };
}

export function buildMoveAnywayComponents(
  intent: MoveAnywayIntent,
): ActionRowBuilder<ButtonBuilder>[] {
  return [
    new ActionRowBuilder<ButtonBuilder>().addComponents(
      new ButtonBuilder()
        .setCustomId(buildMoveAnywayCustomId(intent))
        .setLabel("Move anyway")
        .setStyle(ButtonStyle.Danger),
    ),
  ];
}
