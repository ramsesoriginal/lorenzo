import { SlashCommandBuilder } from "discord.js";
import {
  claimHonoredEvent,
  describeItem,
  nameCharacter,
  recordCharacterEvents,
  takeEvent,
} from "../character-events.js";
import {
  type LootClaim,
  deleteLootClaim,
  deleteLootClaimsForDrop,
  getLootClaim,
  getLootDrop,
  insertLootDrop,
  listLootClaims,
  markLootDropApplied,
  setLootDropMessageId,
  upsertLootClaim,
} from "../db.js";
import {
  type ClaimOutcome,
  availableDropItems,
  buildApplySummaryEmbed,
  buildDropComponents,
  buildDropEmbed,
  buildQuantityModal,
  parseClaimType,
} from "../format-drop.js";
import {
  type BulkAssignItem,
  type ItemInstanceOut,
  type LorenzoApiClient,
  LorenzoApiError,
  createLorenzoApiClient,
} from "../lorenzo-client.js";
import { resolveCurrentCharacter } from "../preferences.js";
import { getValidAccessToken } from "../token-provider.js";
import { transferItem } from "./item-transfer.js";
import type {
  Command,
  CommandContext,
  ModalMessageModalSubmitInteraction,
  StringSelectMenuInteraction,
} from "./types.js";

/**
 * `/drop` - a GM drops a pre-made container's contents into the channel;
 * players take a whole item or part of a stack immediately, or claim one
 * for the GM to resolve later with "apply claims" (ADR 0052). The one
 * command in this bot with its own persistent, multi-user-interactive
 * message rather than a single request/response.
 */
