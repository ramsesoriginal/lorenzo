import { SlashCommandBuilder } from "discord.js";
import {
  buildMoveAnywayComponents,
  type MoveAnywayIntent,
  parseMoveAnywayCustomId,
} from "../format-move.js";
import {
  createLorenzoApiClient,
  type LorenzoApiClient,
  LorenzoApiError,
} from "../lorenzo-client.js";
import { getValidAccessToken } from "../token-provider.js";
import { recordUndo } from "../undo-actions.js";
import { filterChoices, formatItemChoiceName } from "./autocomplete.js";
import { rememberActingCharacter } from "./remember-character.js";
import type { Command, CommandContext } from "./types.js";

/**
 * `/move` - moves one of the caller's own items into another container
 * they own. Self-service only - self-or-managed's "self" branch already
 * covers "rearrange your own stuff," no GM gate needed. `item` suggests
 * everything owned; `container` narrows to `isContainer === true` (ADR
 * 0068, consuming main's own `is_container` computed field, ADR 0066) -
 * closing the gap this docstring used to flag directly: "nothing in the
 * real API flags which owned items are actually container-capable."
 * Still just a suggestion, not a restriction - free-typing any owned
 * entity id still works, same convention every other autocomplete here
 * follows.
 *
 * A move that doesn't fit (ADR 0128), or that takes something bound out of
 * what binds it (ADR 0129), is refused with the API's own message; a GM
 * also gets a "Move anyway" button, which moves it with `override`, and for
 * a binding "Move and lift binding", which lifts it for good as well.
 */
export const moveCommand: Command = {
  definition: new SlashCommandBuilder()
    .setName("move")
    .setDescription("Move one of your items into another container you own.")
    .addStringOption((opt) =>
      opt
        .setName("item")
        .setDescription("The item to move")
        .setRequired(true)
        .setAutocomplete(true),
    )
    .addStringOption((opt) =>
      opt
        .setName("container")
        .setDescription("Where to move it")
        .setRequired(true)
        .setAutocomplete(true),
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

    const items = await client.getMyItemInstances(tenantId, accessToken);
    const candidates = focused.name === "container" ? items.filter((i) => i.isContainer) : items;
    const choices = candidates.map((item) => ({
      name: formatItemChoiceName(item.title, item.quantity),
      value: item.entityId,
    }));
    await interaction.respond(filterChoices(choices, focused.value));
  },

  async execute(interaction, ctx) {
    await interaction.deferReply({ ephemeral: true });

    const accessToken = await getValidAccessToken(interaction.user.id);
    if (!accessToken) {
      await interaction.editReply("You haven't linked your account yet — run `/link` first.");
      return;
    }

    const intent: MoveAnywayIntent = {
      itemEntityId: interaction.options.getString("item", true),
      containerEntityId: interaction.options.getString("container", true),
      lift: false,
    };
    const client = createLorenzoApiClient(ctx.config.lorenzoApiBaseUrl);

    try {
      const title = await performMove(client, ctx, interaction.user.id, accessToken, intent);
      await interaction.editReply(`Moved ${title}.`);
    } catch (error) {
      if (error instanceof LorenzoApiError && MOVE_ANYWAY.has(error.problemType ?? "")) {
        // Only a GM may move anyway; the API decides for this item on the click.
        const gm = await client.isCampaignGm(accessToken).catch(() => false);
        const offerLift = error.problemType === BOUND;
        await interaction.editReply({
          content: error.message,
          components: gm ? buildMoveAnywayComponents(intent, { offerLift }) : [],
        });
        return;
      }
      if (error instanceof LorenzoApiError) {
        await interaction.editReply(describeMoveError(error));
        return;
      }
      throw error;
    }
  },

  async onButton(interaction, ctx) {
    const intent = parseMoveAnywayCustomId(interaction.customId);
    if (!intent) {
      await interaction.update({
        content: "That button isn't valid anymore — run `/move` again.",
        components: [],
      });
      return;
    }
    // Stripping the button first means a second click can't move twice.
    await interaction.update({ content: "Moving…", components: [] });

    const accessToken = await getValidAccessToken(interaction.user.id);
    if (!accessToken) {
      await interaction.editReply("You haven't linked your account yet — run `/link` first.");
      return;
    }
    const client = createLorenzoApiClient(ctx.config.lorenzoApiBaseUrl);
    try {
      const title = await performMove(client, ctx, interaction.user.id, accessToken, intent, {
        override: true,
      });
      await interaction.editReply(
        intent.lift ? `Moved ${title}, and lifted its binding.` : `Moved ${title} anyway.`,
      );
    } catch (error) {
      if (error instanceof LorenzoApiError) {
        await interaction.editReply(describeMoveError(error));
        return;
      }
      throw error;
    }
  },
};

const BOUND = "item-bound";
// What a GM may move anyway: what doesn't fit (ADR 0128), what's bound (ADR 0129).
const MOVE_ANYWAY = new Set(["capacity-exceeded", BOUND]);

/** Moves it, records the Undo, and returns its title. */
async function performMove(
  client: LorenzoApiClient,
  ctx: CommandContext,
  discordUserId: string,
  accessToken: string,
  intent: MoveAnywayIntent,
  { override = false }: { override?: boolean } = {},
): Promise<string> {
  const tenantId = ctx.config.lorenzoTenantId;
  // Fresh etag, not whatever autocomplete last showed - same
  // re-validate-before-writing discipline every other write command in
  // this bot already follows.
  const { data: current, etag } = await client.getItemInstance(
    tenantId,
    intent.itemEntityId,
    accessToken,
  );
  const moved = await client.setItemInstanceContainer(
    tenantId,
    intent.itemEntityId,
    intent.containerEntityId,
    accessToken,
    etag ?? undefined,
    { override, liftBinding: intent.lift },
  );

  await recordUndo(discordUserId, {
    kind: "restore-container",
    entityId: intent.itemEntityId,
    previousContainerEntityId: current.container_entity_id,
  });
  await rememberActingCharacter(
    client,
    tenantId,
    accessToken,
    discordUserId,
    current.owner_entity_id,
    ctx.logger,
  );
  return moved.title ?? "(untitled)";
}

function describeMoveError(error: LorenzoApiError): string {
  // The API's own words where it has them: what doesn't fit, what's bound,
  // a stack, or who may move anyway (ADR 0128, 0129).
  if (error.status === 409 || error.problemType === "override-forbidden") {
    return error.message;
  }
  switch (error.status) {
    case 403:
      return "That's not something you can move — it isn't reachable from any of your characters.";
    case 404:
      return "Couldn't find that item or that container anymore — run `/move` again and re-pick from the suggestions.";
    case 412:
      return "Someone else changed that item just now — run `/move` again to try again.";
    case 422:
      return `Couldn't do that: ${error.message}`;
    default:
      return "Something went wrong moving that item.";
  }
}
