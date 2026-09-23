import { SlashCommandBuilder } from "discord.js";
import {
  GIVE_CANCEL_CUSTOM_ID,
  type GiveIntent,
  buildGiveConfirmComponents,
  formatGivePrompt,
  parseGiveConfirmCustomId,
} from "../format-give.js";
import {
  type ControlledCharacter,
  type LorenzoApiClient,
  LorenzoApiError,
  createLorenzoApiClient,
} from "../lorenzo-client.js";
import { getValidAccessToken } from "../token-provider.js";
import { recordUndo } from "../undo-actions.js";
import { filterChoices, formatItemChoiceName } from "./autocomplete.js";
import { transferItem } from "./item-transfer.js";
import { rememberActingCharacter } from "./remember-character.js";
import type { ButtonInteraction, Command, CommandContext } from "./types.js";

/**
 * `/give` - loot-splitting (ADR 0051). No `quantity`, or one that covers
 * the whole stack, transfers the source instance's ownership outright;
 * a smaller `quantity` splits that amount off first (POST .../split) and
 * transfers only the split-off instance - see ADR 0051 for the full
 * split-vs-transfer reasoning and why the item's container is left
 * untouched either way.
 *
 * Nothing moves when the command runs: it shows what's about to leave the
 * caller's inventory and waits for one click on "Give" (ADR 0088). The
 * transfer itself happens in `onButton`, re-validated against fresh state
 * exactly as the command used to do inline.
 */
export const giveCommand: Command = {
  definition: new SlashCommandBuilder()
    .setName("give")
    .setDescription("Give one of your items to another character.")
    .addStringOption((opt) =>
      opt
        .setName("item")
        .setDescription("The item to give")
        .setRequired(true)
        .setAutocomplete(true),
    )
    .addStringOption((opt) =>
      opt.setName("to").setDescription("Who to give it to").setRequired(true).setAutocomplete(true),
    )
    .addIntegerOption((opt) =>
      opt
        .setName("quantity")
        .setDescription("How many to give, for a stack (default: all of it)")
        .setRequired(false)
        .setMinValue(1),
    ),

  async autocomplete(interaction, ctx) {
    const focused = interaction.options.getFocused(true);
    const accessToken = await getValidAccessToken(interaction.user.id);
    if (!accessToken) {
      await interaction.respond([]);
      return;
    }

    const client = createLorenzoApiClient(ctx.config.lorenzoApiBaseUrl);
    const tenantId = ctx.config.lorenzoTenantId;

    if (focused.name === "item") {
      const items = await client.getMyItemInstances(tenantId, accessToken);
      const choices = items.map((item) => ({
        name: formatItemChoiceName(item.title, item.quantity),
        value: item.entityId,
      }));
      await interaction.respond(filterChoices(choices, focused.value));
      return;
    }

    if (focused.name === "to") {
      const chosenItemId = interaction.options.getString("item");
      const characters = await findGiveTargets(client, tenantId, accessToken, chosenItemId);
      const choices = characters.map((c) => ({ name: c.name, value: c.entityId }));
      await interaction.respond(filterChoices(choices, focused.value));
    }
  },

  async execute(interaction, ctx) {
    await interaction.deferReply({ ephemeral: true });

    const accessToken = await getValidAccessToken(interaction.user.id);
    if (!accessToken) {
      await interaction.editReply("You haven't linked your account yet — run `/link` first.");
      return;
    }

    const itemEntityId = interaction.options.getString("item", true);
    const targetCharacterId = interaction.options.getString("to", true);
    const requestedQuantity = interaction.options.getInteger("quantity");

    const client = createLorenzoApiClient(ctx.config.lorenzoApiBaseUrl);
    const tenantId = ctx.config.lorenzoTenantId;

    try {
      // Read now, only to word the prompt and fail early on the things that
      // can never work (unreachable item, unknown target, a quantity on a
      // non-stack) instead of costing a click first. Nothing here decides
      // the transfer - `onButton` re-reads before writing (ADR 0051).
      const { data: current } = await client.getItemInstance(tenantId, itemEntityId, accessToken);
      if (requestedQuantity !== null && current.quantity === null) {
        await interaction.editReply(NOT_A_STACK_MESSAGE);
        return;
      }
      const targetName = await client.getCharacterName(tenantId, targetCharacterId, accessToken);

      const intent: GiveIntent = {
        itemEntityId,
        targetCharacterId,
        quantity: requestedQuantity,
      };
      await interaction.editReply({
        content: formatGivePrompt(
          current.title ?? "(untitled)",
          current.quantity,
          requestedQuantity,
          targetName,
        ),
        components: buildGiveConfirmComponents(intent),
      });
    } catch (error) {
      if (error instanceof LorenzoApiError) {
        await interaction.editReply(describeGiveError(error));
        return;
      }
      throw error;
    }
  },

  async onButton(interaction, ctx) {
    if (interaction.customId === GIVE_CANCEL_CUSTOM_ID) {
      await interaction.update({ content: "Cancelled — nothing was given.", components: [] });
      return;
    }

    const intent = parseGiveConfirmCustomId(interaction.customId);
    if (!intent) {
      await interaction.update({
        content: "That confirmation isn't valid anymore — run `/give` again.",
        components: [],
      });
      return;
    }

    // The click's own acknowledgement also strips the buttons, so a second
    // click on a message that already lost them can't confirm twice - a
    // partial give is a split, and splitting twice isn't idempotent.
    await interaction.update({ content: "Giving…", components: [] });
    await confirmGive(interaction, ctx, intent);
  },
};