export const dropCommand: Command = {
  definition: new SlashCommandBuilder()
    .setName("drop")
    .setDescription("Drop a pre-made loot container's contents into this channel.")
    .addStringOption((opt) =>
      opt
        .setName("container")
        .setDescription("The container's entity id or slug")
        .setRequired(true),
    ),

  async execute(interaction, ctx) {
    await interaction.deferReply(); // public - the whole point is the party sees it

    const accessToken = await getValidAccessToken(interaction.user.id);
    if (!accessToken) {
      await interaction.editReply("You haven't linked your account yet — run `/link` first.");
      return;
    }

    const client = createLorenzoApiClient(ctx.config.lorenzoApiBaseUrl);
    if (!(await client.isCampaignGm(accessToken))) {
      await interaction.editReply("Only a GM can drop loot.");
      return;
    }

    const containerInput = interaction.options.getString("container", true);
    const tenantId = ctx.config.lorenzoTenantId;

    let containerEntityId: string;
    let items: readonly ItemInstanceOut[];
    try {
      // A slug (ADR 0043) is a friendlier way for a GM to name a
      // pre-prepared container than pasting a raw entity id - resolved
      // first when the input doesn't already look like one.
      containerEntityId = isUuid(containerInput)
        ? containerInput
        : (await client.getItemInstanceBySlug(tenantId, containerInput, accessToken)).data
            .entity_id;
      items = await client.getItemInstancesByContainer(tenantId, containerEntityId, accessToken);
    } catch (error) {
      if (error instanceof LorenzoApiError && (error.status === 404 || error.status === 422)) {
        await interaction.editReply(
          "Couldn't find that container — check the id/slug and try again.",
        );
        return;
      }
      throw error;
    }

    const drop = await insertLootDrop({
      containerEntityId,
      discordChannelId: interaction.channelId,
      createdByDiscordUserId: interaction.user.id,
    });

    const available = availableDropItems(items);
    const message = await interaction.editReply({
      embeds: [buildDropEmbed(available, [])],
      components: buildDropComponents(drop.id, available),
    });
    await setLootDropMessageId(drop.id, message.id);
  },

  async onSelectMenu(interaction, ctx) {
    const [, action, dropId] = interaction.customId.split(":");
    const itemEntityId = interaction.values[0];
    if (!action || !dropId || !itemEntityId) return;

    if (action === "take") {
      await interaction.showModal(buildQuantityModal("take", dropId, itemEntityId));
      return;
    }

    if (action === "claim") {
      const existing = await getLootClaim(dropId, itemEntityId, interaction.user.id);
      if (existing) {
        await deleteLootClaim(dropId, itemEntityId, interaction.user.id);
        await refreshDropMessage(interaction, ctx, dropId);
        return;
      }
      await interaction.showModal(buildQuantityModal("claim", dropId, itemEntityId));
    }
  },

  async onModalSubmit(interaction, ctx) {
    if (!interaction.isFromMessage()) return;
    const [, action, dropId, itemEntityId] = interaction.customId.split(":");
    if (!dropId || !itemEntityId) return;

    if (action === "take-modal") {
      await handleTakeModalSubmit(interaction, ctx, dropId, itemEntityId);
      return;
    }
    if (action === "claim-modal") {
      await handleClaimModalSubmit(interaction, ctx, dropId, itemEntityId);
    }
  },

  async onButton(interaction, ctx) {
    const [, action, dropId] = interaction.customId.split(":");
    if ((action !== "apply" && action !== "clear") || !dropId) return;

    const accessToken = await getValidAccessToken(interaction.user.id);
    if (!accessToken) {
      await interaction.reply({
        content: "You haven't linked your account yet — run `/link` first.",
        ephemeral: true,
      });
      return;
    }

    const client = createLorenzoApiClient(ctx.config.lorenzoApiBaseUrl);
    if (!(await client.isCampaignGm(accessToken))) {
      await interaction.reply({
        content: `Only a GM can ${action === "apply" ? "apply" : "clear"} claims.`,
        ephemeral: true,
      });
      return;
    }

    await interaction.deferUpdate();
    const tenantId = ctx.config.lorenzoTenantId;

    if (action === "clear") {
      // No apply - just discard every outstanding claim and leave the drop
      // open (ADR 0068), unlike "apply" below which also marks it resolved.
      await deleteLootClaimsForDrop(dropId);
      const drop = await getLootDrop(dropId);
      if (!drop) return;
      const view = await buildDropView(
        client,
        tenantId,
        drop.containerEntityId,
        dropId,
        accessToken,
      );
      await interaction.editReply(view);
      return;
    }

    const claims = await listLootClaims(dropId);
    const outcomes = await applyAllClaims(client, tenantId, claims, accessToken, ctx);

    await markLootDropApplied(dropId);
    await deleteLootClaimsForDrop(dropId);

    await interaction.editReply({
      embeds: [buildApplySummaryEmbed(outcomes)],
      components: [],
    });
  },
};

const UUID_PATTERN = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

function isUuid(value: string): boolean {
  return UUID_PATTERN.test(value);
}

type QuantityInput = number | null | "invalid";

function parseQuantityInput(raw: string): QuantityInput {
  const trimmed = raw.trim();
  if (trimmed === "") return null;
  const parsed = Number(trimmed);
  if (!Number.isInteger(parsed) || parsed <= 0) return "invalid";
  return parsed;
}

