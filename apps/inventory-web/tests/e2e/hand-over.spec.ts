// Handing things over when giving, and stacks leaving containers whole (ADR 0115).
import type { Locator, Page } from '@playwright/test';
import { expect, test } from './support/fixtures.ts';
import { packed } from './support/scenes.ts';
import type { Person, Player, World } from './support/world.ts';

async function boardOf(as: (who: Person) => Promise<Page>, world: World, player: Player) {
  const page = await as(player);
  await page.goto(`/board/?tenant=${world.tenantId}&character=${player.character.entity_id}`);
  return page;
}

const column = (page: Page, name: string) => page.getByRole('region', { name });
const card = (page: Page, in_: string, name: string) =>
  column(page, in_).getByRole('button', { name, exact: true });

/** Picks `name` in the being search within `scope`. */
async function giveTo(scope: Page | Locator, name: string) {
  await scope.getByLabel('Search beings').filter({ visible: true }).fill(name);
  await scope.getByRole('option').getByRole('button', { name }).click();
}

test('hands an item over, out of her backpack and out of her hands', async ({ world, as }) => {
  await packed(world, world.pia);
  const page = await boardOf(as, world, world.pia);

  await card(page, 'Backpack', 'Ornate Spellbook').click();
  await page.getByRole('button', { name: 'Give to…' }).click();
  await expect(page.getByText('Otherwise it stays in the Backpack, theirs now.')).toBeVisible();
  await page.getByLabel('Hand it over').check();
  await giveTo(page, 'Brisk');
  await expect(page.getByText('Given to Brisk.')).toBeVisible();
  // In his hands, in no container of his.
  expect(await world.carried(world.oskar)).toEqual(['(none): Ornate Spellbook']);
  // Nothing of hers holds it now, so she can't take it back: no Undo that would fail.
  await expect(card(page, 'Ashfang', 'Backpack')).toBeVisible();
  await expect(page.getByRole('button', { name: 'Undo' })).toBeHidden();
});

test("a GM's hand-over can be undone, back into the backpack", async ({ world, as }) => {
  await packed(world, world.pia);
  const page = await as(world.gm);
  await page.goto(`/board/?tenant=${world.tenantId}`);
  await page.getByRole('tab', { name: 'Browse a being' }).click();
  await giveTo(page, 'Ashfang');

  await card(page, 'Backpack', 'Ornate Spellbook').click();
  await page.getByRole('button', { name: 'Give to…' }).click();
  await page.getByLabel('Hand it over').check();
  await giveTo(page.getByRole('dialog'), 'Brisk');
  await expect(page.getByText('Given to Brisk.')).toBeVisible();
  expect(await world.carried(world.oskar)).toEqual(['(none): Ornate Spellbook']);

  await page.getByRole('button', { name: 'Undo' }).click();
  await expect(card(page, 'Backpack', 'Ornate Spellbook')).toBeVisible();
  expect(await world.carried(world.pia)).toContain('Backpack: Ornate Spellbook');
  expect(await world.carried(world.oskar)).toEqual([]);
});

test('hands over part of a stack', async ({ world, as }) => {
  await packed(world, world.pia);
  const page = await boardOf(as, world, world.pia);

  await card(page, 'Backpack', 'Arrow ×3').click();
  await page.getByRole('button', { name: 'Give to…' }).click();
  await page.getByLabel('How many? (of 3, blank for all)').fill('2');
  await page.getByLabel('Hand it over').check();
  await giveTo(page, 'Brisk');
  await expect(card(page, 'Backpack', 'Arrow')).toBeVisible();
  expect(await world.carried(world.oskar)).toEqual(['(none): Arrow ×2']);
});

test('offers no hand-over for what is in no container', async ({ world, as }) => {
  await packed(world, world.pia);
  const page = await boardOf(as, world, world.pia);

  await card(page, 'Ashfang', 'Backpack').click();
  await page.getByRole('button', { name: 'Give to…' }).click();
  await expect(page.getByLabel('Search beings').filter({ visible: true })).toBeVisible();
  await expect(page.getByLabel('Hand it over')).toHaveCount(0);
});

test('hands a whole selection over', async ({ world, as }) => {
  await packed(world, world.pia);
  const page = await boardOf(as, world, world.pia);

  await page.getByRole('button', { name: 'Select items' }).click();
  await card(page, 'Backpack', 'Ornate Spellbook').click();
  await card(page, 'Backpack', 'Arrow ×3').click();
  await page.getByRole('button', { name: 'Give selected to…' }).click();
  await page.getByLabel('Hand them over').check();
  await giveTo(page, 'Brisk');
  await expect(page.getByText('Gave 2 item(s) to Brisk.')).toBeVisible();
  await expect
    .poll(() => world.carried(world.oskar))
    .toEqual(['(none): Arrow ×3', '(none): Ornate Spellbook']);
});

test('takes a stack out of its container whole, and undo puts it back', async ({ world, as }) => {
  await packed(world, world.pia);
  const page = await boardOf(as, world, world.pia);

  await card(page, 'Backpack', 'Arrow ×3').click();
  await page.getByRole('button', { name: 'Move to…' }).click();
  await page.getByRole('button', { name: 'Remove from container' }).click();
  // Ashfang carries it now, all three: before, the count was lost here.
  await expect(card(page, 'Ashfang', 'Arrow ×3')).toBeVisible();
  expect(await world.carried(world.pia)).toContain('(none): Arrow ×3');

  // Carried, it isn't in a container to be taken out of.
  await card(page, 'Ashfang', 'Arrow ×3').click();
  await page.getByRole('button', { name: 'Move to…' }).click();
  await expect(page.getByRole('button', { name: 'Remove from container' })).toHaveCount(0);
  await page.keyboard.press('Escape');

  await page.getByRole('button', { name: 'Undo' }).click();
  await expect(card(page, 'Backpack', 'Arrow ×3')).toBeVisible();
});

test("drags a stack onto its owner's column, whole", async ({ world, as }) => {
  await packed(world, world.pia);
  const page = await boardOf(as, world, world.pia);

  await card(page, 'Backpack', 'Arrow ×3').dragTo(column(page, 'Ashfang'));
  await expect(card(page, 'Ashfang', 'Arrow ×3')).toBeVisible();
  await expect.poll(() => world.carried(world.pia)).toContain('(none): Arrow ×3');

  // And back into the backpack from there.
  await card(page, 'Ashfang', 'Arrow ×3').dragTo(column(page, 'Backpack'));
  await expect.poll(() => world.carried(world.pia)).toContain('Backpack: Arrow ×3');
});
