import { EmbedBuilder, type HexColorString } from "discord.js";
import type { MyProfile } from "./lorenzo-client.js";

/**
 * Renders `/introduce`'s public post (ADR 0060) - a deliberately narrow,
 * curated subset of `MyProfile`, unlike `/whoami`'s own private, complete
 * view (format-whoami.ts): name, pronouns, bio, favorite color, and
 * picture only. No `email`, `nickname`, `locales`, or any tenant/character
 * info - nothing here is sensitive, but nothing here is *relevant* to a
 * channel introduction either, and apps/api's own ADR 0060 already draws
 * this same line (only `display_name`/`user_color` - alongside `nickname`,
 * which this command skips as not being an "introduce yourself" fact - are
 * ever exposed to *other* users on the tenant roster; `pronouns`/`bio`
 * stay private-to-`/me` on apps/api's side, but posting one's own to a
 * channel via a command *you* ran is a voluntary act of self-disclosure,
 * not apps/api exposing it to someone else on your behalf).
 *
 * Returns `null` when there's nothing to introduce - no `displayName` and
 * no `nickname` means no name to even title the post with, and posting a
 * nameless embed publicly would be worse than not posting at all.
 */
export function formatIntroduceEmbed(profile: MyProfile): EmbedBuilder | null {
  const name = profile.displayName ?? profile.nickname;
  if (!name) return null;

  const embed = new EmbedBuilder()
    .setTitle(profile.pronouns ? `${name} (${profile.pronouns})` : name)
    .setThumbnail(profile.pictureUrl);

  // apps/api validates this as `^#[0-9A-Fa-f]{6}$` at the schema boundary
  // (ADR 0060) before it's ever stored, so the cast is safe whenever it's
  // non-null - never constructed client-side.
  if (profile.color) embed.setColor(profile.color as HexColorString);

  if (profile.bio) embed.setDescription(profile.bio);

  return embed;
}
