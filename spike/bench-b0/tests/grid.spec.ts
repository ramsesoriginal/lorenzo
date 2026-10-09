import { expect, test } from "@playwright/test";
import { field, id, open, record, reset, row } from "./helpers";

test.beforeEach(async ({ request }) => reset(request));

test("300 rows render, and one row's change updates only that row", async ({ page }) => {
  await open(page);
  await expect(page.locator("bench-row")).toHaveCount(300);
  const boot = await page.evaluate(() => {
    const b = (window as any).__bench;
    return { loadMs: b.loadMs, renderMs: b.renderMs, exported: b.exported };
  });
  record("grid.boot", boot);

  const renders = () => page.evaluate(() => [...document.querySelectorAll("bench-row")].map((r) => Number((r as HTMLElement).dataset.renders)));
  const before = await renders();
  await field(page, 5, "name").fill("Changed");
  await expect(row(page, 5)).toHaveAttribute("data-state", "waiting");
  const after = await renders();
  const changed = after.map((n, i) => (n !== before[i] ? i : -1)).filter((i) => i >= 0);
  record("grid.isolation", { changedRows: changed });
  expect(changed).toEqual([5]);
});

test("typing keeps every keystroke, focus and selection while the rows around it change", async ({ page }) => {
  await open(page);
  const input = field(page, 5, "name");
  await input.fill("");
  await input.focus();
  // other rows change continuously (commands, state changes) for the whole time of typing
  await page.evaluate((skip) => {
    const b = (window as any).__bench;
    let n = 0;
    (window as any).__noise = setInterval(() => {
      const target = `00000000-0000-4000-8000-${String(10 + (n % 280)).padStart(12, "0")}`;
      if (target !== skip) b.model.edit(target, "a", String(n));
      b.model.edit(skip, "b", String(n)); // and the typed-in row's own state changes too
      n++;
    }, 3);
  }, id(5));
  const text = "The quick brown fox jumps over the lazy dog";
  await input.pressSequentially(text, { delay: 8 });
  await page.evaluate(() => clearInterval((window as any).__noise));
  await expect(input).toHaveValue(text);
  await expect(input).toBeFocused();

  // a selection survives the same noise
  await input.evaluate((el: HTMLInputElement) => el.setSelectionRange(4, 9));
  const changes = await page.evaluate(async (skip) => {
    const b = (window as any).__bench;
    for (let n = 0; n < 150; n++) {
      b.model.edit(`00000000-0000-4000-8000-${String(20 + (n % 250)).padStart(12, "0")}`, "c", String(n + 1000));
      if (n % 10 === 0) b.model.edit(skip, "c", String(n)); // own row's state/pending count changes
      await new Promise((r) => setTimeout(r, 1));
    }
    return n_done(b);
    function n_done(bb: any) { return bb.model.commands.length; }
  }, id(5));
  const sel = await input.evaluate((el: HTMLInputElement) => [el.selectionStart, el.selectionEnd, document.activeElement === el, el.value]);
  record("grid.typing", { text, commandsQueued: changes, selection: sel });
  expect(sel).toEqual([4, 9, true, text]);
});

test("an update costs little: 300 rows, 100 single-row edits", async ({ page }) => {
  await open(page);
  const t = await page.evaluate(async () => {
    const b = (window as any).__bench;
    const times: number[] = [];
    for (let n = 0; n < 100; n++) {
      const rid = `00000000-0000-4000-8000-${String(n * 2).padStart(12, "0")}`;
      const t0 = performance.now();
      b.model.edit(rid, "a", String(5000 + n));
      await Promise.resolve(); // effects run in a microtask
      await Promise.resolve();
      times.push(performance.now() - t0);
    }
    times.sort((x, y) => x - y);
    return { p50: times[50], p95: times[95], max: times[99] };
  });
  record("grid.updateCost", t);
  expect(t.p95).toBeLessThan(16); // a frame
});
