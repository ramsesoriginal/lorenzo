import { SlashCommandBuilder } from "discord.js";
import {
  GIVE_CONTENTS_CANCEL_CUSTOM_ID,
  type GiveContentsIntent,
  buildGiveContentsComponents,
  formatContentsGiven,
  formatGiveContentsPrompt,
  formatNothingInsideToGive,
  givenCount,
  parseGiveContentsCustomId,
} from "../format-give-contents.js";
import { LorenzoApiError, createLorenzoApiClient } from "../lorenzo-client.js";
import { getValidAccessToken } from "../token-provider.js";
import { filterChoices, formatItemChoiceName } from "./autocomplete.js";
import { describeGiveError, findGiveTargets, targetNameOf } from "./give.js";
import type { ButtonInteraction, Command, CommandContext } from "./types.js";

/**
 * `/give-contents` - gives everything inside one of your containers, at any
 * depth, to another character or a group, but not the container itself
 * (ADR 0125). Whatever inside isn't yours to give stays whose it is.
 *
 * Like `/give` (ADR 0088), nothing moves when the command runs: a dry run
 * words the question - how many things go, and whose the rest stay - and
 * one click on "Give" does it. No Undo: there's no single thing to give
 * back.
 */
export const giveContentsCommand: Command = {
  definition: new SlashCommandBuilder()
    .setName("give-contents")
    .setDescription("Give everything inside one of your containers to another character.")
    .addStringOption((opt) =>
      opt
        .setName("container")
        .setDescription("The container whose contents to give")
        .setRequired(true)
        .setAutocomplete(true),
    )
    .addStringOption((opt) =>
      opt.setName("to").setDescription("Who to give it to").setRequired(true).setAutocomplete(true),
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

    if (focused.name === "container") {
      // Only what holds something: an empty one has nothing to give (ADR 0066's is_container).
      const items = await client.getMyItemInstances(tenantId, accessToken);
      const choices = items
        .filter((item) => item.isContainer === true)
        .map((item) => ({
          name: formatItemChoiceName(item.title, item.quantity),
          value: item.entityId,
        }));
      await interaction.respond(filterChoices(choices, focused.value));
      return;
    }

    if (focused.name === "to") {
      const chosenContainerId = interaction.options.getString("container");
      const targets = await findGiveTargets(client, tenantId, accessToken, chosenContainerId);
      const choices = targets.map((t) => ({ name: t.name, value: t.entityId }));
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

    const intent: GiveContentsIntent = {
      containerEntityId: interaction.options.getString("container", true),
      targetCharacterId: interaction.options.getString("to", true),
    };
    const client = createLorenzoApiClient(ctx.config.lorenzoApiBaseUrl);
    const tenantId = ctx.config.lorenzoTenantId;

    try {
      const { data: container } = await client.getItemInstance(
        tenantId,
        intent.containerEntityId,
        accessToken,
      );
      const targetName = await targetNameOf(
        client,
        tenantId,
        intent.targetCharacterId,
        accessToken,
      );
      const preview = await client.giveContents(
        tenantId,
        intent.containerEntityId,
        intent.targetCharacterId,
        accessToken,
        { dryRun: true },
      );
      const containerTitle = container.title ?? "(untitled)";
      if (givenCount(preview) === 0) {
        await interaction.editReply(formatNothingInsideToGive(containerTitle, targetName, preview));
        return;
      }
      await interaction.editReply({
        content: formatGiveContentsPrompt(containerTitle, targetName, preview),
        components: buildGiveContentsComponents(intent),
      });
    } catch (error) {
      if (error instanceof LorenzoApiError) {
        await interaction.editReply(describeGiveContentsError(error));
        return;
      }
      throw error;
    }
  },

  async onButton(interaction, ctx) {
    if (interaction.customId === GIVE_CONTENTS_CANCEL_CUSTOM_ID) {
      await interaction.update({ content: "Cancelled — nothing was given.", components: [] });
      return;
    }

    const intent = parseGiveContentsCustomId(interaction.customId);
    if (!intent) {
      await interaction.update({
        content: "That confirmation isn't valid anymore — run `/give-contents` again.",
        components: [],
      });
      return;
    }

    // Stripping the buttons first means a second click can't give twice.
    await interaction.update({ content: "Giving…", components: [] });
    await confirmGiveContents(interaction, ctx, intent);
  },
};

async function confirmGiveContents(
  interaction: ButtonInteraction,
  ctx: CommandContext,
  intent: GiveContentsIntent,
): Promise<void> {
  const accessToken = await getValidAccessToken(interaction.user.id);
  if (!accessToken) {
    await interaction.editReply("You haven't linked your account yet — run `/link` first.");
    return;
  }

  const client = createLorenzoApiClient(ctx.config.lorenzoApiBaseUrl);
  const tenantId = ctx.config.lorenzoTenantId;

  try {
    const results = await client.giveContents(
      tenantId,
      intent.containerEntityId,
      intent.targetCharacterId,
      accessToken,
    );
    const [container, targetName] = await Promise.all([
      client
        .getItemInstance(tenantId, intent.containerEntityId, accessToken)
        .then(({ data }) => data.title ?? "(untitled)")
        .catch(() => "the container"),
      targetNameOf(client, tenantId, intent.targetCharacterId, accessToken).catch(() => "them"),
    ]);
    await interaction.editReply(
      givenCount(results) > 0
        ? formatContentsGiven(container, targetName, results)
        : formatNothingInsideToGive(container, targetName, results),
    );
  } catch (error) {
    if (error instanceof LorenzoApiError) {
      await interaction.editReply(describeGiveContentsError(error));
      return;
    }
    throw error;
  }
}

function describeGiveContentsError(error: LorenzoApiError): string {
  // Its own wording where the container, not an item given away, is what's refused.
  if (error.status === 403 && error.problemType !== "item-not-yours-to-give") {
    return "That's not a container you can reach from any of your characters.";
  }
  return describeGiveError(error).replaceAll("`/give`", "`/give-contents`");
}
