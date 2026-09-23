import { ActionRowBuilder, ButtonBuilder, ButtonStyle } from "discord.js";

/**
 * `/give`'s confirmation step (ADR 0088) - pure builders, no Discord API
 * calls, mirroring format-drop.ts's split from drop.ts.
 *
 * The whole intent lives in the confirm button's own `customId`, not in
 * bot-side state: the click can land on a different Cloud Run instance than
 * the one that showed the prompt (ADR 0053's scale-out), so an in-memory
 * pending-action map (`pending-bulk-give.ts`'s shape) would sometimes lose
 * it. Two entity ids plus a quantity fit Discord's 100-character `customId`
 * limit even at the largest quantity an integer option can carry - pinned
 * by a test, since exceeding it fails at send time, not compile time.
 */
export type GiveIntent = Readonly<{
  itemEntityId: string;
  targetCharacterId: string;
  /** `null` means "all of it" - `/give`'s own omitted-quantity meaning. */
  quantity: number | null;
}>;

export const GIVE_CONFIRM_ACTION = "ok";
export const GIVE_CANCEL_CUSTOM_ID = "give:no";

const ALL = "all";

export function buildGiveConfirmCustomId(intent: GiveIntent): string {
  return `give:${GIVE_CONFIRM_ACTION}:${intent.itemEntityId}:${intent.targetCharacterId}:${intent.quantity ?? ALL}`;
}

/** Inverse of {@link buildGiveConfirmCustomId}; `undefined` for anything
 * that isn't a well-formed confirm id, rather than guessing at it. */
export function parseGiveConfirmCustomId(customId: string): GiveIntent | undefined {
  const [namespace, action, itemEntityId, targetCharacterId, quantityPart, ...rest] =
    customId.split(":");
  if (namespace !== "give" || action !== GIVE_CONFIRM_ACTION || rest.length > 0) return undefined;
  if (!itemEntityId || !targetCharacterId || !quantityPart) return undefined;

  if (quantityPart === ALL) return { itemEntityId, targetCharacterId, quantity: null };
  if (!/^\d+$/.test(quantityPart)) return undefined;
  const quantity = Number(quantityPart);
  if (!Number.isSafeInteger(quantity) || quantity < 1) return undefined;
  return { itemEntityId, targetCharacterId, quantity };
}

export function buildGiveConfirmComponents(intent: GiveIntent): ActionRowBuilder<ButtonBuilder>[] {
  return [
    new ActionRowBuilder<ButtonBuilder>().addComponents(
      new ButtonBuilder()
        .setCustomId(buildGiveConfirmCustomId(intent))
        .setLabel("Give")
        .setStyle(ButtonStyle.Primary),
      new ButtonBuilder()
        .setCustomId(GIVE_CANCEL_CUSTOM_ID)
        .setLabel("Cancel")
        .setStyle(ButtonStyle.Secondary),
    ),
  ];
}

/** What's about to leave the caller's inventory, worded from the *current*
 * state of the stack - "all 5 Torch" vs "2 of Torch (you have 5)". */
export function formatGivePrompt(
  title: string,
  currentQuantity: number | null,
  requestedQuantity: number | null,
  targetName: string,
): string {
  const partial =
    requestedQuantity !== null && currentQuantity !== null && requestedQuantity < currentQuantity;
  if (partial) {
    return `Give **${requestedQuantity} of ${title}** (you have ${currentQuantity}) to **${targetName}**?`;
  }
  const stack = currentQuantity !== null && currentQuantity > 1;
  return `Give **${title}${stack ? ` ×${currentQuantity}` : ""}** to **${targetName}**?`;
}
