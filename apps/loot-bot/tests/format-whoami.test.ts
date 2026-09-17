import { describe, expect, it } from "vitest";
import { formatWhoamiEmbed } from "../src/format-whoami.js";
import type { MyProfile } from "../src/lorenzo-client.js";

function profile(overrides: Partial<MyProfile> = {}): MyProfile {
  return { membershipRole: null, characters: [], gmCampaignCount: 0, ...overrides };
}

describe("formatWhoamiEmbed", () => {
  it("labels an owner membership", () => {
    const embed = formatWhoamiEmbed(profile({ membershipRole: "owner" })).toJSON();
    expect(embed.fields?.[0]).toEqual({ name: "Tenant role", value: "Owner" });
  });

  it("labels an orga membership", () => {
    const embed = formatWhoamiEmbed(profile({ membershipRole: "orga" })).toJSON();
    expect(embed.fields?.[0]).toEqual({ name: "Tenant role", value: "Orga" });
  });

  it("explains a null membershipRole as the normal player case, not an error", () => {
    const embed = formatWhoamiEmbed(profile()).toJSON();
    expect(embed.fields?.[0]?.value).toBe("Player (no tenant-wide admin role)");
  });

  it("lists character names, singular field label for exactly one", () => {
    const embed = formatWhoamiEmbed(
      profile({ characters: [{ entityId: "1", name: "Frodo" }] }),
    ).toJSON();
    expect(embed.fields?.[1]).toEqual({ name: "Character", value: "Frodo" });
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
    expect(embed.fields?.[1]).toEqual({ name: "Characters", value: "Frodo, Sam" });
  });

  it("shows 'None yet.' when the caller controls no characters in this tenant", () => {
    const embed = formatWhoamiEmbed(profile()).toJSON();
    expect(embed.fields?.[1]).toEqual({ name: "Characters", value: "None yet." });
  });

  it("omits the GM field entirely when the caller isn't a GM anywhere", () => {
    const embed = formatWhoamiEmbed(profile()).toJSON();
    expect(embed.fields).toHaveLength(2);
  });

  it("shows a singular GM count", () => {
    const embed = formatWhoamiEmbed(profile({ gmCampaignCount: 1 })).toJSON();
    expect(embed.fields?.[2]?.value).toMatch(/^GM for 1 campaign \(/);
  });

  it("shows a plural GM count", () => {
    const embed = formatWhoamiEmbed(profile({ gmCampaignCount: 3 })).toJSON();
    expect(embed.fields?.[2]?.value).toMatch(/^GM for 3 campaigns \(/);
  });
});
