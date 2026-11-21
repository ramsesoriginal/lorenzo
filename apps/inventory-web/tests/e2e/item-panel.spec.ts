// An item opens beside the board on a wide screen, as a sheet on a tablet and as its page on a
// phone; its actions are on the card's menu too (IN3, IN4).
import type { Page } from '@playwright/test';
import { expect, test } from './support/fixtures.ts';
import { packed } from './support/scenes.ts';
import type { Person, World } from './support/world.ts';

async function boardOf(as: (who: Person) => Promise<Page>, world: World, size: number[]) {
  const page = await as(world.pia);
  await page.setViewportSize({ width: size[0] ?? 1440, height: size[1] ?? 900 });
  await page.goto(`/board/?tenant=${world.tenantId}&character=${world.pia.character.entity_id}`);
  return page;
}

const card = (page: Page, column: string, name: string) =>
  page.getByRole('region', { name: column }).getByRole('button', { name, exact: true });
const panel = (page: Page) => page.locator('[data-item-detail]');

test('opens beside the board, which stays in use', async ({ world, as }) => {
  await packed(world, world.pia);
  const page = await boardOf(as, world, [1440, 900]);

  await card(page, 'Backpack', 'Ornate Spellbook').click();
  await expect(panel(page)).toBeVisible();
  await expect(panel(page).getByRole('heading', { name: 'Ornate Spellbook' })).toBeVisible();
  // Not a modal: the board is still there, and another card swaps what the panel shows.
  await expect(card(page, 'Backpack', 'Arrow ×3')).toBeVisible();
  await card(page, 'Backpack', 'Arrow ×3').click();
  await expect(panel(page).getByRole('heading', { name: 'Arrow' })).toBeVisible();
  await expect(panel(page).getByRole('heading', { name: 'Ornate Spellbook' })).toHaveCount(0);

  await panel(page).getByRole('button', { name: 'Close' }).click();
  await expect(panel(page)).toBeHidden();
});

test('closes with Escape', async ({ world, as }) => {
  await packed(world, world.pia);
  const page = await boardOf(as, world, [1440, 900]);

  await card(page, 'Backpack', 'Ornate Spellbook').click();
  await expect(panel(page)).toBeVisible();
  await panel(page).getByRole('button', { name: 'Move to…' }).focus();
  await page.keyboard.press('Escape');
  await expect(panel(page)).toBeHidden();
});

test('sets a thing down from the panel, with an Undo', async ({ world, as }) => {
  await packed(world, world.pia);
  const page = await boardOf(as, world, [1440, 900]);

  await card(page, 'Backpack', 'Ornate Spellbook').click();
  await panel(page).getByRole('button', { name: 'Set down' }).click();
  await expect(page.getByText('Set down Ornate Spellbook.')).toBeVisible();
  await expect(card(page, 'Not carried', 'Ornate Spellbook')).toBeVisible();
});

test("does the card's menu's action, opening the item with it ready", async ({ world, as }) => {
  await packed(world, world.pia);
  const page = await boardOf(as, world, [1440, 900]);

  await page
    .getByRole('region', { name: 'Backpack' })
    .getByRole('listitem')
    .filter({ hasText: 'Ornate Spellbook' })
    .getByRole('button', { name: 'Actions' })
    .click();
  await expect(page.getByRole('menuitem', { name: 'Open' })).toBeVisible();
  await expect(page.getByRole('menuitem', { name: 'Split…' })).toHaveCount(0);
  await page.getByRole('menuitem', { name: 'Give to…' }).click();
  await expect(panel(page).getByLabel('Hand it over')).toBeVisible();
});

test('is a sheet on a tablet', async ({ world, as }) => {
  await packed(world, world.pia);
  const page = await boardOf(as, world, [834, 1000]);

  await card(page, 'Backpack', 'Ornate Spellbook').click();
  await expect(page.getByRole('dialog', { name: 'Ornate Spellbook' })).toBeVisible();
  await page.keyboard.press('Escape');
  await expect(panel(page)).toBeHidden();
});

test('is its page on a phone, with the actions on the card menu', async ({ world, as }) => {
  await packed(world, world.pia);
  const page = await boardOf(as, world, [430, 900]);

  await page.getByRole('tab', { name: /Backpack/ }).click();
  await page
    .getByRole('region', { name: 'Backpack' })
    .getByRole('listitem')
    .filter({ hasText: 'Ornate Spellbook' })
    .getByRole('button', { name: 'Actions' })
    .click();
  await expect(page.getByRole('menuitem', { name: 'Open' })).toBeVisible();
  await page.keyboard.press('Escape');

  await card(page, 'Backpack', 'Ornate Spellbook').click();
  await expect(page).toHaveURL(/\/item\//);
});
