import { EmbedBuilder } from "discord.js";
import type { EntityDetailOut } from "./lorenzo-client.js";

const MAX_FIELDS_PER_EMBED = 25;
const MAX_FIELD_VALUE_LENGTH = 1024;

type Information = EntityDetailOut["information"][number];
type Payload = Information["payloads"][number];

/**
 * Renders an entity (fetched via `getEntity`) as a single Discord embed -
 * name, stats, and every visible `Information` entry as its own field
 * (`/item`, "display item"). Pure function, no Discord API calls -
 * mirrors format-inventory.ts's own split from inventory.ts.
 *
 * `information` is already server-side visibility-filtered
 * (`information_visibility.py`/ADR 0035) before it ever reaches this
 * function - unlike `/give`'s autocomplete, there is no "never
 * authoritative" caveat to repeat here, this really is everything the
 * caller is allowed to see.
 */
export function formatItemEmbed(entity: EntityDetailOut): EmbedBuilder {
  const embed = new EmbedBuilder().setTitle(entity.name);

  const firstPicture = entity.information
    .flatMap((info) => info.payloads)
    .find(
      (payload): payload is Extract<Payload, { kind: "picture" }> => payload.kind === "picture",
    );
  if (firstPicture) {
    embed.setImage(firstPicture.url);
  }

  if (entity.stats.length > 0) {
    const statLines = entity.stats.map((stat) => `${stat.name}: ${stat.value}`).join("\n");
    embed.addFields({ name: "Stats", value: truncate(statLines) });
  }

  const budget = MAX_FIELDS_PER_EMBED - (entity.stats.length > 0 ? 1 : 0);
  const visibleInfo = entity.information.slice(0, Math.max(budget, 0));
  for (const info of visibleInfo) {
    embed.addFields({ name: info.title, value: truncate(formatPayloads(info.payloads)) });
  }

  const omitted = entity.information.length - visibleInfo.length;
  if (omitted > 0) {
    embed.setFooter({ text: `…and ${omitted} more note${omitted === 1 ? "" : "s"}, not shown.` });
  }

  if (entity.stats.length === 0 && entity.information.length === 0) {
    embed.setDescription("No stats or notes visible to you.");
  }

  return embed;
}

function formatPayloads(payloads: readonly Payload[]): string {
  if (payloads.length === 0) return "(no content)";
  return payloads
    .map((payload) => {
      switch (payload.kind) {
        case "description":
          return payload.content;
        case "number":
          return payload.value;
        case "picture":
          return `[picture](${payload.url})`;
        case "document":
          return `[${payload.filename}](${payload.url})`;
        default:
          return "(unrecognized content)";
      }
    })
    .join("\n");
}

function truncate(text: string): string {
  return text.length <= MAX_FIELD_VALUE_LENGTH
    ? text
    : `${text.slice(0, MAX_FIELD_VALUE_LENGTH - 1)}…`;
}
