import { describe, expect, it } from "vitest";
import { formatWhoamiEmbed } from "../src/format-whoami.js";
import type { MyProfile } from "../src/lorenzo-client.js";

function profile(overrides: Partial<MyProfile> = {}): MyProfile {
  return {
    email: null,
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

describe("formatWhoamiEmbed", () => {
  it("sets the thumbnail to the caller's own picture_url", () => {
    const embed = formatWhoamiEmbed(profile()).toJSON();
    expect(embed.thumbnail?.url).toBe("https://lorenzo-api.test/users/user-1/picture");
  });

  it("sets the embed color from user_color when set", () => {
    const embed = formatWhoamiEmbed(profile({ color: "#00FF00" })).toJSON();
    expect(embed.color).toBe(0x00ff00);
  });

  it("leaves the embed color unset when user_color is null", () => {
    const embed = formatWhoamiEmbed(profile()).toJSON();
    expect(embed.color).toBeUndefined();
  });

  it("shows '(not set)' for every unset identity field", () => {
    const embed = formatWhoamiEmbed(profile()).toJSON();
    expect(embed.fields?.[0]).toEqual({
      name: "Identity",
      value:
        "**Display name:** (not set)\n**Nickname:** (not set)\n**Pronouns:** (not set)\n**Email:** (not set)",
    });
  });

  it("shows every set identity field", () => {
    const embed = formatWhoamiEmbed(
      profile({
        displayName: "Frodo Baggins",
        nickname: "frodo",
        pronouns: "he/him",
        email: "frodo@shire.example",
      }),
    ).toJSON();
    expect(embed.fields?.[0]).toEqual({
      name: "Identity",
      value:
        "**Display name:** Frodo Baggins\n**Nickname:** frodo\n**Pronouns:** he/him\n**Email:** frodo@shire.example",
    });
  });

  it("omits the Bio field when unset", () => {
    const embed = formatWhoamiEmbed(profile()).toJSON();
    expect(embed.fields?.some((f) => f.name === "Bio")).toBe(false);
  });

  it("shows the Bio field when set", () => {
    const embed = formatWhoamiEmbed(profile({ bio: "Just a hobbit." })).toJSON();
    expect(embed.fields?.find((f) => f.name === "Bio")).toEqual({
      name: "Bio",
      value: "Just a hobbit.",
    });
  });

  it("omits the Locales field when empty", () => {
    const embed = formatWhoamiEmbed(profile()).toJSON();
    expect(embed.fields?.some((f) => f.name === "Locales")).toBe(false);
  });

  it("shows the Locales field, comma-separated, when set", () => {
    const embed = formatWhoamiEmbed(profile({ locales: ["en-US", "de-DE"] })).toJSON();
    expect(embed.fields?.find((f) => f.name === "Locales")).toEqual({
      name: "Locales",
      value: "en-US, de-DE",
    });
  });

  it("labels an owner membership", () => {
    const embed = formatWhoamiEmbed(profile({ membershipRole: "owner" })).toJSON();
    expect(embed.fields?.find((f) => f.name === "Tenant role")?.value).toBe("Owner");
  });

  it("labels an orga membership", () => {
    const embed = formatWhoamiEmbed(profile({ membershipRole: "orga" })).toJSON();
    expect(embed.fields?.find((f) => f.name === "Tenant role")?.value).toBe("Orga");
  });

  it("explains a null membershipRole as the normal player case, not an error", () => {
    const embed = formatWhoamiEmbed(profile()).toJSON();
    expect(embed.fields?.find((f) => f.name === "Tenant role")?.value).toBe(
      "Player (no tenant-wide admin role)",
    );
  });

  it("lists character names, singular field label for exactly one", () => {
    const embed = formatWhoamiEmbed(
      profile({ characters: [{ entityId: "1", name: "Frodo" }] }),
    ).toJSON();
    expect(embed.fields?.find((f) => f.name === "Character")).toEqual({
      name: "Character",
      value: "Frodo",
    });
  });

  it("lists multiple character names comma-separated, plural field label", () => {
    const embed = formatWhoamiEmbed(
      profile({
        characters: [
          { entityId: "1", name: "Frodo" },
          { entityId: "2", name: "Sam" },
        ],
      }),
    ).toJSON();
    expect(embed.fields?.find((f) => f.name === "Characters")).toEqual({
      name: "Characters",
      value: "Frodo, Sam",
    });
  });

  it("shows 'None yet.' when the caller controls no characters in this tenant", () => {
    const embed = formatWhoamiEmbed(profile()).toJSON();
    expect(embed.fields?.find((f) => f.name === "Characters")).toEqual({
      name: "Characters",
      value: "None yet.",
    });
  });

  it("omits the GM field entirely when the caller isn't a GM anywhere", () => {
    const embed = formatWhoamiEmbed(profile()).toJSON();
    expect(embed.fields?.some((f) => f.name === "GM")).toBe(false);
  });

  it("shows a singular GM count", () => {
    const embed = formatWhoamiEmbed(profile({ gmCampaignCount: 1 })).toJSON();
    expect(embed.fields?.find((f) => f.name === "GM")?.value).toMatch(/^GM for 1 campaign \(/);
  });

  it("shows a plural GM count", () => {
    const embed = formatWhoamiEmbed(profile({ gmCampaignCount: 3 })).toJSON();
    expect(embed.fields?.find((f) => f.name === "GM")?.value).toMatch(/^GM for 3 campaigns \(/);
  });
});
