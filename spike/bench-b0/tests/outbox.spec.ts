import { expect, test } from "@playwright/test";
import { field, id, open, pass, record, reset, row, serverEntries, serverLog } from "./helpers";

test.beforeEach(async ({ request }) => reset(request));

test("an edit waits, then syncs, with its own state on the way", async ({ page, request }) => {
  await open(page);
  await field(page, 3, "name").fill("Renamed three");
  await expect(row(page, 3)).toHaveAttribute("data-state", "waiting");
  await expect(row(page, 3).locator(".state")).toHaveText("Waiting to sync (1)");
  await expect(row(page, 4)).toHaveAttribute("data-state", "synced");
  await pass(page);
  await expect(row(page, 3)).toHaveAttribute("data-state", "synced");
  const e = (await serverEntries(request)).find((x: any) => x.id === id(3));
  expect(e.name).toBe("Renamed three");
  expect(e.version).toBe("v2");
});

test("typing sends one command, not one per keystroke", async ({ page, request }) => {
  await open(page);
  await field(page, 3, "name").fill("");
  await field(page, 3, "name").pressSequentially("Slowly typed name", { delay: 5 });
  const n = await page.evaluate(() => (window as any).__bench.model.commands.length);
  expect(n).toBe(1);
  await pass(page);
  const log = (await serverLog(request)).log.filter((l: string) => l.startsWith("PATCH"));
  expect(log).toEqual([`PATCH ${id(3)} name=Slowly typed name`]);
});

test("a conflict pauses its entry only, and Keep mine / Use theirs both resolve it", async ({ page, request }) => {
  await open(page);
  await field(page, 7, "name").fill("Mine seven");
  await field(page, 8, "name").fill("Mine eight");
  await field(page, 9, "name").fill("Mine nine");
  await field(page, 10, "name").fill("Mine ten");
  // someone else changed rows 7 and 9 on the server since the base
  for (const i of [7, 9]) await request.post("/api/_test/mutate", { data: { id: id(i), field: "name", value: `Theirs ${i}` } });
  await pass(page);

  await expect(row(page, 7)).toHaveAttribute("data-state", "conflict");
  await expect(row(page, 9)).toHaveAttribute("data-state", "conflict");
  await expect(row(page, 8)).toHaveAttribute("data-state", "synced"); // carried on past the paused entry
  await expect(row(page, 10)).toHaveAttribute("data-state", "synced");
  await expect(row(page, 7).locator(".conflict")).toContainText("base Entry 7 / mine Mine seven / theirs Theirs 7");
  // nothing was overwritten on the server
  let entries = await serverEntries(request);
  expect(entries.find((e: any) => e.id === id(7)).name).toBe("Theirs 7");
  expect(entries.find((e: any) => e.id === id(8)).name).toBe("Mine eight");

  await row(page, 7).getByRole("button", { name: "Keep mine" }).click();
  await row(page, 9).getByRole("button", { name: "Use theirs" }).click();
  await expect(row(page, 7)).toHaveAttribute("data-state", "synced");
  await expect(row(page, 9)).toHaveAttribute("data-state", "synced");
  await expect(field(page, 9, "name")).toHaveValue("Theirs 9");
  await expect(field(page, 7, "name")).toHaveValue("Mine seven");
  entries = await serverEntries(request);
  expect(entries.find((e: any) => e.id === id(7)).name).toBe("Mine seven");
  expect(entries.find((e: any) => e.id === id(9)).name).toBe("Theirs 9");
  const left = await page.evaluate(() => (window as any).__bench.model.commands.length);
  expect(left).toBe(0);
  record("outbox.conflict", { pausedOnlyDisputed: true, resolvedBothWays: true });
});

test("when the other side already has my value, nothing is sent (how a replay resolves)", async ({ page, request }) => {
  await open(page);
  await field(page, 11, "name").fill("Same value");
  await request.post("/api/_test/mutate", { data: { id: id(11), field: "name", value: "Same value" } });
  await pass(page);
  await expect(row(page, 11)).toHaveAttribute("data-state", "synced");
  const patches = (await serverLog(request)).log.filter((l: string) => l.startsWith("PATCH"));
  expect(patches).toEqual([]);
});

test("a create whose response was lost is a replay, not a duplicate", async ({ page, request }) => {
  await open(page);
  await page.click("#new");
  // the server applies the create; the page never gets the answer
  await page.route("**/api/entries", async (r) => {
    await r.fetch();
    await r.abort("connectionreset");
  });
  await pass(page);
  await page.unroute("**/api/entries");
  const created = await page.evaluate(() => (window as any).__bench.model.commands.map((c: any) => c.type + ":" + c.state));
  expect(created).toEqual(["entry.create:waiting"]); // still queued: we cannot tell
  await pass(page); // sent again with the same client-made id
  const log = (await serverLog(request)).log.filter((l: string) => l.startsWith("POST"));
  expect(log.map((l: string) => l.split(" ")[2])).toEqual(["created", "replay"]);
  const all = await serverEntries(request);
  expect(all).toHaveLength(301);
  expect(await page.evaluate(() => (window as any).__bench.model.commands.length)).toBe(0);
});

test("an edit made while the command was being sent is kept, not lost", async ({ page, request }) => {
  await open(page);
  await field(page, 12, "name").fill("first");
  await page.route("**/api/entries/**", async (r) => {
    if (r.request().method() === "PATCH") {
      // the user types again while the PATCH is in flight
      await page.evaluate((i) => (window as any).__bench.model.edit(i, "name", "second"), id(12));
    }
    await r.continue();
  });
  await pass(page);
  await page.unroute("**/api/entries/**");
  const mid = await page.evaluate((i) => (window as any).__bench.model.project(i), id(12));
  expect(mid.name).toBe("second");
  expect(mid.pending).toBe(1);
  await pass(page);
  expect((await serverEntries(request)).find((e: any) => e.id === id(12)).name).toBe("second");
});