async function handleTakeModalSubmit(
  interaction: ModalMessageModalSubmitInteraction,
  ctx: CommandContext,
  dropId: string,
  itemEntityId: string,
): Promise<void> {
  const requestedQuantity = parseQuantityInput(interaction.fields.getTextInputValue("quantity"));
  if (requestedQuantity === "invalid") {
    await interaction.reply({
      content: "That doesn't look like a valid quantity.",
      ephemeral: true,
    });
    return;
  }

  const accessToken = await getValidAccessToken(interaction.user.id);
  if (!accessToken) {
    await interaction.reply({
      content: "You haven't linked your account yet — run `/link` first.",
      ephemeral: true,
    });
    return;
  }

  const characterEntityId = await resolveCurrentCharacter(
    interaction.user.id,
    interaction.channelId,
    undefined,
  );
  if (!characterEntityId) {
    await interaction.reply({
      content: "Set a current character first — run `/set-current`.",
      ephemeral: true,
    });
    return;
  }

  const client = createLorenzoApiClient(ctx.config.lorenzoApiBaseUrl);
  const tenantId = ctx.config.lorenzoTenantId;

  try {
    const { data: current, etag } = await client.getItemInstance(
      tenantId,
      itemEntityId,
      accessToken,
    );
    const result = await transferItem(
      client,
      tenantId,
      current,
      etag,
      requestedQuantity,
      characterEntityId,
      accessToken,
    );

    if (result.kind === "not-a-stack") {
      await interaction.reply({
        content: "That item isn't a stack — leave quantity blank to take the whole thing.",
        ephemeral: true,
      });
      return;
    }

    await refreshDropMessage(interaction, ctx, dropId);
    const amount = result.splitting ? `${result.requestedQuantity} of ` : "";

    // For `/changes` (ADR 0096). Best-effort - the take has already happened.
    const taker = nameCharacter(
      characterEntityId,
      await client.getCharacterName(tenantId, characterEntityId, accessToken).catch(() => null),
    );
    if (taker) {
      await recordCharacterEvents(
        [
          takeEvent({
            character: taker,
            item: describeItem(result.given.title ?? "(untitled)", result.given.quantity),
          }),
        ],
        ctx.logger,
      );
    }

    await interaction.followUp({
      content: `Took ${amount}${result.given.title ?? "(untitled)"}.`,
      ephemeral: true,
    });
  } catch (error) {
    if (error instanceof LorenzoApiError) {
      await interaction.reply({ content: describeTakeError(error), ephemeral: true });
      return;
    }
    throw error;
  }
}

async function handleClaimModalSubmit(
  interaction: ModalMessageModalSubmitInteraction,
  ctx: CommandContext,
  dropId: string,
  itemEntityId: string,
): Promise<void> {
  const quantity = parseQuantityInput(interaction.fields.getTextInputValue("quantity"));
  if (quantity === "invalid") {
    await interaction.reply({
      content: "That doesn't look like a valid quantity.",
      ephemeral: true,
    });
    return;
  }

  const characterEntityId = await resolveCurrentCharacter(
    interaction.user.id,
    interaction.channelId,
    undefined,
  );
  if (!characterEntityId) {
    await interaction.reply({
      content: "Set a current character first — run `/set-current`.",
      ephemeral: true,
    });
    return;
  }

  const claimType = parseClaimType(interaction.fields.getTextInputValue("claim-type"));

  await upsertLootClaim({
    lootDropId: dropId,
    itemEntityId,
    discordUserId: interaction.user.id,
    characterEntityId,
    quantity,
    claimType,
  });

  await refreshDropMessage(interaction, ctx, dropId);
}

/** Rebuilds and applies the drop message's embed/components in place -
 * the shared step after every take/claim/unclaim. Uses the *drop's own
 * creator's* access token, not the acting user's - ADR 0052's own
 * documented reasoning: once an item has an owner, ADR 0040 narrows who
 * can still see it, and the GM who started this drop is far more likely
 * to retain reach into it (their own campaign's roster) than whichever
 * player happened to trigger this particular refresh. Silently no-ops
 * (just acknowledges the interaction) if the drop or the GM's own token
 * can't be found - a known, accepted edge case, not a crash.
 */
/** The embed/components pair every drop-message rebuild needs (initial
 * post, every take/claim/unclaim refresh, and "clear claims" - ADR 0068) -
 * factored out once a third call site needed the identical sequence. */
async function buildDropView(
  client: LorenzoApiClient,
  tenantId: string,
  containerEntityId: string,
  dropId: string,
  accessToken: string,
): Promise<{
  embeds: [ReturnType<typeof buildDropEmbed>];
  components: ReturnType<typeof buildDropComponents>;
}> {
  const [items, claims] = await Promise.all([
    client.getItemInstancesByContainer(tenantId, containerEntityId, accessToken),
    listLootClaims(dropId),
  ]);
  const available = availableDropItems(items);
  return {
    embeds: [buildDropEmbed(available, claims)],
    components: buildDropComponents(dropId, available),
  };
}

