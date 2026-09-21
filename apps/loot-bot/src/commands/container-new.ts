import { SlashCommandBuilder } from "discord.js";
import { clearContainerPrototypeId } from "../db.js";
import { MAX_FILL_OPTIONS, buildFillComponents, parseFillCustomId } from "../format-container.js";
import { LorenzoApiError, createLorenzoApiClient } from "../lorenzo-client.js";
import { resolveCurrentCharacter } from "../preferences.js";
import { getValidAccessToken } from "../token-provider.js";
import { filterChoices } from "./autocomplete.js";
import { resolveSackPrototype } from "./sack-prototype.js";
import type { Command, CommandContext, StringSelectMenuInteraction } from "./types.js";

/**
 * `/container-new` - bundle loose items into an ad-hoc container without
 * leaving Discord (ADR 0091). Two steps: the command makes a *sack* (an
 * instance of the tenant's "Sack" catalog item, owned by the chosen
 * character) and shows a multi-select of that character's loose items; the
 * pick moves the chosen ones in (`onSelectMenu`).
 *
 * The sack exists from the first step, so an abandoned picker leaves an empty
 * sack behind - accepted deliberately: it's visible in `/inventory`, harmless,
 * and the alternative (holding the name and pick in bot-side state until a
 * second step creates it) would be state a click can lose on another Cloud
 * Run instance. Named `container-new`, not `container new`: this bot has no
 * subcommand support (ADR 0053) and every multi-word command is hyphenated.
 */
export const containerNewCommand: Command = {
  definition: new SlashCommandBuilder()
    .setName("container-new")
    .setDescription("Make a sack and put some of your loose items in it.")
    .addStringOption((opt) =>
      opt
        .setName("name")
        .setDescription("What to call it, e.g. Camp supplies")
        .setRequired(true)
        .setMinLength(1)
        .setMaxLength(100),
    )
    .addStringOption((opt) =>
      opt
        .setName("character")
        .setDescription("Whose sack it is (default: your current character)")
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
    const characters = await client.getControlledCharacters(
      ctx.config.lorenzoTenantId,
      accessToken,
    );
    const choices = characters.map((c) => ({ name: c.name, value: c.entityId }));
    await interaction.respond(filterChoices(choices, focused.value));
  },

  async execute(interaction, ctx) {
    await interaction.deferReply({ ephemeral: true });

    const accessToken = await getValidAccessToken(interaction.user.id);
    if (!accessToken) {
      await interaction.editReply("You haven't linked your account yet — run `/link` first.");
      return;
    }

    const client = createLorenzoApiClient(ctx.config.lorenzoApiBaseUrl);
    const tenantId = ctx.config.lorenzoTenantId;
    const name = interaction.options.getString("name", true).trim();
    if (!name) {
      await interaction.editReply("Give the sack a name.");
      return;
    }

    // Explicit option, then the stored default (`/set-current`, ADR 0068),
    // then the only character the caller controls - `/sheet`'s own rule.
    let characterEntityId = await resolveCurrentCharacter(
      interaction.user.id,
      interaction.channelId,
      interaction.options.getString("character"),
    );
    if (!characterEntityId) {
      const mine = await client.getControlledCharacters(tenantId, accessToken);
      if (mine.length === 0) {
        await interaction.editReply("You don't control any characters here yet.");
        return;
      }
      if (mine.length > 1) {
        await interaction.editReply(
          "You have more than one character — pick whose sack it is with the `character` option, or set a default with `/set-current`.",
        );
        return;
      }
      characterEntityId = mine[0]?.entityId;
    }
    if (!characterEntityId) return;

    try {
      const sack = await resolveSackPrototype(client, tenantId, accessToken);
      if (sack.kind === "needs-catalog-access") {
        await interaction.editReply(NEEDS_CATALOG_ACCESS_MESSAGE);
        return;
      }

      const made = await client
        .createItemInstance(
          tenantId,
          sack.prototypeId,
          characterEntityId,
          undefined,
          accessToken,
          name,
        )
        .catch(async (error: unknown) => {
          // A stored prototype that no longer exists (someone deleted the
          // catalog item): forget it so the next run re-resolves, rather
          // than failing the same way forever.
          if (error instanceof LorenzoApiError && error.status === 422) {
            await clearContainerPrototypeId(tenantId);
          }
          throw error;
        });

      const owned = await client.getItemInstancesOwnedBy(tenantId, characterEntityId, accessToken);
      const loose = owned.groups
        .filter((group) => group.container === null)
        .flatMap((group) => group.item_instances)
        .filter((item) => item.entity_id !== made.entity_id)
        .map((item) => ({
          entityId: item.entity_id,
          title: item.title ?? "(untitled)",
          quantity: item.quantity,
        }));

      const title = made.title ?? name;
      if (loose.length === 0) {
        await interaction.editReply(
          `Made **${title}**. You've nothing loose to put in it, so it's empty for now.`,
        );
        return;
      }

      const hidden = loose.length - MAX_FILL_OPTIONS;
      const more =
        hidden > 0 ? ` Only the first ${MAX_FILL_OPTIONS} are listed; ${hidden} more aren't.` : "";
      await interaction.editReply({
        content: `Made **${title}**. Choose what goes inside.${more}`,
        components: buildFillComponents(made.entity_id, loose),
      });
    } catch (error) {
      if (error instanceof LorenzoApiError) {
        await interaction.editReply(describeCreateError(error));
        return;
      }
      throw error;
    }
  },

  async onSelectMenu(interaction, ctx) {
    const sackEntityId = parseFillCustomId(interaction.customId);
    if (!sackEntityId) {
      await interaction.update({
        content: "That menu isn't valid anymore — run `/container-new` again.",
        components: [],
      });
      return;
    }

    // Acknowledge first (moving several items can outlast Discord's 3-second
    // window), then edit the message with the outcome. Unlike `/give`'s
    // split, moving into the same container twice is harmless, so a second
    // pick before the edit lands can't do damage.
    await interaction.deferUpdate();
    await fillSack(interaction, ctx, sackEntityId);
  },
};

