// Select turns on a bar for the cards picked: Move to…, Give…, Merge and Done (IN4).
import type { Page } from '@playwright/test';
import { expect, test } from './support/fixtures.ts';
import { packed } from './support/scenes.ts';
import type { Person, World } from './support/world.ts';

async function boardOf(as: (who: Person) => Promise<Page>, world: World) {
  const page = await as(world.pia);
  await page.goto(`/board/?tenant=${world.tenantId}&character=${world.pia.character.entity_id}`);
  return page;
}

const column = (page: Page, name: string) => page.getByRole('region', { name });
const card = (page: Page, in_: string, name: string) =>
  column(page, in_).getByRole('button', { name, exact: true });
const bar = (page: Page) => page.getByRole('toolbar', { name: 'Selected cards' });

test('moves the selected cards into a container, and is done', async ({ world, as }) => {
  const { items, pouch } = await packed(world, world.pia);
  await world.instance(items.book, { owner: world.pia, container: pouch });
  const page = await boardOf(as, world);

  await expect(page.getByRole('region', { name: 'Belt Pouch' })).toBeVisible();
  // Marks on the columns go if the board is drawn again; the board is not fetched again either.
  await page.evaluate(() => {
    for (const el of document.querySelectorAll('[data-column]'))
      el.setAttribute('data-probe', 'kept');
  });
  const boardReads: string[] = [];

  page.on('request', (request) => {
    if (request.url().includes('/controlled-by/')) boardReads.push(request.url());
  });

  await page.getByRole('button', { name: 'Select', exact: true }).click();
  await expect(bar(page)).toBeHidden();
  await card(page, 'Backpack', 'Ornate Spellbook').click();
  await card(page, 'Backpack', 'Arrow ×3').click();
  await expect(bar(page).getByText('2 cards selected')).toBeVisible();

  await bar(page).getByRole('button', { name: 'Move to…' }).click();
  await page
    .locator('[data-selection-panel]')
    .getByRole('button', { name: 'Belt Pouch', exact: true })
    .click();

  await expect(card(page, 'Belt Pouch', 'Arrow ×3')).toBeVisible({ timeout: 15_000 });
  await expect(card(page, 'Belt Pouch', 'Ornate Spellbook')).toBeVisible();
  await expect(bar(page)).toBeHidden();
  await expect(
    page.getByRole('region', { name: 'Backpack' }).locator('[data-column-count]'),
  ).toHaveText('0');
  await expect(
    page.getByRole('region', { name: 'Belt Pouch' }).locator('[data-column-count]'),
  ).toHaveText('3');
  await expect(page.locator('[data-column]:not([data-probe])')).toHaveCount(0);
  expect(boardReads).toEqual([]);
});

test('merges stacks of one item, and only those', async ({ world, as }) => {
  const { items, backpack } = await packed(world, world.pia);
  await world.instance(items.arrow, { owner: world.pia, container: backpack });
  const page = await boardOf(as, world);

  await expect(card(page, 'Backpack', 'Arrow ×3')).toBeVisible();
  await page.evaluate(() => {
    for (const el of document.querySelectorAll('[data-column]')) el.setAttribute('data-probe', '1');
  });
  const reads: string[] = [];

  page.on('request', (request) => {
    if (request.url().includes('/controlled-by/')) reads.push(request.url());
  });

  await page.getByRole('button', { name: 'Select', exact: true }).click();
  await card(page, 'Backpack', 'Ornate Spellbook').click();
  await expect(bar(page).getByRole('button', { name: 'Merge' })).toBeDisabled();
  await card(page, 'Backpack', 'Ornate Spellbook').click();
  await card(page, 'Backpack', 'Arrow ×3').click();
  await card(page, 'Backpack', 'Arrow').click();
  await expect(bar(page).getByRole('button', { name: 'Merge' })).toBeEnabled();

  await bar(page).getByRole('button', { name: 'Merge' }).click();
  await expect(card(page, 'Backpack', 'Arrow ×4')).toBeVisible();
  await expect(bar(page)).toBeHidden();
  await expect(page.locator('[data-column]:not([data-probe])')).toHaveCount(0);
  expect(reads).toEqual([]);

  await page.getByRole('button', { name: 'Select', exact: true }).click();
  await card(page, 'Backpack', 'Arrow ×4').click();
  await bar(page).getByRole('button', { name: 'Done' }).click();
  await expect(bar(page)).toBeHidden();
});
