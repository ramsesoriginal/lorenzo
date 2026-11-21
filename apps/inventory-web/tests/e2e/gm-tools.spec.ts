// What a game master does from the board and its panel: make an item from the catalog, reassign,
// unassign and delete an instance; a player has none of it (IN6).
import type { Page } from '@playwright/test';
import { browseBeing } from './support/board.ts';
import { expect, test } from './support/fixtures.ts';
import { packed } from './support/scenes.ts';
import type { Person, World } from './support/world.ts';

const card = (page: Page, in_: string, name: string) =>
  page.getByRole('region', { name: in_ }).getByRole('button', { name, exact: true });
const panel = (page: Page) => page.locator('[data-item-detail]');

async function gmOnAshfang(as: (who: Person) => Promise<Page>, world: World) {
  const page = await as(world.gm);
  await page.goto(`/board/?tenant=${world.tenantId}`);
  await browseBeing(page, 'Ashfang');
  return page;
}

test('a game master makes an item from the catalog, for whose board it is', async ({
  world,
  as,
}) => {
  await world.item('Lantern');
  const page = await gmOnAshfang(as, world);

  await page.getByRole('button', { name: 'Make from catalog' }).click();
  const dialog = page.getByRole('dialog', { name: 'Make from catalog' });
  await dialog.getByRole('combobox', { name: 'Find an item' }).click();
  await dialog.getByRole('option').getByRole('button', { name: 'Lantern' }).click();
  await dialog.getByRole('button', { name: 'Create for Ashfang' }).click();

  await expect(card(page, 'Not carried', 'Lantern')).toBeVisible();
  expect(await world.carried(world.pia)).toContain('(none): Lantern');
});

test('reassigns, unassigns and deletes an instance, from its panel', async ({ world, as }) => {
  await packed(world, world.pia);
  const page = await gmOnAshfang(as, world);

  await card(page, 'Backpack', 'Ornate Spellbook').click();
  await panel(page).getByRole('button', { name: 'Reassign…' }).click();
  await panel(page).getByLabel('Search beings').fill('Bri');
  await panel(page).getByRole('option').getByRole('button', { name: 'Brisk' }).click();
  await expect(page.getByText('Reassigned Ornate Spellbook to Brisk.')).toBeVisible();
  await expect(card(page, 'Backpack', 'Ornate Spellbook')).toHaveCount(0);
  await expect.poll(() => world.carried(world.oskar)).toEqual(['Backpack: Ornate Spellbook']);

  await card(page, 'Backpack', 'Arrow ×3').click();
  await panel(page).getByRole('button', { name: 'Unassign' }).click();
  await expect(page.getByText('Unassigned Arrow.')).toBeVisible();
  await expect(card(page, 'Backpack', 'Arrow ×3')).toHaveCount(0);

  await card(page, 'Equipped', 'Belt Pouch').click();
  page.once('dialog', (dialog) => dialog.accept());
  await panel(page).getByRole('button', { name: 'Delete…' }).click();
  await expect(card(page, 'Equipped', 'Belt Pouch')).toHaveCount(0);
});

test('a player has none of it', async ({ world, as }) => {
  await packed(world, world.pia);
  const page = await as(world.pia);
  await page.goto(`/board/?tenant=${world.tenantId}&character=${world.pia.character.entity_id}`);

  await expect(page.getByRole('button', { name: 'Make from catalog' })).toBeHidden();
  await card(page, 'Backpack', 'Ornate Spellbook').click();
  await expect(panel(page).getByRole('button', { name: 'Move to…' })).toBeVisible();
  await expect(panel(page).getByRole('button', { name: 'Reassign…' })).toBeHidden();
  await expect(panel(page).getByRole('button', { name: 'Delete…' })).toBeHidden();
});
