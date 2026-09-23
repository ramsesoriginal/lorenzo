import { beforeEach, describe, expect, it, vi } from "vitest";
import type { LorenzoApiClient } from "../src/lorenzo-client.js";

const { setPreference } = vi.hoisted(() => ({ setPreference: vi.fn() }));
vi.mock("../src/db.js", () => ({ setPreference, GLOBAL_PREFERENCE_CHANNEL_ID: "" }));

const { rememberActingCharacter } = await import("../src/commands/remember-character.js");

const getControlledCharacters = vi.fn();
const client = { getControlledCharacters } as unknown as LorenzoApiClient;
const warn = vi.fn();
const logger = { warn } as never;

function remember(ownerEntityId: string | null) {
  return rememberActingCharacter(client, "tenant-1", "token-1", "user-1", ownerEntityId, logger);
}

describe("rememberActingCharacter", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("stores a character the caller controls as their server-wide default", async () => {
    getControlledCharacters.mockResolvedValue([
      { entityId: "char-1", name: "Frodo" },
      { entityId: "char-2", name: "Sam" },
    ]);

    await remember("char-2");

    expect(getControlledCharacters).toHaveBeenCalledWith("tenant-1", "token-1");
    expect(setPreference).toHaveBeenCalledWith("user-1", "", { characterEntityId: "char-2" });
  });

  it("ignores an item someone else's character owns (a GM acting on a player's item)", async () => {
    getControlledCharacters.mockResolvedValue([{ entityId: "char-1", name: "Frodo" }]);

    await remember("someone-elses-char");

    expect(setPreference).not.toHaveBeenCalled();
  });

  it("ignores an ownerless item without even asking the API who the caller controls", async () => {
    await remember(null);

    expect(getControlledCharacters).not.toHaveBeenCalled();
    expect(setPreference).not.toHaveBeenCalled();
  });

  it("swallows and logs an API failure - it must never break the write that already succeeded", async () => {
    getControlledCharacters.mockRejectedValue(new Error("api down"));

    await expect(remember("char-1")).resolves.toBeUndefined();

    expect(setPreference).not.toHaveBeenCalled();
    expect(warn).toHaveBeenCalledTimes(1);
  });

  it("swallows and logs a database failure too", async () => {
    getControlledCharacters.mockResolvedValue([{ entityId: "char-1", name: "Frodo" }]);
    setPreference.mockRejectedValue(new Error("db down"));

    await expect(remember("char-1")).resolves.toBeUndefined();

    expect(warn).toHaveBeenCalledTimes(1);
  });
});
