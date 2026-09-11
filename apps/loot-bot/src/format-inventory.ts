import { EmbedBuilder } from "discord.js";
import type { OwnedByResponse } from "./lorenzo-client.js";

const MAX_FIELD_VALUE_LENGTH = 1024;
const MAX_FIELDS_PER_EMBED = 25;
// Leaves room for the "…and N more items." summary line appended after
// truncating - see formatItemList.
const TRUNCATION_MARGIN = 24;

/**
 * Renders one character's inventory (already fetched via
 * `getItemInstancesOwnedBy`) as a single Discord embed, one field per direct
 * container (ADR 0020's own "owned-by, grouped by direct container" shape) -
 * a null container becomes "Not in a container". Pure function, no Discord
 * API calls - deliberately separate from commands/inventory.ts so it's
 * testable against plain fixture data (ADR 0029's own stated test strategy).
 *
 * One embed per character; if a character has more containers than fit in
 * one embed's 25 fields, or a container's own item list overflows a single
 * field's 1024-character value, this truncates with a visible note rather
 * than paginating - an accepted v1 simplification (rich pagination is
 * explicitly out of scope for this slice), not a silent gap.
 */
export function formatInventoryEmbed(
  characterName: string,
  response: OwnedByResponse,
): EmbedBuilder {
  const embed = new EmbedBuilder().setTitle(characterName);

  const nonEmptyGroups = response.groups.filter((group) => group.item_instances.length > 0);
  if (nonEmptyGroups.length === 0) {
    return embed.setDescription("No items.");
  }

  const visibleGroups = nonEmptyGroups.slice(0, MAX_FIELDS_PER_EMBED);
  for (const group of visibleGroups) {
    embed.addFields({
      name: group.container?.name ?? "Not in a container",
      value: formatItemList(group.item_instances),
    });
  }

  const omittedGroups = nonEmptyGroups.length - visibleGroups.length;
  if (omittedGroups > 0) {
    embed.setFooter({
      text: `…and ${omittedGroups} more container${omittedGroups === 1 ? "" : "s"}, not shown.`,
    });
  }

  return embed;
}

function formatItemList(items: OwnedByResponse["groups"][number]["item_instances"]): string {
  const lines = items.map((item) => `• ${item.title ?? "(untitled)"}`);
  const full = lines.join("\n");
  if (full.length <= MAX_FIELD_VALUE_LENGTH) return full;

  let shown = 0;
  let result = "";
  for (const line of lines) {
    const candidate = result.length === 0 ? line : `${result}\n${line}`;
    if (candidate.length > MAX_FIELD_VALUE_LENGTH - TRUNCATION_MARGIN) break;
    result = candidate;
    shown += 1;
  }
  const omitted = lines.length - shown;
  return `${result}\n…and ${omitted} more item${omitted === 1 ? "" : "s"}.`;
}
