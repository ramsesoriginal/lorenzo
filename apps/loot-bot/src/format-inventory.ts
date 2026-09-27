import { EmbedBuilder } from "discord.js";
import type { HeldByResponse } from "./lorenzo-client.js";

type HeldGroup = HeldByResponse["groups"][number];
type HeldItem = HeldGroup["item_instances"][number];

const MAX_FIELD_NAME_LENGTH = 256;
const MAX_FIELD_VALUE_LENGTH = 1024;
const MAX_FIELDS_PER_EMBED = 25;
// Leaves room for the "…and N more items." summary line appended after
// truncating - see formatItemList.
const TRUNCATION_MARGIN = 24;

export type InventoryEmbedOptions = Readonly<{
  /** What the Equipped field says when nothing's in it - `/inventory`'s search says so. */
  emptyEquipped?: string;
}>;

/**
 * Renders what one character holds (already fetched via
 * `getItemInstancesHeldBy`, ADR 0123) as a single Discord embed: Equipped
 * first and always, then one field per container they carry ("Belt pouch,
 * in Backpack"), then what's held elsewhere ("Elsewhere: Chest, in
 * Carriage"). An item that isn't the character's own ends with whose it is.
 * Pure function, no Discord API calls - deliberately separate from
 * commands/inventory.ts so it's testable against plain fixture data (ADR
 * 0050's own stated test strategy).
 *
 * One embed per character; if a character has more containers than fit in
 * one embed's 25 fields, or a container's own item list overflows a single
 * field's 1024-character value, this truncates with a visible note rather
 * than paginating - an accepted v1 simplification (rich pagination is
 * explicitly out of scope for this slice), not a silent gap.
 */
export function formatInventoryEmbed(
  characterName: string,
  response: HeldByResponse,
  options: InventoryEmbedOptions = {},
): EmbedBuilder {
  const embed = new EmbedBuilder().setTitle(characterName);
  const [own, ...rest] = response.groups;
  const holderId = own?.container.id ?? null;
  const owners = new Map(response.owners.map((owner) => [owner.id, owner.name]));
  const lineOf = (item: HeldItem) => formatItemLine(item, holderId, owners);

  const equipped = own?.item_instances ?? [];
  const fields = [
    {
      name: "Equipped",
      value:
        equipped.length > 0
          ? formatItemList(equipped, lineOf)
          : (options.emptyEquipped ?? "Nothing equipped."),
    },
    ...rest
      .filter((group) => group.item_instances.length > 0)
      .map((group) => ({
        name: groupName(group),
        value: formatItemList(group.item_instances, lineOf),
      })),
  ];

  const visibleFields = fields.slice(0, MAX_FIELDS_PER_EMBED);
  embed.addFields(visibleFields);

  const omittedFields = fields.length - visibleFields.length;
  if (omittedFields > 0) {
    embed.setFooter({
      text: `…and ${omittedFields} more container${omittedFields === 1 ? "" : "s"}, not shown.`,
    });
  }

  return embed;
}

/** "Belt pouch, in Backpack"; "Elsewhere: Pia has these, in Tavern". */
function groupName(group: HeldGroup): string {
  const within = group.path.map((around) => `in ${around.name}`).join(", ");
  const name =
    group.container_kind === "being" ? `${group.container.name} has these` : group.container.name;
  const placed = within ? `${name}, ${within}` : name;
  const full = group.carried ? placed : `Elsewhere: ${placed}`;
  return full.length <= MAX_FIELD_NAME_LENGTH
    ? full
    : `${full.slice(0, MAX_FIELD_NAME_LENGTH - 1)}…`;
}

function formatItemList(items: readonly HeldItem[], lineOf: (item: HeldItem) => string): string {
  const lines = items.map((item) => `• ${lineOf(item)}`);
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

// `quantity` is a stack size (ADR 0041 - splitting a stack needs one) -
// null/1 means "just one, not a stack", so it's only surfaced when it's
// actually informative. A `slug` (ADR 0043 - only ever set on an instance
// someone deliberately named) is shown as an inline code span so it reads as
// something to copy, e.g. into `/drop container:`; most instances have none,
// and their lines are unchanged. Something that isn't the character's own
// says whose it is (ADR 0123).
function formatItemLine(
  item: HeldItem,
  holderId: string | null,
  owners: ReadonlyMap<string, string>,
): string {
  const name = item.title ?? "(untitled)";
  let line = item.quantity !== null && item.quantity > 1 ? `${name} ×${item.quantity}` : name;
  if (item.slug) line = `${line} \`${item.slug}\``;
  if (holderId === null || item.owner_entity_id === holderId) return line;
  if (item.owner_entity_id === null) return `${line} — No one's`;
  const owner = owners.get(item.owner_entity_id);
  return `${line} — ${owner ? `${owner}'s` : "Someone else's"}`;
}
