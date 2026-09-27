import { ActionRowBuilder, ButtonBuilder, ButtonStyle } from "discord.js";

/**
 * `/move`'s "Move anyway" (ADR 0128) - a GM's answer to a move the API
 * refused because it wouldn't fit or because something is bound. For
 * binding, "Move and lift binding" (ADR 0129) also lifts it for good. Pure
 * builders, no Discord API calls, mirroring format-give.ts. The whole
 * intent lives in the button's own `customId` (ADR 0088's pattern): two
 * entity ids fit Discord's 100-character limit.
 */
export type MoveAnywayIntent = Readonly<{
  itemEntityId: string;
  containerEntityId: string;
  /** Also lift the item's binding, so it won't bind again. */
  lift: boolean;
}>;

export function buildMoveAnywayCustomId(intent: MoveAnywayIntent): string {
  const action = intent.lift ? "lift" : "force";
  return `move:${action}:${intent.itemEntityId}:${intent.containerEntityId}`;
}

/** Inverse of {@link buildMoveAnywayCustomId}; `undefined` for anything else. */
export function parseMoveAnywayCustomId(customId: string): MoveAnywayIntent | undefined {
  const [namespace, action, itemEntityId, containerEntityId, ...rest] = customId.split(":");
  if (namespace !== "move" || (action !== "force" && action !== "lift") || rest.length > 0) {
    return undefined;
  }
  if (!itemEntityId || !containerEntityId) return undefined;
  return { itemEntityId, containerEntityId, lift: action === "lift" };
}

/** "Move anyway", and for a binding "Move and lift binding" beside it. */
export function buildMoveAnywayComponents(
  move: Omit<MoveAnywayIntent, "lift">,
  { offerLift }: { offerLift: boolean },
): ActionRowBuilder<ButtonBuilder>[] {
  const row = new ActionRowBuilder<ButtonBuilder>().addComponents(
    new ButtonBuilder()
      .setCustomId(buildMoveAnywayCustomId({ ...move, lift: false }))
      .setLabel("Move anyway")
      .setStyle(ButtonStyle.Danger),
  );
  if (offerLift) {
    row.addComponents(
      new ButtonBuilder()
        .setCustomId(buildMoveAnywayCustomId({ ...move, lift: true }))
        .setLabel("Move and lift binding")
        .setStyle(ButtonStyle.Danger),
    );
  }
  return [row];
}
