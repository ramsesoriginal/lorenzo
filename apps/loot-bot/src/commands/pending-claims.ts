import { SlashCommandBuilder } from "discord.js";
import { listLootClaims, listOpenLootDrops } from "../db.js";
import { type PendingDropSummary, formatPendingDropsEmbed } from "../format-drop.js";
import { createLorenzoApiClient } from "../lorenzo-client.js";
import { getValidAccessToken } from "../token-provider.js";
import type { Command } from "./types.js";

/**
 * `/pending-claims` - every currently-open drop's outstanding claims,
 * across the whole server (ADR 0064). Deliberately not GM-gated, unlike
 * every other new drop affordance - a long-running drop's own message can
 * scroll out of view, and anyone should be able to check what's still
 * outstanding without asking a GM. Bot-local only (`loot_drop`/
 * `loot_claim` never touch apps/api, ADR 0052) plus one read per drop to
 * resolve item/container titles.
 */
export const pendingClaimsCommand: Command = {
  definition: new SlashCommandBuilder()
    .setName("pending-claims")
    .setDescription("List every drop with outstanding claims, across the server."),

  async execute(interaction, ctx) {
    await interaction.deferReply({ ephemeral: true });

    const accessToken = await getValidAccessToken(interaction.user.id);
    if (!accessToken) {
      await interaction.editReply("You haven't linked your account yet — run `/link` first.");
      return;
    }

    const client = createLorenzoApiClient(ctx.config.lorenzoApiBaseUrl);
    const tenantId = ctx.config.lorenzoTenantId;
    const drops = await listOpenLootDrops();

    const summaries: PendingDropSummary[] = await Promise.all(
      drops.map(async (drop) => {
        const [items, claims, containerTitle] = await Promise.all([
          client
            .getItemInstancesByContainer(tenantId, drop.containerEntityId, accessToken)
            .catch(() => []),
          listLootClaims(drop.id),
          client
            .getItemInstance(tenantId, drop.containerEntityId, accessToken)
            .then(({ data }) => data.title ?? "(untitled)")
            .catch(() => "(container)"),
        ]);
        const titleByItemId = new Map(
          items.map((item) => [item.entity_id, item.title ?? "(untitled)"]),
        );

        return {
          discordChannelId: drop.discordChannelId,
          discordMessageId: drop.discordMessageId,
          containerTitle,
          claims: claims.map((claim) => ({
            discordUserId: claim.discordUserId,
            itemTitle: titleByItemId.get(claim.itemEntityId) ?? "(item no longer available)",
            quantity: claim.quantity,
            claimType: claim.claimType,
          })),
        };
      }),
    );

    await interaction.editReply({
      embeds: [formatPendingDropsEmbed(ctx.config.discordGuildId, summaries)],
    });
  },
};
