import {
  ActionRowBuilder,
  type SelectMenuComponentOptionData,
  SlashCommandBuilder,
  StringSelectMenuBuilder,
} from "discord.js";
import { type BulkAssignResultItem, createLorenzoApiClient } from "../lorenzo-client.js";
import { consumePendingBulkGive, storePendingBulkGive } from "../pending-bulk-give.js";
import { getValidAccessToken } from "../token-provider.js";
import { formatItemChoiceName } from "./autocomplete.js";
import type { Command } from "./types.js";

// Discord's own per-select-menu option cap - same convention `/drop`'s own
// take/claim menus already follow (format-drop.ts).
const MAX_SELECT_OPTIONS = 25;

/**
 * `/give-bulk` - give several of the caller's own items to one character
 * in a single flow (ADR 0064). No API change: `POST .../item-instances/
 * bulk-assign` already exists, is already self-or-managed authorized (a
 * player can already batch-reassign their own items), and is already used
 * server-side by `/drop`'s own apply-claims - just never exposed as an
 * everyday player command before.
 *
 * A slash command's own options can't repeat, so picking "several items"
 * needs its own interactive message: a multi-select for items, then a
 * second select for the target character, mirroring `/drop`'s existing
 * select-menu-driven pattern rather than trying to cram a variable-length
 * list into string options. The chosen item ids are handed between the two
 * steps via `pending-bulk-give.ts`'s short-lived token, not the customId
 * itself - Discord caps a customId at 100 characters, nowhere near enough
 * for several full item-instance UUIDs. Whole-instance transfers only in
 * this first cut - no per-item partial-stack quantity yet.
 */
export const giveBulkCommand: Command = {
  definition: new SlashCommandBuilder()
    .setName("give-bulk")
    .setDescription("Give several of your own items to another character at once."),

  async execute(interaction, ctx) {
    await interaction.deferReply({ ephemeral: true });

    const accessToken = await getValidAccessToken(interaction.user.id);
    if (!accessToken) {
      await interaction.editReply("You haven't linked your account yet — run `/link` first.");
      return;
    }

    const client = createLorenzoApiClient(ctx.config.lorenzoApiBaseUrl);
    const tenantId = ctx.config.lorenzoTenantId;
    const items = await client.getMyItemInstances(tenantId, accessToken);

    if (items.length === 0) {
      await interaction.editReply("You don't have any items to give.");
      return;
    }

    const options: SelectMenuComponentOptionData[] = items
      .slice(0, MAX_SELECT_OPTIONS)
      .map((item) => ({
        label: formatItemChoiceName(item.title, item.quantity),
        value: item.entityId,
      }));

    const menu = new StringSelectMenuBuilder()
      .setCustomId("give-bulk:pick-items")
      .setPlaceholder("Pick every item to give")
      .setMinValues(1)
      .setMaxValues(options.length)
      .addOptions(options);

    await interaction.editReply({
      content: "Pick every item you want to give, then who to give them to.",
      components: [new ActionRowBuilder<StringSelectMenuBuilder>().addComponents(menu)],
    });
  },

  async onSelectMenu(interaction, ctx) {
    const [, action, token] = interaction.customId.split(":");
    const accessToken = await getValidAccessToken(interaction.user.id);
    if (!accessToken) {
      await interaction.update({
        content: "You haven't linked your account yet — run `/link` first.",
        components: [],
      });
      return;
    }

    const client = createLorenzoApiClient(ctx.config.lorenzoApiBaseUrl);
    const tenantId = ctx.config.lorenzoTenantId;

    if (action === "pick-items") {
      const pendingToken = storePendingBulkGive({
        discordUserId: interaction.user.id,
        itemEntityIds: interaction.values,
      });

      const players = await client.getMyPlayers(tenantId, accessToken);
      const characters = players.flatMap((player) => player.characters);
      if (characters.length === 0) {
        await interaction.update({
          content: "You don't control any characters to give to.",
          components: [],
        });
        return;
      }

      const options: SelectMenuComponentOptionData[] = characters
        .slice(0, MAX_SELECT_OPTIONS)
        .map((character) => ({ label: character.name, value: character.entityId }));
      const menu = new StringSelectMenuBuilder()
        .setCustomId(`give-bulk:pick-target:${pendingToken}`)
        .setPlaceholder("Who to give them to")
        .addOptions(options);

      await interaction.update({
        content: `Giving ${interaction.values.length} item(s) — now pick who to give them to.`,
        components: [new ActionRowBuilder<StringSelectMenuBuilder>().addComponents(menu)],
      });
      return;
    }

    if (action === "pick-target" && token) {
      const pending = consumePendingBulkGive(token);
      if (!pending || pending.discordUserId !== interaction.user.id) {
        await interaction.update({
          content: "This selection expired — run `/give-bulk` again.",
          components: [],
        });
        return;
      }

      const targetCharacterId = interaction.values[0];
      if (!targetCharacterId) return;

      const results = await client.bulkAssignItemInstances(
        tenantId,
        pending.itemEntityIds.map((entityId) => ({
          entity_id: entityId,
          owner_character_id: targetCharacterId,
        })),
        accessToken,
      );
      const targetName = await client
        .getCharacterName(tenantId, targetCharacterId, accessToken)
        .catch(() => "them");

      await interaction.update({
        content: formatBulkGiveSummary(results, targetName),
        components: [],
      });
    }
  },
};

function formatBulkGiveSummary(
  results: readonly BulkAssignResultItem[],
  targetName: string,
): string {
  const succeeded = results.filter((result) => result.status === "ok").length;
  const failed = results.filter((result) => result.status !== "ok").length;
  const lines = [`Gave ${succeeded} item${succeeded === 1 ? "" : "s"} to ${targetName}.`];
  if (failed > 0) {
    lines.push(`${failed} couldn't be given — they may no longer be reachable from you.`);
  }
  return lines.join("\n");
}