async function refreshDropMessage(
  interaction: StringSelectMenuInteraction | ModalMessageModalSubmitInteraction,
  ctx: CommandContext,
  dropId: string,
): Promise<void> {
  const drop = await getLootDrop(dropId);
  if (!drop) {
    await interaction.deferUpdate();
    return;
  }

  const gmAccessToken = await getValidAccessToken(drop.createdByDiscordUserId);
  if (!gmAccessToken) {
    await interaction.deferUpdate();
    return;
  }

  const client = createLorenzoApiClient(ctx.config.lorenzoApiBaseUrl);
  const tenantId = ctx.config.lorenzoTenantId;
  const view = await buildDropView(client, tenantId, drop.containerEntityId, dropId, gmAccessToken);
  await interaction.update(view);
}

type ItemSnapshot = Readonly<{ current: ItemInstanceOut; etag: string | null }>;

/**
 * Applies every outstanding claim on a drop in one `bulk-assign` call (ADR
 * 0044/0052), instead of one sequential write per claim. Every claimed
 * item is read once up front (nothing mutates until the single call at
 * the end, so every claim against the same item can share one snapshot -
 * a real reduction in round-trips over the old one-`GET`-per-claim loop).
 *
 * Eligibility is decided need-before-greed, oldest-`created_at`-first
 * within each tier (ADR 0068 - need claims always get first crack at a
 * stack's remaining quantity or a non-stack's ownership), client-side:
 * `bulk-assign`'s own server-side authorization has a documented gap (ADR
 * 0044's own Context section) where reassigning an already-owned instance
 * isn't blocked, so nothing stops a *later* array entry from silently
 * stealing a non-stack item a same-batch *earlier* entry already claimed -
 * `assignedThisRun` tracks that here instead. A stack's remaining quantity
 * is tracked the same way (`remainingByItem`), mirroring what a live
 * re-fetch between writes would have shown; the server's own sequential,
 * same-transaction processing of same-`entity_id` array entries then
 * reproduces the same step-by-step result a loop of real writes would
 * have, as long as array order matches claim-resolution order.
 */
