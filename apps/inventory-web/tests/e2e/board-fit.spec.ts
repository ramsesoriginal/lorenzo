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

test('moving a container changes the words of the columns, and draws nothing again', async ({
  world,
  as,
}) => {
  await packed(world, world.pia);
  const page = await as(world.pia);

  await page.goto(`/board/?tenant=${world.tenantId}`);

  const pouch = page.getByRole('region', { name: 'Belt Pouch' });
  const backpack = page.getByRole('region', { name: 'Backpack' });

  await expect(pouch).toBeVisible();
  await expect(pouch.locator('[data-note]')).not.toContainText('Backpack');

  // Mark what is on the page now: if the board is drawn again, the marks go.
  await page.evaluate(() => {
    for (const column of document.querySelectorAll('[data-column]')) {
      column.setAttribute('data-probe', 'kept');
    }
  });

  await page.getByRole('button', { name: 'Belt Pouch', exact: true }).first().click();
  await page.getByRole('button', { name: 'Move to…' }).click();
  await page.getByRole('dialog').getByRole('button', { name: 'Backpack' }).click();

  await expect(backpack.getByRole('button', { name: 'Belt Pouch', exact: true })).toBeVisible();
  await expect(pouch.locator('[data-note]')).toContainText('In Backpack');
  await expect(backpack.locator('[data-column-count]')).toHaveText('3');

  await expect(page.locator('[data-column][data-probe="kept"]')).toHaveCount(
    await page.locator('[data-column]').count(),
  );
});

// Marks every column on the page and counts reads of the board: if the board is drawn again the
// marks go, and if it is fetched again a read shows.
async function watch(page: Page) {
  await expect(page.getByRole('region', { name: 'Backpack' })).toBeVisible();
  await page.evaluate(() => {
    for (const el of document.querySelectorAll('[data-column]')) el.setAttribute('data-probe', '1');
  });

  const reads: string[] = [];

  page.on('request', (request) => {
    if (request.url().includes('/controlled-by/')) reads.push(request.url());
  });

  return async () => {
    await expect(page.locator('[data-column]:not([data-probe])')).toHaveCount(0);
    expect(reads).toEqual([]);
  };
}

const backpack = (page: Page) => page.getByRole('region', { name: 'Backpack' });
const cardIn = (page: Page, name: string) =>
  backpack(page).getByRole('button', { name, exact: true });

async function pickBeing(page: Page, name: string) {
  await page.getByLabel('Search beings').filter({ visible: true }).fill(name);
  await page.getByRole('option').getByRole('button', { name }).click();
}

test('giving a card changes its mark, and neither fetches nor draws the board', async ({
  world,
  as,
}) => {
  await packed(world, world.pia);
  const page = await as(world.pia);

  await page.goto(`/board/?tenant=${world.tenantId}`);
  const unchanged = await watch(page);

  await cardIn(page, 'Ornate Spellbook').click();
  await page.getByRole('button', { name: 'Give to…' }).click();
  await pickBeing(page, 'Brisk');

  await expect(cardIn(page, "Ornate Spellbook Brisk's")).toBeVisible();
  await unchanged();
});

test('giving part of a stack adds a card and says the rest, with no fetch', async ({
  world,
  as,
}) => {
  await packed(world, world.pia);
  const page = await as(world.pia);

  await page.goto(`/board/?tenant=${world.tenantId}`);
  const unchanged = await watch(page);

  await cardIn(page, 'Arrow ×3').click();
  await page.getByRole('button', { name: 'Give to…' }).click();
  await page.getByLabel('How many? (of 3, blank for all)').fill('1');
  await pickBeing(page, 'Brisk');

  await expect(cardIn(page, 'Arrow ×2')).toBeVisible();
  await expect(cardIn(page, "Arrow Brisk's")).toBeVisible();
  await expect(backpack(page).locator('[data-column-count]')).toHaveText('3');
  await unchanged();
});

test('merging a stack into another joins them, with no fetch', async ({ world, as }) => {
  const { items, backpack: bag } = await packed(world, world.pia);

  await world.instance(items.arrow, { owner: world.pia, container: bag });

  const page = await as(world.pia);

  await page.goto(`/board/?tenant=${world.tenantId}`);
  const unchanged = await watch(page);

  await cardIn(page, 'Arrow').click();
  await page.getByRole('button', { name: 'Merge into…' }).click();
  await page.getByRole('dialog').getByRole('button', { name: 'Arrow ×3' }).click();

  await expect(cardIn(page, 'Arrow ×4')).toBeVisible();
  await expect(backpack(page).locator('[data-column-count]')).toHaveText('2');
  await unchanged();
});

test('giving selected cards from the select bar marks them, with no fetch', async ({
  world,
  as,
}) => {
  await packed(world, world.pia);
  const page = await as(world.pia);

  await page.goto(`/board/?tenant=${world.tenantId}`);
  const unchanged = await watch(page);

  await page.getByRole('button', { name: 'Select', exact: true }).click();
  await cardIn(page, 'Ornate Spellbook').click();
  await cardIn(page, 'Arrow ×3').click();
  await page
    .getByRole('toolbar', { name: 'Selected cards' })
    .getByRole('button', { name: 'Give…' })
    .click();
  await pickBeing(page, 'Brisk');

  await expect(cardIn(page, "Ornate Spellbook Brisk's")).toBeVisible();
  await expect(cardIn(page, "Arrow ×3 Brisk's")).toBeVisible();
  await unchanged();
});
