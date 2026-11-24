// The board fills the width and the height of the screen it is on, and a long column scrolls inside
// itself, not the page (IN9); and a move moves the card, not the whole page.
import type { Page } from '@playwright/test';
import { expect, test } from './support/fixtures.ts';
import { packed } from './support/scenes.ts';
import type { World } from './support/world.ts';

async function crowded(world: World) {
  const { backpack } = await packed(world, world.pia);

  for (let i = 0; i < 16; i++) {
    const coin = await world.item(`Coin ${i}`, { stats: { weight: 1 } });

    await world.instance(coin, { owner: world.pia, container: backpack });
  }
}

const pageScrolls = (page: Page) =>
  page.evaluate(() => document.documentElement.scrollHeight - window.innerHeight);

test('fills a wide screen, and a long column scrolls inside itself, not the page', async ({
  world,
  as,
}) => {
  test.setTimeout(120_000);
  await crowded(world);
  const page = await as(world.pia);

  await page.setViewportSize({ width: 2400, height: 900 });
  await page.goto(`/board/?tenant=${world.tenantId}`);
  await expect(page.getByRole('region', { name: 'Backpack' })).toBeVisible();

  // The columns reach the right edge, whatever the width.
  const columns = page.locator('.board-columns');
  const box = await columns.boundingBox();

  expect(box?.x ?? 0).toBeLessThan(40);
  expect((box?.x ?? 0) + (box?.width ?? 0)).toBeGreaterThan(2400 - 40);

  // The long column scrolls on its own, and the page does not.
  const list = page.getByRole('region', { name: 'Backpack' }).locator('.list');
  const inner = await list.evaluate((el) => ({ all: el.scrollHeight, shown: el.clientHeight }));

  expect(inner.all).toBeGreaterThan(inner.shown);
  expect(await pageScrolls(page)).toBeLessThanOrEqual(0);
});

test('a move runs a view transition for the card moved, not for every card or the page', async ({
  world,
  as,
}) => {
  test.setTimeout(120_000);
  await crowded(world);
  const page = await as(world.pia);

  await page.setViewportSize({ width: 1440, height: 900 });
  await page.goto(`/board/?tenant=${world.tenantId}`);
  await expect(page.getByRole('region', { name: 'Belt Pouch' })).toBeVisible();
  await page.evaluate(() => {
    const seen = new Set<string>();
    const w = window as unknown as { __groups: Set<string> };

    w.__groups = seen;
    const timer = setInterval(() => {
      for (const a of document.documentElement.getAnimations({ subtree: true })) {
        const name = (a.effect as KeyframeEffect | null)?.pseudoElement ?? '';

        if (name.startsWith('::view-transition')) seen.add(name);
      }
    }, 15);

    setTimeout(() => clearInterval(timer), 3000);
  });

  await page
    .getByRole('region', { name: 'Backpack' })
    .getByRole('button', { name: 'Ornate Spellbook', exact: true })
    .dragTo(page.getByRole('region', { name: 'Belt Pouch' }));
  await expect(
    page
      .getByRole('region', { name: 'Belt Pouch' })
      .getByRole('button', { name: 'Ornate Spellbook' }),
  ).toBeVisible();
  await page.waitForTimeout(1200);

  const groups = await page.evaluate(() =>
    [...(window as unknown as { __groups: Set<string> }).__groups].filter((n) =>
      n.includes('view-transition-group'),
    ),
  );

  // Only the card that moved is a group of its own; the page is not.
  expect(groups.filter((n) => n.includes('(root)'))).toEqual([]);
  expect(new Set(groups).size).toBeLessThanOrEqual(1);
});