async function confirmGive(
  interaction: ButtonInteraction,
  ctx: CommandContext,
  intent: GiveIntent,
): Promise<void> {
  const accessToken = await getValidAccessToken(interaction.user.id);
  if (!accessToken) {
    await interaction.editReply("You haven't linked your account yet — run `/link` first.");
    return;
  }

  const client = createLorenzoApiClient(ctx.config.lorenzoApiBaseUrl);
  const tenantId = ctx.config.lorenzoTenantId;

  try {
    // Fresh state, not whatever the prompt or autocomplete last showed - the
    // quantity decision below has to be correct now, not a moment ago (ADR
    // 0051), and the prompt may have sat there a while.
    const { data: current, etag } = await client.getItemInstance(
      tenantId,
      intent.itemEntityId,
      accessToken,
    );

    const result = await transferItem(
      client,
      tenantId,
      current,
      etag,
      intent.quantity,
      intent.targetCharacterId,
      accessToken,
    );

    if (result.kind === "not-a-stack") {
      await interaction.editReply(NOT_A_STACK_MESSAGE);
      return;
    }

    if (current.owner_entity_id) {
      await recordUndo(interaction.user.id, {
        kind: "restore-owner",
        entityId: result.given.entity_id,
        previousOwnerCharacterId: current.owner_entity_id,
      });
    }
    await rememberActingCharacter(
      client,
      tenantId,
      accessToken,
      interaction.user.id,
      current.owner_entity_id,
      ctx.logger,
    );

    const targetLookup = await client
      .getCharacterName(tenantId, intent.targetCharacterId, accessToken)
      .catch(() => null);
    const targetName = targetLookup ?? "them";
    const itemName = result.given.title ?? "(untitled)";
    const amount = result.splitting ? `${result.requestedQuantity} of ` : "";

    await interaction.editReply(`Gave ${amount}${itemName} to ${targetName}.`);
  } catch (error) {
    if (error instanceof LorenzoApiError) {
      await interaction.editReply(describeGiveError(error));
      return;
    }
    throw error;
  }
}

const NOT_A_STACK_MESSAGE = "That item isn't a stack — omit the quantity to give the whole thing.";

async function findGiveTargets(
  client: LorenzoApiClient,
  tenantId: string,
  accessToken: string,
  chosenItemId: string | null,
): Promise<readonly ControlledCharacter[]> {
  const players = await client.getMyPlayers(tenantId, accessToken);
  let campaignIds: readonly string[] = players.map((player) => player.campaignId);

  if (chosenItemId) {
    // Narrow to the chosen item's own campaign, if we can tell which one -
    // autocomplete is a convenience, never authoritative (ADR 0051), so a
    // failed/ambiguous lookup here just falls back to "every campaign I'm
    // in" rather than failing the whole autocomplete request.
    try {
      const { data: item } = await client.getItemInstance(tenantId, chosenItemId, accessToken);
      const owningPlayer = players.find((player) =>
        player.characters.some((c) => c.entityId === item.owner_entity_id),
      );
      if (owningPlayer) campaignIds = [owningPlayer.campaignId];
    } catch {
      // fall through to the unnarrowed campaignIds above
    }
  }

  const rosters = await Promise.all(
    campaignIds.map((campaignId) => client.getCampaignPlayers(tenantId, campaignId, accessToken)),
  );
  const byId = new Map(rosters.flat().map((character) => [character.entityId, character]));
  return [...byId.values()];
}

function describeGiveError(error: LorenzoApiError): string {
  switch (error.status) {
    case 403:
      return "That's not something you can give away — it isn't reachable from any of your characters.";
    case 404:
      return "Couldn't find that item or that character anymore — run `/give` again and re-pick from the suggestions.";
    case 412:
      return "Someone else changed that item just now — run `/give` again to pick it up with the current state.";
    case 422:
      return `Couldn't do that: ${error.message}`;
    default:
      return "Something went wrong giving that item away.";
  }
}
