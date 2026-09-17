import { describe, expect, it } from "vitest";
import { formatIntroduceEmbed } from "../src/format-introduce.js";
import type { MyProfile } from "../src/lorenzo-client.js";

function profile(overrides: Partial<MyProfile> = {}): MyProfile {
  return {
    email: "frodo@shire.example",
    nickname: null,
    displayName: null,
    pronouns: null,
    bio: null,
    locales: [],
    color: null,
    pictureUrl: "https://lorenzo-api.test/users/user-1/picture",
    membershipRole: null,
    characters: [],
    gmCampaignCount: 0,
    ...overrides,
  };
}

describe("formatIntroduceEmbed", () => {
  it("returns null when there's no displayName or nickname to title the post with", () => {
    expect(formatIntroduceEmbed(profile())).toBeNull();
  });

  it("titles the post with displayName when set", () => {
    const embed = formatIntroduceEmbed(profile({ displayName: "Frodo Baggins" }))?.toJSON();
    expect(embed?.title).toBe("Frodo Baggins");
  });

  it("falls back to nickname when displayName is unset", () => {
    const embed = formatIntroduceEmbed(profile({ nickname: "frodo" }))?.toJSON();
    expect(embed?.title).toBe("frodo");
  });

  it("prefers displayName over nickname when both are set", () => {
    const embed = formatIntroduceEmbed(
      profile({ displayName: "Frodo Baggins", nickname: "frodo" }),
    )?.toJSON();
    expect(embed?.title).toBe("Frodo Baggins");
  });

  it("appends pronouns to the title in parentheses when set", () => {
    const embed = formatIntroduceEmbed(
      profile({ displayName: "Frodo Baggins", pronouns: "he/him" }),
    )?.toJSON();
    expect(embed?.title).toBe("Frodo Baggins (he/him)");
  });

  it("omits the parenthetical when pronouns are unset", () => {
    const embed = formatIntroduceEmbed(profile({ displayName: "Frodo Baggins" }))?.toJSON();
    expect(embed?.title).toBe("Frodo Baggins");
  });

  it("sets the thumbnail to picture_url", () => {
    const embed = formatIntroduceEmbed(profile({ displayName: "Frodo Baggins" }))?.toJSON();
    expect(embed?.thumbnail?.url).toBe("https://lorenzo-api.test/users/user-1/picture");
  });

  it("sets the embed color from user_color when set", () => {
    const embed = formatIntroduceEmbed(
      profile({ displayName: "Frodo Baggins", color: "#00FF00" }),
    )?.toJSON();
    expect(embed?.color).toBe(0x00ff00);
  });

  it("uses bio as the embed description when set", () => {
    const embed = formatIntroduceEmbed(
      profile({ displayName: "Frodo Baggins", bio: "Just a hobbit." }),
    )?.toJSON();
    expect(embed?.description).toBe("Just a hobbit.");
  });

  it("has no description when bio is unset", () => {
    const embed = formatIntroduceEmbed(profile({ displayName: "Frodo Baggins" }))?.toJSON();
    expect(embed?.description).toBeUndefined();
  });

  it("never shows email, nickname-as-a-field, or tenant/character info - only name/pronouns/bio/color/picture", () => {
    const embed = formatIntroduceEmbed(
      profile({
        displayName: "Frodo Baggins",
        characters: [{ entityId: "1", name: "Frodo" }],
        membershipRole: "owner",
      }),
    )?.toJSON();
    expect(embed?.fields ?? []).toHaveLength(0);
  });
});
