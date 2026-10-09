import { expect, test } from "@playwright/test";
import { field, id, open, record, reset, row, serverEntries } from "./helpers";

test.beforeEach(async ({ request }) => reset(request));

const active = (p: import("@playwright/test").Page) => p.evaluate(() => (window as any).__bench.runner.active.peek());

test("one runner among several tabs; the others follow the store; a closed runner is replaced", async ({ context, request }) => {
  const a = await context.newPage();
  await open(a);
  await expect.poll(() => active(a)).toBe(true);
  const b = await context.newPage();
  await open(b);
  const c = await context.newPage();
  await open(c);
  await new Promise((r) => setTimeout(r, 300));
  expect([await active(a), await active(b), await active(c)]).toEqual([true, false, false]);

  // an edit made in a follower is in the store; the runner and the other follower see it
  await field(b, 20, "name").fill("Edited in tab B");
  await b.evaluate(() => (window as any).__bench.model.flush());
  await expect(row(a, 20)).toHaveAttribute("data-state", "waiting");
  await expect(row(c, 20)).toHaveAttribute("data-state", "waiting");
  await expect(field(c, 20, "name")).toHaveValue("Edited in tab B");

  // only the runner sends; the followers show Synced once it has
  await a.evaluate(() => (window as any).__bench.runner.pass());
  await expect(row(b, 20)).toHaveAttribute("data-state", "synced");
  await expect(row(c, 20)).toHaveAttribute("data-state", "synced");
  const sent = await Promise.all([a, b, c].map((p) => p.evaluate(() => (window as any).__bench.runner.sent.length)));
  expect(sent).toEqual([1, 0, 0]);
  expect((await serverEntries(request)).find((e: any) => e.id === id(20)).name).toBe("Edited in tab B");

  // the runner's tab goes away: another takes the lock
  await a.close();
  await expect.poll(async () => [await active(b), await active(c)].filter(Boolean).length).toBe(1);
  record("tabs", { tabs: 3, singleRunner: true, takeoverOnClose: true });
});

test("a follower typing does not lose focus when the store changes under it", async ({ context }) => {
  const a = await context.newPage();
  await open(a);
  const b = await context.newPage();
  await open(b);
  const input = field(b, 30, "name");
  await input.fill("");
  await input.focus();
  const typing = input.pressSequentially("typing while another tab writes", { delay: 10 });
  for (let i = 0; i < 20; i++) {
    await a.evaluate((n) => (window as any).__bench.model.edit(`00000000-0000-4000-8000-${String(50 + n).padStart(12, "0")}`, "a", String(n)), i);
    await new Promise((r) => setTimeout(r, 12));
  }
  await typing;
  await expect(input).toHaveValue("typing while another tab writes");
  await expect(input).toBeFocused();
});

test("another tab changing the field I am typing in never overwrites what I typed; the disagreement surfaces as a conflict", async ({ context, request }) => {
  const a = await context.newPage();
  await open(a);
  const b = await context.newPage();
  await open(b);
  const input = field(b, 30, "name");
  await input.fill("");
  await input.focus();
  const text = "typed in tab B while tab A keeps editing this very field";
  const typing = input.pressSequentially(text, { delay: 10 });
  for (let i = 0; i < 25; i++) {
    await a.evaluate((n) => (window as any).__bench.model.edit("00000000-0000-4000-8000-000000000030", "name", `A says ${n}`), i);
    await new Promise((r) => setTimeout(r, 10));
  }
  await typing;
  await expect(input).toHaveValue(text);
  await expect(input).toBeFocused();

  // the runner is tab A (first lock). Commands go in the order they were written, so one side's
  // value reaches the server first and the other side is then a real conflict. Which one is not the
  // point: nothing is silently overwritten, and both values are on screen.
  expect(await active(a)).toBe(true);
  await b.evaluate(() => (window as any).__bench.model.flush());
  await a.evaluate(() => (window as any).__bench.model.reloadFromStore());
  await a.evaluate(() => (window as any).__bench.runner.pass());
  await expect(row(b, 30)).toHaveAttribute("data-state", "conflict");
  const shown = await row(b, 30).locator(".conflict").innerText();
  const onServer = (await serverEntries(request)).find((e: any) => e.id === id(30)).name;
  const values = [text, "A says 24"];
  expect(values).toContain(onServer);
  const other = values.find((v) => v !== onServer)!;
  expect(shown).toContain(`theirs ${onServer}`);
  expect(shown).toContain(`mine ${other}`);
  record("tabs.sameFieldConflict", { winnerOnServer: onServer === text ? "tab B (typed)" : "tab A", loserShownAsConflict: true });
});
