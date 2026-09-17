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
import type { ClaimType, LootClaim } from "./db.js";
import type { ItemInstanceOut } from "./lorenzo-client.js";

// Discord's own per-select-menu option cap - a drop with more unowned
// items than this just doesn't show the rest as choices (ADR 0052); the
// container listing itself is already capped to one page for the same
// reason (lorenzo-client.ts's getItemInstancesByContainer).
const MAX_SELECT_OPTIONS = 25;

export type DropItem = Readonly<{ entityId: string; title: string; quantity: number | null }>;

/**
 * The container's own listing, narrowed to what's actually still up for
 * grabs - an item with an owner has already been taken (whole, or down to
 * nothing left via split), and isn't shown as a take/claim choice at all
 * (ADR 0052: this bot's rendering only ever shows "what's left in the
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
      .map((claim) => {
        const details = [
          claim.quantity !== null ? String(claim.quantity) : undefined,
          claim.claimType === "need" ? "need" : undefined,
        ].filter((d) => d !== undefined);
        return `<@${claim.discordUserId}>${details.length > 0 ? ` (${details.join(", ")})` : ""}`;
      });
    const claimText = claimedBy.length > 0 ? ` — claimed by ${claimedBy.join(", ")}` : "";
    return `**${item.title}**${amount}${claimText}`;
  });

  return embed.setDescription(lines.join("\n"));
}

/**
 * The take/claim select menus + apply/clear-claims buttons (ADR 0052/0064).
 * Every `customId` is namespaced `"drop:<action>:<dropId>"` -
 * commands/index.ts's dispatcher routes on the part before the first `:`.
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
    new ButtonBuilder()
      .setCustomId(`drop:clear:${dropId}`)
      .setLabel("Clear claims")
      .setStyle(ButtonStyle.Danger),
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
 * menu (ADR 0052) - `customId` bakes in which action and which item, so
 * the modal-submit handler needs no other state to know what to do. A
 * "claim" also asks for need-vs-greed (ADR 0064) - a second text field, not
 * a separate step: Discord modals only support text inputs, no
 * buttons/selects, so this is the only way to ask for it without adding a
 * whole extra interaction round-trip. */
export function buildQuantityModal(
  action: "take" | "claim",
  dropId: string,
  itemEntityId: string,
): ModalBuilder {
  const quantityInput = new TextInputBuilder()
    .setCustomId("quantity")
    .setLabel("Quantity")
    .setPlaceholder(
      action === "take" ? "Leave blank to take all of it" : "Leave blank to claim whatever's left",
    )
    .setStyle(TextInputStyle.Short)
    .setRequired(false);
  const rows = [new ActionRowBuilder<TextInputBuilder>().addComponents(quantityInput)];

  if (action === "claim") {
    const claimTypeInput = new TextInputBuilder()
      .setCustomId("claim-type")
      .setLabel("Need or greed?")
      .setPlaceholder("Type need or greed - blank defaults to greed")
      .setStyle(TextInputStyle.Short)
      .setRequired(false);
    rows.push(new ActionRowBuilder<TextInputBuilder>().addComponents(claimTypeInput));
  }

  return new ModalBuilder()
    .setCustomId(`drop:${action}-modal:${dropId}:${itemEntityId}`)
    .setTitle(action === "take" ? "Take item" : "Claim item")
    .addComponents(...rows);
}

/** Parses the claim modal's "need or greed?" text field - anything other
 * than a case-insensitive "need" is treated as greed, matching the field's
 * own "blank defaults to greed" placeholder. */
export function parseClaimType(raw: string): ClaimType {
  return raw.trim().toLowerCase() === "need" ? "need" : "greed";
}

export type PendingDropClaim = Readonly<{
  discordUserId: string;
  itemTitle: string;
  quantity: number | null;
  claimType: string;
}>;

export type PendingDropSummary = Readonly<{
  discordChannelId: string;
  discordMessageId: string | null;
  containerTitle: string;
  claims: readonly PendingDropClaim[];
}>;

/** `/pending-claims` (ADR 0064) - everyone's own cross-channel summary of
 * every currently-open drop, not just GMs (unlike every other new drop
 * affordance) - a long-running drop's own message can scroll out of view,
 * and checking what's still outstanding shouldn't require a GM. */
export function formatPendingDropsEmbed(
  guildId: string,
  drops: readonly PendingDropSummary[],
): EmbedBuilder {
  const embed = new EmbedBuilder().setTitle("Pending loot drops").setColor(0xc9a227);

  if (drops.length === 0) {
    return embed.setDescription("No pending drops.");
  }

  for (const drop of drops) {
    const jumpLink = drop.discordMessageId
      ? `https://discord.com/channels/${guildId}/${drop.discordChannelId}/${drop.discordMessageId}`
      : undefined;
    const header = `<#${drop.discordChannelId}>${jumpLink ? ` — [jump to message](${jumpLink})` : ""}`;

    const claimLines =
      drop.claims.length > 0
        ? drop.claims
            .map((claim) => {
              const amount = claim.quantity !== null ? `${claim.quantity} of ` : "";
              const tier = claim.claimType === "need" ? " (need)" : "";
              return `<@${claim.discordUserId}> wants ${amount}**${claim.itemTitle}**${tier}`;
            })
            .join("\n")
        : "Nothing claimed yet.";

    embed.addFields({ name: drop.containerTitle, value: `${header}\n${claimLines}` });
  }

  return embed;
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
