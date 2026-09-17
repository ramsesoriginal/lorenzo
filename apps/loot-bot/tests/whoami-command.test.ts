import { beforeEach, describe, expect, it, vi } from "vitest";
import type { ChatInputCommandInteraction } from "../src/commands/types.js";
import type { Config } from "../src/config.js";

const { getValidAccessToken } = vi.hoisted(() => ({ getValidAccessToken: vi.fn() }));
vi.mock("../src/token-provider.js", () => ({ getValidAccessToken }));

const { getMyProfile, createLorenzoApiClient } = vi.hoisted(() => ({
  getMyProfile: vi.fn(),
  createLorenzoApiClient: vi.fn(),
}));
vi.mock("../src/lorenzo-client.js", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../src/lorenzo-client.js")>();
  return {
    ...actual,
    createLorenzoApiClient: createLorenzoApiClient.mockReturnValue({ getMyProfile }),
  };
});

const { whoamiCommand } = await import("../src/commands/whoami.js");

const config = {
  lorenzoApiBaseUrl: "http://lorenzo-api.test",
  lorenzoTenantId: "tenant-1",
} as Config;

function fakeInteraction(userId = "discord-user-1") {
  return {
    user: { id: userId },
    deferReply: vi.fn(async () => undefined),
    editReply: vi.fn(async () => undefined),
  } as unknown as ChatInputCommandInteraction & {
    deferReply: ReturnType<typeof vi.fn>;
    editReply: ReturnType<typeof vi.fn>;
  };
}

describe("whoamiCommand", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("prompts to /link when there's no valid access token", async () => {
    getValidAccessToken.mockResolvedValue(null);
    const interaction = fakeInteraction();

    await whoamiCommand.execute(interaction, { config, logger: {} as never });

    expect(interaction.editReply).toHaveBeenCalledWith(
      expect.stringContaining("run `/link` first"),
    );
    expect(getMyProfile).not.toHaveBeenCalled();
  });

  it("fetches the profile for this bot's own tenant and replies with one embed", async () => {
    getValidAccessToken.mockResolvedValue("token-123");
    getMyProfile.mockResolvedValue({
      email: "frodo@shire.example",
      nickname: "frodo",
      displayName: "Frodo Baggins",
      pronouns: "he/him",
      bio: null,
      locales: [],
      color: null,
      pictureUrl: "https://lorenzo-api.test/users/user-1/picture",
      membershipRole: "owner",
      characters: [{ entityId: "char-1", name: "Frodo" }],
      gmCampaignCount: 0,
    });

    const interaction = fakeInteraction();
    await whoamiCommand.execute(interaction, { config, logger: {} as never });

    expect(getMyProfile).toHaveBeenCalledWith("tenant-1", "token-123");
    const call = interaction.editReply.mock.calls[0]?.[0];
    expect(call.embeds).toHaveLength(1);
    expect(call.embeds[0].data.title).toBe("You're linked as...");
  });
});
