import { afterEach, describe, expect, it, vi } from "vitest";
import {
  DiscordApiError,
  getRecentChannelAuthorIds,
  sendDirectMessage,
} from "../src/discord-rest.js";

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

describe("sendDirectMessage", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  function json(body: unknown, status = 200) {
    return {
      ok: status < 400,
      status,
      json: async () => body,
      text: async () => JSON.stringify(body),
    };
  }

  it("opens the DM channel, then posts the message to it, as the bot", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(json({ id: "dm-channel-1" }))
      .mockResolvedValueOnce(json({ id: "message-1" }));
    vi.stubGlobal("fetch", fetchMock);

    const result = await sendDirectMessage("bot-token-abc", "user-1", { content: "hello" });

    expect(result).toEqual({ kind: "sent" });
    expect(fetchMock).toHaveBeenNthCalledWith(1, "https://discord.com/api/v10/users/@me/channels", {
      method: "POST",
      headers: { authorization: "Bot bot-token-abc", "content-type": "application/json" },
      body: JSON.stringify({ recipient_id: "user-1" }),
    });
    expect(fetchMock).toHaveBeenNthCalledWith(
      2,
      "https://discord.com/api/v10/channels/dm-channel-1/messages",
      {
        method: "POST",
        headers: { authorization: "Bot bot-token-abc", "content-type": "application/json" },
        body: JSON.stringify({ content: "hello" }),
      },
    );
  });

  it("reports closed DMs (403, code 50007) on sending the message - a fact, not an error", async () => {
    vi.stubGlobal(
      "fetch",
      vi
        .fn()
        .mockResolvedValueOnce(json({ id: "dm-channel-1" }))
        .mockResolvedValueOnce(
          json({ code: 50007, message: "Cannot send messages to this user" }, 403),
        ),
    );

    await expect(sendDirectMessage("t", "user-1", { content: "x" })).resolves.toEqual({
      kind: "closed",
    });
  });

  it("reports closed DMs when it's opening the channel that's refused", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValueOnce(json({ code: 50007, message: "Cannot send" }, 403)),
    );

    await expect(sendDirectMessage("t", "user-1", { content: "x" })).resolves.toEqual({
      kind: "closed",
    });
  });

  it("throws for a 403 that isn't 'DMs closed', carrying Discord's code", async () => {
    vi.stubGlobal(
      "fetch",
      vi
        .fn()
        .mockResolvedValueOnce(json({ id: "dm-channel-1" }))
        .mockResolvedValueOnce(json({ code: 50001, message: "Missing Access" }, 403)),
    );

    await expect(sendDirectMessage("t", "user-1", { content: "x" })).rejects.toMatchObject({
      name: "DiscordApiError",
      status: 403,
      code: 50001,
    });
  });

  it("throws for a rate limit rather than mistaking it for closed DMs", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValueOnce(json({ message: "You are being rate limited." }, 429)),
    );

    await expect(sendDirectMessage("t", "user-1", { content: "x" })).rejects.toBeInstanceOf(
      DiscordApiError,
    );
  });

  it("throws for a non-JSON error body (say, a gateway error page)", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValueOnce({
        ok: false,
        status: 502,
        text: async () => "<html>Bad Gateway</html>",
      }),
    );

    await expect(sendDirectMessage("t", "user-1", { content: "x" })).rejects.toMatchObject({
      status: 502,
      code: undefined,
    });
  });
});
