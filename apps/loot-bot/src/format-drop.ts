import {
  ActionRowBuilder,
  ButtonBuilder,
  ButtonStyle,
  EmbedBuilder,
  ModalBuilder,
  StringSelectMenuBuilder,
  TextInputBuilder,
  TextInputStyle,
} from "discord.js";
import type { LootClaim } from "./db.js";
import type { ItemInstanceOut } from "./lorenzo-client.js";

// Discord's own per-select-menu option cap - a drop with more unowned
// items than this just doesn't show the rest as choices (ADR 0044); the
// container listing itself is already capped to one page for the same
// reason (lorenzo-client.ts's getItemInstancesByContainer).
const MAX_SELECT_OPTIONS = 25;

export type DropItem = Readonly<{ entityId: string; title: string; quantity: number | null }>;

/**
 * The container's own listing, narrowed to what's actually still up for
 * grabs - an item with an owner has already been taken (whole, or down to
 * nothing left via split), and isn't shown as a take/claim choice at all
 * (ADR 0044: this bot's rendering only ever shows "what's left in the
 * pool," not a running history of what's already gone).
 */
export function availableDropItems(items: readonly ItemInstanceOut[]): DropItem[] {
  return items
    .filter((item) => item.owner_entity_id === null)
    .map((item) => ({
      entityId: item.entity_id,
      title: item.title ?? "(untitled)",
      quantity: item.quantity,
    }));
}

export function buildDropEmbed(
  items: readonly DropItem[],
  claims: readonly LootClaim[],
): EmbedBuilder {
  const embed = new EmbedBuilder().setTitle("Loot drop").setColor(0xc9a227);

  if (items.length === 0) {
    return embed.setDescription("Nothing left unclaimed in this drop.");
  }

  const lines = items.map((item) => {
    const amount = item.quantity !== null && item.quantity > 1 ? ` ×${item.quantity}` : "";
    const claimedBy = claims
      .filter((claim) => claim.itemEntityId === item.entityId)
      .map(
        (claim) =>
          `<@${claim.discordUserId}>${claim.quantity !== null ? ` (${claim.quantity})` : ""}`,
      );
    const claimText = claimedBy.length > 0 ? ` — claimed by ${claimedBy.join(", ")}` : "";
    return `**${item.title}**${amount}${claimText}`;
  });

  return embed.setDescription(lines.join("\n"));
}

/**
 * The take/claim select menus + apply-claims button (ADR 0044). Every
 * `customId` is namespaced `"drop:<action>:<dropId>"` - commands/index.ts's
 * dispatcher routes on the part before the first `:`.
 */
export function buildDropComponents(
  dropId: string,
  items: readonly DropItem[],
): (ActionRowBuilder<StringSelectMenuBuilder> | ActionRowBuilder<ButtonBuilder>)[] {
  const applyRow = new ActionRowBuilder<ButtonBuilder>().addComponents(
    new ButtonBuilder()
      .setCustomId(`drop:apply:${dropId}`)
      .setLabel("Apply claims")
      .setStyle(ButtonStyle.Primary),
  );

  if (items.length === 0) {
    return [applyRow];
  }

  const options = items.slice(0, MAX_SELECT_OPTIONS).map((item) => ({
    label:
      item.quantity !== null && item.quantity > 1 ? `${item.title} ×${item.quantity}` : item.title,
    value: item.entityId,
  }));

  const takeMenu = new ActionRowBuilder<StringSelectMenuBuilder>().addComponents(
    new StringSelectMenuBuilder()
      .setCustomId(`drop:take:${dropId}`)
      .setPlaceholder("Take an item")
      .addOptions(options),
  );
  const claimMenu = new ActionRowBuilder<StringSelectMenuBuilder>().addComponents(
    new StringSelectMenuBuilder()
      .setCustomId(`drop:claim:${dropId}`)
      .setPlaceholder("Claim / unclaim an item")
      .addOptions(options),
  );

  return [takeMenu, claimMenu, applyRow];
}

/** The quantity prompt shown after picking an item from either select
 * menu (ADR 0044) - `customId` bakes in which action and which item, so
 * the modal-submit handler needs no other state to know what to do. */
export function buildQuantityModal(
  action: "take" | "claim",
  dropId: string,
  itemEntityId: string,
): ModalBuilder {
  const input = new TextInputBuilder()
    .setCustomId("quantity")
    .setLabel("Quantity")
    .setPlaceholder(
      action === "take" ? "Leave blank to take all of it" : "Leave blank to claim whatever's left",
    )
    .setStyle(TextInputStyle.Short)
    .setRequired(false);
  return new ModalBuilder()
    .setCustomId(`drop:${action}-modal:${dropId}:${itemEntityId}`)
    .setTitle(action === "take" ? "Take item" : "Claim item")
    .addComponents(new ActionRowBuilder<TextInputBuilder>().addComponents(input));
}

export type ClaimOutcome = Readonly<{
  discordUserId: string;
  itemTitle: string;
  status: "given" | "not-enough-left" | "already-taken";
  quantity: number | null;
}>;

/** The final, static message apply-claims leaves behind - no components,
 * a plain record of what happened. */
export function buildApplySummaryEmbed(outcomes: readonly ClaimOutcome[]): EmbedBuilder {
  const embed = new EmbedBuilder().setTitle("Loot drop — claims applied").setColor(0xc9a227);

  if (outcomes.length === 0) {
    return embed.setDescription("No claims were outstanding.");
  }

  const lines = outcomes.map((outcome) => {
    const amount = outcome.quantity !== null ? `${outcome.quantity} of ` : "";
    if (outcome.status === "given") {
      return `<@${outcome.discordUserId}> got ${amount}**${outcome.itemTitle}**.`;
    }
    const reason = outcome.status === "already-taken" ? "already taken" : "not enough left";
    return `<@${outcome.discordUserId}>'s claim on **${outcome.itemTitle}** couldn't be honored (${reason}).`;
  });

  return embed.setDescription(lines.join("\n"));
}
