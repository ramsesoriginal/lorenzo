import { SlashCommandBuilder } from "discord.js";
import { formatInventoryEmbed } from "../format-inventory.js";
import {
  type GroupSummary,
  type HeldByResponse,
  type LorenzoApiClient,
  LorenzoApiError,
  createLorenzoApiClient,
} from "../lorenzo-client.js";
import { getValidAccessToken } from "../token-provider.js";
import type { Command } from "./types.js";

// Discord allows at most 10 embeds per message reply.
const MAX_EMBEDS_PER_REPLY = 10;

/**
 * `/inventory` - lists what the caller's own characters hold (ADR 0123), one
 * embed per character: Equipped first, then what they carry, then what's
 * held elsewhere (formatInventoryEmbed).
 * Depends on the backend contract noted in ADR 0050
 * (`getControlledCharacters`/`getItemInstancesHeldBy` in lorenzo-client.ts)
 * which isn't fully live in apps/api yet - a 404 from either call is
 * treated as "not available yet" rather than a generic failure.
 *
 * Optional `search` (ADR 0068) filters to items whose title contains it,
 * case-insensitively - client-side, same "no server-side search endpoint,
 * so filter what's already fetched" convention `/award`'s catalog
 * autocomplete already established. Matters once a character's inventory
 * outgrows a single embed's fields (format-inventory.ts's own accepted
 * truncation).
 */
export const inventoryCommand: Command = {
  definition: new SlashCommandBuilder()
    .setName("inventory")
    .setDescription("List what your characters hold: equipped, carried, and kept elsewhere.")
    .addStringOption((opt) =>
      opt
        .setName("search")
        .setDescription("Only show items whose name contains this")
        .setRequired(false),
    ),
  async execute(interaction, ctx) {
    await interaction.deferReply({ ephemeral: true });

    const accessToken = await getValidAccessToken(interaction.user.id);
    if (!accessToken) {
      await interaction.editReply("You haven't linked your account yet — run `/link` first.");
      return;
    }

    const search = interaction.options.getString("search")?.toLowerCase();
    const client = createLorenzoApiClient(ctx.config.lorenzoApiBaseUrl);
    const tenantId = ctx.config.lorenzoTenantId;

    const characters = await withNotYetAvailableMessage(interaction, () =>
      client.getControlledCharacters(tenantId, accessToken),
    );
    if (characters === undefined) return;

    if (characters.length === 0) {
      await interaction.editReply("You don't control any characters in this campaign yet.");
      return;
    }

    // Then every group one of them belongs to, which can own things too (ADR 0124).
    const groups = await groupsOf(client, tenantId, accessToken, characters);
    const holders = [...characters, ...groups];
    const embeds = await Promise.all(
      holders.map(async (holder) => {
        const response = await client.getItemInstancesHeldBy(
          tenantId,
          holder.entityId,
          accessToken,
        );
        return search
          ? formatInventoryEmbed(holder.name, filterByTitle(response, search), {
              emptyEquipped: "Nothing here matches.",
            })
          : formatInventoryEmbed(holder.name, response);
      }),
    );

    const visibleEmbeds = embeds.slice(0, MAX_EMBEDS_PER_REPLY);
    const omitted = embeds.length - visibleEmbeds.length;
    await interaction.editReply({
      content:
        omitted > 0
          ? `Showing ${visibleEmbeds.length} of ${embeds.length} characters and groups (Discord's own per-message limit) — ask a GM to check the rest.`
          : "",
      embeds: visibleEmbeds,
    });
  },
};

/** The groups any of `characters` belongs to, each once. A failed lookup
 * just leaves groups out: they're an addition to `/inventory`, not its
 * point. */
async function groupsOf(
  client: LorenzoApiClient,
  tenantId: string,
  accessToken: string,
  characters: readonly { entityId: string }[],
): Promise<readonly GroupSummary[]> {
  const perCharacter = await Promise.all(
    characters.map((character) =>
      client.getCharacterGroups(tenantId, character.entityId, accessToken).catch(() => []),
    ),
  );
  const byId = new Map(perCharacter.flat().map((group) => [group.entityId, group]));
  return [...byId.values()];
}

/** Narrows a held-by response to items whose title contains `search`
 * (already lowercased by the caller), case-insensitively - groups stay
 * present even if they end up empty, matching `formatInventoryEmbed`'s
 * own existing "filter out empty groups" behavior. */
function filterByTitle(response: HeldByResponse, search: string): HeldByResponse {
  return {
    ...response,
    groups: response.groups.map((group) => ({
      ...group,
      item_instances: group.item_instances.filter((item) =>
        (item.title ?? "").toLowerCase().includes(search),
      ),
    })),
  };
}

/**
 * Runs `fn`, and if it throws a 404 `LorenzoApiError`, replies with a
 * specific "not available yet" message and returns `undefined` instead of
 * rethrowing - the expected outcome while apps/api's own character-
 * resolution endpoint (ADR 0050) hasn't shipped yet. Any other error
 * propagates to commands/index.ts's own generic failure handler.
 */
async function withNotYetAvailableMessage<T>(
  interaction: { editReply: (content: string) => Promise<unknown> },
  fn: () => Promise<T>,
): Promise<T | undefined> {
  try {
    return await fn();
  } catch (error) {
    if (error instanceof LorenzoApiError && error.status === 404) {
      await interaction.editReply(
        "This feature isn't available on the Lorenzo server yet — ask your GM to check for an update.",
      );
      return undefined;
    }
    throw error;
  }
}
