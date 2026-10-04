import { SlashCommandBuilder } from "discord.js";
import {
  buildGiveConfirmComponents,
  formatGivePrompt,
  GIVE_CANCEL_CUSTOM_ID,
  type GiveIntent,
  type GiveWithContentsIntent,
  parseGiveConfirmCustomId,
  parseGiveWithContentsCustomId,
} from "../format-give.js";
import {
  formatGivenWithContents,
  formatWithContentsNote,
  givenCount,
} from "../format-give-contents.js";
import {
  type BulkAssignItem,
  type BulkAssignResultItem,
  type ContentsResultItem,
  type ControlledCharacter,
  createLorenzoApiClient,
  type LorenzoApiClient,
  LorenzoApiError,
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
 *
 * A whole container with something inside that could go along also gets
 * "Give with what's inside" (ADR 0125), worded from a dry run: how many
 * things would go, and whose the rest stay.
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
      const targetName = await targetNameOf(client, tenantId, targetCharacterId, accessToken);

      const intent: GiveIntent = {
        itemEntityId,
        targetCharacterId,
        quantity: requestedQuantity,
      };
      const contents =
        requestedQuantity === null && current.is_container === true
          ? await contentsGivenAlong(client, tenantId, intent, accessToken)
          : [];
      const withContents = givenCount(contents) > 0;
      const prompt = formatGivePrompt(
        current.title ?? "(untitled)",
        current.quantity,
        requestedQuantity,
        targetName,
      );
      await interaction.editReply({
        content: withContents ? `${prompt}\n${formatWithContentsNote(contents)}` : prompt,
        components: buildGiveConfirmComponents(intent, { withContents }),
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

    const withContents = parseGiveWithContentsCustomId(interaction.customId);
    if (withContents) {
      await interaction.update({ content: "Giving…", components: [] });
      await confirmGiveWithContents(interaction, ctx, withContents);
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

    const targetLookup = await targetNameOf(
      client,
      tenantId,
      intent.targetCharacterId,
      accessToken,
    ).catch(() => null);
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

/** A whole container, to its target, with everything inside it (ADR 0125). */
function withContentsEntry(intent: GiveWithContentsIntent): BulkAssignItem {
  return {
    entity_id: intent.itemEntityId,
    owner_character_id: intent.targetCharacterId,
    move_to_owner: false,
    with_contents: true,
    override: false,
    lift_binding: false,
  };
}

/** What giving with what's inside would take along, from a dry run (ADR
 * 0125) - nothing when the dry run can't say, so the prompt just offers the
 * plain give. */
async function contentsGivenAlong(
  client: LorenzoApiClient,
  tenantId: string,
  intent: GiveWithContentsIntent,
  accessToken: string,
): Promise<readonly ContentsResultItem[]> {
  try {
    const [preview] = await client.bulkAssignItemInstances(
      tenantId,
      [withContentsEntry(intent)],
      accessToken,
      { dryRun: true },
    );
    return preview?.status === "ok" ? preview.contents : [];
  } catch (error) {
    if (error instanceof LorenzoApiError) return [];
    throw error;
  }
}

async function confirmGiveWithContents(
  interaction: ButtonInteraction,
  ctx: CommandContext,
  intent: GiveWithContentsIntent,
): Promise<void> {
  const accessToken = await getValidAccessToken(interaction.user.id);
  if (!accessToken) {
    await interaction.editReply("You haven't linked your account yet — run `/link` first.");
    return;
  }

  const client = createLorenzoApiClient(ctx.config.lorenzoApiBaseUrl);
  const tenantId = ctx.config.lorenzoTenantId;

  try {
    const { data: current, etag } = await client.getItemInstance(
      tenantId,
      intent.itemEntityId,
      accessToken,
    );
    const [result] = await client.bulkAssignItemInstances(
      tenantId,
      [{ ...withContentsEntry(intent), ...(etag !== null ? { if_match: etag } : {}) }],
      accessToken,
    );
    if (!result || result.status === "error") {
      await interaction.editReply(describeGiveError(problemError(result)));
      return;
    }

    // No Undo: it would only give the container back, not what went with it.
    await rememberActingCharacter(
      client,
      tenantId,
      accessToken,
      interaction.user.id,
      current.owner_entity_id,
      ctx.logger,
    );
    const targetLookup = await targetNameOf(
      client,
      tenantId,
      intent.targetCharacterId,
      accessToken,
    ).catch(() => null);
    await interaction.editReply(
      formatGivenWithContents(
        current.title ?? "(untitled)",
        targetLookup ?? "them",
        result.contents,
      ),
    );
  } catch (error) {
    if (error instanceof LorenzoApiError) {
      await interaction.editReply(describeGiveError(error));
      return;
    }
    throw error;
  }
}

/** A failed bulk-assign entry's problem, as the error a single give would have thrown. */
function problemError(result: BulkAssignResultItem | undefined): LorenzoApiError {
  const problem = result?.problem;
  return new LorenzoApiError(
    problem?.detail ?? problem?.title ?? "Couldn't give that.",
    problem?.status ?? 500,
    problem?.type,
  );
}

const NOT_A_STACK_MESSAGE = "That item isn't a stack — omit the quantity to give the whole thing.";

export async function findGiveTargets(
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

  const [rosters, groups] = await Promise.all([
    Promise.all(
      campaignIds.map((campaignId) => client.getCampaignPlayers(tenantId, campaignId, accessToken)),
    ),
    // A group can own things too (ADR 0124) - offered after the characters.
    client.listGroups(tenantId, accessToken).catch(() => []),
  ]);
  const byId = new Map(rosters.flat().map((character) => [character.entityId, character]));
  return [
    ...byId.values(),
    ...groups.map((group) => ({ entityId: group.entityId, name: `${group.name} (group)` })),
  ];
}

/** A give target's name: a character's, or else a group's (ADR 0124). */
export async function targetNameOf(
  client: LorenzoApiClient,
  tenantId: string,
  targetId: string,
  accessToken: string,
): Promise<string> {
  try {
    return await client.getCharacterName(tenantId, targetId, accessToken);
  } catch (error) {
    if (!(error instanceof LorenzoApiError && error.status === 404)) throw error;
    return client.getGroupName(tenantId, targetId, accessToken);
  }
}

export function describeGiveError(error: LorenzoApiError): string {
  switch (error.status) {
    case 409:
      // What's bound, or what doesn't fit, in the API's words (ADR 0128, 0129).
      return error.message;
    case 403:
      // ADR 0124: carrying something isn't owning it.
      return error.problemType === "item-not-yours-to-give"
        ? "That belongs to someone else — you can move it, but only its owner or a GM can give it away."
        : "That's not something you can give away — it isn't reachable from any of your characters.";
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
