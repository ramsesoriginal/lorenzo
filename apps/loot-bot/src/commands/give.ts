import { SlashCommandBuilder } from "discord.js";
import {
  type ControlledCharacter,
  type ItemInstanceOut,
  type LorenzoApiClient,
  LorenzoApiError,
  createLorenzoApiClient,
} from "../lorenzo-client.js";
import { getValidAccessToken } from "../token-provider.js";
import type { Command } from "./types.js";

const MAX_AUTOCOMPLETE_CHOICES = 25;

type InventoryItem = Readonly<{ entityId: string; title: string; quantity: number | null }>;
type Choice = Readonly<{ name: string; value: string }>;

/**
 * `/give` - loot-splitting (ADR 0043). No `quantity`, or one that covers
 * the whole stack, transfers the source instance's ownership outright;
 * a smaller `quantity` splits that amount off first (POST .../split) and
 * transfers only the split-off instance - see ADR 0043 for the full
 * split-vs-transfer reasoning and why the item's container is left
 * untouched either way.
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
      const items = await findMyItems(client, tenantId, accessToken);
      const choices = items.map((item) => ({
        name: formatItemChoiceName(item),
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
      // Fresh state, not whatever autocomplete last showed - the quantity
      // decision below has to be correct now, not a moment ago (ADR 0043).
      const current = await client.getItemInstance(tenantId, itemEntityId, accessToken);

      if (requestedQuantity !== null && current.quantity === null) {
        await interaction.editReply(
          "That item isn't a stack — omit the quantity to give the whole thing.",
        );
        return;
      }

      const currentQuantity = current.quantity ?? 1;
      const splitting = requestedQuantity !== null && requestedQuantity < currentQuantity;

      const given = splitting
        ? await giveSplit(
            client,
            tenantId,
            itemEntityId,
            requestedQuantity,
            targetCharacterId,
            accessToken,
          )
        : await client.setItemInstanceOwner(tenantId, itemEntityId, targetCharacterId, accessToken);

      const targetName = await client
        .getCharacterName(tenantId, targetCharacterId, accessToken)
        .catch(() => "them");
      const itemName = given.title ?? "(untitled)";
      const amount = splitting ? `${requestedQuantity} of ` : "";
      await interaction.editReply(`Gave ${amount}${itemName} to ${targetName}.`);
    } catch (error) {
      if (error instanceof LorenzoApiError) {
        await interaction.editReply(describeGiveError(error));
        return;
      }
      throw error;
    }
  },
};

// `requestedQuantity` is a plain `number` here (not `number | null`) purely
// to keep the call site above's ternary honest about which branch actually
// needs it - splitting is only ever true when it's already non-null.
async function giveSplit(
  client: LorenzoApiClient,
  tenantId: string,
  sourceEntityId: string,
  requestedQuantity: number,
  targetCharacterId: string,
  accessToken: string,
): Promise<ItemInstanceOut> {
  const split = await client.splitItemInstance(
    tenantId,
    sourceEntityId,
    requestedQuantity,
    accessToken,
  );
  return client.setItemInstanceOwner(tenantId, split.entity_id, targetCharacterId, accessToken);
}

async function findMyItems(
  client: LorenzoApiClient,
  tenantId: string,
  accessToken: string,
): Promise<readonly InventoryItem[]> {
  const players = await client.getMyPlayers(tenantId, accessToken);
  const characters = players.flatMap((player) => player.characters);

  const perCharacter = await Promise.all(
    characters.map(async (character) => {
      const response = await client.getItemInstancesOwnedBy(
        tenantId,
        character.entityId,
        accessToken,
      );
      return response.groups.flatMap((group) =>
        group.item_instances.map((item) => ({
          entityId: item.entity_id,
          title: item.title ?? "(untitled)",
          quantity: item.quantity,
        })),
      );
    }),
  );
  return perCharacter.flat();
}

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
    // autocomplete is a convenience, never authoritative (ADR 0043), so a
    // failed/ambiguous lookup here just falls back to "every campaign I'm
    // in" rather than failing the whole autocomplete request.
    try {
      const item = await client.getItemInstance(tenantId, chosenItemId, accessToken);
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

function formatItemChoiceName(item: InventoryItem): string {
  return item.quantity !== null && item.quantity > 1
    ? `${item.title} ×${item.quantity}`
    : item.title;
}

function filterChoices(choices: readonly Choice[], typed: string): Choice[] {
  const needle = typed.toLowerCase();
  return choices
    .filter((choice) => choice.name.toLowerCase().includes(needle))
    .slice(0, MAX_AUTOCOMPLETE_CHOICES);
}

function describeGiveError(error: LorenzoApiError): string {
  switch (error.status) {
    case 403:
      return "That's not something you can give away — it isn't reachable from any of your characters.";
    case 404:
      return "Couldn't find that item or that character anymore — run `/give` again and re-pick from the suggestions.";
    case 422:
      return `Couldn't do that: ${error.message}`;
    default:
      return "Something went wrong giving that item away.";
  }
}