async function applyAllClaims(
  client: LorenzoApiClient,
  tenantId: string,
  claimsInCreatedOrder: readonly LootClaim[],
  accessToken: string,
  ctx: CommandContext,
): Promise<ClaimOutcome[]> {
  // Array.prototype.sort is stable (ES2019+), so claims already ordered by
  // createdAt (listLootClaims) stay oldest-first within each tier after
  // this - a plain re-sort on tier alone is enough, no secondary key needed.
  const claims = [...claimsInCreatedOrder].sort((a, b) =>
    a.claimType === b.claimType ? 0 : a.claimType === "need" ? -1 : 1,
  );
  const uniqueItemIds = [...new Set(claims.map((claim) => claim.itemEntityId))];
  const snapshots = new Map<string, ItemSnapshot | "not-found">();
  await Promise.all(
    uniqueItemIds.map(async (itemEntityId) => {
      try {
        const { data: current, etag } = await client.getItemInstance(
          tenantId,
          itemEntityId,
          accessToken,
        );
        snapshots.set(itemEntityId, { current, etag });
      } catch (error) {
        if (error instanceof LorenzoApiError && error.status === 404) {
          snapshots.set(itemEntityId, "not-found");
          return;
        }
        throw error;
      }
    }),
  );

  const outcomes: ClaimOutcome[] = [];
  const remainingByItem = new Map<string, number>();
  const assignedThisRun = new Set<string>();
  const requests: BulkAssignItem[] = [];
  // Parallel to `requests` - which claim/title each bulk-assign entry
  // belongs to, to map each result back to its own ClaimOutcome.
  const requestContext: Array<{ claim: LootClaim; itemTitle: string }> = [];

  for (const claim of claims) {
    const snapshot = snapshots.get(claim.itemEntityId);
    if (snapshot === undefined || snapshot === "not-found") {
      outcomes.push({
        discordUserId: claim.discordUserId,
        itemTitle: "(item no longer available)",
        status: "already-taken",
        quantity: claim.quantity,
      });
      continue;
    }

    const { current, etag } = snapshot;
    const itemTitle = current.title ?? "(untitled)";

    if (current.quantity === null) {
      const alreadyTakenBeforeThisRun =
        current.owner_entity_id !== null && current.owner_entity_id !== claim.characterEntityId;
      if (alreadyTakenBeforeThisRun || assignedThisRun.has(claim.itemEntityId)) {
        outcomes.push({
          discordUserId: claim.discordUserId,
          itemTitle,
          status: "already-taken",
          quantity: null,
        });
        continue;
      }
      assignedThisRun.add(claim.itemEntityId);
      requests.push({
        entity_id: claim.itemEntityId,
        owner_character_id: claim.characterEntityId,
        ...(etag !== null ? { if_match: etag } : {}),
      });
      requestContext.push({ claim, itemTitle });
      continue;
    }

    const remaining = remainingByItem.get(claim.itemEntityId) ?? current.quantity;
    const requested = claim.quantity ?? remaining;
    if (requested <= 0 || requested > remaining) {
      outcomes.push({
        discordUserId: claim.discordUserId,
        itemTitle,
        status: "not-enough-left",
        quantity: claim.quantity,
      });
      continue;
    }
    remainingByItem.set(claim.itemEntityId, remaining - requested);

    requests.push({
      entity_id: claim.itemEntityId,
      owner_character_id: claim.characterEntityId,
      ...(requested < remaining ? { quantity: requested } : {}),
      ...(etag !== null ? { if_match: etag } : {}),
    });
    requestContext.push({ claim, itemTitle });
  }

  if (requests.length === 0) return outcomes;

  const results = await client.bulkAssignItemInstances(tenantId, requests, accessToken);
  const honored: Array<{ characterEntityId: string; item: string }> = [];
  results.forEach((result, index) => {
    const context = requestContext[index];
    if (!context) return;
    const { claim, itemTitle } = context;

    if (result.status === "ok") {
      honored.push({
        characterEntityId: claim.characterEntityId,
        item: describeItem(itemTitle, requests[index]?.quantity ?? null),
      });
      outcomes.push({
        discordUserId: claim.discordUserId,
        itemTitle,
        status: "given",
        quantity: requests[index]?.quantity ?? null,
      });
      return;
    }

    outcomes.push({
      discordUserId: claim.discordUserId,
      itemTitle,
      status: result.problem?.status === 422 ? "not-enough-left" : "already-taken",
      quantity: claim.quantity,
    });
  });

  // For `/changes` (ADR 0096): whoever's claim was honored can find out what
  // they got, even if they missed the summary. One name lookup per distinct
  // character, best-effort - the assignment itself has already happened.
  if (honored.length > 0) {
    const names = new Map<string, string | null>();
    await Promise.all(
      [...new Set(honored.map((h) => h.characterEntityId))].map(async (characterEntityId) => {
        names.set(
          characterEntityId,
          await client.getCharacterName(tenantId, characterEntityId, accessToken).catch(() => null),
        );
      }),
    );
    await recordCharacterEvents(
      honored.flatMap((h) => {
        const character = nameCharacter(h.characterEntityId, names.get(h.characterEntityId));
        return character ? [claimHonoredEvent({ character, item: h.item })] : [];
      }),
      ctx.logger,
    );
  }

  return outcomes;
}

function describeTakeError(error: LorenzoApiError): string {
  switch (error.status) {
    case 403:
      return "You can't take that — you don't have a character reachable enough to claim it.";
    case 404:
      return "Someone already took that — the drop message will refresh to show what's left.";
    case 412:
      return "Someone else changed that item just now — pick it again to take the current amount.";
    case 422:
      return `Couldn't do that: ${error.message}`;
    default:
      return "Something went wrong taking that item.";
  }
}
