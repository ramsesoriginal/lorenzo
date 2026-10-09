import { expect, test } from "@playwright/test";
import { field, id, open, pass, record, reset, row, serverEntries, serverLog } from "./helpers";

test.beforeEach(async ({ request }) => reset(request));

test("create and edit offline, reload with no API, come back, sync", async ({ page, context, request }) => {
  await open(page);
  await expect(page.locator("bench-row")).toHaveCount(300);

  // 1. the connection goes: the browser says so, the rows say "Saved on this device"
  await context.setOffline(true);
  await expect(row(page, 2)).toHaveAttribute("data-state", "synced");
  await page.click("#new");
  const newId = await page.evaluate(() => (window as any).__bench.model.order[0]);
  await field(page, newId, "name").fill("Made offline");
  await field(page, newId, "a").fill("42");
  await field(page, 2, "b").fill("77");
  await expect(row(page, newId)).toHaveAttribute("data-state", "saved-on-device");
  await expect(row(page, 2)).toHaveAttribute("data-state", "saved-on-device");
  await expect(row(page, 5)).toHaveAttribute("data-state", "synced");
  await page.evaluate(() => (window as any).__bench.model.flush());
  await context.setOffline(false);

  // 2. reload with the shell reachable but the API not (no service worker is spiked)
  await page.route("**/api/**", (r) => r.abort("internetdisconnected"));
  await page.reload();
  await page.waitForSelector("body[data-ready='1']");
  const exported = await page.evaluate(() => (window as any).__bench.exported);
  expect(exported).toEqual({ offline: true });
  await expect(page.locator("bench-row")).toHaveCount(301);
  await expect(field(page, newId, "name")).toHaveValue("Made offline");
  await expect(field(page, newId, "a")).toHaveValue("42");
  await expect(field(page, 2, "b")).toHaveValue("77");
  await expect(row(page, newId)).toHaveAttribute("data-state", "saved-on-device");
  // nothing reached the server
  expect((await serverLog(request)).log).toEqual([]);

  // 3. back online: Sync sends the create first, then the edits, in the order written
  await page.unroute("**/api/**");
  await pass(page);
  await expect(row(page, newId)).toHaveAttribute("data-state", "synced");
  await expect(row(page, 2)).toHaveAttribute("data-state", "synced");
  const log = (await serverLog(request)).log;
  expect(log[0]).toBe(`POST ${newId} created`);
  expect(log).toContain(`PATCH ${newId} name=Made offline`.replace("name=Made offline", "name=Made offline"));
  expect(log).toContain(`PATCH ${id(2)} b=77`);
  const server = await serverEntries(request);
  const made = server.find((e: any) => e.id === newId);
  expect(made.name).toBe("Made offline");
  expect(made.stats.a).toBe(42);
  record("offline.roundtrip", { log });

  // 4. a later visit finds it in the export and sends nothing
  await page.reload();
  await page.waitForSelector("body[data-ready='1']");
  await expect(page.locator("bench-row")).toHaveCount(301);
  expect(await page.evaluate(() => (window as any).__bench.model.commands.length)).toBe(0);
});

test("a second visit with nothing changed costs a 304", async ({ page }) => {
  await open(page);
  const first = await page.evaluate(() => (window as any).__bench.exported);
  expect(first.notModified).toBe(false);
  await page.reload();
  await page.waitForSelector("body[data-ready='1']");
  const second = await page.evaluate(() => (window as any).__bench.exported);
  expect(second.notModified).toBe(true);
  expect(second.bytes).toBe(0);
  record("offline.etag", { firstBytesChars: first.bytes, firstMs: first.ms, secondMs: second.ms });
});

test("what is stored is per user: a second account starts empty and never sees the first's", async ({ page }) => {
  await open(page, "alice");
  await field(page, 1, "name").fill("Alice's edit");
  await page.evaluate(() => (window as any).__bench.model.flush());
  const dbs = async () => page.evaluate(async () => (await indexedDB.databases()).map((d) => d.name).sort());
  expect(await dbs()).toEqual(["bench-b0:alice"]);

  await open(page, "bob");
  expect(await page.evaluate(() => (window as any).__bench.model.commands.length)).toBe(0);
  expect(await dbs()).toEqual(["bench-b0:alice", "bench-b0:bob"]);
  await expect(field(page, 1, "name")).toHaveValue("Entry 1");

  // logout = delete that user's database (RFC 0039 §3)
  await page.evaluate(async () => {
    (window as any).__bench.store.close();
    await new Promise((res, rej) => {
      const r = indexedDB.deleteDatabase("bench-b0:alice");
      r.onsuccess = res;
      r.onerror = rej;
    });
  });
  expect(await dbs()).toEqual(["bench-b0:bob"]);
});
