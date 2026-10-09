import { expect, test } from "@playwright/test";
import { open, record } from "./helpers";

test("what this browser says about persistence and quota", async ({ page, browser }) => {
  await open(page);
  const info = await page.evaluate(async () => {
    const before = await navigator.storage.persisted();
    const granted = await navigator.storage.persist();
    const est = await navigator.storage.estimate();
    return { persistedBefore: before, persistGranted: granted, quotaMB: Math.round((est.quota ?? 0) / 1e6), usageKB: Math.round((est.usage ?? 0) / 1e3), locks: "locks" in navigator, secure: isSecureContext };
  });
  record("storage.default", info);
  expect(info.locks).toBe(true);

  // a fresh, incognito-like context (Playwright's are ephemeral): IndexedDB still opens, and its quota is whatever it gives
  const ctx = await browser.newContext();
  const p = await ctx.newPage();
  await p.goto("http://127.0.0.1:4173/?user=private");
  await p.waitForSelector("body[data-ready='1']");
  const priv = await p.evaluate(async () => {
    const est = await navigator.storage.estimate();
    return { persistGranted: await navigator.storage.persist(), quotaMB: Math.round((est.quota ?? 0) / 1e6) };
  });
  record("storage.ephemeralContext", priv);
  await ctx.close();
});
