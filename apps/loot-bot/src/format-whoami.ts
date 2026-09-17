import { EmbedBuilder } from "discord.js";
import type { MyProfile } from "./lorenzo-client.js";

// Matches MembershipRole's own two values (apps/api/src/lorenzo_api/models/
// membership.py) - there's no "member" role at all: an ordinary player who
// isn't an owner/orga simply has no Membership row, which is the normal,
// expected case, not a gap to flag.
const ROLE_LABELS: Readonly<Record<string, string>> = {
  owner: "Owner",
  orga: "Orga",
};

/**
 * Renders `/whoami`'s answer (ADR 0050) - pure function, no Discord API
 * calls, tested against plain fixture data like every other `format-*.ts`
 * module. Deliberately doesn't show either raw id `/me` itself carries
 * (`id`, `authgear_subject_id`) - internal identifiers, not anything a
 * player would recognize as "who they are."
 */
export function formatWhoamiEmbed(profile: MyProfile): EmbedBuilder {
  const embed = new EmbedBuilder().setTitle("You're linked as...");

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
