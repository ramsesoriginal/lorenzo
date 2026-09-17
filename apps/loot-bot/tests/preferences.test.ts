import { beforeEach, describe, expect, it, vi } from "vitest";

const { getPreference } = vi.hoisted(() => ({ getPreference: vi.fn() }));
vi.mock("../src/db.js", () => ({ getPreference }));

const { resolveCurrentCharacter, resolveCurrentContainer } = await import("../src/preferences.js");

describe("resolveCurrentCharacter", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("returns the explicit value without touching the stored preference", async () => {
    const result = await resolveCurrentCharacter("user-1", "channel-1", "char-explicit");

    expect(result).toBe("char-explicit");
    expect(getPreference).not.toHaveBeenCalled();
  });

  it("falls back to the stored preference when nothing explicit is given", async () => {
    getPreference.mockResolvedValue({ currentCharacterEntityId: "char-stored" });

    const result = await resolveCurrentCharacter("user-1", "channel-1", undefined);

    expect(result).toBe("char-stored");
    expect(getPreference).toHaveBeenCalledWith("user-1", "channel-1");
  });

  it("falls back to the stored preference for a null explicit value too", async () => {
    getPreference.mockResolvedValue({ currentCharacterEntityId: "char-stored" });

    const result = await resolveCurrentCharacter("user-1", "channel-1", null);

    expect(result).toBe("char-stored");
  });

  it("returns undefined when there's neither an explicit value nor a stored preference", async () => {
    getPreference.mockResolvedValue(undefined);

    const result = await resolveCurrentCharacter("user-1", "channel-1", undefined);

    expect(result).toBeUndefined();
  });
});

describe("resolveCurrentContainer", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("returns the explicit value without touching the stored preference", async () => {
    const result = await resolveCurrentContainer("user-1", "channel-1", "container-explicit");

    expect(result).toBe("container-explicit");
    expect(getPreference).not.toHaveBeenCalled();
  });

  it("falls back to the stored preference when nothing explicit is given", async () => {
    getPreference.mockResolvedValue({ currentContainerEntityId: "container-stored" });

    const result = await resolveCurrentContainer("user-1", "channel-1", undefined);

    expect(result).toBe("container-stored");
    expect(getPreference).toHaveBeenCalledWith("user-1", "channel-1");
  });

  it("returns undefined when the stored preference has no container set", async () => {
    getPreference.mockResolvedValue({ currentContainerEntityId: null });

    const result = await resolveCurrentContainer("user-1", "channel-1", undefined);

    expect(result).toBeUndefined();
  });
});
