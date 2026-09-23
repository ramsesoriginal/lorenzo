import { describe, expect, it } from "vitest";
import {
  BANNER_MAX_ENTRIES,
  buildNotificationEmbed,
  buildUndeliveredBanner,
} from "../src/format-notification.js";

function notice(n: number, body = "Something happened.") {
  return { notificationId: `n-${n}`, title: `Notice ${n}`, body };
}

describe("buildNotificationEmbed", () => {
  it("uses the notification's own title and body, and says where it came from", () => {
    const embed = buildNotificationEmbed({
      title: "You were awarded Ashfang",
      body: "The GM awarded you a sword.",
      scope: "campaign",
    }).toJSON();

    expect(embed.title).toBe("You were awarded Ashfang");
    expect(embed.description).toBe("The GM awarded you a sword.");
    expect(embed.footer?.text).toBe("Lorenzo · campaign notification");
  });

  it("truncates to Discord's embed limits rather than failing the send", () => {
    const embed = buildNotificationEmbed({
      title: "t".repeat(400),
      body: "b".repeat(5000),
      scope: "tenant",
    }).toJSON();

    expect(embed.title).toHaveLength(256);
    expect(embed.description).toHaveLength(4096);
    expect(embed.title?.endsWith("…")).toBe(true);
  });
});

describe("buildUndeliveredBanner", () => {
  it("has nothing to say when nothing is undelivered", () => {
    expect(buildUndeliveredBanner([])).toBeUndefined();
  });

  it("says plainly that it couldn't DM, and lists what it couldn't send", () => {
    const banner = buildUndeliveredBanner([notice(1, "The GM awarded you a sword.")]);

    expect(banner?.content).toContain("**Couldn't DM you.**");
    expect(banner?.content).toContain("1 notification for you");
    expect(banner?.content).toContain("Here it is:");
    expect(banner?.content).toContain("• **Notice 1** — The GM awarded you a sword.");
    expect(banner?.shownIds).toEqual(["n-1"]);
  });

  it("uses the plural for several", () => {
    const banner = buildUndeliveredBanner([notice(1), notice(2)]);

    expect(banner?.content).toContain("2 notifications for you");
    expect(banner?.content).toContain("Here they are:");
  });

  it("shows only a few, counts the rest, and marks only the shown ones as noticed", () => {
    const many = Array.from({ length: BANNER_MAX_ENTRIES + 3 }, (_, i) => notice(i + 1));

    const banner = buildUndeliveredBanner(many);

    expect(banner?.shownIds).toEqual(
      many.slice(0, BANNER_MAX_ENTRIES).map((n) => n.notificationId),
    );
    expect(banner?.content).toContain(`${many.length} notifications`);
    expect(banner?.content).toContain("…and 3 more, which I'll show on your next commands");
    expect(banner?.content).not.toContain(`Notice ${BANNER_MAX_ENTRIES + 1}`);
  });

  it("keeps each entry to a short snippet on one line", () => {
    const banner = buildUndeliveredBanner([notice(1, `line one\n\nline two ${"x".repeat(500)}`)]);

    const line = banner?.content.split("\n").find((l) => l.startsWith("• "));
    expect(line).not.toContain("\n");
    expect(line?.length).toBeLessThan(200);
    expect(line?.endsWith("…")).toBe(true);
  });

  it("omits the dash for a notification with no body", () => {
    const banner = buildUndeliveredBanner([notice(1, "")]);

    expect(banner?.content).toContain("• **Notice 1**");
    expect(banner?.content).not.toContain("• **Notice 1** —");
  });

  it("always fits Discord's 2000-character message limit", () => {
    const banner = buildUndeliveredBanner(
      Array.from({ length: BANNER_MAX_ENTRIES }, (_, i) => ({
        notificationId: `n-${i}`,
        title: "T".repeat(500),
        body: "B".repeat(500),
      })),
    );

    expect(banner?.content.length).toBeLessThanOrEqual(2000);
  });
});
