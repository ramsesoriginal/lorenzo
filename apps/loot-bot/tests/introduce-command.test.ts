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

const { introduceCommand } = await import("../src/commands/introduce.js");

const config = {
  lorenzoApiBaseUrl: "http://lorenzo-api.test",
  lorenzoTenantId: "tenant-1",
} as Config;

function baseProfile() {
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
  };
}

function fakeInteraction(userId = "discord-user-1") {
  return {
    user: { id: userId },
    deferReply: vi.fn(async () => undefined),
    editReply: vi.fn(async () => undefined),
    followUp: vi.fn(async () => ({ id: "message-1" })),
  } as unknown as ChatInputCommandInteraction & {
    deferReply: ReturnType<typeof vi.fn>;
    editReply: ReturnType<typeof vi.fn>;
    followUp: ReturnType<typeof vi.fn>;
  };
}

describe("introduceCommand", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("defers ephemerally - not linked yet stays private", async () => {
    getValidAccessToken.mockResolvedValue(null);
    const interaction = fakeInteraction();

    await introduceCommand.execute(interaction, { config, logger: {} as never });

    expect(interaction.deferReply).toHaveBeenCalledWith({ ephemeral: true });
    expect(interaction.editReply).toHaveBeenCalledWith(
      expect.stringContaining("run `/link` first"),
    );
    expect(interaction.followUp).not.toHaveBeenCalled();
    expect(getMyProfile).not.toHaveBeenCalled();
  });

  it("tells the caller privately when there's nothing to introduce, without posting publicly", async () => {
    getValidAccessToken.mockResolvedValue("token-123");
    getMyProfile.mockResolvedValue(baseProfile());
    const interaction = fakeInteraction();

    await introduceCommand.execute(interaction, { config, logger: {} as never });

    expect(interaction.editReply).toHaveBeenCalledWith(
      expect.stringContaining("nothing to introduce"),
    );
    expect(interaction.followUp).not.toHaveBeenCalled();
  });

  it("posts a public follow-up embed when the caller has a name set", async () => {
    getValidAccessToken.mockResolvedValue("token-123");
    getMyProfile.mockResolvedValue({ ...baseProfile(), displayName: "Frodo Baggins" });
    const interaction = fakeInteraction();

    await introduceCommand.execute(interaction, { config, logger: {} as never });

    expect(getMyProfile).toHaveBeenCalledWith("tenant-1", "token-123");
    expect(interaction.followUp).toHaveBeenCalledTimes(1);
    const call = interaction.followUp.mock.calls[0]?.[0];
    expect(call.ephemeral).toBe(false);
    expect(call.embeds[0].data.title).toBe("Frodo Baggins");
  });
});
