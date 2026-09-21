import { ActionRowBuilder, StringSelectMenuBuilder } from "discord.js";

/**
 * `/container-new`'s "what goes inside" picker (ADR 0091) - pure builders,
 * mirroring format-drop.ts's split from drop.ts.
 *
 * The only state the pick needs is *which sack it fills*, and that rides in
 * the menu's own `customId` (`container-new:fill:<sack entity id>`), the same
 * stateless convention `/give`'s confirmation uses (ADR 0088): a click can
 * land on a different Cloud Run instance than the one that showed the menu.
 * commands/index.ts routes on the part before the first `:`.
 */
export const FILL_ACTION = "fill";

/** Discord's own cap on options in one select menu - the same limit
 * `/drop`'s menus (ADR 0052) live under. */
export const MAX_FILL_OPTIONS = 25;

const MAX_LABEL_LENGTH = 100;

export type LooseItem = Readonly<{ entityId: string; title: string; quantity: number | null }>;

export function buildFillCustomId(sackEntityId: string): string {
  return `container-new:${FILL_ACTION}:${sackEntityId}`;
}

/** The sack a `container-new:fill:<id>` customId refers to, or `undefined`
 * for anything else (another action, a malformed id). */
export function parseFillCustomId(customId: string): string | undefined {
  const [namespace, action, sackEntityId, ...rest] = customId.split(":");
  if (namespace !== "container-new" || action !== FILL_ACTION || rest.length > 0) return undefined;
  return sackEntityId || undefined;
}

function optionLabel(item: LooseItem): string {
  const label =
    item.quantity !== null && item.quantity > 1 ? `${item.title} ×${item.quantity}` : item.title;
  return label.slice(0, MAX_LABEL_LENGTH);
}

/** A multi-select over the given items (at most {@link MAX_FILL_OPTIONS} -
 * the caller says how many were left out). Allows picking any number, from
 * one to all of what's shown. */
export function buildFillComponents(
  sackEntityId: string,
  items: readonly LooseItem[],
): ActionRowBuilder<StringSelectMenuBuilder>[] {
  const shown = items.slice(0, MAX_FILL_OPTIONS);
  return [
    new ActionRowBuilder<StringSelectMenuBuilder>().addComponents(
      new StringSelectMenuBuilder()
        .setCustomId(buildFillCustomId(sackEntityId))
        .setPlaceholder("Choose what goes inside")
        .setMinValues(1)
        .setMaxValues(shown.length)
        .addOptions(shown.map((item) => ({ label: optionLabel(item), value: item.entityId }))),
    ),
  ];
}