const NEEDS_CATALOG_ACCESS_MESSAGE =
  'This server doesn\'t have a sack set up yet, and only someone with tenant access can add one. Ask a GM or admin to run `/container-new` once (or to add an item called "Sack" to the catalog), then try again.';

async function fillSack(
  interaction: StringSelectMenuInteraction,
  ctx: CommandContext,
  sackEntityId: string,
): Promise<void> {
  const accessToken = await getValidAccessToken(interaction.user.id);
  if (!accessToken) {
    await interaction.editReply({
      content: "You haven't linked your account yet — run `/link` first.",
      components: [],
    });
    return;
  }

  const client = createLorenzoApiClient(ctx.config.lorenzoApiBaseUrl);
  try {
    const results = await client.bulkMoveItemInstances(
      ctx.config.lorenzoTenantId,
      sackEntityId,
      interaction.values,
      accessToken,
    );
    const moved = results.filter((r) => r.status === "ok").length;
    const problems = [
      ...new Set(
        results
          .filter((r) => r.status === "error")
          .map((r) => r.problem?.detail ?? r.problem?.title ?? "unknown problem"),
      ),
    ];

    const summary =
      moved === 0 ? "Nothing went in." : `Put ${moved} ${moved === 1 ? "item" : "items"} in.`;
    const failed = results.length - moved;
    const tail = failed > 0 ? ` ${failed} couldn't be moved: ${problems.join("; ")}` : "";
    await interaction.editReply({ content: `${summary}${tail}`, components: [] });
  } catch (error) {
    if (error instanceof LorenzoApiError) {
      await interaction.editReply({ content: describeFillError(error), components: [] });
      return;
    }
    throw error;
  }
}

function describeCreateError(error: LorenzoApiError): string {
  switch (error.status) {
    case 403:
      return "You can't make a sack for that character.";
    case 404:
      return "Couldn't find that character — run `/container-new` again and re-pick from the suggestions.";
    case 422:
      return "The sack template seems to have gone missing from the catalog — run `/container-new` again and it'll be set up afresh.";
    default:
      return "Something went wrong making that sack.";
  }
}

function describeFillError(error: LorenzoApiError): string {
  switch (error.status) {
    case 403:
      return "You can't move things into that sack.";
    case 404:
      return "Couldn't find that sack anymore — run `/container-new` again.";
    case 422:
      return `Couldn't do that: ${error.message}`;
    default:
      return "Something went wrong filling that sack.";
  }
}
