import { SlashCommandBuilder } from "discord.js";
import { LorenzoApiError, createLorenzoApiClient } from "../lorenzo-client.js";
import { resolveCurrentCharacter } from "../preferences.js";
import { getValidAccessToken } from "../token-provider.js";
import { filterChoices, formatItemChoiceName } from "./autocomplete.js";
import type { Command } from "./types.js";

type Visibility = "public" | "private" | "gm-private" | "group";

/**
 * `/note` - adds a note to an item, with one of four visibilities. A GM
 * authoring on someone else's item just works once they can already
 * manage it (`can_manage_campaign`, ADR 0032) - no separate GM-only code
 * path needed here, same as every other write command in this bot.
 *
 * - `public`: `is_public: true`.
 * - `private`: `is_public: false`, then a follow-up `addInformationKnower`
 *   naming the *author's own current character* - the API has no "the
 *   author sees their own private write for free" default, so this
 *   explicit second call is required every time. Needs a `/set-current`
 *   character to target; rejected up front, before creating anything, if
 *   there isn't one - `apps/api` has no way to delete an `Information` row
 *   once created, so this can't be undone if the knower grant is what's
 *   missing.
 * - `gm-private`: `is_public: false`, no knowers added at all - relies on
 *   ADR 0035's GM-reachability bypass in `information_visibility.py`,
 *   confirmed for real against `main`, not just the ADR doc.
 * - `group`: `is_public: false`, then `addInformationKnower` naming the
 *   chosen *group* entity instead of a character - the same sub-resource,
 *   generic over "any knower entity" (ADR 0045's read-only groups API is
 *   what makes offering a group to pick from possible at all; previously
 *   deferred for lack of any way to list them). Needs the `group` option
 *   given; rejected up front for the same "can't undo a missing knower
 *   grant" reason `private` already is.
 */
export const noteCommand: Command = {
  definition: new SlashCommandBuilder()
    .setName("note")
    .setDescription("Add a note to an item.")
    .addStringOption((opt) =>
      opt
        .setName("item")
        .setDescription("The item to add a note to")
        .setRequired(true)
        .setAutocomplete(true),
    )
    .addStringOption((opt) =>
      opt
        .setName("visibility")
        .setDescription("Who can see this note")
        .setRequired(true)
        .addChoices(
          { name: "Public — everyone", value: "public" },
          { name: "Private — just your current character", value: "private" },
          { name: "GM-private — only GMs, not even your own character", value: "gm-private" },
          { name: "Group — everyone in a specific group", value: "group" },
        ),
    )
    .addStringOption((opt) =>
      opt.setName("title").setDescription("A short title").setRequired(true),
    )
    .addStringOption((opt) =>
      opt.setName("content").setDescription("The note itself").setRequired(true),
    )
    .addStringOption((opt) =>
      opt
        .setName("group")
        .setDescription("Which group - only used when visibility is Group")
        .setRequired(false)
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

    if (focused.name === "group") {
      const groups = await client.listGroups(tenantId, accessToken);
      const choices = groups.map((group) => ({ name: group.name, value: group.entityId }));
      await interaction.respond(filterChoices(choices, focused.value));
      return;
    }

    const items = await client.getMyItemInstances(tenantId, accessToken);
    const choices = items.map((item) => ({
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

    const itemEntityId = interaction.options.getString("item", true);
    const visibility = interaction.options.getString("visibility", true) as Visibility;
    const title = interaction.options.getString("title", true);
    const content = interaction.options.getString("content", true);
    const groupEntityId = interaction.options.getString("group") ?? undefined;

    let authorCharacterId: string | undefined;
    if (visibility === "private") {
      authorCharacterId = await resolveCurrentCharacter(interaction.user.id, undefined);
      if (!authorCharacterId) {
        await interaction.editReply(
          "Set a current character first — run `/set-current` — a private note needs to know whose eyes it's for.",
        );
        return;
      }
    }
    if (visibility === "group" && !groupEntityId) {
      await interaction.editReply("Pick a group — a group note needs to know which one.");
      return;
    }

    const client = createLorenzoApiClient(ctx.config.lorenzoApiBaseUrl);
    const tenantId = ctx.config.lorenzoTenantId;

    try {
      const info = await client.createInformation(
        tenantId,
        itemEntityId,
        { title, type: "note", isPublic: visibility === "public", content },
        accessToken,
      );

      const knowerEntityId =
        visibility === "private"
          ? authorCharacterId
          : visibility === "group"
            ? groupEntityId
            : undefined;
      if (knowerEntityId) {
        try {
          await client.addInformationKnower(tenantId, info.id, knowerEntityId, accessToken);
        } catch {
          await interaction.editReply(
            "Added the note, but couldn't grant visibility into it — it may currently be GM-only. Ask a GM to check.",
          );
          return;
        }
      }

      await interaction.editReply(`Added a ${visibility} note to that item.`);
    } catch (error) {
      if (error instanceof LorenzoApiError) {
        await interaction.editReply(describeNoteError(error));
        return;
      }
      throw error;
    }
  },
};

function describeNoteError(error: LorenzoApiError): string {
  switch (error.status) {
    case 403:
      return "You can't add a note to that — it isn't reachable from any of your characters.";
    case 404:
      return "Couldn't find that item anymore — run `/note` again and re-pick from the suggestions.";
    case 422:
      return `Couldn't do that: ${error.message}`;
    default:
      return "Something went wrong adding that note.";
  }
}
