import { afterEach, describe, expect, it, vi } from "vitest";
import { getRecentChannelAuthorIds } from "../src/discord-rest.js";

describe("getRecentChannelAuthorIds", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("returns distinct, non-bot author ids, authenticated with the bot token", async () => {
    const fetchMock = vi.fn(async () => ({
      ok: true,
      json: async () => [
        { author: { id: "user-1" } },
        { author: { id: "user-2" } },
        { author: { id: "user-1" } },
        { author: { id: "bot-1", bot: true } },
      ],
    }));
    vi.stubGlobal("fetch", fetchMock);

    const ids = await getRecentChannelAuthorIds("bot-token-abc", "channel-1");

    expect(ids).toEqual(["user-1", "user-2"]);
    expect(fetchMock).toHaveBeenCalledWith(
      "https://discord.com/api/v10/channels/channel-1/messages?limit=100",
      { headers: { authorization: "Bot bot-token-abc" } },
    );
  });

  it("throws when Discord responds with an error", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => ({ ok: false, status: 403, text: async () => "Missing Permissions" })),
    );

    await expect(getRecentChannelAuthorIds("bot-token-abc", "channel-1")).rejects.toThrow(
      "Discord API call failed: 403",
    );
  });
});
