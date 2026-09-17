import { EmbedBuilder, type HexColorString } from "discord.js";
import type { MyProfile } from "./lorenzo-client.js";

// Matches MembershipRole's own two values (apps/api/src/lorenzo_api/models/
// membership.py) - there's no "member" role at all: an ordinary player who
// isn't an owner/orga simply has no Membership row, which is the normal,
// expected case, not a gap to flag.
const ROLE_LABELS: Readonly<Record<string, string>> = {
  owner: "Owner",
  orga: "Orga",
};

const NOT_SET = "(not set)";

/**
 * Renders `/whoami`'s answer (ADR 0050/0060) - pure function, no Discord
 * API calls, tested against plain fixture data like every other
 * `format-*.ts` module. Deliberately doesn't show the one raw id `/me`
 * itself still carries alongside the profile fields (`authgear_subject_id`)
 * - an internal identifier, not anything a player would recognize as "who
 * they are." Private/ephemeral only (commands/whoami.ts) - shows every
 * profile field, including `email`, since this is the caller looking at
 * their own identity; contrast `/introduce` (format-introduce.ts), which
 * posts a deliberately narrower, public subset.
 */
export function formatWhoamiEmbed(profile: MyProfile): EmbedBuilder {
  const embed = new EmbedBuilder().setTitle("You're linked as...").setThumbnail(profile.pictureUrl);

  // apps/api validates this as `^#[0-9A-Fa-f]{6}$` at the schema boundary
  // (ADR 0060) before it's ever stored, so the cast is safe whenever it's
  // non-null - never constructed client-side.
  if (profile.color) embed.setColor(profile.color as HexColorString);

  embed.addFields({
    name: "Identity",
    value: [
      `**Display name:** ${profile.displayName ?? NOT_SET}`,
      `**Nickname:** ${profile.nickname ?? NOT_SET}`,
      `**Pronouns:** ${profile.pronouns ?? NOT_SET}`,
      `**Email:** ${profile.email ?? NOT_SET}`,
    ].join("\n"),
  });

  if (profile.bio) {
    embed.addFields({ name: "Bio", value: profile.bio });
  }

  if (profile.locales.length > 0) {
    embed.addFields({ name: "Locales", value: profile.locales.join(", ") });
  }

  embed.addFields({
    name: "Tenant role",
    value: profile.membershipRole
      ? (ROLE_LABELS[profile.membershipRole] ?? profile.membershipRole)
      : "Player (no tenant-wide admin role)",
  });

  embed.addFields({
    name: profile.characters.length === 1 ? "Character" : "Characters",
    value:
      profile.characters.length > 0
        ? profile.characters.map((character) => character.name).join(", ")
        : "None yet.",
  });

  if (profile.gmCampaignCount > 0) {
    embed.addFields({
      name: "GM",
      value: `GM for ${profile.gmCampaignCount} campaign${profile.gmCampaignCount === 1 ? "" : "s"} (may include campaigns outside this server's own tenant).`,
    });
  }

  return embed;
}
